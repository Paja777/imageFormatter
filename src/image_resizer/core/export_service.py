"""Write every selected preset into one destination folder."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from image_resizer.core.crop_geometry import CropAnchor, Size, requires_upscale
from image_resizer.core.errors import ExportError
from image_resizer.core.image_processor import render, to_working_mode
from image_resizer.core.presets import Preset
from image_resizer.models.settings import (
    DEFAULT_QUALITY,
    WHITE,
    CollisionPolicy,
    Color,
    OutputFormat,
    ResizeMode,
)


STRETCH_WARNING = (
    "Stretching ignores the original aspect ratio and may distort the image."
)
UPSCALE_WARNING = (
    "At least one output is larger than the source and will be upscaled."
)

ProgressCallback = Callable[[int, int], None]

_WINDOWS_RESERVED = frozenset(
    {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_STEM_LENGTH = 80


@dataclass(frozen=True, slots=True)
class ExportFileResult:
    """Outcome of writing one preset."""

    preset_id: str
    preset_name: str
    path: Path | None
    width: int
    height: int
    upscaled: bool
    renamed: bool
    skipped: bool
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and not self.skipped


@dataclass(frozen=True, slots=True)
class ExportSummary:
    """Folder layout and per-file results for one export."""

    output_directory: Path
    files: tuple[ExportFileResult, ...]
    distortion_warning: str | None = None
    upscale_warning: str | None = None

    @property
    def succeeded(self) -> tuple[ExportFileResult, ...]:
        return tuple(item for item in self.files if item.ok)

    @property
    def failed(self) -> tuple[ExportFileResult, ...]:
        return tuple(item for item in self.files if item.error is not None)

    @property
    def skipped_files(self) -> tuple[ExportFileResult, ...]:
        return tuple(item for item in self.files if item.skipped and item.error is None)


def filesystem_stem(filename: str) -> str:
    """Turn an untrusted source name into a single safe path component."""
    if not isinstance(filename, str):
        filename = str(filename)
    base = filename.replace("\\", "/").split("/")[-1]
    stem = Path(base).stem
    stem = _UNSAFE_CHARS.sub("_", stem)
    stem = re.sub(r"\s+", " ", stem)
    stem = re.sub(r"_+", "_", stem).strip(" ._")
    if not stem:
        return "image"
    if stem.upper() in _WINDOWS_RESERVED:
        stem = f"_{stem}"
    if len(stem) > _MAX_STEM_LENGTH:
        stem = stem[:_MAX_STEM_LENGTH].rstrip(" ._")
    return stem or "image"


def convert_for_output(
    image: Image.Image,
    output_format: OutputFormat,
    background: Color = WHITE,
) -> Image.Image:
    """Return pixels ready to save, flattening alpha when the format cannot keep it."""
    working = to_working_mode(image)
    prepared = working.copy() if output_format.supports_alpha else _flatten_on_background(working, background)
    # Copy the info dict before stripping EXIF so the caller's image is left untouched.
    prepared.info = dict(prepared.info)
    _drop_export_metadata(prepared)
    return prepared


def export_image(
    image: Image.Image,
    source_filename: str,
    presets: Sequence[Preset],
    destination: str | Path,
    *,
    mode: ResizeMode,
    output_format: OutputFormat = OutputFormat.JPEG,
    quality: int = DEFAULT_QUALITY,
    background: Color | None = None,
    crop_anchors: Mapping[str, CropAnchor] | None = None,
    collision_policy: CollisionPolicy = CollisionPolicy.RENAME,
    progress: ProgressCallback | None = None,
) -> ExportSummary:
    """Export each preset into ``<destination>/<source stem>/``.

    Files are named ``<stem>_<width>x<height>.<ext>``. A second preset with
    the same dimensions gets a numeric suffix. Existing files are renamed,
    skipped, or replaced according to ``collision_policy``.
    """
    _validate_request(image, presets, mode, output_format, collision_policy, quality)
    matte = background if background is not None else WHITE
    anchors = dict(crop_anchors or {})
    stem = filesystem_stem(source_filename)
    output_directory = _prepare_output_directory(Path(destination), stem)
    allocator = _NameAllocator(output_directory, collision_policy)
    total = len(presets)
    if progress is not None:
        progress(0, total)

    results: list[ExportFileResult] = []
    for index, preset in enumerate(presets, start=1):
        results.append(
            _export_one(
                image=image,
                preset=preset,
                stem=stem,
                mode=mode,
                output_format=output_format,
                quality=quality,
                background=matte,
                anchor=anchors.get(preset.id, CropAnchor()),
                allocator=allocator,
            )
        )
        if progress is not None:
            progress(index, total)

    wrote_upscaled = any(item.upscaled and item.ok for item in results)
    return ExportSummary(
        output_directory=output_directory,
        files=tuple(results),
        distortion_warning=STRETCH_WARNING if mode is ResizeMode.STRETCH else None,
        upscale_warning=UPSCALE_WARNING if wrote_upscaled else None,
    )


def _validate_request(
    image: Image.Image,
    presets: Sequence[Preset],
    mode: ResizeMode,
    output_format: OutputFormat,
    collision_policy: CollisionPolicy,
    quality: int,
) -> None:
    if not isinstance(image, Image.Image):
        raise ExportError("A source image is required.")
    if not presets:
        raise ExportError("Select at least one preset before exporting.")
    if any(not isinstance(preset, Preset) for preset in presets):
        raise ExportError("Each export item must be a preset.")
    if not isinstance(mode, ResizeMode):
        raise ExportError("Unsupported resize mode.")
    if not isinstance(output_format, OutputFormat):
        raise ExportError("Unsupported output format.")
    if not isinstance(collision_policy, CollisionPolicy):
        raise ExportError("Unsupported filename collision policy.")
    if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100:
        raise ExportError("Quality must be an integer from 1 to 100.")


def _prepare_output_directory(destination: Path, stem: str) -> Path:
    if destination.exists() and not destination.is_dir():
        raise ExportError("Export destination must be a directory.")
    output_directory = destination / stem
    if output_directory.exists() and not output_directory.is_dir():
        raise ExportError("The output folder path is already a file.")
    try:
        output_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ExportError(f"Could not create the export folder: {exc}") from exc
    return output_directory


def _export_one(
    *,
    image: Image.Image,
    preset: Preset,
    stem: str,
    mode: ResizeMode,
    output_format: OutputFormat,
    quality: int,
    background: Color,
    anchor: CropAnchor,
    allocator: _NameAllocator,
) -> ExportFileResult:
    upscaled = requires_upscale(
        Size(image.width, image.height),
        Size(preset.width, preset.height),
        mode,
    )
    allocated: _AllocatedName | None = None
    try:
        allocated = allocator.allocate(
            stem,
            preset.width,
            preset.height,
            output_format.extension,
        )
        if allocated.skipped:
            return _result(preset, allocated.path, upscaled, renamed=False, skipped=True)
        processed = render(
            image,
            Size(preset.width, preset.height),
            mode,
            crop_anchor=anchor,
            background=background,
        )
        _atomic_save(processed.image, allocated.path, output_format, quality, background)
        return _result(
            preset,
            allocated.path,
            processed.upscaled,
            renamed=allocated.renamed,
            skipped=False,
        )
    except Exception as exc:
        path = None if allocated is None else allocated.path
        renamed = False if allocated is None else allocated.renamed
        return _result(preset, path, upscaled, renamed=renamed, skipped=False, error=str(exc))


def _result(
    preset: Preset,
    path: Path | None,
    upscaled: bool,
    *,
    renamed: bool,
    skipped: bool,
    error: str | None = None,
) -> ExportFileResult:
    return ExportFileResult(
        preset_id=preset.id,
        preset_name=preset.name,
        path=path,
        width=preset.width,
        height=preset.height,
        upscaled=upscaled,
        renamed=renamed,
        skipped=skipped,
        error=error,
    )


def _flatten_on_background(image: Image.Image, background: Color) -> Image.Image:
    if image.mode == "RGB" and background.alpha == 255:
        flat = image.copy()
    else:
        rgba = image.convert("RGBA")
        matte = Image.new("RGBA", rgba.size, background.as_rgba())
        if background.alpha != 255:
            white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            matte = Image.alpha_composite(white, matte)
        flat = Image.alpha_composite(matte, rgba).convert("RGB")
    _drop_export_metadata(flat)
    return flat


def _atomic_save(
    image: Image.Image,
    path: Path,
    output_format: OutputFormat,
    quality: int,
    background: Color,
) -> None:
    temporary = path.with_name(f".{path.name}.part")
    try:
        prepared = convert_for_output(image, output_format, background)
        _drop_export_metadata(prepared)
        save_kwargs: dict[str, object] = {}
        icc_profile = image.info.get("icc_profile")
        if isinstance(icc_profile, bytes):
            save_kwargs["icc_profile"] = icc_profile
        if output_format is OutputFormat.JPEG:
            prepared.save(
                temporary,
                format="JPEG",
                quality=quality,
                optimize=True,
                **save_kwargs,
            )
        elif output_format is OutputFormat.PNG:
            prepared.save(temporary, format="PNG", optimize=True, **save_kwargs)
        elif output_format is OutputFormat.WEBP:
            prepared.save(
                temporary,
                format="WEBP",
                quality=quality,
                method=4,
                **save_kwargs,
            )
        else:
            raise ExportError(f"Unsupported output format: {output_format}.")
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _drop_export_metadata(image: Image.Image) -> None:
    """Remove orientation metadata so a viewer cannot rotate the file again."""
    image.info.pop("exif", None)
    image.info.pop("Raw profile type exif", None)


@dataclass(frozen=True, slots=True)
class _AllocatedName:
    path: Path
    renamed: bool
    skipped: bool


class _NameAllocator:
    """Reserve output names, treating the folder as case-insensitive.

    Windows cannot keep two files whose names differ only by case. The
    allocator follows that rule on every platform so an export copied to
    Windows does not collide with itself.
    """

    def __init__(self, directory: Path, policy: CollisionPolicy) -> None:
        self._directory = directory
        self._policy = policy
        self._reserved: set[str] = set()
        self._on_disk: dict[str, str] = {}
        if directory.exists():
            for entry in directory.iterdir():
                if entry.is_file():
                    self._on_disk[entry.name.casefold()] = entry.name

    def allocate(self, stem: str, width: int, height: int, extension: str) -> _AllocatedName:
        root = f"{stem}_{width}x{height}"
        primary = f"{root}.{extension}"
        existing = self._lookup(primary)
        if existing is None and primary.casefold() not in self._reserved:
            return self._claim(primary, renamed=False, skipped=False)
        if existing is not None and primary.casefold() not in self._reserved:
            if self._policy is CollisionPolicy.OVERWRITE:
                return self._claim(existing, renamed=False, skipped=False)
            if self._policy is CollisionPolicy.SKIP:
                return self._claim(existing, renamed=False, skipped=True)

        for index in range(2, 10_001):
            candidate = f"{root}_{index}.{extension}"
            if candidate.casefold() in self._reserved:
                continue
            occupied = self._lookup(candidate)
            if occupied is None:
                return self._claim(candidate, renamed=True, skipped=False)
            if self._policy is CollisionPolicy.OVERWRITE:
                return self._claim(occupied, renamed=True, skipped=False)
        raise ExportError(f"Could not find a free filename for {primary}.")

    def _lookup(self, name: str) -> str | None:
        return self._on_disk.get(name.casefold())

    def _claim(self, filename: str, *, renamed: bool, skipped: bool) -> _AllocatedName:
        self._reserved.add(filename.casefold())
        return _AllocatedName(self._directory / filename, renamed=renamed, skipped=skipped)
