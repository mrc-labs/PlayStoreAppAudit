from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QFileDialog, QMessageBox

import playstore_app_audit.services.re_audit as re_audit
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.state as state


def _text_attr(widget: object, name: str) -> str:
    target = getattr(widget, name, None)
    if target is None or not hasattr(target, "text"):
        return ""
    return str(target.text() or "").strip()


def _checked_attr(widget: object, name: str) -> bool:
    target = getattr(widget, name, None)
    return bool(target is not None and hasattr(target, "isChecked") and target.isChecked())


def build_window_export_context(window: object) -> dict[str, Any]:
    rows = list(getattr(window, "current_rows", []) or [])
    first = rows[0] if rows and isinstance(rows[0], dict) else {}
    settings = state.load_settings()
    context: dict[str, Any] = {
        "source_mode": str(getattr(window, "source_mode", "") or ""),
        "store_country": _text_attr(window, "country_edit") or str(first.get("store_country") or ""),
        "store_language": str(first.get("store_language") or ""),
        "audit_policy": re_audit.policy_context(settings),
        "filters": {
            "search": _text_attr(window, "search_edit"),
            "hide_system": _checked_attr(window, "hide_system_check"),
            "status": sorted(str(item) for item in getattr(window, "_status_filters", set()) or set()),
            "preset": str(getattr(window, "_active_filter_preset", "All") or "All"),
            # Preserve the v2 export-context shape after retiring the dedicated
            # session-only SDK filter. SDK row data and Smart Query fields remain.
            "sdk": {
                "target_sdk_max": None,
                "min_sdk_max": None,
                "compatibility": "",
            },
        },
    }
    summary = getattr(window, "_device_summary", None)
    if isinstance(summary, dict) and summary:
        context["device"] = dict(summary)
    return context


def _rows_for_scope(window: object, visible: bool) -> list[dict[str, Any]]:
    if visible:
        provider = getattr(window, "_visible_rows", None)
        if callable(provider):
            return [dict(row) for row in provider() if isinstance(row, dict)]
    return [dict(row) for row in getattr(window, "current_rows", []) if isinstance(row, dict)]


def export_window_results_json(window: object, *, visible: bool) -> None:
    rows = _rows_for_scope(window, visible)
    if not rows:
        QMessageBox.information(window, "Nothing to export", "There are no results to export.")
        return

    scope = "visible" if visible else "all"
    default_name = (
        "playstore_audit_visible_results.json" if visible else "playstore_audit_results.json"
    )
    selected, _ = QFileDialog.getSaveFileName(
        window,
        f"Export {scope} results as versioned JSON",
        default_name,
        "JSON (*.json)",
    )
    if not selected:
        return
    if not selected.lower().endswith(".json"):
        selected += ".json"

    try:
        result_json.write_results_json(
            selected,
            rows,
            scope=scope,
            context=build_window_export_context(window),
        )
        QMessageBox.information(window, "Export complete", f"JSON export saved to:\n{selected}")
    except Exception as exc:
        QMessageBox.critical(window, "Export failed", str(exc))
