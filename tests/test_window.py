"""Offscreen checks for the window, preset editor, and export wiring."""

from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QEventLoop, QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from image_resizer.core.crop_geometry import CropAnchor, Size, cover_crop_box
from image_resizer.core.image_processor import render
from image_resizer.core.presets import PresetStore
from image_resizer.models.settings import OutputFormat, ResizeMode
from image_resizer.services.preferences import PreferencesStore
from image_resizer.ui.dialogs import PresetEditorDialog
from image_resizer.ui.images import build_preview, format_file_size, pil_to_qimage
from image_resizer.ui.main_window import MainWindow
from image_resizer.ui.styles import apply_theme


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


@pytest.fixture
def window(qapp: QApplication, tmp_path: Path):
    presets = PresetStore(tmp_path)
    preferences = PreferencesStore(tmp_path)
    host = MainWindow(presets, preferences)
    apply_theme(qapp, "light")
    host.resize(1280, 720)
    host.show()
    qapp.processEvents()
    yield host
    host.close()
    qapp.processEvents()


def test_preview_copy_and_file_size_label() -> None:
    image = Image.new("RGB", (2400, 1200), "white")
    preview = build_preview(image, max_edge=1600)
    assert max(preview.size) == 1600
    assert preview.size[0] / preview.size[1] == pytest.approx(2)
    assert format_file_size(1536) == "1.5 KB"
    qimage = pil_to_qimage(Image.new("RGBA", (2, 1), (255, 0, 0, 128)))
    assert qimage.pixelColor(0, 0).red() == 255
    assert qimage.pixelColor(0, 0).alpha() == 128


def test_preset_dialog_keeps_invalid_names_open(qapp: QApplication) -> None:
    del qapp
    dialog = PresetEditorDialog(title="New preset")
    dialog.findChild(QLineEdit, "presetName").setText("   ")
    dialog.accept()
    assert int(dialog.result()) != int(QDialog.DialogCode.Accepted)
    assert dialog.findChild(QLabel, "presetError").text()

    created: dict[str, object] = {}

    def validate(name: str, width: int, height: int) -> None:
        created["value"] = (name, width, height)

    dialog = PresetEditorDialog(title="New preset", validate=validate)
    dialog.findChild(QLineEdit, "presetName").setText("  Wide  ")
    dialog.findChild(QWidget, "presetWidth").setValue(32)  # type: ignore[union-attr]
    dialog.findChild(QWidget, "presetHeight").setValue(8)  # type: ignore[union-attr]
    dialog.accept()
    assert int(dialog.result()) == int(QDialog.DialogCode.Accepted)
    assert created["value"] == ("  Wide  ", 32, 8)


def test_clicking_a_preset_card_includes_that_size(window: MainWindow, tmp_path: Path, qapp: QApplication) -> None:
    source = tmp_path / "photo.png"
    Image.new("RGB", (80, 40), "red").save(source)
    _wait(qapp, window.image_loaded, window.image_failed, lambda: window.open_image(str(source)))

    thumbnail = window.findChild(QCheckBox, "preset-check-thumbnail")
    assert thumbnail is not None
    assert not thumbnail.isChecked()
    card = thumbnail.parentWidget()
    assert card is not None
    QTest.mouseClick(
        card,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(card.width() // 2, max(0, card.height() - 6)),
    )
    qapp.processEvents()
    assert thumbnail.isChecked()

    directory = window.findChild(QLineEdit, "exportDirectory")
    button = window.findChild(QPushButton, "exportButton")
    hint = window.findChild(QLabel, "exportHint")
    assert directory is not None and button is not None
    directory.setText(str(tmp_path / "out"))
    qapp.processEvents()
    assert button.isEnabled(), "" if hint is None else hint.text()


def test_window_rejects_an_unsupported_drop(window: MainWindow) -> None:
    window.import_local_paths(["/tmp/notes.txt"])
    banner = window.findChild(QLabel, "bannerLabel")
    assert banner is not None
    assert "Unsupported" in banner.text()


def test_theme_choice_is_saved(window: MainWindow, tmp_path: Path) -> None:
    theme = window.findChild(QCheckBox, "darkTheme")
    assert theme is not None
    theme.click()
    saved = (tmp_path / "preferences.json").read_text(encoding="utf-8")
    assert '"theme": "dark"' in saved


def test_dragged_crop_is_the_crop_that_gets_exported(window: MainWindow, tmp_path: Path, qapp: QApplication) -> None:
    source = tmp_path / "marker.png"
    image = Image.new("RGB", (100, 50), (255, 0, 0))
    blue = Image.new("RGB", (50, 50), (0, 0, 255))
    image.paste(blue, (50, 0))
    image.save(source)

    _wait(qapp, window.image_loaded, window.image_failed, lambda: window.open_image(str(source)))
    dimensions = window.findChild(QLabel, "sourceDimensions")
    assert dimensions is not None
    assert dimensions.text() == "100 × 50"

    thumbnail = window.findChild(QCheckBox, "preset-check-thumbnail")
    small = window.findChild(QCheckBox, "preset-check-small-thumbnail")
    assert thumbnail is not None and small is not None
    thumbnail.click()
    qapp.processEvents()

    canvas = window.findChild(QWidget, "cropCanvas")
    assert canvas is not None and canvas.width() > 80 and canvas.height() > 80
    canvas.repaint()
    origin = QPoint(canvas.width() // 2, canvas.height() // 2)
    moved = origin + QPoint(120, 0)
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, origin)
    QTest.mouseMove(canvas, moved)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, moved)
    qapp.processEvents()

    before = cover_crop_box(Size(100, 50), Size(400, 400), CropAnchor())
    anchor = window.crop_anchor_for("thumbnail")
    after = cover_crop_box(Size(100, 50), Size(400, 400), anchor)
    assert after.left != before.left

    small.click()
    output_format = window.findChild(QComboBox, "outputFormat")
    directory = window.findChild(QLineEdit, "exportDirectory")
    assert output_format is not None and directory is not None
    output_format.setCurrentIndex(1)
    assert output_format.currentData() is OutputFormat.PNG
    directory.setText(str(tmp_path / "out"))

    button = window.findChild(QPushButton, "exportButton")
    hint = window.findChild(QLabel, "exportHint")
    assert button is not None
    assert button.isEnabled(), "" if hint is None else hint.text()
    _wait(qapp, window.export_completed, window.export_failed, button.click)

    folder = tmp_path / "out" / "marker"
    wide = folder / "marker_400x400.png"
    thumb = folder / "marker_150x150.png"
    assert wide.is_file()
    assert thumb.is_file()
    expected = render(
        Image.open(source),
        Size(400, 400),
        ResizeMode.CROP,
        crop_anchor=anchor,
    ).image
    exported = Image.open(wide)
    assert exported.size == (400, 400)
    assert exported.getpixel((10, 10)) == expected.getpixel((10, 10))
    assert exported.getpixel((390, 390)) == expected.getpixel((390, 390))
    assert Image.open(thumb).size == (150, 150)


def _wait(qapp: QApplication, done, failed, start) -> None:
    loop = QEventLoop()
    done.connect(loop.quit)
    failed.connect(lambda *_args: loop.quit())
    QTimer.singleShot(15000, loop.quit)
    start()
    loop.exec()
    qapp.processEvents()
