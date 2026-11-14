"""Preview copies and Qt image buffers.

The on-screen copy is only for display. Crop anchors stay in the
coordinate space of the full decoded image, which export still uses.
"""

from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage


PREVIEW_MAX_EDGE = 1600


def format_file_size(size: int) -> str:
    """Format a byte count for the source panel."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def build_preview(image: Image.Image, max_edge: int = PREVIEW_MAX_EDGE) -> Image.Image:
    """Return a LANCZOS copy whose longest side is at most ``max_edge``."""
    width, height = image.size
    longest = max(width, height)
    if longest <= max_edge:
        return image.copy()
    scale = max_edge / longest
    preview_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(preview_size, Image.Resampling.LANCZOS)


def pil_to_qimage(image: Image.Image) -> QImage:
    """Copy Pillow pixels into a ``QImage`` the painter can keep."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    raw = image.tobytes("raw", "RGBA")
    qimage = QImage(image.width, image.height, QImage.Format.Format_RGBA8888)
    if qimage.isNull():
        return qimage
    buffer = qimage.bits()
    buffer[: len(raw)] = raw
    return qimage
