"""Application object, theme, and startup."""

from __future__ import annotations

import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from image_resizer import __version__
from image_resizer.services.config_service import open_preset_store, user_data_dir
from image_resizer.services.preferences import open_preferences
from image_resizer.ui.main_window import MainWindow
from image_resizer.ui.styles import apply_theme, build_app_icon


def _windows_taskbar_icon() -> None:
    """Point the Windows taskbar at this program's icon instead of python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ImageResizer.ImageResizer")
    except (AttributeError, OSError):
        return


def create_application(argv: list[str]) -> QApplication:
    """Create the Qt application with a native-looking Fusion style."""
    _windows_taskbar_icon()
    app = QApplication(argv)
    app.setApplicationName("Image Resizer")
    app.setApplicationDisplayName("Image Resizer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("ImageResizer")
    app.setStyle("Fusion")
    if sys.platform == "win32":
        app.setFont(QFont("Segoe UI", 10))
    app.setWindowIcon(build_app_icon())
    return app


def run(argv: list[str] | None = None) -> int:
    """Open the window and run the event loop."""
    app = create_application(list(sys.argv if argv is None else argv))
    try:
        directory = user_data_dir()
        presets = open_preset_store(directory)
        preferences = open_preferences(directory)
    except Exception as exc:
        QMessageBox.critical(
            None,
            "Image Resizer",
            f"Settings could not be opened.\n\n{exc}",
        )
        return 1
    window = MainWindow(presets, preferences)
    window.setWindowIcon(app.windowIcon())
    apply_theme(app, preferences.get().theme)
    window.show()
    return app.exec()
