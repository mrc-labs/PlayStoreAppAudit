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
    all_csv = export_menu.addAction("Export all results as CSV…", export_all_csv)
    visible_csv = export_menu.addAction(
        "Export visible results as CSV…", export_visible_csv
    )
    export_menu.addSeparator()
    all_html = export_menu.addAction("Export all results as HTML…", export_all_html)
    visible_html = export_menu.addAction(
        "Export visible results as HTML…", export_visible_html
    )
    export_menu.addSeparator()
    all_json = export_menu.addAction(
        "Export all results as versioned JSON…", export_all_json
    )
    visible_json = export_menu.addAction(
        "Export visible results as versioned JSON…", export_visible_json
    )
    return ResultExportActions(
        menu=export_menu,
        all_results=(all_csv, all_html, all_json),
        visible_results=(visible_csv, visible_html, visible_json),
    )


def add_result_actions(
    file_menu: QMenu,
    *,
    run_audit: Callable[[], None],
    export_all_csv: Callable[[], None],
    export_visible_csv: Callable[[], None],
    clear_results: Callable[[], None],
    export_all_html: Callable[[], None],
    export_visible_html: Callable[[], None],
    export_all_json: Callable[[], None],
    export_visible_json: Callable[[], None],
) -> ResultActions:
    """Add the canonical contiguous Run / Export / Clear result section."""
    run_action = file_menu.addAction("Run Play Store audit", run_audit)
    export_menu = file_menu.addMenu("Export Results")
    exports = populate_result_export_menu(
        export_menu,
        export_all_csv=export_all_csv,
        export_visible_csv=export_visible_csv,
        export_all_html=export_all_html,
        export_visible_html=export_visible_html,
        export_all_json=export_all_json,
        export_visible_json=export_visible_json,
    )
    clear_action = file_menu.addAction("Clear Results", clear_results)
    return ResultActions(run=run_action, exports=exports, clear=clear_action)
