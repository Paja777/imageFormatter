"""Load one source image and apply its EXIF orientation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from image_resizer.core.errors import (
    CorruptedImageError,
    ImageNotFoundError,
    ImageTooLargeError,
    UnsupportedFormatError,
)
from image_resizer.core.image_processor import to_working_mode


SUPPORTED_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"})
SUPPORTED_PIL_FORMATS = frozenset({"JPEG", "PNG", "WEBP", "BMP", "TIFF"})
DEFAULT_MAX_FILE_BYTES = 512 * 1024 * 1024
DEFAULT_LARGE_IMAGE_WARNING_PIXELS = 40_000_000
_ORIENTATION_TAG = 274


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    """Facts the interface can show without inspecting pixels again."""

    path: Path
    filename: str
    format: str
    source_mode: str
    mode: str
    width: int
    height: int
    file_size: int
    exif_orientation: int | None
    large_image_warning: bool

    @property
    def had_exif_orientation(self) -> bool:
        return self.exif_orientation not in (None, 1)

    @property
    def pixel_count(self) -> int:
        return self.width * self.height


@dataclass(slots=True)
class LoadedImage:
    """Decoded pixels with orientation already applied."""

    image: Image.Image
    metadata: ImageMetadata


def load_image(
    path: str | Path,
    *,
    max_file_bytes: int | None = DEFAULT_MAX_FILE_BYTES,
    max_pixels: int | None = None,
    warn_above_pixels: int | None = DEFAULT_LARGE_IMAGE_WARNING_PIXELS,
) -> LoadedImage:
    """Open a supported image, apply EXIF orientation, and detach it from disk.

    Pillow's decompression-bomb limit is left at its default. ``max_pixels``
    is an additional hard cap; ``warn_above_pixels`` only sets a flag.
    """
    source = Path(path)
    if not source.exists() or not source.is_file():
        raise ImageNotFoundError(f"Image file not found: {source}.")

    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"Unsupported image format '{suffix or source.name}'. "
            "Use JPG, PNG, WEBP, BMP, or TIFF."
        )

    file_size = source.stat().st_size
    if max_file_bytes is not None and file_size > max_file_bytes:
        raise ImageTooLargeError(
            f"The file is larger than the {max_file_bytes} byte limit."
        )

    try:
        with Image.open(source) as img:
            detected = img.format
            if detected not in SUPPORTED_PIL_FORMATS:
                raise UnsupportedFormatError(
                    f"Unsupported image content ({detected or 'unknown'})."
                )
            orientation = _read_orientation(img)
            img.load()
            pixel_count = img.width * img.height
            if max_pixels is not None and pixel_count > max_pixels:
                raise ImageTooLargeError(
                    f"The image has {pixel_count} pixels, above the {max_pixels} pixel limit."
                )
            oriented = ImageOps.exif_transpose(img) or img
            source_mode = img.mode
            working = to_working_mode(oriented).copy()
            working.info = dict(oriented.info)
            _drop_orientation_tag(working)
            width, height = working.size
    except Image.DecompressionBombError as exc:
        raise ImageTooLargeError("The image is too large to decode safely.") from exc
    except (UnsupportedFormatError, ImageTooLargeError):
        raise
    except (Image.UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise CorruptedImageError(f"The image file could not be read: {source.name}.") from exc

    return LoadedImage(
        image=working,
        metadata=ImageMetadata(
            path=source,
            filename=source.name,
            format=detected or "UNKNOWN",
            source_mode=source_mode,
            mode=working.mode,
            width=width,
            height=height,
            file_size=file_size,
            exif_orientation=orientation,
            large_image_warning=(
                warn_above_pixels is not None and width * height > warn_above_pixels
            ),
        ),
    )


def _read_orientation(image: Image.Image) -> int | None:
    try:
        value = image.getexif().get(_ORIENTATION_TAG)
    except (AttributeError, OSError, ValueError):
        return None
    if isinstance(value, int) and 1 <= value <= 8:
        return value
    return None


def _drop_orientation_tag(image: Image.Image) -> None:
    try:
        exif = image.getexif()
    except (AttributeError, OSError, ValueError):
        image.info.pop("exif", None)
        return
    if _ORIENTATION_TAG in exif:
        del exif[_ORIENTATION_TAG]
    if len(exif) == 0:
        image.info.pop("exif", None)
        return
    image.info["exif"] = exif.tobytes()
