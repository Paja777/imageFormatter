"""Packaging configuration that can be checked without a Windows toolchain."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from image_resizer import __version__
from image_resizer.core.presets import bundled_presets_path
from image_resizer.paths import resource_path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "pyinstaller.spec"
INSTALLER = ROOT / "packaging" / "installer.iss"
BUILD_SCRIPT = ROOT / "packaging" / "build_windows.ps1"


class _Recorded:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.pure: list[object] = []
        self.scripts: list[object] = []
        self.binaries: list[object] = []
        self.datas = list(kwargs.get("datas", []))


def test_development_resources_are_the_shipped_files() -> None:
    presets = bundled_presets_path()
    icon = resource_path("app.ico")
    assert presets == ROOT / "src" / "image_resizer" / "resources" / "default_presets.json"
    assert presets.is_file()
    assert icon.is_file()


def test_frozen_resources_come_from_the_pyinstaller_bundle(monkeypatch) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", r"C:\bundle\_internal", raising=False)
    root = Path(r"C:\bundle\_internal") / "image_resizer" / "resources"
    assert bundled_presets_path() == root / "default_presets.json"
    assert resource_path("app.ico") == root / "app.ico"


@pytest.fixture(scope="module")
def packaging_app() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


def test_application_icon_has_the_windows_sizes_and_loads(packaging_app: QApplication) -> None:
    del packaging_app
    with Image.open(resource_path("app.ico")) as icon:
        sizes = set(icon.info["sizes"])
    assert {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)} <= sizes
    loaded = QIcon(str(resource_path("app.ico")))
    pixmap = loaded.pixmap(32, 32)
    assert not loaded.isNull()
    assert not pixmap.isNull()


def test_pyinstaller_spec_is_windowed_one_directory() -> None:
    namespace = {
        "SPECPATH": str(SPEC.parent),
        "Analysis": _Recorded,
        "PYZ": _Recorded,
        "EXE": _Recorded,
        "COLLECT": _Recorded,
    }
    exec(SPEC.read_text(encoding="utf-8"), namespace)
    analysis = namespace["a"]
    executable = namespace["exe"]
    collected = namespace["coll"]
    assert analysis.kwargs["pathex"] == [str(ROOT / "src")]
    assert Path(analysis.args[0][0]) == ROOT / "src" / "image_resizer" / "main.py"
    bundled = analysis.kwargs["datas"]
    assert {Path(source).name for source, _destination in bundled} == {
        "default_presets.json",
        "app.ico",
    }
    assert {destination for _source, destination in bundled} == {"image_resizer/resources"}
    assert executable.kwargs["name"] == "ImageResizer"
    assert executable.kwargs["console"] is False
    assert executable.kwargs["exclude_binaries"] is True
    assert executable.kwargs["upx"] is False
    assert str(executable.kwargs["icon"]).endswith("app.ico")
    assert collected.kwargs["name"] == "ImageResizer"


def test_inno_script_is_a_per_user_upgradeable_installer() -> None:
    text = INSTALLER.read_text(encoding="utf-8")
    assert "AppId={{7E2C9A14-5B63-4F80-9D21-C8A6E0F13B47}}" in text
    assert "PrivilegesRequired=lowest" in text
    assert r"DefaultDirName={localappdata}\Programs\{#AppName}" in text
    assert "OutputBaseFilename=ImageResizer-Setup-{#AppVersion}" in text
    assert 'Source: "..\\dist\\ImageResizer\\*"' in text
    assert 'Name: "desktopicon"' in text
    assert "Flags: unchecked" in text
    assert 'Filename: "{uninstallexe}"' in text
    assert "UsePreviousAppDir=yes" in text
    assert "SetupIconFile=..\\src\\image_resizer\\resources\\app.ico" in text
    assert "ArchitecturesInstallIn64BitMode=x64compatible" in text

    release = __version__.split(".")
    assert len(release) == 3 and all(part.isascii() and part.isdigit() for part in release)
    file_version = f"{__version__}.0"
    assert len(file_version.split(".")) == 4
    assert f'#define AppVersion "{__version__}"' in text
    directives = {
        line.split(";", 1)[0].strip()
        for line in text.splitlines()
        if line.split(";", 1)[0].strip()
    }
    assert "VersionInfoVersion={#AppVersion}.0" in directives
    assert "AppVersion={#AppVersion}" in directives
    assert "AppVerName={#AppName} {#AppVersion}" in directives
    assert "VersionInfoProductVersion={#AppVersion}" in directives
    assert "OutputBaseFilename=ImageResizer-Setup-{#AppVersion}" in directives
    visible = directives - {"VersionInfoVersion={#AppVersion}.0"}
    assert all("{#AppVersion}.0" not in line and file_version not in line for line in visible)
    setup_name = f"ImageResizer-Setup-{__version__}.exe"
    assert setup_name == "ImageResizer-Setup-1.0.0.exe"
    assert file_version == "1.0.0.0"


def test_build_script_stops_off_windows_and_calls_both_tools() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert '$env:OS -ne "Windows_NT"' in text
    assert "PyInstaller" in text
    assert "ISCC" in text
    assert "ImageResizer.exe" in text
    assert "ImageResizer-Setup-" in text
    assert ".[packaging]" in text
    assert "Is64BitOperatingSystem" in text
