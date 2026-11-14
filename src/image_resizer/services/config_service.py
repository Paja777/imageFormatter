"""Locations for per-user data.

Custom presets and, later, preferences live here so a normal account can
write them without administrator rights. On Windows that directory is
``%APPDATA%/ImageResizer``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from image_resizer.core.presets import PresetStore


APP_NAME = "ImageResizer"


def user_data_dir() -> Path:
    """Return the per-user configuration directory for this application."""
    if sys.platform == "win32":
        root = os.environ.get("APPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Roaming"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        root = os.environ.get("XDG_DATA_HOME")
        base = Path(root) if root else Path.home() / ".local" / "share"
    return base / APP_NAME


def open_preset_store(user_dir: Path | None = None) -> PresetStore:
    """Open the preset store for ``user_dir`` or the platform user-data directory."""
    return PresetStore(user_dir if user_dir is not None else user_data_dir())
