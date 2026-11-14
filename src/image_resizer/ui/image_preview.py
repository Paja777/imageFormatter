"""Result preview that uses the same crop and fit geometry as export."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from image_resizer.core.crop_geometry import (
    Box,
    CropAnchor,
    Size,
    cover_crop_box,
    fit_placement,
    requires_upscale,
)
from image_resizer.core.export_service import STRETCH_WARNING
from image_resizer.core.presets import Preset
from image_resizer.models.settings import WHITE, Color, ResizeMode
from image_resizer.ui.crop_math import pan_crop_anchor, place_crop_anchor, source_delta_for_drag
from image_resizer.ui.paint import fit_rect, paint_checkerboard


_MODE_LABELS = {
    ResizeMode.CROP: "Crop",
    ResizeMode.FIT: "Fit",
    ResizeMode.STRETCH: "Stretch",
}


class CropCanvas(QWidget):
    """Zoom-to-fit preview. In crop mode the pointer moves the shared anchor."""

    anchor_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cropCanvas")
        self.setMinimumSize(280, 220)
        self.setMouseTracking(True)
        self._image: QImage | None = None
        self._source: Size | None = None
        self._target: Size | None = None
        self._mode = ResizeMode.CROP
        self._anchor = CropAnchor()
        self._background = WHITE
        self._flatten = False
        self._source_has_alpha = False
        self._dark = False
        self._interactive = True
        self._empty = "Drop an image to preview it here."
        self._dragging = False
        self._drag_minimap = False
        self._press_pos = QPointF()
        self._press_anchor = CropAnchor()
        self._press_box: Box | None = None
        self._result_rect = QRectF()
        self._minimap_bounds = QRectF()
        self._minimap_image = QRectF()

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._interactive = enabled
        if not enabled:
            self._dragging = False
        self.unsetCursor()

    def set_scene(
        self,
        *,
        image: QImage | None,
        source: Size | None,
        target: Size | None,
        mode: ResizeMode,
        anchor: CropAnchor,
        background: Color,
        flatten: bool,
        source_has_alpha: bool,
        dark: bool,
        empty: str,
    ) -> None:
        self._dragging = False
        self._image = image
        self._source = source
        self._target = target
        self._mode = mode
        self._anchor = anchor
        self._background = background
        self._flatten = flatten
        self._source_has_alpha = source_has_alpha
        self._dark = dark
        self._empty = empty
        self.update()

    def center_crop(self) -> None:
        if self._source is None or self._target is None:
            return
        self._anchor = CropAnchor()
        self.anchor_changed.emit(self._anchor)
        self.update()

    def anchor(self) -> CropAnchor:
        return self._anchor

    def paintEvent(self, event) -> None:  # noqa: ANN001
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        bounds = QRectF(self.rect().adjusted(12, 12, -12, -12))
        self._result_rect = QRectF()
        self._minimap_bounds = QRectF()
        self._minimap_image = QRectF()
        if not self._can_paint():
            painter.setPen(QColor("#94A3B8" if self._dark else "#64748B"))
            painter.drawText(bounds, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self._empty)
            painter.end()
            return
        assert self._image is not None
        assert self._source is not None
        assert self._target is not None
        self._paint_result(painter, bounds)
        if self._mode is ResizeMode.CROP:
            self._paint_minimap(painter)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if (
            not self._interactive
            or self._mode is not ResizeMode.CROP
            or not self._can_paint()
            or event.button() != Qt.MouseButton.LeftButton
        ):
            super().mousePressEvent(event)
            return
        position = event.position()
        if self._minimap_image.contains(position):
            self._dragging = True
            self._drag_minimap = True
            self._move_minimap(position)
            event.accept()
            return
        if self._result_rect.contains(position) and self._press_box_available():
            self._dragging = True
            self._drag_minimap = False
            self._press_pos = position
            self._press_anchor = self._anchor
            self._press_box = cover_crop_box(self._source, self._target, self._anchor)  # type: ignore[arg-type]
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        position = event.position()
        if self._dragging and self._drag_minimap:
            self._move_minimap(position)
            event.accept()
            return
        if self._dragging and self._press_box is not None and self._result_rect.width() > 0:
            delta_x, delta_y = source_delta_for_drag(
                self._press_box.width,
                self._press_box.height,
                self._result_rect.width(),
                self._result_rect.height(),
                position.x() - self._press_pos.x(),
                position.y() - self._press_pos.y(),
            )
            self._set_anchor(
                pan_crop_anchor(self._source, self._target, self._press_anchor, delta_x, delta_y)  # type: ignore[arg-type]
            )
            event.accept()
            return
        if (
            self._interactive
            and self._mode is ResizeMode.CROP
            and (self._result_rect.contains(position) or self._minimap_image.contains(position))
        ):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._drag_minimap = False
            self._press_box = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _can_paint(self) -> bool:
        return (
            self._image is not None
            and not self._image.isNull()
            and self._source is not None
            and self._target is not None
        )

    def _press_box_available(self) -> bool:
        return self._source is not None and self._target is not None

    def _set_anchor(self, anchor: CropAnchor) -> None:
        if anchor == self._anchor:
            return
        self._anchor = anchor
        self.anchor_changed.emit(anchor)
        self.update()

    def _move_minimap(self, position: QPointF) -> None:
        if self._source is None or self._target is None or self._minimap_image.width() <= 0:
            return
        relative_x = (position.x() - self._minimap_image.left()) / self._minimap_image.width()
        relative_y = (position.y() - self._minimap_image.top()) / self._minimap_image.height()
        relative_x = min(1.0, max(0.0, relative_x))
        relative_y = min(1.0, max(0.0, relative_y))
        self._set_anchor(
            place_crop_anchor(
                self._source,
                self._target,
                relative_x * self._source.width,
                relative_y * self._source.height,
            )
        )

    def _paint_result(self, painter: QPainter, bounds: QRectF) -> None:
        assert self._image is not None
        assert self._source is not None
        assert self._target is not None
        if self._mode is ResizeMode.CROP:
            box = cover_crop_box(self._source, self._target, self._anchor)
            dest = fit_rect(bounds, float(box.width), float(box.height))
        else:
            box = None
            dest = fit_rect(bounds, float(self._target.width), float(self._target.height))
        self._result_rect = dest
        path = QPainterPath()
        path.addRoundedRect(dest, 8, 8)
        painter.save()
        painter.setClipPath(path)
        self._fill_backdrop(painter, dest)
        if self._mode is ResizeMode.CROP and box is not None:
            scale_x = self._image.width() / self._source.width
            scale_y = self._image.height() / self._source.height
            source_rect = QRectF(
                box.left * scale_x,
                box.top * scale_y,
                box.width * scale_x,
                box.height * scale_y,
            )
            painter.drawImage(dest, self._image, source_rect)
        elif self._mode is ResizeMode.FIT:
            placed = fit_placement(self._source, self._target)
            scale_x = dest.width() / self._target.width
            scale_y = dest.height() / self._target.height
            content = QRectF(
                dest.left() + placed.x * scale_x,
                dest.top() + placed.y * scale_y,
                placed.content.width * scale_x,
                placed.content.height * scale_y,
            )
            painter.drawImage(content, self._image)
        else:
            painter.drawImage(dest, self._image)
        painter.restore()
        pen = QPen(QColor("#1362F8") if self._mode is ResizeMode.CROP else QColor("#94A3B8"))
        pen.setWidthF(1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _fill_backdrop(self, painter: QPainter, dest: QRectF) -> None:
        if self._flatten:
            painter.fillRect(dest, QColor(255, 255, 255))
            if self._background.alpha != 255:
                painter.fillRect(dest, QColor(*self._background.as_rgba()))
            return
        needs_grid = self._mode is ResizeMode.FIT or self._source_has_alpha
        if needs_grid and (self._mode is not ResizeMode.FIT or self._background.alpha != 255):
            paint_checkerboard(painter, dest, dark=self._dark)
        if self._mode is ResizeMode.FIT and self._background.alpha:
            painter.fillRect(dest, QColor(*self._background.as_rgba()))

    def _paint_minimap(self, painter: QPainter) -> None:
        if self._source is None or self._image is None or self._target is None:
            return
        bounds = self._minimap_bounds_for(QRectF(self.rect().adjusted(8, 8, -8, -8)))
        if bounds is None:
            return
        self._minimap_bounds = bounds
        image_rect = fit_rect(
            bounds.adjusted(6, 6, -6, -6),
            float(self._source.width),
            float(self._source.height),
        )
        self._minimap_image = image_rect
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(12, 23, 35, 170))
        painter.drawRoundedRect(bounds, 8, 8)
        painter.drawImage(image_rect, self._image)
        box = cover_crop_box(self._source, self._target, self._anchor)  # type: ignore[arg-type]
        crop = QRectF(
            image_rect.left() + (box.left / self._source.width) * image_rect.width(),
            image_rect.top() + (box.top / self._source.height) * image_rect.height(),
            (box.width / self._source.width) * image_rect.width(),
            (box.height / self._source.height) * image_rect.height(),
        )
        shade = QPainterPath()
        shade.setFillRule(Qt.FillRule.OddEvenFill)
        shade.addRect(image_rect)
        shade.addRect(crop)
        painter.setBrush(QColor(15, 23, 42, 120))
        painter.drawPath(shade)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#1362F8"), 1.5))
        painter.drawRect(crop)
        painter.restore()

    def _minimap_bounds_for(self, area: QRectF) -> QRectF | None:
        width = 116.0
        height = 84.0
        gap = 8.0
        dest = self._result_rect
        candidates = (
            QRectF(dest.right() + gap, dest.center().y() - height / 2, width, height),
            QRectF(dest.left() - gap - width, dest.center().y() - height / 2, width, height),
            QRectF(area.right() - width, area.bottom() - height, width, height),
        )
        for candidate in candidates:
            if area.contains(candidate) and not dest.intersects(candidate.adjusted(1, 1, -1, -1)):
                return candidate
        overlay = QRectF(dest.right() - width - 12, dest.bottom() - height - 12, width, height)
        if dest.width() >= 220 and dest.height() >= 160 and dest.contains(overlay):
            return overlay
        return None


class PreviewPanel(QFrame):
    """Preview header, preset switcher, and the crop canvas."""

    preview_requested = Signal(str)
    anchor_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(320)

        heading = QLabel("Preview")
        heading.setObjectName("heading")
        self._chooser = QComboBox()
        self._chooser.setObjectName("previewPreset")
        self._chooser.currentIndexChanged.connect(self._on_choice)
        self._center = QPushButton("Center crop")
        self._center.clicked.connect(self._on_center)
        self._details = QLabel("Select a preset to preview its output size.")
        self._details.setObjectName("previewDetails")
        self._details.setWordWrap(True)
        self._notice = QLabel("")
        self._notice.setObjectName("warning")
        self._notice.setWordWrap(True)
        self._canvas = CropCanvas()
        self._canvas.anchor_changed.connect(self.anchor_changed.emit)
        self._hint = QLabel("The preview is scaled to fit. Export uses the full selected size.")
        self._hint.setObjectName("hint")
        self._hint.setWordWrap(True)

        header = QHBoxLayout()
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self._center)
        chooser_row = QHBoxLayout()
        chooser_label = QLabel("Showing")
        chooser_label.setObjectName("muted")
        chooser_row.addWidget(chooser_label)
        chooser_row.addWidget(self._chooser, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(chooser_row)
        layout.addWidget(self._details)
        layout.addWidget(self._notice)
        layout.addWidget(self._canvas, stretch=1)
        layout.addWidget(self._hint)

    def set_interaction_enabled(self, enabled: bool) -> None:
        self._canvas.set_interaction_enabled(enabled)
        self._center.setEnabled(enabled)
        self._chooser.setEnabled(enabled and self._chooser.count() > 0)

    def set_scene(
        self,
        *,
        image: QImage | None,
        source: Size | None,
        preset: Preset | None,
        choices: Sequence[Preset],
        mode: ResizeMode,
        anchor: CropAnchor,
        background: Color,
        flatten_alpha: bool,
        source_has_alpha: bool,
        dark: bool,
    ) -> None:
        self._fill_choices(choices, preset)
        target = Size(preset.width, preset.height) if preset is not None else None
        if image is None or source is None:
            empty = "Drop an image to preview it here."
        elif preset is None:
            empty = "Select a preset to preview this size."
        else:
            empty = ""
        self._canvas.set_scene(
            image=image,
            source=source,
            target=target,
            mode=mode,
            anchor=anchor,
            background=background,
            flatten=flatten_alpha,
            source_has_alpha=source_has_alpha,
            dark=dark,
            empty=empty,
        )
        self._details.setText(_details_text(preset, mode))
        notice = _notice_text(
            source,
            target,
            mode,
            background,
            flatten_alpha,
            source_has_alpha,
        )
        self._notice.setText(notice)
        self._notice.setVisible(bool(notice))
        self._hint.setText(_hint_text(mode, preset is not None and image is not None))
        can_center = (
            mode is ResizeMode.CROP and image is not None and preset is not None and source is not None
        )
        self._center.setVisible(can_center)

    def _fill_choices(self, choices: Sequence[Preset], preset: Preset | None) -> None:
        self._chooser.blockSignals(True)
        self._chooser.clear()
        seen: set[str] = set()
        for item in choices:
            self._chooser.addItem(f"{item.name}  ·  {item.width}×{item.height}", item.id)
            seen.add(item.id)
        if preset is not None and preset.id not in seen:
            self._chooser.addItem(f"{preset.name}  ·  preview only", preset.id)
        if preset is not None:
            index = self._chooser.findData(preset.id)
            if index >= 0:
                self._chooser.setCurrentIndex(index)
        self._chooser.setEnabled(self._chooser.count() > 0)
        self._chooser.blockSignals(False)

    def _on_choice(self, index: int) -> None:
        preset_id = self._chooser.itemData(index)
        if isinstance(preset_id, str):
            self.preview_requested.emit(preset_id)

    def _on_center(self) -> None:
        self._canvas.center_crop()


def _details_text(preset: Preset | None, mode: ResizeMode) -> str:
    if preset is None:
        return "Select a preset to preview its output size."
    return (
        f"{_MODE_LABELS[mode]} · export {preset.width} × {preset.height} · {preset.aspect_label()}"
    )


def _notice_text(
    source: Size | None,
    target: Size | None,
    mode: ResizeMode,
    background: Color,
    flatten_alpha: bool,
    has_alpha: bool,
) -> str:
    notes: list[str] = []
    if mode is ResizeMode.STRETCH:
        notes.append(STRETCH_WARNING)
    if source is not None and target is not None and requires_upscale(source, target, mode):
        notes.append("This output is larger than the photo and will be upscaled.")
    if flatten_alpha and (has_alpha or background.alpha != 255):
        if background.alpha == 255:
            notes.append("JPEG cannot keep transparency. Transparent areas use the background color.")
        else:
            notes.append("JPEG cannot keep transparency. Transparent areas are flattened onto white.")
    return "\n".join(notes)


def _hint_text(mode: ResizeMode, ready: bool) -> str:
    if not ready:
        return "The preview is scaled to fit. Export uses the full selected size."
    if mode is ResizeMode.CROP:
        return "Drag the preview to move the crop. The frame stays inside the photo. Export uses this position."
    if mode is ResizeMode.FIT:
        return "The whole photo is kept. Empty space uses the background color."
    return "Stretching ignores the original proportions. Export uses the full selected size."
