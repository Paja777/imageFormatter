"""Pixel rendering for crop, fit, and stretch.

The same functions serve export and, later, the on-screen preview.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from image_resizer.core.crop_geometry import (
    Box,
    CropAnchor,
    Size,
    cover_crop_box,
    fit_placement,
    requires_upscale,
)
from image_resizer.core.errors import ImageResizerError
from image_resizer.models.settings import MAX_IMAGE_DIMENSION, WHITE, Color, ResizeMode


@dataclass(slots=True)
class ProcessedImage:
    """One rendered target, plus the geometry used to produce it."""

    image: Image.Image
    upscaled: bool
    crop_box: Box | None = None


def to_working_mode(image: Image.Image) -> Image.Image:
    """Convert uncommon color modes to RGB or RGBA.

    RGB and RGBA are returned unchanged so callers can avoid an extra copy.
    """
    if image.mode in {"RGB", "RGBA"}:
        return image
    if image.mode in {"LA", "PA", "RGBa"} or _palette_has_alpha(image):
        return image.convert("RGBA")
    if "A" in image.getbands():
        return image.convert("RGBA")
    try:
        return image.convert("RGB")
    except (ValueError, OSError) as exc:
        raise ImageResizerError("The image color mode could not be converted.") from exc


def render(
    image: Image.Image,
    target: Size,
    mode: ResizeMode,
    *,
    crop_anchor: CropAnchor | None = None,
    background: Color | None = None,
) -> ProcessedImage:
    """Render ``image`` at exactly ``target`` using ``mode``.

    The source image is not modified. Crop position defaults to the center.
    """
    if not isinstance(image, Image.Image):
        raise ImageResizerError("A source image is required.")
    if not isinstance(mode, ResizeMode):
        raise ImageResizerError("Unsupported resize mode.")
    if target.width > MAX_IMAGE_DIMENSION or target.height > MAX_IMAGE_DIMENSION:
        raise ImageResizerError(
            f"Output dimensions cannot exceed {MAX_IMAGE_DIMENSION} pixels."
        )

    working = to_working_mode(image)
    source = Size(working.width, working.height)
    matte = background if background is not None else WHITE
    try:
        anchor = (crop_anchor or CropAnchor()).clamped()
    except ValueError as exc:
        raise ImageResizerError(str(exc)) from exc

    upscaled = requires_upscale(source, target, mode)
    if mode is ResizeMode.CROP:
        box = cover_crop_box(source, target, anchor)
        cropped = working.crop(box.as_pillow())
        return ProcessedImage(_resize(cropped, target), upscaled, box)
    if mode is ResizeMode.FIT:
        placed = _render_fit(working, target, matte)
        return ProcessedImage(placed, upscaled, None)
    if mode is ResizeMode.STRETCH:
        return ProcessedImage(_resize(working, target), upscaled, None)
    raise ImageResizerError(f"Unsupported resize mode: {mode}.")


def _render_fit(image: Image.Image, target: Size, background: Color) -> Image.Image:
    placement = fit_placement(Size(image.width, image.height), target)
    resized = _resize(image, placement.content)
    canvas = Image.new("RGBA", (target.width, target.height), background.as_rgba())
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    layer.paste(resized.convert("RGBA"), (placement.x, placement.y))
    merged = Image.alpha_composite(canvas, layer)
    if image.mode != "RGBA" and background.alpha == 255:
        return merged.convert("RGB")
    return merged


def _resize(image: Image.Image, target: Size) -> Image.Image:
    if image.size == (target.width, target.height):
        return image.copy()
    return image.resize((target.width, target.height), Image.Resampling.LANCZOS)


def _palette_has_alpha(image: Image.Image) -> bool:
    return image.mode == "P" and "transparency" in image.info
