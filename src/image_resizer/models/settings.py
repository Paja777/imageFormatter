"""Options shared by the processing pipeline.

Preference persistence for theme, quality, and the last export folder
belongs to a later phase. Custom presets are stored separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


DEFAULT_QUALITY = 90
MAX_IMAGE_DIMENSION = 16_384


class ResizeMode(Enum):
    """How a source image is mapped onto a target size."""

    CROP = "crop"
    FIT = "fit"
    STRETCH = "stretch"


class OutputFormat(Enum):
    """Formats the exporter can write."""

    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"

    @property
    def extension(self) -> str:
        if self is OutputFormat.JPEG:
            return "jpg"
        return self.value

    @property
    def supports_alpha(self) -> bool:
        return self is not OutputFormat.JPEG


class CollisionPolicy(Enum):
    """What to do when an output filename is already taken."""

    RENAME = "rename"
    SKIP = "skip"
    OVERWRITE = "overwrite"


def _channel(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
        raise ValueError(f"{name} must be an integer from 0 to 255.")
    return value


@dataclass(frozen=True, slots=True)
class Color:
    """8-bit color, including an optional alpha channel."""

    red: int
    green: int
    blue: int
    alpha: int = 255

    def __post_init__(self) -> None:
        object.__setattr__(self, "red", _channel(self.red, "red"))
        object.__setattr__(self, "green", _channel(self.green, "green"))
        object.__setattr__(self, "blue", _channel(self.blue, "blue"))
        object.__setattr__(self, "alpha", _channel(self.alpha, "alpha"))

    def as_rgb(self) -> tuple[int, int, int]:
        return (self.red, self.green, self.blue)

    def as_rgba(self) -> tuple[int, int, int, int]:
        return (self.red, self.green, self.blue, self.alpha)


WHITE = Color(255, 255, 255)
BLACK = Color(0, 0, 0)
TRANSPARENT = Color(0, 0, 0, 0)
