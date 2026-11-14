"""Left panel: drop target, original preview, and file facts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from image_resizer.services.image_loader import ImageMetadata
from image_resizer.ui.drop_zone import DropZone
from image_resizer.ui.images import format_file_size
from image_resizer.ui.paint import fit_rect


class FittedImage(QWidget):
    """Draw one image scaled to fit, without changing the source pixels."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image: QImage | None) -> None:
        self._image = image
        self.update()

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        if self._image is None or self._image.isNull():
            painter.end()
            return
        bounds = QRectF(self.rect().adjusted(4, 4, -4, -4))
        target = fit_rect(bounds, float(self._image.width()), float(self._image.height()))
        painter.drawImage(target, self._image)
        painter.end()


class SourcePanel(QFrame):
    """Image input: drag-and-drop, browse, preview, and metadata."""

    browse_requested = Signal()
    paths_dropped = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(280)
        self._full_name = ""

        self._drop = DropZone()
        self._drop.browse_requested.connect(self.browse_requested.emit)
        self._drop.paths_dropped.connect(self.paths_dropped.emit)
        self._view = FittedImage()
        self._view.setObjectName("sourcePreview")
        self._filename = QLabel("No image loaded")
        self._filename.setObjectName("sourceFilename")
        self._dimensions = QLabel("")
        self._dimensions.setObjectName("sourceDimensions")
        self._file_info = QLabel("JPG, PNG, WEBP, BMP, or TIFF")
        self._file_info.setObjectName("muted")
        self._file_info.setWordWrap(True)
        self._notes = QLabel("")
        self._notes.setObjectName("sourceNotes")
        self._notes.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(self._drop)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(self._filename)
        layout.addWidget(self._dimensions)
        layout.addWidget(self._file_info)
        layout.addWidget(self._notes)

    def set_image(self, metadata: ImageMetadata | None, image: QImage | None) -> None:
        self._view.set_image(image)
        self._drop.set_has_image(metadata is not None)
        if metadata is None:
            self._full_name = ""
            self._filename.setText("No image loaded")
            self._filename.setToolTip("")
            self._dimensions.setText("")
            self._dimensions.setVisible(False)
            self._file_info.setText("JPG, PNG, WEBP, BMP, or TIFF")
            self._notes.setText("")
            self._notes.setVisible(False)
            return
        self._full_name = metadata.filename
        self._filename.setToolTip(metadata.filename)
        self._apply_filename()
        self._dimensions.setText(f"{metadata.width} × {metadata.height}")
        self._dimensions.setVisible(True)
        self._file_info.setText(
            f"{metadata.format} · {metadata.mode} · {format_file_size(metadata.file_size)}"
        )
        notes: list[str] = []
        if metadata.had_exif_orientation:
            notes.append("Orientation was corrected from the photo metadata.")
        if metadata.large_image_warning:
            notes.append(
                "This image is very large. The preview is reduced; export still uses the full photo."
            )
        self._notes.setText(" ".join(notes))
        self._notes.setVisible(bool(notes))

    def set_busy(self, busy: bool) -> None:
        self._drop.setEnabled(not busy)

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        self._apply_filename()

    def _apply_filename(self) -> None:
        if not self._full_name:
            return
        width = max(40, self._filename.width())
        self._filename.setText(
            self._filename.fontMetrics().elidedText(
                self._full_name,
                Qt.TextElideMode.ElideMiddle,
                width,
            )
        )
