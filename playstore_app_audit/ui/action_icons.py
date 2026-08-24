from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap

MainAction = Literal["choose_file", "scan_phone", "export_results"]
_ICON_SIZES = (16, 20, 24, 32, 48, 64)


def _draw_choose_file(painter: QPainter) -> None:
    back = QPainterPath(QPointF(4, 18.5))
    back.lineTo(4, 7)
    back.quadTo(4, 5, 6, 5)
    back.lineTo(10, 5)
    back.lineTo(12, 7.5)
    back.lineTo(18.5, 7.5)
    back.quadTo(20, 7.5, 20, 9)
    back.lineTo(20, 11)
    painter.drawPath(back)

    front = QPainterPath(QPointF(4, 10.5))
    front.lineTo(21, 10.5)
    front.lineTo(18, 19)
    front.lineTo(5.5, 19)
    front.quadTo(4, 19, 4, 17.5)
    front.closeSubpath()
    painter.drawPath(front)


def _draw_scan_phone(painter: QPainter) -> None:
    painter.drawRoundedRect(QRectF(7, 2.5, 10, 19), 2, 2)
    painter.drawLine(QPointF(10, 5), QPointF(14, 5))
    painter.drawLine(QPointF(10.5, 19), QPointF(13.5, 19))
    painter.drawLine(QPointF(3.5, 11), QPointF(20.5, 11))
    painter.drawLine(QPointF(3.5, 8.5), QPointF(3.5, 13.5))
    painter.drawLine(QPointF(20.5, 8.5), QPointF(20.5, 13.5))


def _draw_export_results(painter: QPainter) -> None:
    document = QPainterPath(QPointF(4, 3))
    document.lineTo(13, 3)
    document.lineTo(18, 8)
    document.lineTo(18, 12)
    document.moveTo(4, 3)
    document.lineTo(4, 21)
    document.lineTo(15, 21)
    document.moveTo(13, 3)
    document.lineTo(13, 8)
    document.lineTo(18, 8)
    painter.drawPath(document)

    arrow = QPainterPath(QPointF(10.5, 15.5))
    arrow.lineTo(21, 5)
    arrow.moveTo(15.5, 5)
    arrow.lineTo(21, 5)
    arrow.lineTo(21, 10.5)
    painter.drawPath(arrow)


_DRAWERS: dict[MainAction, Callable[[QPainter], None]] = {
    "choose_file": _draw_choose_file,
    "scan_phone": _draw_scan_phone,
    "export_results": _draw_export_results,
}


def main_action_icon(action: MainAction, palette: QPalette) -> QIcon:
    """Create one palette-aware, multi-resolution icon from the main-action family."""
    icon = QIcon()
    colour = palette.color(QPalette.ColorRole.ButtonText)
    for size in _ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(size / 24, size / 24)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                colour,
                1.7,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        _DRAWERS[action](painter)
        painter.end()
        icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.Off)
    icon.setIsMask(True)
    return icon
