"""Image loading, EXIF orientation, and rejected files."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from image_resizer.core.errors import (
    CorruptedImageError,
    ImageNotFoundError,
    ImageTooLargeError,
    UnsupportedFormatError,
)
from image_resizer.services.image_loader import load_image
from support import BLUE, RED, almost


def _half_and_half(size: tuple[int, int] = (64, 32)) -> Image.Image:
    image = Image.new("RGB", size, RED)
    image.paste(Image.new("RGB", (size[0] // 2, size[1]), BLUE), (size[0] // 2, 0))
    return image


def _save_oriented(path: Path, image: Image.Image, orientation: int) -> None:
    exif = image.getexif()
    exif[274] = orientation
    image.save(path, format="JPEG", quality=95, subsampling=0, exif=exif)


def test_supported_formats_load_with_metadata(tmp_path: Path) -> None:
    cases = (
        ("photo.jpg", "JPEG", RED),
        ("photo.jpeg", "JPEG", BLUE),
        ("photo.png", "PNG", RED),
        ("photo.webp", "WEBP", (0, 255, 0)),
        ("photo.bmp", "BMP", (0, 0, 255)),
        ("photo.tiff", "TIFF", (255, 255, 0)),
        ("photo.TIF", "TIFF", RED),
        ("PHOTO.JPG", "JPEG", BLUE),
    )
    for filename, expected_format, color in cases:
        path = tmp_path / filename
        Image.new("RGB", (12, 8), color).save(path)
        before = path.read_bytes()
        loaded = load_image(path)
        assert path.read_bytes() == before
        assert loaded.metadata.format == expected_format
        assert loaded.metadata.filename == filename
        assert loaded.metadata.width == 12
        assert loaded.metadata.height == 8
        assert loaded.metadata.file_size == path.stat().st_size
        assert loaded.metadata.large_image_warning is False
        assert loaded.image.size == (12, 8)
        assert almost(loaded.image.getpixel((1, 1)), color, tolerance=2)


def test_grayscale_png_and_cmyk_tiff_become_rgb(tmp_path: Path) -> None:
    gray_path = tmp_path / "gray.png"
    Image.new("L", (8, 8), 40).save(gray_path)
    gray = load_image(gray_path)
    assert gray.metadata.source_mode == "L"
    assert gray.image.mode == "RGB"
    assert gray.image.getpixel((0, 0)) == (40, 40, 40)

    cmyk_path = tmp_path / "print.tiff"
    Image.new("CMYK", (8, 8), (0, 0, 0, 0)).save(cmyk_path)
    cmyk = load_image(cmyk_path)
    assert cmyk.metadata.source_mode == "CMYK"
    assert cmyk.image.mode == "RGB"
    assert cmyk.image.getpixel((0, 0)) == (255, 255, 255)


def test_palette_png_with_transparency_keeps_alpha(tmp_path: Path) -> None:
    path = tmp_path / "indexed.png"
    image = Image.new("P", (4, 4), 0)
    image.putpalette([0, 0, 0, 255, 0, 0] + [0, 0, 0] * 254)
    image.info["transparency"] = 0
    image.putpixel((0, 0), 1)
    image.save(path)
    loaded = load_image(path)
    assert loaded.image.mode == "RGBA"
    assert loaded.image.getpixel((0, 0))[:3] == RED
    assert loaded.image.getpixel((0, 0))[3] == 255
    assert loaded.image.getpixel((3, 3))[3] == 0


@pytest.mark.parametrize(
    ("orientation", "expected_size", "red_pixel", "blue_pixel"),
    [
        (2, (64, 32), (48, 8), (8, 8)),
        (3, (64, 32), (48, 24), (8, 24)),
        (6, (32, 64), (16, 8), (16, 48)),
        (8, (32, 64), (16, 48), (16, 8)),
    ],
)
def test_exif_orientation_is_applied_and_not_applied_twice(
    tmp_path: Path,
    orientation: int,
    expected_size: tuple[int, int],
    red_pixel: tuple[int, int],
    blue_pixel: tuple[int, int],
) -> None:
    path = tmp_path / f"oriented-{orientation}.jpg"
    _save_oriented(path, _half_and_half(), orientation)
    original_bytes = path.read_bytes()
    with Image.open(path) as raw:
        assert raw.getexif().get(274) == orientation
        assert raw.size == (64, 32)

    loaded = load_image(path)
    assert path.read_bytes() == original_bytes
    assert loaded.metadata.had_exif_orientation is True
    assert loaded.metadata.exif_orientation == orientation
    assert loaded.image.size == expected_size
    assert almost(loaded.image.getpixel(red_pixel), RED, tolerance=8)
    assert almost(loaded.image.getpixel(blue_pixel), BLUE, tolerance=8)
    assert loaded.image.getexif().get(274) in (None, 1)

    resaved = tmp_path / f"resaved-{orientation}.png"
    loaded.image.save(resaved)
    again = load_image(resaved)
    assert again.image.size == expected_size
    assert again.metadata.had_exif_orientation is False
    assert almost(again.image.getpixel(red_pixel), RED, tolerance=8)


def test_corrupted_and_unreadable_images_are_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    garbage = tmp_path / "garbage.jpg"
    garbage.write_bytes(b"this is not a jpeg")
    truncated = tmp_path / "truncated.webp"
    valid = tmp_path / "valid.webp"
    Image.new("RGB", (16, 16), RED).save(valid)
    truncated.write_bytes(valid.read_bytes()[:12])
    missing = tmp_path / "missing.png"
    directory = tmp_path / "folder.jpg"
    directory.mkdir()

    for path in (empty, garbage, truncated):
        with pytest.raises(CorruptedImageError):
            load_image(path)
    with pytest.raises(ImageNotFoundError):
        load_image(missing)
    with pytest.raises(ImageNotFoundError):
        load_image(directory)


def test_unsupported_extension_is_rejected_before_decoding(tmp_path: Path) -> None:
    gif_path = tmp_path / "animation.gif"
    Image.new("RGB", (6, 6), RED).save(gif_path, format="GIF")
    text_path = tmp_path / "notes.txt"
    text_path.write_text("hello", encoding="utf-8")
    with pytest.raises(UnsupportedFormatError):
        load_image(gif_path)
    with pytest.raises(UnsupportedFormatError):
        load_image(text_path)


def test_mislabelled_content_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "actually-gif.png"
    Image.new("RGB", (6, 6), RED).save(path, format="GIF")
    with pytest.raises((UnsupportedFormatError, CorruptedImageError)):
        load_image(path)


def test_file_and_pixel_limits_reject_oversized_input(tmp_path: Path) -> None:
    path = tmp_path / "small.png"
    Image.new("RGB", (20, 20), RED).save(path)
    with pytest.raises(ImageTooLargeError):
        load_image(path, max_file_bytes=10)
    with pytest.raises(ImageTooLargeError):
        load_image(path, max_pixels=10)

    warned = load_image(path, warn_above_pixels=1)
    assert warned.metadata.large_image_warning is True
    quiet = load_image(path, warn_above_pixels=None)
    assert quiet.metadata.large_image_warning is False


def test_decompression_bomb_protection_stays_enabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import image_resizer
    from PIL import Image as PilImage

    assert PilImage.MAX_IMAGE_PIXELS is not None
    assert image_resizer.__version__

    path = tmp_path / "bomb.png"
    Image.new("RGB", (32, 32), RED).save(path)
    monkeypatch.setattr(PilImage, "MAX_IMAGE_PIXELS", 20)
    with pytest.raises(ImageTooLargeError):
        load_image(path)
