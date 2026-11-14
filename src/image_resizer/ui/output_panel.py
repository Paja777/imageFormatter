"""Right panel: presets, resize options, and export."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from image_resizer.core.export_service import STRETCH_WARNING
from image_resizer.core.presets import Preset
from image_resizer.models.settings import (
    DEFAULT_QUALITY,
    WHITE,
    CollisionPolicy,
    Color,
    OutputFormat,
    ResizeMode,
)
from image_resizer.services.preferences import Preferences
from image_resizer.ui.dialogs import open_in_file_manager
from image_resizer.ui.preset_selector import PresetSelector


@dataclass(frozen=True, slots=True)
class ExportSettings:
    """The output choices currently shown in the panel."""

    mode: ResizeMode
    output_format: OutputFormat
    quality: int
    background: Color
    collision_policy: CollisionPolicy
    directory: str


class OutputPanel(QFrame):
    """Preset selection and the controls that define an export."""

    values_changed = Signal()
    commit_changed = Signal()
    export_requested = Signal()
    cancel_requested = Signal()
    add_preset_requested = Signal()
    edit_preset_requested = Signal()
    delete_preset_requested = Signal()
    check_changed = Signal(str, bool)
    preview_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(300)
        self._applying = False
        self._busy = False
        self._background = WHITE
        self._source_has_alpha = False
        self._output_folder: str | None = None

        heading = QLabel("Output")
        heading.setObjectName("heading")
        self._selector = PresetSelector()
        self._selector.check_changed.connect(self.check_changed.emit)
        self._selector.preview_requested.connect(self.preview_requested.emit)

        self._add = QPushButton("New preset")
        self._add.setObjectName("newPreset")
        self._edit = QPushButton("Edit")
        self._edit.setObjectName("editPreset")
        self._delete = QPushButton("Delete")
        self._delete.setObjectName("deletePreset")
        self._add.clicked.connect(self.add_preset_requested.emit)
        self._edit.clicked.connect(self.edit_preset_requested.emit)
        self._delete.clicked.connect(self.delete_preset_requested.emit)
        self._edit.setEnabled(False)
        self._delete.setEnabled(False)
        self._edit.setToolTip("Built-in presets cannot be edited.")
        self._delete.setToolTip("Built-in presets cannot be deleted.")

        preset_buttons = QHBoxLayout()
        preset_buttons.addWidget(self._add)
        preset_buttons.addWidget(self._edit)
        preset_buttons.addWidget(self._delete)

        self._crop = QRadioButton("Crop — fill the frame")
        self._fit = QRadioButton("Fit — keep the whole image")
        self._stretch = QRadioButton("Stretch — exact size, may distort")
        self._crop.setChecked(True)
        self._modes = QButtonGroup(self)
        self._modes.addButton(self._crop)
        self._modes.addButton(self._fit)
        self._modes.addButton(self._stretch)
        self._crop.toggled.connect(self._on_crop_toggled)
        self._fit.toggled.connect(self._on_mode_toggled)
        self._stretch.toggled.connect(self._on_mode_toggled)
        self._stretch_note = QLabel(STRETCH_WARNING)
        self._stretch_note.setObjectName("warning")
        self._stretch_note.setWordWrap(True)
        self._stretch_note.setVisible(False)

        self._format = QComboBox()
        self._format.setObjectName("outputFormat")
        self._format.addItem("JPEG", OutputFormat.JPEG)
        self._format.addItem("PNG", OutputFormat.PNG)
        self._format.addItem("WebP", OutputFormat.WEBP)
        self._format.currentIndexChanged.connect(self._on_format_changed)
        self._jpeg_note = QLabel("JPEG flattens transparency onto the background.")
        self._jpeg_note.setObjectName("muted")
        self._jpeg_note.setWordWrap(True)

        self._quality = QSlider(Qt.Orientation.Horizontal)
        self._quality.setRange(1, 100)
        self._quality.setValue(DEFAULT_QUALITY)
        self._quality_value = QSpinBox()
        self._quality_value.setRange(1, 100)
        self._quality_value.setValue(DEFAULT_QUALITY)
        self._quality_value.setSuffix("")
        self._quality.valueChanged.connect(self._on_quality_slider)
        self._quality.sliderReleased.connect(self._emit_commit)
        self._quality_value.valueChanged.connect(self._on_quality_spin)
        quality_row = QHBoxLayout()
        quality_label = QLabel("Quality")
        quality_label.setObjectName("muted")
        quality_row.addWidget(quality_label)
        quality_row.addWidget(self._quality, stretch=1)
        quality_row.addWidget(self._quality_value)
        self._quality_wrap = QWidget()
        self._quality_wrap.setLayout(quality_row)

        self._swatch = QPushButton()
        self._swatch.setObjectName("swatch")
        self._swatch.setToolTip("Background color")
        self._swatch.clicked.connect(self._pick_color)
        self._transparent = QCheckBox("Transparent padding")
        self._transparent.toggled.connect(self._on_transparent)
        color_row = QHBoxLayout()
        color_label = QLabel("Background")
        color_label.setObjectName("muted")
        color_row.addWidget(color_label)
        color_row.addWidget(self._swatch)
        color_row.addWidget(self._transparent, stretch=1)

        self._collision = QComboBox()
        self._collision.setObjectName("collisionPolicy")
        self._collision.addItem("Rename if the file exists", CollisionPolicy.RENAME)
        self._collision.addItem("Skip existing files", CollisionPolicy.SKIP)
        self._collision.addItem("Overwrite existing files", CollisionPolicy.OVERWRITE)
        self._collision.currentIndexChanged.connect(self._emit_commit)

        self._directory = QLineEdit()
        self._directory.setObjectName("exportDirectory")
        self._directory.setPlaceholderText("Export folder")
        self._directory.textChanged.connect(self._on_directory_text)
        self._directory.editingFinished.connect(self._emit_commit)
        browse = QPushButton("Browse")
        browse.setObjectName("browseExport")
        browse.clicked.connect(self._browse_directory)
        self._browse = browse
        directory_row = QHBoxLayout()
        directory_row.addWidget(self._directory, stretch=1)
        directory_row.addWidget(browse)

        self._export = QPushButton("Export images")
        self._export.setObjectName("exportButton")
        self._export.clicked.connect(self.export_requested.emit)
        self._cancel = QPushButton("Cancel")
        self._cancel.setObjectName("cancelExport")
        self._cancel.setVisible(False)
        self._cancel.clicked.connect(self.cancel_requested.emit)
        export_row = QHBoxLayout()
        export_row.addWidget(self._export, stretch=1)
        export_row.addWidget(self._cancel)

        self._hint = QLabel("Add an image first.")
        self._hint.setObjectName("exportHint")
        self._hint.setWordWrap(True)
        self._progress = QProgressBar()
        self._progress.setObjectName("exportProgress")
        self._progress.setTextVisible(False)
        self._progress.setVisible(False)
        self._status = QLabel("")
        self._status.setObjectName("exportStatus")
        self._status.setWordWrap(True)
        self._status.setVisible(False)
        self._open = QPushButton("Open output folder")
        self._open.setVisible(False)
        self._open.clicked.connect(self._open_folder)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(heading)
        layout.addWidget(self._selector, stretch=1)
        layout.addLayout(preset_buttons)
        layout.addWidget(_section("Resize"))
        layout.addWidget(self._crop)
        layout.addWidget(self._fit)
        layout.addWidget(self._stretch)
        layout.addWidget(self._stretch_note)
        layout.addWidget(_section("File"))
        layout.addWidget(self._format)
        layout.addWidget(self._jpeg_note)
        layout.addWidget(self._quality_wrap)
        layout.addLayout(color_row)
        layout.addWidget(self._collision)
        layout.addLayout(directory_row)
        layout.addLayout(export_row)
        layout.addWidget(self._hint)
        layout.addWidget(self._progress)
        layout.addWidget(self._status)
        layout.addWidget(self._open)
        self._sync_swatch()
        self._sync_format_rows()

    def settings(self) -> ExportSettings:
        return ExportSettings(
            mode=self.resize_mode(),
            output_format=self.output_format(),
            quality=self._quality.value(),
            background=self._background,
            collision_policy=self.collision_policy(),
            directory=self.directory(),
        )

    def directory(self) -> str:
        return self._directory.text().strip()

    def resize_mode(self) -> ResizeMode:
        if self._fit.isChecked():
            return ResizeMode.FIT
        if self._stretch.isChecked():
            return ResizeMode.STRETCH
        return ResizeMode.CROP

    def output_format(self) -> OutputFormat:
        value = self._format.currentData()
        if isinstance(value, OutputFormat):
            return value
        return OutputFormat.JPEG

    def collision_policy(self) -> CollisionPolicy:
        value = self._collision.currentData()
        if isinstance(value, CollisionPolicy):
            return value
        return CollisionPolicy.RENAME

    def apply_preferences(self, preferences: Preferences, directory: str) -> None:
        self._applying = True
        try:
            self._set_combo_data(self._format, preferences.output_format)
            self._quality.setValue(preferences.quality)
            self._quality_value.setValue(preferences.quality)
            self._crop.setChecked(preferences.resize_mode is ResizeMode.CROP)
            self._fit.setChecked(preferences.resize_mode is ResizeMode.FIT)
            self._stretch.setChecked(preferences.resize_mode is ResizeMode.STRETCH)
            self._stretch_note.setVisible(preferences.resize_mode is ResizeMode.STRETCH)
            self._background = preferences.background
            self._transparent.setChecked(preferences.background.alpha == 0)
            self._sync_swatch()
            self._set_combo_data(self._collision, preferences.collision_policy)
            self._directory.setText(directory)
            self._sync_format_rows()
        finally:
            self._applying = False

    def set_presets(
        self,
        presets: Sequence[Preset],
        checked: set[str],
        preview_id: str | None,
    ) -> None:
        self._selector.set_presets(presets, checked, preview_id)

    def set_marks(self, checked: set[str], preview_id: str | None) -> None:
        self._selector.set_marks(checked, preview_id)

    def set_source_has_alpha(self, has_alpha: bool) -> None:
        if self._source_has_alpha == has_alpha:
            return
        self._source_has_alpha = has_alpha
        self._sync_format_rows()

    def set_custom_actions(self, enabled: bool) -> None:
        self._edit.setEnabled(enabled and not self._busy)
        self._delete.setEnabled(enabled and not self._busy)
        reason = "" if enabled else "Built-in presets cannot be changed."
        self._edit.setToolTip(reason)
        self._delete.setToolTip(reason)

    def set_busy(self, busy: bool) -> None:
        self._busy = busy
        for widget in (
            self._selector,
            self._add,
            self._crop,
            self._fit,
            self._stretch,
            self._format,
            self._quality,
            self._quality_value,
            self._swatch,
            self._transparent,
            self._collision,
            self._directory,
            self._browse,
        ):
            widget.setEnabled(not busy)
        self._cancel.setVisible(busy)
        self._cancel.setEnabled(busy)
        self._progress.setVisible(busy)
        if busy:
            self._edit.setEnabled(False)
            self._delete.setEnabled(False)
            self._export.setEnabled(False)
        if not busy:
            self._progress.setValue(0)

    def set_export_state(self, *, enabled: bool, reason: str, count: int) -> None:
        self._export.setEnabled(enabled and not self._busy)
        if count == 1:
            self._export.setText("Export 1 image")
        elif count > 1:
            self._export.setText(f"Export {count} images")
        else:
            self._export.setText("Export images")
        show_reason = bool(reason) and not enabled
        self._hint.setText(reason if show_reason else "")
        self._hint.setVisible(show_reason)

    def set_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, max(1, total))
        self._progress.setValue(done)
        self._progress.setVisible(True)

    def set_status(self, text: str, kind: str) -> None:
        self._status.setText(text)
        self._status.setVisible(bool(text))
        name = {"warning": "warning", "success": "heading"}.get(kind, "muted")
        self._status.setObjectName(name)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

    def set_output_folder(self, path: str | None) -> None:
        self._output_folder = path
        self._open.setVisible(bool(path))

    def _emit_commit(self) -> None:
        if self._applying:
            return
        self.commit_changed.emit()
        self.values_changed.emit()

    def _on_directory_text(self) -> None:
        if not self._applying:
            self.values_changed.emit()

    def _on_crop_toggled(self, checked: bool) -> None:
        self._on_mode_toggled(checked)

    def _on_mode_toggled(self, checked: bool) -> None:
        if not checked or self._applying:
            return
        self._stretch_note.setVisible(self._stretch.isChecked())
        self._emit_commit()

    def _on_format_changed(self) -> None:
        self._sync_format_rows()
        self._emit_commit()

    def _sync_format_rows(self) -> None:
        lossy = self.output_format() is not OutputFormat.PNG
        self._quality_wrap.setVisible(lossy)
        show_jpeg_note = self.output_format() is OutputFormat.JPEG and (
            self._source_has_alpha or self._background.alpha != 255
        )
        self._jpeg_note.setVisible(show_jpeg_note)

    def _on_quality_slider(self, value: int) -> None:
        if self._quality_value.value() != value:
            self._quality_value.blockSignals(True)
            self._quality_value.setValue(value)
            self._quality_value.blockSignals(False)

    def _on_quality_spin(self, value: int) -> None:
        if self._quality.value() != value:
            self._quality.blockSignals(True)
            self._quality.setValue(value)
            self._quality.blockSignals(False)
        if not self._applying:
            self._emit_commit()

    def _on_transparent(self, checked: bool) -> None:
        if self._applying:
            return
        alpha = 0 if checked else 255
        self._background = Color(
            self._background.red,
            self._background.green,
            self._background.blue,
            alpha,
        )
        self._sync_swatch()
        self._sync_format_rows()
        self._emit_commit()

    def _pick_color(self) -> None:
        initial = QColor(*self._background.as_rgb())
        chosen = QColorDialog.getColor(initial, self, "Background color")
        if not chosen.isValid():
            return
        alpha = 0 if self._transparent.isChecked() else 255
        self._background = Color(chosen.red(), chosen.green(), chosen.blue(), alpha)
        self._sync_swatch()
        self._emit_commit()

    def _sync_swatch(self) -> None:
        pixmap = QPixmap(28, 28)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.fillRect(0, 0, 28, 28, QColor("#E2E8F0"))
        painter.fillRect(0, 0, 14, 14, QColor("#FFFFFF"))
        painter.fillRect(14, 14, 14, 14, QColor("#FFFFFF"))
        painter.fillRect(0, 0, 28, 28, QColor(*self._background.as_rgba()))
        painter.setPen(QPen(QColor("#94A3B8")))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, 27, 27)
        painter.end()
        self._swatch.setIcon(QIcon(pixmap))
        self._swatch.setIconSize(pixmap.size())

    def _browse_directory(self) -> None:
        start = self.directory() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Export folder", start)
        if not chosen:
            return
        self._directory.setText(chosen)
        self._emit_commit()

    def _open_folder(self) -> None:
        if self._output_folder:
            open_in_file_manager(Path(self._output_folder))

    def _set_combo_data(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    return label
