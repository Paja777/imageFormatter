"""Preference defaults, partial recovery, and persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from image_resizer.models.settings import DEFAULT_QUALITY, CollisionPolicy, OutputFormat, ResizeMode
from image_resizer.services.preferences import Preferences, PreferencesStore, open_preferences


def test_preferences_round_trip(tmp_path: Path) -> None:
    store = PreferencesStore(tmp_path)
    assert store.get().quality == DEFAULT_QUALITY
    assert store.get().theme == "light"
    assert not store.path.exists()

    store.update(
        Preferences(
            export_directory=str(tmp_path / "out"),
            output_format=OutputFormat.PNG,
            quality=75,
            theme="dark",
            resize_mode=ResizeMode.FIT,
            background=store.get().background.__class__(10, 20, 30, 0),
            collision_policy=CollisionPolicy.SKIP,
        )
    )
    reloaded = PreferencesStore(tmp_path).get()
    assert reloaded.export_directory == str(tmp_path / "out")
    assert reloaded.output_format is OutputFormat.PNG
    assert reloaded.quality == 75
    assert reloaded.theme == "dark"
    assert reloaded.resize_mode is ResizeMode.FIT
    assert reloaded.background.as_rgba() == (10, 20, 30, 0)
    assert reloaded.collision_policy is CollisionPolicy.SKIP


def test_invalid_fields_fall_back_without_dropping_the_rest(tmp_path: Path) -> None:
    payload = {
        "version": 1,
        "export_directory": str(tmp_path),
        "output_format": "gif",
        "quality": 0,
        "theme": "neon",
        "resize_mode": "crop",
        "background": [0, 0, 0],
        "collision_policy": "rename",
    }
    (tmp_path / "preferences.json").write_text(json.dumps(payload), encoding="utf-8")
    store = PreferencesStore(tmp_path)
    prefs = store.get()
    assert prefs.export_directory == str(tmp_path)
    assert prefs.output_format is OutputFormat.JPEG
    assert prefs.quality == DEFAULT_QUALITY
    assert prefs.theme == "light"
    assert prefs.resize_mode is ResizeMode.CROP
    assert prefs.background.as_rgb() == (0, 0, 0)
    assert prefs.collision_policy is CollisionPolicy.RENAME
    assert store.warnings
    assert (tmp_path / "preferences.json").is_file()


def test_unreadable_preferences_are_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "preferences.json"
    path.write_text("{", encoding="utf-8")
    store = PreferencesStore(tmp_path)
    assert store.get().theme == "light"
    assert store.warnings
    assert not path.exists()
    assert list(tmp_path.glob("preferences.json.invalid*"))
    store.update(Preferences(theme="dark"))
    assert PreferencesStore(tmp_path).get().theme == "dark"


def test_open_preferences_uses_the_user_data_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    store = open_preferences()
    store.update(Preferences(quality=81))
    assert (tmp_path / "ImageResizer" / "preferences.json").is_file()
    assert open_preferences().get().quality == 81
