"""Drag-and-drop target for a single local image."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from image_resizer.services.image_loader import SUPPORTED_EXTENSIONS


def local_paths_from_mime(mime) -> list[str]:
    """Return local filesystem paths carried by a drop, ignoring remote URLs."""
    if mime is None or not mime.hasUrls():
        return []
    paths: list[str] = []
    for url in mime.urls():
        if url.isLocalFile():
            paths.append(url.toLocalFile())
    return paths


def first_supported_image(paths: list[str]) -> str | None:
    """Return the first path that has a supported image extension and is a file."""
    for path in paths:
        candidate = Path(path)
        if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
            return str(candidate)
    return None


class DropZone(QFrame):
    """Dashed target that accepts image files and offers a browse button."""

    browse_requested = Signal()
    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(132)

        self._title = QLabel("Drag an image here")
        self._title.setObjectName("heading")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint = QLabel("JPG, PNG, WEBP, BMP, or TIFF")
        self._hint.setObjectName("muted")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._browse = QPushButton("Browse image")
        self._browse.clicked.connect(self.browse_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        layout.addStretch(1)
        layout.addWidget(self._title)
        layout.addWidget(self._hint)
        layout.addWidget(self._browse, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

    def set_has_image(self, has_image: bool) -> None:
        if has_image:
            self._title.setText("Drop a new image to replace")
            self._browse.setText("Replace image")
        else:
            self._title.setText("Drag an image here")
            self._browse.setText("Browse image")

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            self._set_active(True)
            event.acceptProposedAction()
            return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: ANN001
        self._set_active(False)
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_active(False)
        paths = local_paths_from_mime(event.mimeData())
        self.paths_dropped.emit(paths)
        if paths or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def _set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
