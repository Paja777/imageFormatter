"""Entry point for the desktop application."""

from __future__ import annotations

import sys

from image_resizer.app import run


def main(argv: list[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
