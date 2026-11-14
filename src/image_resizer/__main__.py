"""``python -m image_resizer`` launches the desktop window."""

from __future__ import annotations

import sys

from image_resizer.main import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
