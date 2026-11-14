"""Built-in and user-defined output presets."""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from image_resizer.core.errors import (
    BuiltinPresetError,
    InvalidPresetError,
    PresetNotFoundError,
)
from image_resizer.models.settings import MAX_IMAGE_DIMENSION
from image_resizer.paths import resource_path


PRESETS_FILENAME = "presets.json"
MAX_PRESET_NAME_LENGTH = 80
_USER_PRESET_VERSION = 1


def bundled_presets_path() -> Path:
    """Built-in preset catalog, including the copy inside a PyInstaller build."""
    return resource_path("default_presets.json")


def validate_preset_name(name: object) -> str:
    if not isinstance(name, str):
        raise InvalidPresetError("Preset name must be a string.")
    cleaned = name.strip()
    if not cleaned:
        raise InvalidPresetError("Preset name cannot be empty.")
    if len(cleaned) > MAX_PRESET_NAME_LENGTH:
        raise InvalidPresetError(
            f"Preset name cannot exceed {MAX_PRESET_NAME_LENGTH} characters."
        )
    if any(ord(character) < 32 for character in cleaned):
        raise InvalidPresetError("Preset name cannot contain control characters.")
    return cleaned


def validate_preset_dimensions(width: object, height: object) -> tuple[int, int]:
    checked: list[int] = []
    for label, value in (("Width", width), ("Height", height)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidPresetError(f"{label} must be an integer.")
        if value < 1:
            raise InvalidPresetError(f"{label} must be at least 1 pixel.")
        if value > MAX_IMAGE_DIMENSION:
            raise InvalidPresetError(
                f"{label} must be at most {MAX_IMAGE_DIMENSION} pixels."
            )
        checked.append(value)
    return checked[0], checked[1]


@dataclass(frozen=True, slots=True)
class Preset:
    """One named output size."""

    name: str
    width: int
    height: int
    builtin: bool = False
    id: str = ""

    def __post_init__(self) -> None:
        name = validate_preset_name(self.name)
        width, height = validate_preset_dimensions(self.width, self.height)
        if not isinstance(self.builtin, bool):
            raise InvalidPresetError("Preset builtin flag must be a boolean.")
        if not isinstance(self.id, str):
            raise InvalidPresetError("Preset id must be a string.")
        preset_id = self.id.strip() or uuid.uuid4().hex
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "id", preset_id)

    def aspect_label(self) -> str:
        divisor = math.gcd(self.width, self.height)
        return f"{self.width // divisor}:{self.height // divisor}"


def load_builtin_presets(path: Path | None = None) -> tuple[Preset, ...]:
    presets_path = bundled_presets_path() if path is None else Path(path)
    return _load_builtin_file(str(presets_path))


@lru_cache(maxsize=8)
def _load_builtin_file(path_str: str) -> tuple[Preset, ...]:
    path = Path(path_str)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidPresetError(f"Could not read built-in presets from {path}.") from exc
    entries = payload.get("presets") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise InvalidPresetError(f"Built-in preset file is invalid: {path}.")

    presets: list[Preset] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for entry in entries:
        preset = _builtin_preset(entry, path)
        if preset.id in seen_ids or preset.name.casefold() in seen_names:
            raise InvalidPresetError(f"Built-in presets contain a duplicate: {preset.name}.")
        seen_ids.add(preset.id)
        seen_names.add(preset.name.casefold())
        presets.append(preset)
    if not presets:
        raise InvalidPresetError("Built-in preset file does not define any presets.")
    return tuple(presets)


def _builtin_preset(entry: object, path: Path) -> Preset:
    if not isinstance(entry, dict):
        raise InvalidPresetError(f"Built-in preset file is invalid: {path}.")
    preset_id = entry.get("id")
    if not isinstance(preset_id, str) or not preset_id.strip():
        raise InvalidPresetError(f"A built-in preset is missing an id in {path}.")
    try:
        return Preset(
            name=entry.get("name", ""),
            width=entry.get("width"),
            height=entry.get("height"),
            builtin=True,
            id=preset_id,
        )
    except InvalidPresetError as exc:
        raise InvalidPresetError(f"{exc} ({path})") from exc


class PresetStore:
    """Built-in presets plus custom presets saved in a user-writable directory."""

    def __init__(self, user_dir: Path, defaults_path: Path | None = None) -> None:
        self.user_dir = Path(user_dir)
        self.warnings: list[str] = []
        self._builtin = load_builtin_presets(defaults_path)
        self._custom: list[Preset] = []
        self._load_custom()

    @property
    def presets_file(self) -> Path:
        return self.user_dir / PRESETS_FILENAME

    def builtin_presets(self) -> tuple[Preset, ...]:
        return self._builtin

    def custom_presets(self) -> tuple[Preset, ...]:
        return tuple(self._custom)

    def presets(self) -> tuple[Preset, ...]:
        return self._builtin + self.custom_presets()

    def get(self, preset_id: str) -> Preset | None:
        for preset in self.presets():
            if preset.id == preset_id:
                return preset
        return None

    def add_custom(self, name: str, width: int, height: int) -> Preset:
        cleaned = validate_preset_name(name)
        checked_width, checked_height = validate_preset_dimensions(width, height)
        self._ensure_unique_name(cleaned, ignore_id=None)
        preset = Preset(
            name=cleaned,
            width=checked_width,
            height=checked_height,
            builtin=False,
        )
        self._custom.append(preset)
        self._save_custom()
        return preset

    def update_custom(
        self,
        preset_id: str,
        *,
        name: str,
        width: int,
        height: int,
    ) -> Preset:
        index = self._require_custom(preset_id, "modified")
        cleaned = validate_preset_name(name)
        checked_width, checked_height = validate_preset_dimensions(width, height)
        self._ensure_unique_name(cleaned, ignore_id=preset_id)
        updated = Preset(
            name=cleaned,
            width=checked_width,
            height=checked_height,
            builtin=False,
            id=preset_id,
        )
        self._custom[index] = updated
        self._save_custom()
        return updated

    def delete_custom(self, preset_id: str) -> None:
        index = self._require_custom(preset_id, "deleted")
        del self._custom[index]
        self._save_custom()

    def _ensure_unique_name(self, name: str, ignore_id: str | None) -> None:
        key = name.casefold()
        for preset in self.presets():
            if preset.id == ignore_id:
                continue
            if preset.name.casefold() == key:
                raise InvalidPresetError(f"A preset named {preset.name!r} already exists.")

    def _require_custom(self, preset_id: str, action: str) -> int:
        if any(preset.id == preset_id for preset in self._builtin):
            raise BuiltinPresetError(f"Built-in presets cannot be {action}.")
        for index, preset in enumerate(self._custom):
            if preset.id == preset_id:
                return index
        raise PresetNotFoundError(f"Custom preset {preset_id!r} was not found.")

    def _load_custom(self) -> None:
        path = self.presets_file
        if not path.exists():
            return
        if not path.is_file():
            self.warnings.append(f"Custom preset path is not a file: {path}.")
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            backup = _quarantine(path)
            self.warnings.append(f"Ignored unreadable custom presets. Backup: {backup.name}.")
            return
        entries = payload.get("presets") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            backup = _quarantine(path)
            self.warnings.append(f"Ignored invalid custom presets. Backup: {backup.name}.")
            return

        builtin_ids = {preset.id for preset in self._builtin}
        seen_ids: set[str] = set()
        seen_names = {preset.name.casefold() for preset in self._builtin}
        loaded: list[Preset] = []
        for entry in entries:
            preset = _custom_preset_or_none(entry)
            if preset is None:
                self.warnings.append("Skipped a custom preset with invalid data.")
                continue
            if preset.id in builtin_ids or preset.id in seen_ids:
                self.warnings.append(f"Skipped custom preset with a duplicate id: {preset.id}.")
                continue
            if preset.name.casefold() in seen_names:
                self.warnings.append(f"Skipped custom preset with a duplicate name: {preset.name}.")
                continue
            seen_ids.add(preset.id)
            seen_names.add(preset.name.casefold())
            loaded.append(preset)
        self._custom = loaded

    def _save_custom(self) -> None:
        payload = {
            "version": _USER_PRESET_VERSION,
            "presets": [
                {
                    "id": preset.id,
                    "name": preset.name,
                    "width": preset.width,
                    "height": preset.height,
                }
                for preset in self._custom
            ],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        _atomic_write_text(self.presets_file, text)


def _custom_preset_or_none(entry: object) -> Preset | None:
    if not isinstance(entry, dict):
        return None
    preset_id = entry.get("id")
    if not isinstance(preset_id, str) or not preset_id.strip():
        return None
    try:
        return Preset(
            name=entry.get("name", ""),
            width=entry.get("width"),
            height=entry.get("height"),
            builtin=False,
            id=preset_id,
        )
    except InvalidPresetError:
        return None


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
