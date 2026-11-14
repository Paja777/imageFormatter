"""Locations of files shipped inside the application.

Development reads them from the package directory. A PyInstaller build reads
them from ``sys._MEIPASS``, which is the ``_internal`` folder next to the
executable in one-directory mode.
"""

from __future__ import annotations

import sys
from pathlib import Path


def package_root() -> Path:
    """Return the ``image_resizer`` directory that holds packaged data."""
    if getattr(sys, "frozen", False):
        bundle = getattr(sys, "_MEIPASS", None)
        if bundle:
            return Path(bundle) / "image_resizer"
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """Return one file under the shipped ``resources`` directory."""
    return package_root().joinpath("resources", *parts)
