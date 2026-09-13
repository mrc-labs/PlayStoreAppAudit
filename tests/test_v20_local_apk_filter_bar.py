from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _window(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    *,
    width: int,
) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "inventory_history_enabled": False,
        "details_panel_position": "auto",
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "add_recent_source", lambda _path: None)
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)
    window = MainWindow()
    window.resize(width, 760)
    window.source_mode = "local_apk"
    window._sync_action_availability()
    window.show()
    app.processEvents()
    return window


def test_apk_vs_store_buttons_use_store_status_semantic_colours(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(app, monkeypatch, width=1900)
    try:
        expected = {
            "Outdated": "orange",
            "Newer": "green",
            "Match": "green",
            "Device-specific": "blue",
            "N/A": "red",
        }
        for relationship, status_key in expected.items():
            button = window.apk_relationship_buttons[relationship]
            info = base_ui.CRITICALITY[status_key]
            stylesheet = button.styleSheet()
            assert str(info["background"]) in stylesheet
            assert str(info["foreground"]) in stylesheet
            assert str(info["accent"]) in stylesheet

        # All and the mixed More menu remain neutral rather than inventing one
        # semantic state for multiple underlying relationships.
        assert window.apk_relationship_buttons["All"].styleSheet() == ""
        assert window.apk_relationship_more.styleSheet() == ""
    finally:
        window.close()


def test_apk_vs_store_reflows_beside_store_status_then_below_when_needed(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window = _window(app, monkeypatch, width=1900)
    try:
        store_button = window.all_chip
        apk_button = window.apk_relationship_buttons["All"]

        # This deliberately tests the wide path without tightening Store Status.
        wide_width = max(1900, window._filter_layout_required_width() + 200)
        window.resize(wide_width, 760)
        app.processEvents()
        app.processEvents()
        wide_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        wide_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert abs(wide_store_y - wide_apk_y) <= 3

        window.resize(1100, 760)
        app.processEvents()
        app.processEvents()
        narrow_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        narrow_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert narrow_apk_y > narrow_store_y

        window.resize(wide_width, 760)
        app.processEvents()
        app.processEvents()
        restored_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        restored_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert abs(restored_store_y - restored_apk_y) <= 3
    finally:
        window.close()
