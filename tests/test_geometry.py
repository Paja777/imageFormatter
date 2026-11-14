"""Crop and fit geometry, independent of pixel resampling."""

from __future__ import annotations

import math

import pytest

from image_resizer.core.crop_geometry import (
    CropAnchor,
    Size,
    cover_crop_box,
    fit_placement,
    requires_upscale,
)
from image_resizer.models.settings import ResizeMode


def test_crop_anchor_clamps_to_the_unit_interval() -> None:
    assert CropAnchor(2, -1).clamped() == CropAnchor(1, 0)
    assert CropAnchor(0.5, 0.5).clamped() == CropAnchor(0.5, 0.5)
    with pytest.raises(ValueError):
        CropAnchor(float("nan"), 0.5).clamped()


def test_crop_window_stays_inside_the_source() -> None:
    cases = ((200, 80), (80, 200), (64, 64), (17, 13), (1, 40), (40, 1))
    targets = ((30, 20), (20, 30), (1, 1), (100, 40))
    anchors = (CropAnchor(0, 0), CropAnchor(0.5, 0.5), CropAnchor(1, 1), CropAnchor(-1, 3))
    for source_size in cases:
        for target_size in targets:
            for anchor in anchors:
                box = cover_crop_box(Size(*source_size), Size(*target_size), anchor)
                assert box.width >= 1 and box.height >= 1
                assert box.left >= 0 and box.top >= 0
                assert box.right <= source_size[0]
                assert box.bottom <= source_size[1]


def test_centered_crop_and_edge_anchors() -> None:
    source = Size(120, 30)
    target = Size(30, 30)
    center = cover_crop_box(source, target, CropAnchor(0.5, 0.5))
    assert center == cover_crop_box(source, target, None)
    assert center.left == 45
    assert center.top == 0
    assert center.width == 30 and center.height == 30

    assert cover_crop_box(source, target, CropAnchor(0, 0)).left == 0
    assert cover_crop_box(source, target, CropAnchor(1, 0)).right == source.width
    partial = cover_crop_box(source, target, CropAnchor(0.25, 0))
    assert partial.left == math.floor((source.width - partial.width) * 0.25 + 0.5)


def test_crop_keeps_the_full_limiting_edge() -> None:
    wide = cover_crop_box(Size(200, 50), Size(20, 10), CropAnchor())
    assert wide.height == 50
    assert abs(wide.width - 100) <= 1

    tall = cover_crop_box(Size(50, 200), Size(10, 20), CropAnchor())
    assert tall.width == 50
    assert abs(tall.height - 100) <= 1


def test_fit_centers_the_whole_image_without_cropping_a_side() -> None:
    wide = fit_placement(Size(200, 100), Size(200, 200))
    assert (wide.content.width, wide.content.height, wide.x, wide.y) == (200, 100, 0, 50)

    tall = fit_placement(Size(100, 200), Size(100, 100))
    assert (tall.content.width, tall.content.height, tall.x, tall.y) == (50, 100, 25, 0)

    padded = fit_placement(Size(10, 10), Size(30, 10))
    assert (padded.content.width, padded.content.height, padded.x, padded.y) == (10, 10, 10, 0)

    same = fit_placement(Size(40, 20), Size(40, 20))
    assert (same.content.width, same.content.height, same.x, same.y) == (40, 20, 0, 0)


def test_fit_content_never_exceeds_the_target() -> None:
    for source_size in ((80, 30), (30, 80), (15, 15), (2, 9)):
        for target_size in ((40, 20), (20, 40), (8, 8)):
            placed = fit_placement(Size(*source_size), Size(*target_size))
            assert placed.content.width <= target_size[0]
            assert placed.content.height <= target_size[1]
            assert placed.x >= 0 and placed.y >= 0
            assert placed.x + placed.content.width <= target_size[0]
            assert placed.y + placed.content.height <= target_size[1]


def test_upscale_detection_follows_the_resize_mode() -> None:
    source = Size(10, 10)
    assert requires_upscale(source, Size(20, 5), ResizeMode.STRETCH)
    assert not requires_upscale(source, Size(10, 10), ResizeMode.STRETCH)
    assert requires_upscale(source, Size(8, 20), ResizeMode.CROP)
    assert not requires_upscale(Size(100, 100), Size(50, 80), ResizeMode.CROP)
    assert requires_upscale(source, Size(11, 11), ResizeMode.FIT)
    assert not requires_upscale(source, Size(20, 8), ResizeMode.FIT)


def test_size_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError):
        Size(0, 10)
    with pytest.raises(ValueError):
        Size(10, -4)
    with pytest.raises(ValueError):
        Size(True, 10)  # type: ignore[arg-type]
