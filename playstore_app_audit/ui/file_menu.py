from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QMenu


def add_result_actions(
    file_menu: QMenu,
    *,
    run_audit: Callable[[], None],
    export_all_csv: Callable[[], None],
    export_visible_csv: Callable[[], None],
    clear_results: Callable[[], None],
    export_all_html: Callable[[], None] | None = None,
    export_visible_html: Callable[[], None] | None = None,
) -> QMenu:
    """Add the canonical contiguous Run / Export / Clear result section."""
    file_menu.addAction("Run Play Store audit", run_audit)
    export_menu = file_menu.addMenu("Export Results")
    export_menu.addAction("Export all results as CSV…", export_all_csv)
    export_menu.addAction("Export visible results as CSV…", export_visible_csv)

    if export_all_html is not None or export_visible_html is not None:
        export_menu.addSeparator()
        if export_all_html is not None:
            export_menu.addAction("Export all results as HTML…", export_all_html)
        if export_visible_html is not None:
            export_menu.addAction("Export visible results as HTML…", export_visible_html)

    owner = getattr(run_audit, "__self__", None)
    if owner is not None:
        from playstore_app_audit.ui.json_export import export_window_results_json

        export_menu.addSeparator()
        export_menu.addAction(
            "Export all results as versioned JSON…",
            lambda: export_window_results_json(owner, visible=False),
        )
        export_menu.addAction(
            "Export visible results as versioned JSON…",
            lambda: export_window_results_json(owner, visible=True),
        )

    file_menu.addAction("Clear Results", clear_results)
    return export_menu
