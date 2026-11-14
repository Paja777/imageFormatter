"""Resize modes: exact dimensions, aspect ratio, and visible source content."""

from __future__ import annotations

import pytest
from PIL import Image

from image_resizer.core.crop_geometry import CropAnchor, Size
from image_resizer.core.image_processor import render
from image_resizer.core.presets import load_builtin_presets
from image_resizer.models.settings import WHITE, Color, ResizeMode
from support import (
    BLACK,
    BLUE,
    GREEN,
    RED,
    YELLOW,
    almost,
    color_bbox,
    columns,
    pixel_values,
    quadrants,
    rows,
    same_pixels,
)


PAD = Color(0, 180, 0)


@pytest.mark.parametrize("source_size", [(64, 40), (15, 15), (17, 13), (8, 40)])
@pytest.mark.parametrize("target_size", [(30, 20), (20, 30), (16, 16), (1, 1)])
@pytest.mark.parametrize("mode", list(ResizeMode))
def test_output_dimensions_match_the_target_for_every_mode(
    source_size: tuple[int, int],
    target_size: tuple[int, int],
    mode: ResizeMode,
) -> None:
    image = Image.new("RGB", source_size, (20, 40, 60))
    result = render(image, Size(*target_size), mode, background=PAD)
    assert result.image.size == target_size


def test_builtin_presets_render_at_their_exact_sizes() -> None:
    source = Image.new("RGB", (32, 18), RED)
    for preset in load_builtin_presets():
        target = Size(preset.width, preset.height)
        for mode in ResizeMode:
            result = render(source, target, mode, background=WHITE)
            assert result.image.size == (preset.width, preset.height)


def test_crop_preserves_aspect_ratio_of_a_square_marker() -> None:
    image = Image.new("RGB", (40, 20), BLACK)
    image.paste(Image.new("RGB", (10, 10), RED), (15, 5))
    original = pixel_values(image)

    cropped = render(image, Size(20, 20), ResizeMode.CROP)
    assert pixel_values(image) == original
    assert cropped.image.size == (20, 20)
    assert color_bbox(cropped.image, RED) == (5, 5, 10, 10)

    tall = Image.new("RGB", (20, 40), BLACK)
    tall.paste(Image.new("RGB", (10, 10), RED), (5, 15))
    tall_crop = render(tall, Size(20, 20), ResizeMode.CROP)
    assert color_bbox(tall_crop.image, RED) == (5, 5, 10, 10)

    scaled = render(image, Size(10, 10), ResizeMode.CROP)
    bbox = color_bbox(scaled.image, RED, tolerance=8)
    assert bbox is not None
    assert abs(bbox[2] - bbox[3]) <= 1
    assert bbox[2] < scaled.image.width


def test_fit_preserves_the_complete_source_image() -> None:
    source = quadrants(40, 20)
    fitted = render(source, Size(40, 40), ResizeMode.FIT, background=PAD)
    assert fitted.image.size == (40, 40)
    assert fitted.image.getpixel((10, 15)) == RED
    assert fitted.image.getpixel((30, 15)) == GREEN
    assert fitted.image.getpixel((10, 25)) == BLUE
    assert fitted.image.getpixel((30, 25)) == YELLOW
    assert fitted.image.getpixel((10, 0)) == PAD.as_rgb()
    assert fitted.image.getpixel((10, 39)) == PAD.as_rgb()

    identity = render(source, Size(40, 20), ResizeMode.FIT, background=PAD)
    assert same_pixels(identity.image, source)

    reduced = render(source, Size(20, 20), ResizeMode.FIT, background=PAD)
    assert reduced.image.size == (20, 20)
    for color in (RED, GREEN, BLUE, YELLOW):
        assert any(almost(pixel, color, tolerance=30) for pixel in pixel_values(reduced.image))
    assert reduced.image.getpixel((0, 0)) == PAD.as_rgb()


def test_fit_uses_the_selected_padding_color() -> None:
    image = Image.new("RGB", (10, 10), RED)
    fitted = render(image, Size(30, 10), ResizeMode.FIT, background=PAD)
    assert fitted.image.getpixel((0, 5)) == PAD.as_rgb()
    assert fitted.image.getpixel((15, 5)) == RED
    assert fitted.image.getpixel((29, 5)) == PAD.as_rgb()


def test_stretch_generates_exact_target_dimensions_and_keeps_both_halves() -> None:
    image = Image.new("RGB", (40, 40), RED)
    image.paste(Image.new("RGB", (20, 40), BLUE), (20, 0))
    stretched = render(image, Size(20, 40), ResizeMode.STRETCH)
    assert stretched.image.size == (20, 40)
    assert stretched.image.getpixel((4, 0)) == RED
    assert stretched.image.getpixel((16, 0)) == BLUE
    assert stretched.upscaled is False

    enlarged = render(image, Size(80, 20), ResizeMode.STRETCH)
    assert enlarged.image.size == (80, 20)
    assert enlarged.upscaled is True


def test_crop_defaults_to_the_center() -> None:
    image = columns(90, 30, (RED, GREEN, BLUE))
    centered = render(image, Size(30, 30), ResizeMode.CROP)
    assert centered.crop_box is not None
    assert (centered.crop_box.left, centered.crop_box.top, centered.crop_box.width) == (30, 0, 30)
    assert same_pixels(centered.image, Image.new("RGB", (30, 30), GREEN))

    omitted = render(image, Size(30, 30), ResizeMode.CROP, crop_anchor=None)
    assert same_pixels(omitted.image, centered.image)


def test_custom_crop_anchor_selects_the_requested_region() -> None:
    horizontal = columns(90, 30, (RED, GREEN, BLUE))
    left = render(horizontal, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(0, 0.5))
    right = render(horizontal, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(1, 0.5))
    forced = render(horizontal, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(4, -2))
    assert same_pixels(left.image, Image.new("RGB", (30, 30), RED))
    assert same_pixels(right.image, Image.new("RGB", (30, 30), BLUE))
    assert same_pixels(forced.image, right.image)

    vertical = rows(30, 90, (RED, GREEN, BLUE))
    top = render(vertical, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(0.5, 0))
    bottom = render(vertical, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(0.5, 1))
    middle = render(vertical, Size(30, 30), ResizeMode.CROP, crop_anchor=CropAnchor(0.5, 0.5))
    assert same_pixels(top.image, Image.new("RGB", (30, 30), RED))
    assert same_pixels(bottom.image, Image.new("RGB", (30, 30), BLUE))
    assert same_pixels(middle.image, Image.new("RGB", (30, 30), GREEN))


def test_alpha_channel_survives_every_mode_when_the_size_does_not_change() -> None:
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0, 128))
    image.putpixel((5, 5), (0, 255, 0, 255))
    for mode in ResizeMode:
        result = render(image, Size(10, 10), mode, background=Color(0, 0, 0, 0))
        assert result.image.mode == "RGBA"
        assert result.image.getpixel((0, 0)) == (255, 0, 0, 128)
        assert result.image.getpixel((5, 5)) == (0, 255, 0, 255)


def test_fit_can_pad_with_transparency() -> None:
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0, 128))
    image.putpixel((5, 5), (0, 255, 0, 255))
    fitted = render(image, Size(10, 20), ResizeMode.FIT, background=Color(0, 0, 0, 0))
    assert fitted.image.mode == "RGBA"
    assert fitted.image.getpixel((0, 0))[3] == 0
    assert fitted.image.getpixel((0, 5)) == (255, 0, 0, 128)
    assert fitted.image.getpixel((5, 10)) == (0, 255, 0, 255)


def test_non_rgb_sources_are_converted_without_changing_the_canvas_size() -> None:
    cmyk = Image.new("CMYK", (6, 4), (0, 0, 0, 0))
    converted = render(cmyk, Size(6, 4), ResizeMode.STRETCH)
    assert converted.image.mode == "RGB"
    assert converted.image.size == (6, 4)
    assert converted.image.getpixel((0, 0)) == (255, 255, 255)

    gray = Image.new("L", (4, 4), 40)
    gray_result = render(gray, Size(4, 4), ResizeMode.FIT)
    assert gray_result.image.mode == "RGB"
    assert gray_result.image.getpixel((1, 1)) == (40, 40, 40)
