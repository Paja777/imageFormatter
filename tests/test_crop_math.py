"""Pointer motion stays on the same crop rectangle export will use."""

from __future__ import annotations

import random

from image_resizer.core.crop_geometry import CropAnchor, Size, cover_crop_box
from image_resizer.ui.crop_math import pan_crop_anchor, place_crop_anchor, source_delta_for_drag


def test_screen_drag_moves_the_crop_window_opposite_the_pointer() -> None:
    delta_x, delta_y = source_delta_for_drag(100, 50, 200, 100, 20, -10)
    assert delta_x == -10
    assert delta_y == 5
    assert source_delta_for_drag(10, 10, 0, 10, 5, 5) == (0.0, 0.0)


def test_pan_shifts_and_clamps_inside_the_source() -> None:
    source = Size(800, 400)
    target = Size(200, 200)
    centered = cover_crop_box(source, target, CropAnchor())
    moved = pan_crop_anchor(source, target, CropAnchor(), -30, 0)
    box = cover_crop_box(source, target, moved)
    assert box.left == centered.left - 30
    assert box.top == centered.top
    assert box.right <= source.width

    pinned = pan_crop_anchor(source, target, CropAnchor(0, 0.5), -50, 25)
    pinned_box = cover_crop_box(source, target, pinned)
    assert pinned_box.left == 0
    assert pinned_box.bottom <= source.height


def test_non_finite_pan_keeps_the_current_window() -> None:
    source = Size(300, 200)
    target = Size(100, 80)
    original = cover_crop_box(source, target, CropAnchor(0.25, 0.75))
    moved = pan_crop_anchor(source, target, CropAnchor(0.25, 0.75), float("nan"), 4)
    assert cover_crop_box(source, target, moved) == original


def test_placed_anchor_round_trips_through_cover_crop_box() -> None:
    rng = random.Random(0)
    sizes = (
        (800, 400, 200, 200),
        (1000, 500, 1920, 1080),
        (1200, 800, 1200, 628),
        (50, 50, 50, 80),
        (10, 10, 10, 10),
        (640, 480, 1080, 1920),
    )
    cases = list(sizes)
    for _ in range(24):
        cases.append(tuple(rng.randint(1, 900) for _ in range(4)))
    for sw, sh, tw, th in cases:
        source = Size(sw, sh)
        target = Size(tw, th)
        sample = cover_crop_box(source, target, CropAnchor())
        span_x = source.width - sample.width
        span_y = source.height - sample.height
        left = 0 if span_x == 0 else rng.randint(0, span_x)
        top = 0 if span_y == 0 else rng.randint(0, span_y)
        anchor = place_crop_anchor(
            source,
            target,
            left + sample.width / 2,
            top + sample.height / 2,
        )
        got = cover_crop_box(source, target, anchor)
        assert (got.left, got.top, got.width, got.height) == (left, top, sample.width, sample.height)
