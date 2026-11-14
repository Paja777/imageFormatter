"""Preset editor and the export summary."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from image_resizer.core.errors import ImageResizerError
from image_resizer.core.export_service import ExportSummary
from image_resizer.core.presets import validate_preset_dimensions, validate_preset_name
from image_resizer.models.settings import MAX_IMAGE_DIMENSION


ValidatePreset = Callable[[str, int, int], None]


class PresetEditorDialog(QDialog):
    """Collect a preset name and size. ``validate`` keeps the dialog open on errors."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str,
        name: str = "",
        width: int = 800,
        height: int = 600,
        validate: ValidatePreset | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(380)
        self._validate = validate

        self._name = QLineEdit(name)
        self._name.setObjectName("presetName")
        self._name.setMaxLength(80)
        self._name.setPlaceholderText("Banner")
        self._width = _size_spin(width, "presetWidth")
        self._height = _size_spin(height, "presetHeight")
        self._error = QLabel("")
        self._error.setObjectName("presetError")
        self._error.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Name", self._name)
        form.addRow("Width", self._width)
        form.addRow("Height", self._height)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setObjectName("primary")

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._error)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, int, int]:
        return self._name.text(), self._width.value(), self._height.value()

    def accept(self) -> None:
        name, width, height = self.values()
        try:
            if self._validate is not None:
                self._validate(name, width, height)
            else:
                validate_preset_name(name)
                validate_preset_dimensions(width, height)
        except ImageResizerError as exc:
            self._error.setText(str(exc))
            return
        super().accept()


class ExportSummaryDialog(QDialog):
    """Non-modal report of one export, with a shortcut to the output folder."""

    def __init__(self, summary: ExportSummary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export summary" if summary.succeeded else "Export failed")
        self.setModal(False)
        self.setMinimumSize(460, 280)
        self._directory = summary.output_directory

        intro = QLabel(_intro(summary))
        intro.setWordWrap(True)
        intro.setObjectName("heading" if summary.succeeded else "warning")

        details = QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(_details(summary))

        self._open = QPushButton("Open output folder")
        self._open.setObjectName("primary")
        self._open.setEnabled(self._directory.is_dir())
        self._open.clicked.connect(lambda: open_in_file_manager(self._directory))
        close = QPushButton("Close")
        close.clicked.connect(self.close)

        actions = QHBoxLayout()
        actions.addWidget(self._open)
        actions.addStretch(1)
        actions.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(details, stretch=1)
        layout.addLayout(actions)


def open_in_file_manager(path: Path) -> bool:
    """Open ``path`` in the system file manager. Returns whether Qt accepted it."""
    return QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def _size_spin(value: int, object_name: str) -> QSpinBox:
    spin = QSpinBox()
    spin.setObjectName(object_name)
    spin.setRange(1, MAX_IMAGE_DIMENSION)
    spin.setValue(value)
    spin.setSuffix(" px")
    spin.setAccelerated(True)
    return spin


def _intro(summary: ExportSummary) -> str:
    saved = len(summary.succeeded)
    noun = "image" if saved == 1 else "images"
    if saved and not summary.failed:
        return f"Saved {saved} {noun}."
    if saved:
        return f"Saved {saved} {noun}. {len(summary.failed)} failed."
    return "No images were saved."


def _details(summary: ExportSummary) -> str:
    lines = [str(summary.output_directory), ""]
    for item in summary.files:
        if item.error:
            lines.append(f"Failed — {item.preset_name}: {item.error}")
        elif item.skipped:
            lines.append(f"Skipped — {item.preset_name}")
        else:
            name = item.path.name if item.path is not None else item.preset_name
            renamed = " (renamed so nothing was overwritten)" if item.renamed else ""
            lines.append(f"Saved — {name}{renamed}")
    notes = [note for note in (summary.upscale_warning, summary.distortion_warning) if note]
    if notes:
        lines.append("")
        lines.extend(notes)
    return "\n".join(lines)
