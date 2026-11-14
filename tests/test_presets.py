"""Built-in presets, validation, and custom preset persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from image_resizer.core.errors import BuiltinPresetError, InvalidPresetError, PresetNotFoundError
from image_resizer.core.presets import PresetStore, load_builtin_presets
from image_resizer.models.settings import MAX_IMAGE_DIMENSION
from image_resizer.services.config_service import open_preset_store, user_data_dir


EXPECTED_PRESETS = (
    ("full-hd", "Full HD", 1920, 1080, "16:9"),
    ("hd", "HD", 1280, 720, "16:9"),
    ("square", "Square", 1080, 1080, "1:1"),
    ("portrait", "Portrait", 1080, 1350, "4:5"),
    ("story-reel", "Story / Reel", 1080, 1920, "9:16"),
    ("web-banner", "Web Banner", 1200, 628, "300:157"),
    ("website-hero", "Website Hero", 1920, 600, "16:5"),
    ("thumbnail", "Thumbnail", 400, 400, "1:1"),
    ("small-thumbnail", "Small Thumbnail", 150, 150, "1:1"),
)


def test_builtin_presets_match_the_shipped_catalog() -> None:
    presets = load_builtin_presets()
    assert len(presets) == len(EXPECTED_PRESETS)
    for preset, expected in zip(presets, EXPECTED_PRESETS, strict=True):
        preset_id, name, width, height, aspect = expected
        assert preset.id == preset_id
        assert preset.name == name
        assert preset.width == width
        assert preset.height == height
        assert preset.builtin is True
        assert preset.aspect_label() == aspect


def test_invalid_dimensions_and_names_are_rejected(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    invalid_sizes = (
        (0, 10),
        (10, 0),
        (-5, 10),
        (10, -1),
        (MAX_IMAGE_DIMENSION + 1, 10),
        (10, MAX_IMAGE_DIMENSION + 1),
    )
    for width, height in invalid_sizes:
        with pytest.raises(InvalidPresetError):
            store.add_custom("Banner", width, height)
    for name in ("", "   ", "x" * 81, "bad\nname"):
        with pytest.raises(InvalidPresetError):
            store.add_custom(name, 10, 10)
    with pytest.raises(InvalidPresetError):
        store.add_custom("Banner", True, 10)  # type: ignore[arg-type]
    with pytest.raises(InvalidPresetError):
        store.add_custom("Banner", 10.5, 10)  # type: ignore[arg-type]
    with pytest.raises(InvalidPresetError):
        store.add_custom("Full HD", 32, 32)
    with pytest.raises(InvalidPresetError):
        store.add_custom("full hd", 32, 32)
    assert store.custom_presets() == ()
    assert not store.presets_file.exists()


def test_custom_presets_persist_across_store_instances(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    created = store.add_custom("  Široki kadar  ", 800, 200)
    assert created.name == "Široki kadar"
    assert created.builtin is False

    reloaded = PresetStore(tmp_path)
    found = reloaded.get(created.id)
    assert found is not None
    assert (found.name, found.width, found.height, found.builtin) == ("Široki kadar", 800, 200, False)
    saved = json.loads(store.presets_file.read_text(encoding="utf-8"))
    assert saved["version"] == 1
    assert saved["presets"] == [
        {"id": created.id, "name": "Široki kadar", "width": 800, "height": 200}
    ]
    assert "Full HD" not in store.presets_file.read_text(encoding="utf-8")

    updated = reloaded.update_custom(created.id, name="Uži kadar", width=640, height=200)
    assert updated.id == created.id
    third = PresetStore(tmp_path)
    assert third.get(created.id) is not None
    assert (third.get(created.id).name, third.get(created.id).width) == ("Uži kadar", 640)  # type: ignore[union-attr]

    with pytest.raises(InvalidPresetError):
        third.update_custom(created.id, name="Square", width=20, height=20)
    third.delete_custom(created.id)
    assert PresetStore(tmp_path).get(created.id) is None
    assert PresetStore(tmp_path).custom_presets() == ()


def test_builtin_presets_cannot_be_edited_or_deleted(tmp_path: Path) -> None:
    store = PresetStore(tmp_path)
    builtin = store.builtin_presets()[0]
    with pytest.raises(BuiltinPresetError):
        store.delete_custom(builtin.id)
    with pytest.raises(BuiltinPresetError):
        store.update_custom(builtin.id, name="Renamed", width=10, height=10)
    with pytest.raises(PresetNotFoundError):
        store.delete_custom("missing-id")
    assert store.get(builtin.id) == builtin
    assert not store.presets_file.exists()


def test_unreadable_custom_preset_file_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "presets.json"
    path.write_text("{", encoding="utf-8")
    store = PresetStore(tmp_path)
    assert store.custom_presets() == ()
    assert store.warnings
    assert not path.exists()
    assert list(tmp_path.glob("presets.json.invalid*"))
    store.add_custom("Recovered", 16, 16)
    assert PresetStore(tmp_path).custom_presets()[0].name == "Recovered"


def test_invalid_custom_entries_are_skipped_without_dropping_valid_ones(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "presets": [
            {"id": "ok", "name": "Ok", "width": 12, "height": 8},
            {"id": "bad", "name": "Bad", "width": 0, "height": 8},
            {"name": "Missing id", "width": 4, "height": 4},
            {"id": "full-hd", "name": "Custom Full", "width": 10, "height": 10},
            {"id": "dup-name", "name": "full hd", "width": 10, "height": 10},
        ],
    }
    (tmp_path / "presets.json").write_text(json.dumps(payload), encoding="utf-8")
    store = PresetStore(tmp_path)
    assert [preset.id for preset in store.custom_presets()] == ["ok"]
    assert store.warnings
    assert "bad" in (tmp_path / "presets.json").read_text(encoding="utf-8")


def test_user_data_directory_follows_the_platform(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert user_data_dir() == tmp_path / "Roaming" / "ImageResizer"

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert user_data_dir() == tmp_path / "xdg" / "ImageResizer"

    monkeypatch.setattr(sys, "platform", "darwin")

    def home(cls: type[Path]) -> Path:
        return tmp_path / "mac-home"

    monkeypatch.setattr(Path, "home", classmethod(home))
    assert user_data_dir() == tmp_path / "mac-home" / "Library" / "Application Support" / "ImageResizer"


def test_open_preset_store_writes_under_the_user_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = open_preset_store()
    created = store.add_custom("Mine", 20, 30)
    assert (tmp_path / "ImageResizer" / "presets.json").is_file()
    reopened = open_preset_store()
    assert reopened.get(created.id) is not None
    assert reopened.get(created.id).width == 20  # type: ignore[union-attr]
