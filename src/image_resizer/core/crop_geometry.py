"""Source-space geometry shared by preview and export.

Crop and fit decisions are computed here once. Rendering only samples
pixels, so a preview and a saved file cannot drift apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from image_resizer.models.settings import ResizeMode


def _positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer.")
    return value


@dataclass(frozen=True, slots=True)
class Size:
    """Pixel width and height."""

    width: int
    height: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _positive_int(self.width, "Width"))
        object.__setattr__(self, "height", _positive_int(self.height, "Height"))


@dataclass(frozen=True, slots=True)
class Box:
    """Inclusive-exclusive rectangle in source pixels: [left, right) x [top, bottom)."""

    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def as_pillow(self) -> tuple[int, int, int, int]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True, slots=True)
class FitPlacement:
    """Where the fitted image sits on the target canvas."""

    content: Size
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class CropAnchor:
    """Normalized crop position.

    ``0`` keeps the crop against the left or top edge, ``1`` against the
    opposite edge, and ``0.5`` centers it. Values outside that range are
    clamped when the box is computed.
    """

    x: float = 0.5
    y: float = 0.5

    def clamped(self) -> CropAnchor:
        x = _unit_interval(self.x)
        y = _unit_interval(self.y)
        if x == self.x and y == self.y:
            return self
        return CropAnchor(x, y)


def _unit_interval(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Crop anchor must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Crop anchor must be a finite number.")
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number


def _rounded_div(numerator: int, denominator: int) -> int:
    """Divide positive integers and round half up.

    A crop window has to use whole pixels, so its aspect can be at most
    half a pixel away from the target. The final resize then lands on
    the exact requested size.
    """
    if denominator <= 0:
        raise ValueError("Cannot divide by zero.")
    return (numerator + denominator // 2) // denominator


def _offset(span: int, anchor: float) -> int:
    if span <= 0:
        return 0
    offset = math.floor(span * anchor + 0.5)
    if offset < 0:
        return 0
    if offset > span:
        return span
    return int(offset)


def cover_crop_box(source: Size, target: Size, anchor: CropAnchor | None = None) -> Box:
    """Return the source rectangle used by cover-style cropping.

    The rectangle keeps the target aspect ratio (to the nearest pixel)
    and is the largest such rectangle that fits in the source. Resizing
    it to the target is therefore a uniform scale, not a stretch.
    """
    position = (anchor or CropAnchor()).clamped()
    sw, sh = source.width, source.height
    tw, th = target.width, target.height

    if sw * th > tw * sh:
        crop_h = sh
        crop_w = min(sw, max(1, _rounded_div(sh * tw, th)))
    else:
        crop_w = sw
        crop_h = min(sh, max(1, _rounded_div(sw * th, tw)))

    left = _offset(sw - crop_w, position.x)
    top = _offset(sh - crop_h, position.y)
    return Box(left, top, crop_w, crop_h)


def fit_placement(source: Size, target: Size) -> FitPlacement:
    """Scale the whole source so it sits inside the target, then center it."""
    sw, sh = source.width, source.height
    tw, th = target.width, target.height

    if tw * sh <= th * sw:
        content_w = tw
        content_h = min(th, max(1, _rounded_div(sh * tw, sw)))
    else:
        content_h = th
        content_w = min(tw, max(1, _rounded_div(sw * th, sh)))

    return FitPlacement(
        content=Size(content_w, content_h),
        x=(tw - content_w) // 2,
        y=(th - content_h) // 2,
    )


def requires_upscale(source: Size, target: Size, mode: ResizeMode) -> bool:
    """Report whether the chosen mode enlarges source pixels.

    Fit only upscales when the whole image must grow. Crop and stretch
    upscale as soon as either target edge exceeds the source.
    """
    if mode is ResizeMode.FIT:
        return target.width > source.width and target.height > source.height
    return target.width > source.width or target.height > source.height
