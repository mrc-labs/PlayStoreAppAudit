from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.audit_window import APK_FILTER_GROUP_INDENT
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

        device_button = window.apk_relationship_buttons["Device-specific"]
        assert device_button.text() == "Device Spec"
        assert device_button.accessibleName() == "Device Specific"
        assert device_button.toolTip() == (
            "The Store version varies by device; a direct comparison may not be available."
        )

        rows = [
            {
                "package_name": "com.example.device",
                "source_mode": "local_apk",
                "local_apk_version_comparison": "Device-specific",
            },
            {
                "package_name": "com.example.match",
                "source_mode": "local_apk",
                "local_apk_version_comparison": "Match",
            },
        ]
        window.current_rows = rows
        window.model.set_rows(rows)
        window._set_apk_relationship_filter("Device-specific")
        assert window._apk_relationship_filters == {"Device-specific"}
        assert window.proxy.rowCount() == 1
        assert (
            window.proxy.index(0, window.model.columns.index("package_name")).data()
            == "com.example.device"
        )
        assert device_button.isChecked()
        window._clear_all_filters()

        # All and More remain neutral, with a visible checked border.
        all_button = window.apk_relationship_buttons["All"]
        assert all_button.isChecked()
        assert "QPushButton:checked {border:2px solid #657786; font-weight:650;}" in all_button.styleSheet()
        assert "background:#FFFFFF" in all_button.styleSheet()
        assert "QPushButton:checked {border:2px solid #657786; font-weight:650;}" in window.apk_relationship_more.styleSheet()
        window._set_apk_relationship_filter("Different")
        assert not all_button.isChecked()
        assert window.apk_relationship_more.isChecked()
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

        margins = window._results_layout.contentsMargins()
        available = window._results_card.contentsRect().width() - margins.left() - margins.right()
        window_chrome = window.width() - available
        required = window._filter_layout_required_width()
        wide_width = required + window_chrome + 80
        window.resize(wide_width, 760)
        app.processEvents()
        app.processEvents()
        wide_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        wide_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert abs(wide_store_y - wide_apk_y) <= 3
        assert window._apk_relationship_on_store_row
        assert window._filter_layout_required_width() == required
        relationship_label = window.apk_relationship_filter_row.layout().itemAt(0).widget()
        assert relationship_label is not None
        gap = (
            relationship_label.mapToGlobal(relationship_label.rect().topLeft()).x()
            - window.criticality_buttons["green"].mapToGlobal(
                window.criticality_buttons["green"].rect().topRight()
            ).x()
        )
        assert 10 <= gap <= 16
        assert window.apk_relationship_filter_row.layout().contentsMargins().left() == APK_FILTER_GROUP_INDENT

        # Cross the natural-width threshold while the Store chips still fit.
        window.resize(required + window_chrome - 2, 760)
        app.processEvents()
        app.processEvents()
        assert not window._apk_relationship_on_store_row
        assert window._filter_layout_required_width() == required
        assert apk_button.mapToGlobal(apk_button.rect().topLeft()).y() > store_button.mapToGlobal(
            store_button.rect().topLeft()
        ).y()
        assert window.apk_relationship_filter_row.layout().contentsMargins().left() == 0
        for button in (window.all_chip, *window.criticality_buttons.values(), *window.apk_relationship_buttons.values(), window.apk_relationship_more):
            assert button.width() >= button.sizeHint().width()
            assert button.height() >= button.sizeHint().height()
            assert button.maximumHeight() > button.sizeHint().height()

        window.resize(1100, 760)
        app.processEvents()
        app.processEvents()
        narrow_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        narrow_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert narrow_apk_y > narrow_store_y
        assert not window._apk_relationship_on_store_row

        window.resize(wide_width, 760)
        app.processEvents()
        app.processEvents()
        restored_store_y = store_button.mapToGlobal(store_button.rect().topLeft()).y()
        restored_apk_y = apk_button.mapToGlobal(apk_button.rect().topLeft()).y()
        assert abs(restored_store_y - restored_apk_y) <= 3
        assert window._apk_relationship_on_store_row
        assert window._filter_layout_required_width() == required
    finally:
        window.close()


def test_more_selection_reflows_when_its_natural_label_grows(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(app, monkeypatch, width=1900)
    try:
        margins = window._results_layout.contentsMargins()
        available = window._results_card.contentsRect().width() - margins.left() - margins.right()
        window_chrome = window.width() - available
        initial_required = window._filter_layout_required_width()
        window.resize(initial_required + window_chrome + 2, 760)
        app.processEvents()
        app.processEvents()
        assert window._apk_relationship_on_store_row

        window._set_apk_relationship_filter("Different")
        app.processEvents()
        app.processEvents()
        assert window.apk_relationship_more.isChecked()
        assert window._filter_layout_required_width() > initial_required
        assert not window._apk_relationship_on_store_row
        assert window.apk_relationship_more.width() >= window.apk_relationship_more.sizeHint().width()
    finally:
        window.close()
