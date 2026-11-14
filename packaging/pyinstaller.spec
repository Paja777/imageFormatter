# -*- mode: python ; coding: utf-8 -*-
"""One-directory Windows build of Image Resizer.

PyInstaller injects Analysis, PYZ, EXE, COLLECT, and SPECPATH.
The executable is windowed (no console) and the resources land in
``_internal/image_resizer/resources``, which is ``sys._MEIPASS``.
"""

from pathlib import Path

project_root = Path(SPECPATH).resolve().parent
source_root = project_root / "src"
resources = source_root / "image_resizer" / "resources"
entry_script = source_root / "image_resizer" / "main.py"
presets_file = resources / "default_presets.json"
icon_file = resources / "app.ico"

missing = [path for path in (entry_script, presets_file, icon_file) if not path.is_file()]
if missing:
    joined = ", ".join(str(path) for path in missing)
    raise SystemExit(f"Missing files required by the Windows build: {joined}")

datas = [
    (str(presets_file), "image_resizer/resources"),
    (str(icon_file), "image_resizer/resources"),
]

a = Analysis(
    [str(entry_script)],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ImageResizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(icon_file),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ImageResizer",
)
