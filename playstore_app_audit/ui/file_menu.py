from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu


@dataclass(frozen=True, slots=True)
class ResultExportActions:
    menu: QMenu
    all_results: tuple[QAction, ...]
    visible_results: tuple[QAction, ...]


@dataclass(frozen=True, slots=True)
class ResultActions:
    run: QAction
    exports: ResultExportActions
    clear: QAction


def populate_result_export_menu(
    export_menu: QMenu,
    *,
    export_all_csv: Callable[[], None],
    export_visible_csv: Callable[[], None],
    export_all_html: Callable[[], None],
    export_visible_html: Callable[[], None],
    export_all_json: Callable[[], None],
    export_visible_json: Callable[[], None],
) -> ResultExportActions:
    """Populate the canonical all/visible result export structure."""
    all_csv = export_menu.addAction("All CSV", export_all_csv)
    visible_csv = export_menu.addAction("Visible CSV", export_visible_csv)
    export_menu.addSeparator()
    all_json = export_menu.addAction("All JSON", export_all_json)
    visible_json = export_menu.addAction("Visible JSON", export_visible_json)
    export_menu.addSeparator()
    all_html = export_menu.addAction("All HTML", export_all_html)
    visible_html = export_menu.addAction("Visible HTML", export_visible_html)
    return ResultExportActions(
        menu=export_menu,
        all_results=(all_csv, all_json, all_html),
        visible_results=(visible_csv, visible_json, visible_html),
    )
