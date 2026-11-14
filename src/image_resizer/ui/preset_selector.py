"""Scrollable preset cards with multi-select and a preview focus."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from image_resizer.core.presets import Preset


class PresetCard(QFrame):
    """One output size. The checkbox includes it in the export."""

    check_changed = Signal(str, bool)
    preview_requested = Signal(str)

    def __init__(self, preset: Preset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preset = preset
        self.setObjectName("presetCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._check = QCheckBox(preset.name)
        self._check.setObjectName(f"preset-check-{preset.id}")
        self._check.setToolTip("Include this size in the export")
        self._check.toggled.connect(self._on_toggled)
        size = QLabel(f"{preset.width} × {preset.height} · {preset.aspect_label()}")
        size.setObjectName("muted")
        size.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self._check, stretch=1)
        if not preset.builtin:
            badge = QLabel("Custom")
            badge.setObjectName("muted")
            badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            top.addWidget(badge)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        layout.addLayout(top)
        layout.addWidget(size)
        self.set_marks(False, False)

    def set_marks(self, checked: bool, active: bool) -> None:
        self._check.blockSignals(True)
        self._check.setChecked(checked)
        self._check.blockSignals(False)
        self.setProperty("checked", "true" if checked else "false")
        self.setProperty("active", "true" if active else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if event.button() == Qt.MouseButton.LeftButton and not self._check.isChecked():
            # The card looks selected on click, so that click also includes the size.
            self._check.setChecked(True)
        elif event.button() == Qt.MouseButton.LeftButton:
            self.preview_requested.emit(self.preset.id)
        super().mousePressEvent(event)

    def _on_toggled(self, checked: bool) -> None:
        self.check_changed.emit(self.preset.id, checked)
        if checked:
            self.preview_requested.emit(self.preset.id)


class PresetSelector(QWidget):
    """Built-in and custom presets loaded from the preset store."""

    check_changed = Signal(str, bool)
    preview_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cards: dict[str, PresetCard] = {}
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._list = QVBoxLayout(self._host)
        self._list.setContentsMargins(0, 0, 4, 0)
        self._list.setSpacing(8)
        self._list.addStretch(1)
        self._scroll.setWidget(self._host)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll)

    def set_presets(
        self,
        presets: Sequence[Preset],
        checked: set[str],
        preview_id: str | None,
    ) -> None:
        while self._list.count() > 1:
            item = self._list.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards.clear()
        for preset in presets:
            card = PresetCard(preset)
            card.check_changed.connect(self.check_changed.emit)
            card.preview_requested.connect(self.preview_requested.emit)
            card.set_marks(preset.id in checked, preset.id == preview_id)
            self._list.insertWidget(self._list.count() - 1, card)
            self._cards[preset.id] = card

    def set_marks(self, checked: set[str], preview_id: str | None) -> None:
        for preset_id, card in self._cards.items():
            card.set_marks(preset_id in checked, preset_id == preview_id)
