from __future__ import annotations

import os
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.sdk_maintenance as sdk_maintenance
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.smart_queries import SmartQueryDialog


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window_and_settings(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MainWindow, dict[str, Any]]:
    settings: dict[str, Any] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "smart_queries": {"schema_version": 1, "items": []},
    }

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
    sdk_maintenance.set_active_sdk_filter(None)
    created = MainWindow()
    yield created, settings
    sdk_maintenance.set_active_sdk_filter(None)
    created.close()
    app.processEvents()


def _condition(
    field: str,
    operator: smart_queries.Operator | str,
    value: object = None,
) -> smart_queries.SmartCondition:
    result = smart_queries.normalise_condition(
        {"field": field, "operator": str(operator), "value": value}
    )
    assert result is not None
    return result


def _query(
    name: str,
    *conditions: smart_queries.SmartCondition,
) -> smart_queries.SmartQuery:
    result = smart_queries.create_query(name, smart_queries.MatchMode.ALL, conditions)
    assert result is not None
    return result


def _seed_results(window: MainWindow, rows: list[dict[str, object]]) -> None:
    window.current_rows = rows
    window.model.set_rows(rows)
    window._update_summary()


def test_view_menu_separates_quick_filters_smart_queries_and_audit_profiles(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
) -> None:
    window, settings = window_and_settings
    assert window._filter_menu.title() == "Quick Filters"
    assert window.smart_queries_menu.title() == "Smart Queries"
    assert window.audit_profiles_menu.title() == "Audit Profiles"
    assert window.view_menu.actions().index(window.smart_queries_menu.menuAction()) < (
        window.view_menu.actions().index(window.sdk_filter_action)
    )
    assert window.audit_profiles_menu.menuAction() in window.tools_menu.actions()
    assert "active_smart_query" not in settings
    assert settings.get("saved_filters") is None


def test_smart_query_actions_follow_results_and_running_state(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
) -> None:
    window, _settings = window_and_settings
    saved = _query("Stale Apps", _condition("age_days", "greater_than", 365))
    smart_queries.save_query(saved)
    window._clear_smart_query()

    assert window.new_smart_query_action.isEnabled()
    assert window.manage_smart_queries_action.isEnabled()
    assert not window.clear_smart_query_action.isEnabled()
    assert len(window.saved_smart_query_actions) == 1
    assert not window.saved_smart_query_actions[0].isEnabled()

    _seed_results(window, [{"package_name": "com.example.app", "age_days": 500}])
    assert window.saved_smart_query_actions[0].isEnabled()

    window._source_operation_active = True
    window._sync_action_availability()
    assert not window.smart_queries_menu.menuAction().isEnabled()
    assert not window.new_smart_query_action.isEnabled()
    assert not window.manage_smart_queries_action.isEnabled()
    assert not window.saved_smart_query_actions[0].isEnabled()
    window._source_operation_active = False
    window._sync_action_availability()


def test_smart_query_composes_with_every_existing_filter_and_preserves_status(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
) -> None:
    window, settings = window_and_settings
    rows = [
        {
            "package_name": "com.keep.match",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "target_sdk": 30,
            "is_system": False,
        },
        {
            "package_name": "com.keep.google",
            "criticality_key": "orange",
            "installer_category": "google_play",
            "age_days": 800,
            "target_sdk": 30,
            "is_system": False,
        },
        {
            "package_name": "com.keep.current",
            "criticality_key": "green",
            "installer_category": "alternative_store",
            "age_days": 100,
            "target_sdk": 30,
            "is_system": False,
        },
        {
            "package_name": "com.other.search",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "target_sdk": 30,
            "is_system": False,
        },
        {
            "package_name": "com.keep.system",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "target_sdk": 30,
            "is_system": True,
        },
        {
            "package_name": "com.keep.new-sdk",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "target_sdk": 35,
            "is_system": False,
        },
    ]
    _seed_results(window, rows)
    window.search_edit.setText("com.keep")
    window._set_criticality_filter("orange")
    window._apply_filter_preset("Old apps")
    window._set_sdk_filter(sdk_maintenance.SdkMaintenanceFilter(target_sdk_max=32))
    window.status_label.setText("Audit completed: 6 apps")

    query = _query(
        "Alternative stale apps",
        _condition("age_days", "greater_or_equal", 730),
        _condition("installer_category", "is", "alternative_store"),
    )
    window._apply_smart_query(query)

    assert window.proxy.rowCount() == 1
    assert window.status_label.text() == "Audit completed: 6 apps"
    assert "Smart Query: Alternative stale apps" in window.summary_label.text()
    assert window.summary_label.toolTip() == "Active Smart Query: Alternative stale apps"
    assert window.clear_smart_query_action.isEnabled()
    assert "active_smart_query" not in settings

    refreshed = [dict(rows[0], package_name="com.keep.refreshed")]
    _seed_results(window, refreshed)
    assert window.proxy.rowCount() == 1

    window._clear_smart_query()
    assert window.proxy.rowCount() == 1
    assert "Smart Query:" not in window.summary_label.text()
    assert window.summary_label.toolTip() == ""
    assert window.status_label.text() == "Audit completed: 6 apps"


def test_dialog_is_native_accessible_and_responsive(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
) -> None:
    window, _settings = window_and_settings
    _seed_results(window, [{"package_name": "com.example.app"}])
    applied: list[smart_queries.SmartQuery] = []
    deleted: list[str] = []
    dialog = SmartQueryDialog(
        window,
        apply_callback=applied.append,
        delete_callback=deleted.append,
        new_query=True,
    )
    try:
        assert dialog.minimumWidth() <= 1100
        assert dialog.minimumHeight() <= 700
        assert dialog.saved_list.accessibleName() == "Saved Smart Queries"
        assert dialog.name_edit.accessibleName() == "Smart Query Name"
        assert dialog.match_combo.accessibleName() == "Condition Match Mode"
        assert len(dialog._condition_rows) == 1
        row = dialog._condition_rows[0]
        assert row.accessibleName() == "Condition 1"
        assert row.field_combo.accessibleName() == "Condition Field"
        assert row.operator_combo.accessibleName() == "Condition Operator"
        assert row.remove_button.accessibleName() == "Remove Condition"
        assert row.remove_button.toolTip() == "Remove condition"
        assert not row.remove_button.isEnabled()
        assert row.validation_label.text() == "Enter a valid value for this condition."
        assert row.validation_label.isVisibleTo(dialog)
        assert not dialog.save_button.isEnabled()
        assert not dialog.apply_button.isEnabled()

        row.text_value.setText("example")
        assert not row.validation_label.isVisibleTo(dialog)
        assert dialog.apply_button.isEnabled()
        assert not dialog.save_button.isEnabled()
        dialog.name_edit.setText("Example Packages")
        assert dialog.save_button.isEnabled()

        dialog.add_condition_button.click()
        assert len(dialog._condition_rows) == 2
        second = dialog._condition_rows[1]
        field_index = second.field_combo.findData("age_days")
        second.field_combo.setCurrentIndex(field_index)
        assert second.operator_combo.findData("greater_than") >= 0
        assert second.value_stack.currentWidget() is second.number_value
        assert all(item.accessibleName() for item in dialog._condition_rows)
    finally:
        dialog.close()


def test_dialog_save_does_not_apply_then_apply_and_delete_stay_synchronised(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_and_settings
    _seed_results(
        window,
        [
            {"package_name": "com.example.one", "is_system": False},
            {"package_name": "org.sample.two", "is_system": False},
        ],
    )
    window.status_label.setText("Ready")
    dialog = SmartQueryDialog(
        window,
        apply_callback=window._apply_smart_query,
        delete_callback=window._on_smart_query_deleted,
        new_query=True,
    )
    try:
        row = dialog._condition_rows[0]
        row.text_value.setText("com.example")
        dialog.name_edit.setText("Example Packages")
        dialog.save_button.click()

        loaded = smart_queries.load_queries()
        assert len(loaded) == 1
        assert loaded[0].name == "Example Packages"
        assert window._active_smart_query is None
        assert window.proxy.rowCount() == 2
        assert settings["smart_queries"]["schema_version"] == 1
        assert "active_smart_query" not in settings

        dialog.apply_button.click()
        assert window._active_smart_query == loaded[0]
        assert window.proxy.rowCount() == 1
        assert window.status_label.text() == "Ready"
        checked = [action.text() for action in window.saved_smart_query_actions if action.isChecked()]
        assert checked == ["Example Packages"]

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
        )
        dialog.delete_button.click()
        assert smart_queries.load_queries() == []
        assert window._active_smart_query is None
        assert window.proxy.rowCount() == 2
        assert window.status_label.text() == "Ready"
    finally:
        dialog.close()
