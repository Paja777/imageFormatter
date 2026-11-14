"""Turn pointer motion into the crop anchor shared with export.

The rectangle always comes from ``cover_crop_box``. These helpers only
choose the anchor that places that rectangle where the pointer left it.
"""

from __future__ import annotations

import math

from image_resizer.core.crop_geometry import Box, CropAnchor, Size, cover_crop_box


def source_delta_for_drag(
    crop_width: int,
    crop_height: int,
    display_width: float,
    display_height: float,
    screen_dx: float,
    screen_dy: float,
) -> tuple[float, float]:
    """Convert a drag of the visible photo into a crop-window shift.

    The photo follows the pointer, so the window over the source moves
    in the opposite direction. Distances are in source pixels.
    """
    if (
        display_width <= 0
        or display_height <= 0
        or not math.isfinite(screen_dx)
        or not math.isfinite(screen_dy)
    ):
        return (0.0, 0.0)
    return (
        -screen_dx * (crop_width / display_width),
        -screen_dy * (crop_height / display_height),
    )


def pan_crop_anchor(
    source: Size,
    target: Size,
    anchor: CropAnchor,
    delta_x: float,
    delta_y: float,
) -> CropAnchor:
    """Move the current crop window by ``delta_x`` and ``delta_y`` source pixels."""
    current = cover_crop_box(source, target, anchor)
    if not math.isfinite(delta_x) or not math.isfinite(delta_y):
        return _anchor_for_origin(source, target, current.left, current.top)
    span_x = source.width - current.width
    span_y = source.height - current.height
    left = _clamp_round(current.left + delta_x, span_x)
    top = _clamp_round(current.top + delta_y, span_y)
    return _anchor_for_origin(source, target, left, top)


def place_crop_anchor(
    source: Size,
    target: Size,
    center_x: float,
    center_y: float,
) -> CropAnchor:
    """Center the crop window on a point in source pixels, then clamp it."""
    sample = cover_crop_box(source, target, CropAnchor())
    span_x = source.width - sample.width
    span_y = source.height - sample.height
    if not math.isfinite(center_x) or not math.isfinite(center_y):
        return CropAnchor()
    left = _clamp_round(center_x - sample.width / 2, span_x)
    top = _clamp_round(center_y - sample.height / 2, span_y)
    return _anchor_for_origin(source, target, left, top)


def _anchor_for_origin(source: Size, target: Size, left: int, top: int) -> CropAnchor:
    return CropAnchor(
        _anchor_component(source, target, left, "x"),
        _anchor_component(source, target, top, "y"),
    )


def _anchor_component(source: Size, target: Size, offset: int, axis: str) -> float:
    """Return an anchor whose crop box reproduces ``offset`` on ``axis``."""
    sample = cover_crop_box(source, target, CropAnchor())
    span = (source.width - sample.width) if axis == "x" else (source.height - sample.height)
    if span <= 0:
        return 0.5
    desired = min(span, max(0, offset))

    def read(value: float) -> int:
        anchor = CropAnchor(value, 0.5) if axis == "x" else CropAnchor(0.5, value)
        box: Box = cover_crop_box(source, target, anchor)
        return box.left if axis == "x" else box.top

    lower = _first_at_least(read, desired)
    upper = _last_at_most(read, desired, lower)
    candidate = (lower + upper) / 2
    if read(candidate) == desired:
        return candidate
    if read(lower) == desired:
        return lower
    if read(upper) == desired:
        return upper
    return desired / span


def _first_at_least(read, desired: int) -> float:
    left = 0.0
    right = 1.0
    for _ in range(48):
        mid = (left + right) / 2
        if read(mid) < desired:
            left = mid
        else:
            right = mid
    return right


def _last_at_most(read, desired: int, lower: float) -> float:
    left = lower
    right = 1.0
    for _ in range(48):
        mid = (left + right) / 2
        if read(mid) <= desired:
            left = mid
        else:
            right = mid
    return left


def _clamp_round(value: float, span: int) -> int:
    if span <= 0:
        return 0
    rounded = int(math.floor(value + 0.5))
    if rounded < 0:
        return 0
    if rounded > span:
        return span
    return rounded
