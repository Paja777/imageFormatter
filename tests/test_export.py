"""Export layout, collisions, alpha, and JPEG flattening."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

from image_resizer.core.crop_geometry import CropAnchor
from image_resizer.core.errors import ExportError, ImageResizerError
from image_resizer.core.export_service import (
    STRETCH_WARNING,
    UPSCALE_WARNING,
    convert_for_output,
    export_image,
    filesystem_stem,
)
from image_resizer.core.presets import Preset, load_builtin_presets
from image_resizer.models.settings import WHITE, CollisionPolicy, Color, OutputFormat, ResizeMode
from support import BLUE, GREEN, RED, almost, columns, same_pixels


def _preset(name: str, width: int, height: int, preset_id: str) -> Preset:
    return Preset(name=name, width=width, height=height, id=preset_id)


def test_filesystem_stem_is_safe_and_stable() -> None:
    assert filesystem_stem("product-photo.jpg") == "product-photo"
    assert filesystem_stem("../secret/product-photo.jpg") == "product-photo"
    assert filesystem_stem("..\\secret\\product-photo.jpg") == "product-photo"
    assert filesystem_stem("CON.jpg") == "_CON"
    assert filesystem_stem("my photo.PNG") == "my photo"
    assert filesystem_stem("a<>b.jpg") == "a_b"
    assert filesystem_stem("fotografija.webp") == "fotografija"
    assert filesystem_stem("") == "image"
    assert len(filesystem_stem(("a" * 200) + ".jpg")) == 80


def test_multiple_presets_export_separate_files(tmp_path: Path) -> None:
    source = Image.new("RGB", (12, 8), RED)
    presets = (
        _preset("Wide", 8, 4, "wide"),
        _preset("Square", 4, 4, "square"),
        _preset("Tall", 4, 8, "tall"),
    )
    summary = export_image(
        source,
        "product-photo.jpg",
        presets,
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    assert summary.output_directory == tmp_path / "product-photo"
    names = sorted(item.path.name for item in summary.succeeded if item.path is not None)
    assert names == [
        "product-photo_4x4.png",
        "product-photo_4x8.png",
        "product-photo_8x4.png",
    ]
    for item in summary.succeeded:
        assert item.path is not None
        with Image.open(item.path) as saved:
            assert saved.size == (item.width, item.height)
    assert summary.failed == ()
    assert summary.distortion_warning == STRETCH_WARNING


def test_spec_example_presets_export_exact_jpeg_dimensions(tmp_path: Path) -> None:
    catalog = {preset.id: preset for preset in load_builtin_presets()}
    selected = (catalog["full-hd"], catalog["square"], catalog["story-reel"])
    summary = export_image(
        Image.new("RGB", (8, 8), RED),
        "product-photo.jpg",
        selected,
        tmp_path,
        mode=ResizeMode.CROP,
        output_format=OutputFormat.JPEG,
    )
    by_name = {item.path.name: item for item in summary.succeeded if item.path is not None}
    expected = {
        "product-photo_1920x1080.jpg": (1920, 1080),
        "product-photo_1080x1080.jpg": (1080, 1080),
        "product-photo_1080x1920.jpg": (1080, 1920),
    }
    assert set(by_name) == set(expected)
    for filename, size in expected.items():
        with Image.open(summary.output_directory / filename) as saved:
            assert saved.size == size
            assert saved.mode == "RGB"
            assert saved.getexif().get(274) in (None, 1)
    assert summary.upscale_warning == UPSCALE_WARNING


def test_each_selected_preset_keeps_its_own_crop_anchor(tmp_path: Path) -> None:
    source = columns(90, 30, (RED, GREEN, BLUE))
    left = _preset("Left", 30, 30, "left")
    center = _preset("Center", 30, 30, "center")
    right = _preset("Right", 30, 30, "right")
    summary = export_image(
        source,
        "bands.png",
        (left, center, right),
        tmp_path,
        mode=ResizeMode.CROP,
        output_format=OutputFormat.PNG,
        crop_anchors={
            left.id: CropAnchor(0, 0.5),
            center.id: CropAnchor(0.5, 0.5),
            right.id: CropAnchor(1, 0.5),
        },
    )
    colors = {RED: left.id, GREEN: center.id, BLUE: right.id}
    for expected, preset_id in colors.items():
        item = next(result for result in summary.files if result.preset_id == preset_id)
        assert item.path is not None
        with Image.open(item.path) as saved:
            assert saved.size == (30, 30)
            assert same_pixels(saved, Image.new("RGB", (30, 30), expected))
    assert len({item.path.name for item in summary.files}) == 3


def test_existing_files_are_not_overwritten_unless_requested(tmp_path: Path) -> None:
    destination = tmp_path / "out"
    red = Image.new("RGB", (16, 16), RED)
    blue = Image.new("RGB", (16, 16), BLUE)
    preset = _preset("Same", 16, 16, "same")
    first = export_image(
        red,
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    original = first.succeeded[0].path
    assert original is not None
    original_bytes = original.read_bytes()

    renamed = export_image(
        blue,
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
        collision_policy=CollisionPolicy.RENAME,
    )
    assert original.read_bytes() == original_bytes
    assert renamed.succeeded[0].renamed is True
    assert renamed.succeeded[0].path is not None
    assert renamed.succeeded[0].path.name == "photo_16x16_2.png"
    with Image.open(renamed.succeeded[0].path) as saved:
        assert saved.getpixel((0, 0)) == BLUE

    skipped = export_image(
        blue,
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
        collision_policy=CollisionPolicy.SKIP,
    )
    assert skipped.succeeded == ()
    assert skipped.skipped_files[0].path == original
    assert original.read_bytes() == original_bytes

    replaced = export_image(
        blue,
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
        collision_policy=CollisionPolicy.OVERWRITE,
    )
    assert replaced.succeeded[0].path == original
    assert replaced.succeeded[0].renamed is False
    with Image.open(original) as saved:
        assert saved.getpixel((0, 0)) == BLUE


def test_filename_collisions_are_case_insensitive(tmp_path: Path) -> None:
    destination = tmp_path / "out"
    preset = _preset("Same", 8, 8, "same")
    first = export_image(
        Image.new("RGB", (8, 8), RED),
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    created = first.succeeded[0].path
    assert created is not None
    upper = created.with_name(created.name.upper())
    created.rename(upper)
    original = upper.read_bytes()

    skipped = export_image(
        Image.new("RGB", (8, 8), BLUE),
        "photo.png",
        (preset,),
        destination,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
        collision_policy=CollisionPolicy.SKIP,
    )
    assert skipped.skipped_files[0].path == upper
    names = [path.name for path in (destination / "photo").iterdir() if not path.name.startswith(".")]
    assert names == [upper.name]
    assert upper.read_bytes() == original


def test_two_presets_with_the_same_dimensions_get_distinct_names(tmp_path: Path) -> None:
    summary = export_image(
        Image.new("RGB", (8, 8), RED),
        "photo.png",
        (_preset("One", 8, 8, "one"), _preset("Two", 8, 8, "two")),
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    names = sorted(item.path.name for item in summary.succeeded if item.path is not None)
    assert names == ["photo_8x8.png", "photo_8x8_2.png"]


def test_transparent_png_exports_to_jpeg_on_the_chosen_background(tmp_path: Path) -> None:
    image = Image.new("RGBA", (32, 16), (0, 0, 0, 0))
    image.paste(Image.new("RGBA", (16, 16), (255, 0, 0, 255)), (16, 0))
    background = Color(0, 0, 255)
    flat = convert_for_output(image, OutputFormat.JPEG, background)
    assert flat.mode == "RGB"
    assert flat.getpixel((4, 8)) == (0, 0, 255)
    assert flat.getpixel((24, 8)) == RED

    summary = export_image(
        image,
        "product.png",
        (_preset("Same", 32, 16, "same"),),
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.JPEG,
        background=background,
        quality=95,
    )
    saved_path = summary.succeeded[0].path
    assert saved_path is not None
    with Image.open(saved_path) as saved:
        assert saved.mode == "RGB"
        assert saved.size == (32, 16)
        left = saved.getpixel((4, 8))
        right = saved.getpixel((24, 8))
    assert almost(left, (0, 0, 255), tolerance=8)
    assert almost(right, RED, tolerance=8)

    half = Image.new("RGBA", (8, 8), (255, 0, 0, 128))
    blended = convert_for_output(half, OutputFormat.JPEG, WHITE)
    expected = Image.alpha_composite(Image.new("RGBA", (8, 8), (255, 255, 255, 255)), half)
    assert blended.getpixel((1, 1)) == expected.convert("RGB").getpixel((1, 1))


def test_png_and_webp_exports_keep_an_alpha_channel(tmp_path: Path) -> None:
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    image.paste(Image.new("RGBA", (32, 16), (255, 0, 0, 255)), (0, 16))
    preset = _preset("Same", 32, 32, "same")
    for output_format in (OutputFormat.PNG, OutputFormat.WEBP):
        summary = export_image(
            image,
            "alpha.png",
            (preset,),
            tmp_path / output_format.value,
            mode=ResizeMode.STRETCH,
            output_format=output_format,
            quality=95,
        )
        path = summary.succeeded[0].path
        assert path is not None
        with Image.open(path) as saved:
            assert saved.mode == "RGBA"
            assert saved.size == (32, 32)
            assert saved.getpixel((8, 4))[3] < 20
            bottom = saved.getpixel((8, 24))
            assert bottom[3] > 230
            assert almost(bottom, (255, 0, 0, 255), tolerance=20)


def test_jpeg_quality_changes_the_file_size(tmp_path: Path) -> None:
    noisy = Image.frombytes("RGB", (64, 64), os.urandom(64 * 64 * 3))
    preset = _preset("Same", 64, 64, "same")

    def write(quality: int) -> int:
        summary = export_image(
            noisy,
            "noise.png",
            (preset,),
            tmp_path / str(quality),
            mode=ResizeMode.STRETCH,
            output_format=OutputFormat.JPEG,
            quality=quality,
        )
        path = summary.succeeded[0].path
        assert path is not None
        return path.stat().st_size

    assert write(20) < write(95)


def test_smaller_output_does_not_warn_about_upscaling(tmp_path: Path) -> None:
    summary = export_image(
        Image.new("RGB", (100, 100), RED),
        "large.png",
        (_preset("Small", 10, 10, "small"),),
        tmp_path,
        mode=ResizeMode.CROP,
        output_format=OutputFormat.PNG,
    )
    assert summary.upscale_warning is None
    assert summary.succeeded[0].upscaled is False
    fit = export_image(
        Image.new("RGB", (8, 8), RED),
        "pad.png",
        (_preset("Wide", 16, 8, "wide"),),
        tmp_path,
        mode=ResizeMode.FIT,
        output_format=OutputFormat.PNG,
    )
    assert fit.upscale_warning is None


def test_progress_reports_each_preset_and_one_failure_does_not_stop_the_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import image_resizer.core.export_service as export_service

    real_render = export_service.render

    def flaky(image: Image.Image, target: object, mode: ResizeMode, **kwargs: object) -> object:
        if getattr(target, "width", None) == 5:
            raise ImageResizerError("conversion failed")
        return real_render(image, target, mode, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(export_service, "render", flaky)
    events: list[tuple[int, int]] = []
    summary = export_image(
        Image.new("RGB", (8, 8), RED),
        "batch.png",
        (_preset("Ok", 6, 6, "ok"), _preset("Bad", 5, 5, "bad")),
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
        progress=lambda done, total: events.append((done, total)),
    )
    assert events[0] == (0, 2)
    assert events[-1] == (2, 2)
    by_id = {item.preset_id: item for item in summary.files}
    assert by_id["ok"].ok
    assert by_id["ok"].path is not None and Image.open(by_id["ok"].path).size == (6, 6)
    assert by_id["bad"].error is not None
    assert "conversion failed" in by_id["bad"].error


def test_export_rejects_an_empty_selection_and_a_bad_destination(tmp_path: Path) -> None:
    image = Image.new("RGB", (4, 4), RED)
    with pytest.raises(ExportError):
        export_image(image, "a.jpg", [], tmp_path, mode=ResizeMode.FIT)
    with pytest.raises(ExportError):
        export_image(
            image,
            "a.jpg",
            (_preset("A", 4, 4, "a"),),
            tmp_path,
            mode=ResizeMode.FIT,
            quality=0,
        )
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x", encoding="utf-8")
    with pytest.raises(ExportError):
        export_image(
            image,
            "a.jpg",
            (_preset("A", 4, 4, "a"),),
            blocked,
            mode=ResizeMode.FIT,
        )


def test_unsafe_source_names_cannot_escape_the_destination(tmp_path: Path) -> None:
    summary = export_image(
        Image.new("RGB", (4, 4), RED),
        "../secret/product-photo.jpg",
        (_preset("A", 4, 4, "a"),),
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    assert summary.output_directory == tmp_path / "product-photo"
    reserved = export_image(
        Image.new("RGB", (4, 4), RED),
        "CON.jpg",
        (_preset("A", 4, 4, "a"),),
        tmp_path,
        mode=ResizeMode.STRETCH,
        output_format=OutputFormat.PNG,
    )
    assert reserved.output_directory.name == "_CON"


def test_default_quality_constant_is_90() -> None:
    from image_resizer.models.settings import DEFAULT_QUALITY

    assert DEFAULT_QUALITY == 90
