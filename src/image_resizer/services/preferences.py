"""User preferences stored beside custom presets.

The file lives in the per-user data directory. A broken file is moved
aside and replaced by defaults so a bad save cannot stop the next launch.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from image_resizer.models.settings import (
    DEFAULT_QUALITY,
    WHITE,
    CollisionPolicy,
    Color,
    OutputFormat,
    ResizeMode,
)
from image_resizer.services.config_service import user_data_dir


PREFERENCES_FILENAME = "preferences.json"
_VERSION = 1
_THEMES = frozenset({"light", "dark"})


def default_export_directory() -> str:
    """A writable folder to suggest before the user has chosen one."""
    pictures = Path.home() / "Pictures"
    if pictures.is_dir():
        return str(pictures)
    return str(Path.home())


@dataclass(frozen=True, slots=True)
class Preferences:
    """Values the window can restore on the next launch."""

    export_directory: str = ""
    output_format: OutputFormat = OutputFormat.JPEG
    quality: int = DEFAULT_QUALITY
    theme: str = "light"
    resize_mode: ResizeMode = ResizeMode.CROP
    background: Color = WHITE
    collision_policy: CollisionPolicy = CollisionPolicy.RENAME

    def __post_init__(self) -> None:
        if not isinstance(self.export_directory, str) or "\x00" in self.export_directory:
            raise ValueError("Export directory must be a string.")
        if not isinstance(self.output_format, OutputFormat):
            raise ValueError("Unsupported output format.")
        if isinstance(self.quality, bool) or not isinstance(self.quality, int) or not 1 <= self.quality <= 100:
            raise ValueError("Quality must be an integer from 1 to 100.")
        if self.theme not in _THEMES:
            raise ValueError("Theme must be light or dark.")
        if not isinstance(self.resize_mode, ResizeMode):
            raise ValueError("Unsupported resize mode.")
        if not isinstance(self.background, Color):
            raise ValueError("Background must be a color.")
        if not isinstance(self.collision_policy, CollisionPolicy):
            raise ValueError("Unsupported filename collision policy.")


class PreferencesStore:
    """Load and save ``preferences.json`` in a user-writable directory."""

    def __init__(self, user_dir: Path) -> None:
        self.user_dir = Path(user_dir)
        self.warnings: list[str] = []
        self._preferences = self._load()

    @property
    def path(self) -> Path:
        return self.user_dir / PREFERENCES_FILENAME

    def get(self) -> Preferences:
        return self._preferences

    def update(self, preferences: Preferences) -> None:
        if not isinstance(preferences, Preferences):
            raise ValueError("Preferences are required.")
        self._preferences = preferences
        self._save()

    def _load(self) -> Preferences:
        path = self.path
        if not path.exists():
            return Preferences()
        if not path.is_file():
            self.warnings.append(f"Preferences path is not a file: {path}.")
            return Preferences()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            backup = _quarantine(path)
            self.warnings.append(f"Ignored unreadable preferences. Backup: {backup.name}.")
            return Preferences()
        if not isinstance(payload, dict):
            backup = _quarantine(path)
            self.warnings.append(f"Ignored invalid preferences. Backup: {backup.name}.")
            return Preferences()
        return _preferences_from_payload(payload, self.warnings)

    def _save(self) -> None:
        prefs = self._preferences
        payload = {
            "version": _VERSION,
            "export_directory": prefs.export_directory,
            "output_format": prefs.output_format.value,
            "quality": prefs.quality,
            "theme": prefs.theme,
            "resize_mode": prefs.resize_mode.value,
            "background": list(prefs.background.as_rgba()),
            "collision_policy": prefs.collision_policy.value,
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        _atomic_write_text(self.path, text)


def open_preferences(user_dir: Path | None = None) -> PreferencesStore:
    """Open preferences for ``user_dir`` or the platform user-data directory."""
    return PreferencesStore(user_dir if user_dir is not None else user_data_dir())


def _preferences_from_payload(payload: dict[str, object], warnings: list[str]) -> Preferences:
    export_directory = payload.get("export_directory", "")
    if not isinstance(export_directory, str) or "\x00" in export_directory:
        warnings.append("Ignored an invalid export directory.")
        export_directory = ""

    output_format = _enum_value(
        OutputFormat,
        payload.get("output_format", OutputFormat.JPEG.value),
        OutputFormat.JPEG,
        warnings,
        "output format",
    )
    resize_mode = _enum_value(
        ResizeMode,
        payload.get("resize_mode", ResizeMode.CROP.value),
        ResizeMode.CROP,
        warnings,
        "resize mode",
    )
    collision_policy = _enum_value(
        CollisionPolicy,
        payload.get("collision_policy", CollisionPolicy.RENAME.value),
        CollisionPolicy.RENAME,
        warnings,
        "filename collision policy",
    )

    quality = payload.get("quality", DEFAULT_QUALITY)
    if isinstance(quality, bool) or not isinstance(quality, int) or not 1 <= quality <= 100:
        warnings.append("Ignored an invalid quality setting.")
        quality = DEFAULT_QUALITY

    theme = payload.get("theme", "light")
    if theme not in _THEMES:
        warnings.append("Ignored an invalid theme.")
        theme = "light"

    background = _color_value(payload.get("background", [255, 255, 255, 255]), warnings)
    return Preferences(
        export_directory=export_directory,
        output_format=output_format,
        quality=quality,
        theme=theme,
        resize_mode=resize_mode,
        background=background,
        collision_policy=collision_policy,
    )


def _enum_value(enum_cls: type, value: object, default: object, warnings: list[str], label: str):
    if isinstance(value, str):
        try:
            return enum_cls(value)
        except ValueError:
            pass
    warnings.append(f"Ignored an invalid {label}.")
    return default


def _color_value(value: object, warnings: list[str]) -> Color:
    if isinstance(value, list) and len(value) in {3, 4} and all(isinstance(channel, int) and not isinstance(channel, bool) for channel in value):
        alpha = 255 if len(value) == 3 else value[3]
        try:
            return Color(value[0], value[1], value[2], alpha)
        except ValueError:
            pass
    warnings.append("Ignored an invalid background color.")
    return WHITE


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _quarantine(path: Path) -> Path:
    candidate = path.with_name(path.name + ".invalid")
    index = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.invalid-{index}")
        index += 1
    path.replace(candidate)
    return candidate
