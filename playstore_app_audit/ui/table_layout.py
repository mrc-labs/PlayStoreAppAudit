from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHeaderView, QStyle, QTableView

from playstore_app_audit.ui import schema

HEADER_HORIZONTAL_PADDING = 7
HEADER_HORIZONTAL_BORDER = 1
HEADER_VERTICAL_PADDING = 3


def header_chrome_width(_header: QHeaderView) -> int:
    """Reserve the shared section padding and border used by the table QSS.

    Only the actively sorted section draws a sort mark, so semantic defaults do
    not reserve that transient indicator in every column.
    """

    return 2 * HEADER_HORIZONTAL_PADDING + HEADER_HORIZONTAL_BORDER


def default_column_width(table: QTableView, column: str) -> int:
    header = table.horizontalHeader()
    return schema.semantic_default_width(
        column,
        header.fontMetrics().horizontalAdvance,
        header_chrome_width=header_chrome_width(header),
    )


def shared_header_height(header: QHeaderView) -> int:
    """Fit two explicit text lines without changing body-row geometry."""

    frame = max(
        1,
        min(
            2,
            header.style().pixelMetric(
                QStyle.PixelMetric.PM_DefaultFrameWidth,
                None,
                header,
            ),
        ),
    )
    return 2 * header.fontMetrics().lineSpacing() + 2 * HEADER_VERTICAL_PADDING + frame


def configure_header(table: QTableView) -> None:
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
    header.setFixedHeight(shared_header_height(header))
