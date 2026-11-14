"""Light and dark theme for the desktop window."""

from __future__ import annotations

from string import Template

from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from image_resizer.paths import resource_path


def apply_theme(app: QApplication, theme: str) -> None:
    """Apply the palette and stylesheet for ``light`` or ``dark``."""
    dark = theme == "dark"
    app.setPalette(build_palette(dark))
    app.setStyleSheet(build_stylesheet(dark))


def build_palette(dark: bool) -> QPalette:
    palette = QPalette()
    if dark:
        window = QColor("#0C1723")
        surface = QColor("#112031")
        text = QColor("#E8EEF6")
        muted = QColor("#94A3B8")
        border = QColor("#1E3348")
    else:
        window = QColor("#F8FAFC")
        surface = QColor("#FFFFFF")
        text = QColor("#0F172A")
        muted = QColor("#64748B")
        border = QColor("#E2E8F0")
    accent = QColor("#1362F8")
    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, window)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, surface)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, muted)
    palette.setColor(QPalette.ColorRole.Mid, border)
    palette.setColor(QPalette.ColorRole.ToolTipBase, surface)
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    return palette


def build_app_icon() -> QIcon:
    """Window icon. The shipped .ico matches the executable icon."""
    icon_file = resource_path("app.ico")
    if icon_file.is_file():
        icon = QIcon(str(icon_file))
        if not icon.isNull():
            return icon
    return QIcon(_icon_pixmap())


def _icon_pixmap() -> QPixmap:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#1362F8"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setBrush(QColor("#FFFFFF"))
    painter.drawRoundedRect(16, 18, 32, 26, 4, 4)
    painter.setBrush(QColor("#1362F8"))
    painter.drawEllipse(34, 22, 6, 6)
    painter.drawRoundedRect(20, 32, 18, 5, 2, 2)
    painter.end()
    return pixmap


def build_stylesheet(dark: bool) -> str:
    colors = {
        "bg": "#0C1723" if dark else "#F8FAFC",
        "surface": "#112031" if dark else "#FFFFFF",
        "text": "#E8EEF6" if dark else "#0F172A",
        "muted": "#94A3B8" if dark else "#64748B",
        "border": "#1E3348" if dark else "#E2E8F0",
        "primary": "#1362F8",
        "primary_hover": "#3B7BFA",
        "primary_pressed": "#0E4FD0",
        "soft": "#16293A" if dark else "#F1F5F9",
        "checked": "#173056" if dark else "#E8F0FF",
        "warning_bg": "#3A2A12" if dark else "#FFFBEB",
        "warning_border": "#92400E" if dark else "#FCD34D",
        "warning_text": "#FDE68A" if dark else "#92400E",
        "success_bg": "#052E1A" if dark else "#F0FDF4",
        "success_border": "#166534" if dark else "#86EFAC",
        "success_text": "#BBF7D0" if dark else "#166534",
        "info_bg": "#10243A" if dark else "#EFF6FF",
        "info_border": "#1D4ED8" if dark else "#BFDBFE",
        "info_text": "#DBEAFE" if dark else "#1E3A8A",
        "drop": "#102033" if dark else "#F8FAFC",
        "drop_active": "#173056" if dark else "#EEF4FF",
    }
    return Template(_STYLESHEET).substitute(colors)


_STYLESHEET = """
QMainWindow, QDialog {
    background: $bg;
    color: $text;
}
QWidget#central, QWidget#header {
    background: $bg;
    color: $text;
}
QFrame#panel {
    background: $surface;
    border: 1px solid $border;
    border-radius: 16px;
}
QFrame#banner {
    border-radius: 10px;
    padding: 2px;
}
QFrame#banner[kind="warning"] {
    background: $warning_bg;
    border: 1px solid $warning_border;
}
QFrame#banner[kind="success"] {
    background: $success_bg;
    border: 1px solid $success_border;
}
QFrame#banner[kind="info"] {
    background: $info_bg;
    border: 1px solid $info_border;
}
QLabel {
    background: transparent;
    color: $text;
}
QLabel#title {
    font-size: 18px;
    font-weight: 650;
}
QLabel#heading {
    font-size: 15px;
    font-weight: 650;
}
QLabel#muted, QLabel#hint {
    color: $muted;
}
QLabel#warning {
    color: $warning_text;
}
QLabel#bannerLabel[kind="warning"] {
    color: $warning_text;
}
QLabel#bannerLabel[kind="success"] {
    color: $success_text;
}
QLabel#bannerLabel[kind="info"] {
    color: $info_text;
}
QFrame#DropZone {
    background: $drop;
    border: 2px dashed $border;
    border-radius: 14px;
}
QFrame#DropZone[active="true"] {
    background: $drop_active;
    border-color: $primary;
}
QFrame#presetCard {
    background: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#presetCard[checked="true"] {
    background: $checked;
}
QFrame#presetCard[active="true"] {
    border: 1px solid $primary;
}
QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {
    background: $bg;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 6px 8px;
    min-height: 18px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid $primary;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QPushButton {
    background: $soft;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 7px 12px;
    min-height: 18px;
}
QPushButton:hover {
    border-color: $primary;
}
QPushButton:disabled {
    color: $muted;
    background: $soft;
}
QPushButton#primary, QPushButton#exportButton {
    background: $primary;
    color: white;
    border: none;
    font-weight: 650;
    padding: 10px 16px;
}
QPushButton#primary:hover, QPushButton#exportButton:hover {
    background: $primary_hover;
}
QPushButton#primary:pressed, QPushButton#exportButton:pressed {
    background: $primary_pressed;
}
QPushButton#primary:disabled, QPushButton#exportButton:disabled {
    background: $border;
    color: $muted;
}
QLabel#presetError {
    color: $warning_text;
}
QPushButton#swatch {
    padding: 2px;
    min-width: 32px;
    max-width: 32px;
    min-height: 32px;
    max-height: 32px;
    border: 1px solid $muted;
    background: $surface;
}
QCheckBox, QRadioButton {
    color: $text;
    spacing: 8px;
    background: transparent;
}
QProgressBar {
    background: $soft;
    border: none;
    border-radius: 5px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: $primary;
    border-radius: 5px;
}
QScrollArea {
    border: none;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 4px 0;
}
QScrollBar::handle:vertical {
    background: $border;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line {
    height: 0px;
}
QSplitter::handle {
    background: transparent;
}
QToolTip {
    background: $surface;
    color: $text;
    border: 1px solid $border;
    padding: 4px 6px;
}
"""
