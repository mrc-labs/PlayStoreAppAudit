from __future__ import annotations

import os
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _legacy_settings() -> dict[str, Any]:
    return {
        "view_preset": "Basic",
        "recent_sources": [],
        # The retired implementation was session-only and never wrote settings.
        # Seed both a plausible container and its former runtime field names to
        # prove unknown upgrade-era values cannot reactivate hidden filtering.
        "sdk_filter": {
            "active": True,
            "target_sdk_max": 28,
            "min_sdk_max": 21,
            "compatibility": "Legacy target",
        },
        "target_sdk_max": 28,
        "min_sdk_max": 21,
        "sdk_compatibility": "Legacy target",
    }


def _install_settings(
    monkeypatch: pytest.MonkeyPatch, settings: dict[str, Any]
) -> None:
    def load() -> dict[str, Any]:
        return dict(settings)

    def save(values: dict[str, Any]) -> dict[str, Any]:
        settings.clear()
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load)
    monkeypatch.setattr(state, "save_settings", save)
    monkeypatch.setattr(compact_ui, "load_settings", load)
    monkeypatch.setattr(compact_ui, "save_settings", save)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])


def _seed_sdk_rows(window: MainWindow) -> None:
    rows = [
        {
            "package_name": "com.example.legacy",
            "target_sdk": "28",
            "min_sdk": "21",
            "compatibility_status": "Legacy target",
            "is_system": False,
        },
        {
            "package_name": "com.example.modern",
            "target_sdk": "35",
            "min_sdk": "24",
            "compatibility_status": "Modern",
            "is_system": False,
        },
    ]
    window.current_rows = rows
    window.model.set_rows(rows)
    window._update_summary()


def test_dedicated_sdk_filter_surface_is_absent_and_quick_filters_remain(
    app: QApplication,
) -> None:
    window = MainWindow()
    try:
        view_actions = [action.text() for action in window.view_menu.actions()]
        quick_actions = [action.text() for action in window._filter_menu.actions()]

        assert "SDK Maintenance Filter…" not in view_actions
        assert "Clear SDK Filter" not in view_actions
        assert not hasattr(window, "sdk_filter_action")
        assert not hasattr(window, "clear_sdk_filter_action")
        assert not hasattr(window, "_show_sdk_filter_dialog")
        assert not hasattr(window, "_set_sdk_filter")
        assert "Google Play" in quick_actions
        assert "Alternative Stores" in quick_actions
        assert "Sideloaded" in quick_actions
    finally:
        window.close()
        app.processEvents()


def test_seeded_legacy_sdk_state_never_filters_results_after_restart(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _legacy_settings()
    _install_settings(monkeypatch, settings)

    first = MainWindow()
    try:
        _seed_sdk_rows(first)
        assert first.proxy.rowCount() == 2
        assert first.model.row_dict(0)["target_sdk"] == "28"
        assert first.model.row_dict(0)["min_sdk"] == "21"
        assert first.model.row_dict(0)["compatibility_status"] == "Legacy target"
    finally:
        first.close()
        app.processEvents()

    second = MainWindow()
    try:
        _seed_sdk_rows(second)
        assert second.proxy.rowCount() == 2
        assert settings["sdk_filter"]["active"] is True
    finally:
        second.close()
        app.processEvents()


@pytest.mark.parametrize(
    ("field", "operator", "value", "expected_package"),
    [
        ("compatibility_status", "is", "Legacy target", "com.example.legacy"),
        ("target_sdk", "less_or_equal", 28, "com.example.legacy"),
        ("min_sdk", "greater_than", 21, "com.example.modern"),
    ],
)
def test_smart_queries_retain_sdk_and_compatibility_support(
    field: str,
    operator: str,
    value: object,
    expected_package: str,
) -> None:
    condition = smart_queries.normalise_condition(
        {"field": field, "operator": operator, "value": value}
    )
    assert condition is not None
    query = smart_queries.create_query("SDK query", smart_queries.MatchMode.ALL, [condition])
    assert query is not None

    rows = [
        {
            "package_name": "com.example.legacy",
            "target_sdk": "28",
            "min_sdk": "21",
            "compatibility_status": "Legacy target",
        },
        {
            "package_name": "com.example.modern",
            "target_sdk": "35",
            "min_sdk": "24",
            "compatibility_status": "Modern",
        },
    ]

    matched = [row["package_name"] for row in rows if smart_queries.query_matches(row, query)]
    assert matched == [expected_package]


def test_builtin_filter_selection_is_session_level_and_updates_proxy(
    app: QApplication,
) -> None:
    window = MainWindow()
    try:
        window._apply_filter_preset("Alternative stores")
        assert window._active_filter_preset == "Alternative stores"
        assert window.proxy.v9_preset == "Alternative stores"
    finally:
        window.close()
        app.processEvents()
