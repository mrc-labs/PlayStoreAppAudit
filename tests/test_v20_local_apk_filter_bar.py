from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.theme as theme_ui
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
            "Different": "yellow",
            "Unknown": "purple",
            "Device-specific": "blue",
            "N/A": "red",
        }
        for relationship, status_key in expected.items():
            button = window.apk_relationship_buttons[relationship]
            assert button.styleSheet() == (
                theme_ui.semantic_filter_button_stylesheet(
                    status_key,
                    app.palette(),
                )
            )
        window._refresh_theme_styles()
        for relationship, status_key in expected.items():
            assert window.apk_relationship_buttons[relationship].styleSheet() == (
                theme_ui.semantic_filter_button_stylesheet(status_key, app.palette())
            )

        device_button = window.apk_relationship_buttons["Device-specific"]
        assert device_button.text() == "Device Specific"
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

        # All remains neutral; relationship buttons use the shared semantic palette.
        all_button = window.apk_relationship_buttons["All"]
        assert all_button.isChecked()

        expected_neutral = (
            theme_ui.neutral_filter_button_stylesheet(
                app.palette()
            )
        )

        assert all_button.styleSheet() == expected_neutral
        assert window.apk_relationship_buttons["Different"].styleSheet() == (
            theme_ui.semantic_filter_button_stylesheet("yellow", app.palette())
        )
        assert window.apk_relationship_buttons["Unknown"].styleSheet() == (
            theme_ui.semantic_filter_button_stylesheet("purple", app.palette())
        )
        window._set_apk_relationship_filter("Different")
        assert not all_button.isChecked()
        assert window.apk_relationship_buttons["Different"].isChecked()
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
        assert 14 <= gap <= 20
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
        for button in (window.all_chip, *window.criticality_buttons.values(), *window.apk_relationship_buttons.values()):
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


def test_all_relationship_filters_are_direct_visible_buttons_in_required_order(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _window(app, monkeypatch, width=1900)
    try:
        assert list(window.apk_relationship_buttons) == [
            "All",
            "Outdated",
            "Newer",
            "Match",
            "Different",
            "Unknown",
            "Device-specific",
            "N/A",
        ]
        assert not hasattr(window, "apk_relationship_more")
        for relationship in ("Different", "Unknown"):
            button = window.apk_relationship_buttons[relationship]
            assert button.isVisible()
            window._set_apk_relationship_filter(relationship)
            assert button.isChecked()
    finally:
        window.close()
