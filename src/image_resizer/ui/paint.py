"""Small painting helpers shared by the source view and the result preview."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter


def fit_rect(bounds: QRectF, width: float, height: float) -> QRectF:
    """Largest rectangle of the given pixel aspect that fits inside ``bounds``."""
    if width <= 0 or height <= 0 or bounds.width() <= 0 or bounds.height() <= 0:
        return QRectF(bounds)
    scale = min(bounds.width() / width, bounds.height() / height)
    fitted_width = width * scale
    fitted_height = height * scale
    left = bounds.left() + (bounds.width() - fitted_width) / 2
    top = bounds.top() + (bounds.height() - fitted_height) / 2
    return QRectF(left, top, fitted_width, fitted_height)


def paint_checkerboard(painter: QPainter, rect: QRectF, *, dark: bool) -> None:
    """Draw a transparency grid clipped to ``rect``."""
    light = QColor("#1B3348") if dark else QColor("#F8FAFC")
    shade = QColor("#243E56") if dark else QColor("#E2E8F0")
    painter.save()
    painter.setClipRect(rect)
    painter.fillRect(rect, light)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(shade)
    cell = 10
    left = int(rect.left())
    top = int(rect.top())
    right = math.ceil(rect.right())
    bottom = math.ceil(rect.bottom())
    row = 0
    y = top
    while y < bottom:
        column = 0
        x = left
        while x < right:
            if (row + column) % 2 == 0:
                painter.drawRect(x, y, cell, cell)
            x += cell
            column += 1
        y += cell
        row += 1
    painter.restore()
