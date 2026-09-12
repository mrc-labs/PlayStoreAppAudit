from __future__ import annotations

import os
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.audit_profiles as audit_profiles_ui
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
    created = MainWindow()
    yield created, settings
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


def test_view_menu_separates_result_filters_and_audit_owns_presets(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
) -> None:
    window, settings = window_and_settings
    assert window._filter_menu.title() == "Quick Filters"
    assert window.smart_queries_menu.title() == "Smart Queries"
    assert window.audit_profiles_menu.title() == "Audit Presets"
    assert window.audit_profiles_menu.menuAction() in window.audit_menu.actions()
    assert window.audit_profiles_menu.menuAction() not in window.tools_menu.actions()
    assert [action.text() for action in window.audit_profiles_menu.actions()] == [
        "Save Current as Preset…",
        "Manage Presets…",
        "",
        "No Saved Audit Presets",
    ]
    assert "active_smart_query" not in settings
    assert settings.get("saved_filters") is None


def test_legacy_audit_preset_is_visible_but_applies_execution_state_only(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_and_settings
    legacy_profile = {
        "schema_version": 1,
        "source_mode": "file",
        "view_preset": "Technical",
        "store_country": "de",
        "settings": {
            "store_language": "de",
            "fallback_countries": "fr, us",
            "store_workers": 12,
            "cache_enabled": False,
            "cache_ttl_hours": 24,
            "collect_device_metadata": False,
            "permissions_audit_enabled": True,
            "inventory_history_enabled": False,
            "compare_previous": True,
            "exclude_system_source": False,
            "search": "preset-search",
            "active_filter_preset": "Sideloaded",
            "active_smart_query": {"name": "Preset query"},
            "sdk_filter": {"target_sdk_max": 28},
            "details_panel_position": "right",
            "show_app_icons": True,
            "date_format": "YYYY-MM-DD",
            "custom_view_columns": ["criticality"],
        },
    }
    settings.update(
        {
            "audit_profiles": {"Existing phone audit": legacy_profile},
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name", "play_title"],
            "custom_view_order": ["package_name", "play_title", "criticality"],
            "custom_view_widths": {"package_name": 319, "play_title": 281},
            "details_panel_position": "hidden",
            "show_app_icons": False,
            "date_format": "DD.MM.YYYY",
        }
    )
    window.user_settings.update(settings)
    window._set_view_preset("Custom")
    window._set_details_panel_position("hidden")
    window.search_edit.setText("current-search")
    window._set_criticality_filter("orange")
    window._apply_filter_preset("Old apps")
    query = _query(
        "Current SDK query",
        _condition("compatibility_status", "is", "Legacy target"),
    )
    window._apply_smart_query(query)
    audit_profiles_ui.populate_audit_profiles_menu(window, window.audit_profiles_menu)

    assert "Existing phone audit" in [
        action.text() for action in window.audit_profiles_menu.actions()
    ]
    manage_action = next(
        action
        for action in window.audit_profiles_menu.actions()
        if action.text() == "Manage Presets…"
    )
    assert manage_action.isEnabled()

    audit_profiles_ui.apply_window_profile(window, legacy_profile)

    assert settings["store_language"] == "de"
    assert settings["store_workers"] == 12
    assert settings["cache_enabled"] is False
    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_columns"] == ["criticality", "package_name", "play_title"]
    assert settings["custom_view_order"] == ["package_name", "play_title", "criticality"]
    assert settings["custom_view_widths"] == {"package_name": 319, "play_title": 281}
    assert settings["details_panel_position"] == "hidden"
    assert settings["show_app_icons"] is False
    assert settings["date_format"] == "DD.MM.YYYY"
    assert window.search_edit.text() == "current-search"
    assert window._status_filters == {"orange"}
    assert window._active_filter_preset == "Old apps"
    assert window._active_smart_query is query
    assert window.proxy.smart_query is query
    assert next(
        action for action in window.view_preset_actions if action.text() == "Custom"
    ).isChecked()

    monkeypatch.setattr(
        audit_profiles_ui.QInputDialog,
        "getItem",
        lambda *_args, **_kwargs: ("Existing phone audit", True),
    )
    monkeypatch.setattr(
        audit_profiles_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs: audit_profiles_ui.QMessageBox.StandardButton.Yes,
    )
    manage_action.trigger()
    assert settings["audit_profiles"] == {}


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


def test_smart_query_composes_with_search_status_and_quick_filters_and_preserves_status(
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
    window.status_label.setText("Audit completed: 6 apps")

    query = _query(
        "Alternative stale apps",
        _condition("age_days", "greater_or_equal", 730),
        _condition("installer_category", "is", "alternative_store"),
    )
    window._apply_smart_query(query)

    assert window.proxy.rowCount() == 2
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


def test_clear_all_filters_resets_only_current_result_visibility(
    window_and_settings: tuple[MainWindow, dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_and_settings
    settings.update(
        {
            "audit_profiles": {"Keep preset": {"schema_version": 1}},
            "view_preset": "Basic",
            "details_panel_position": "right",
            "show_app_icons": False,
            "date_format": "DD.MM.YYYY",
            "sdk_filter": {"active": True, "target_sdk_max": 28},
        }
    )
    rows = [
        {
            "package_name": "com.keep.match",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "is_system": False,
        },
        {
            "package_name": "com.keep.other-status",
            "criticality_key": "green",
            "installer_category": "alternative_store",
            "age_days": 800,
            "is_system": False,
        },
        {
            "package_name": "com.keep.current",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 20,
            "is_system": False,
        },
        {
            "package_name": "com.keep.system",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "is_system": True,
        },
        {
            "package_name": "org.other.match",
            "criticality_key": "orange",
            "installer_category": "alternative_store",
            "age_days": 800,
            "is_system": False,
        },
    ]
    query = _query(
        "Saved alternative query",
        _condition("installer_category", "is", "alternative_store"),
        _condition("age_days", "greater_or_equal", 730),
    )
    smart_queries.save_query(query)
    _seed_results(window, rows)
    package_column = window.model.columns.index("package_name")
    window.table.sortByColumn(package_column, window.table.horizontalHeader().sortIndicatorOrder())
    window.search_edit.setText("com.keep")
    window._set_criticality_filter("orange")
    window._apply_filter_preset("Old apps")
    window._apply_smart_query(query)
    window.hide_system_check.setChecked(True)
    assert window.proxy.rowCount() == 1
    window.table.selectRow(0)
    selected_package = window.table.currentIndex().data(Qt.ItemDataRole.UserRole)[
        "package_name"
    ]
    sort_section = window.table.horizontalHeader().sortIndicatorSection()
    sort_order = window.table.horizontalHeader().sortIndicatorOrder()
    details_position = window._details_panel_position
    store_country = window.country_edit.text()
    exclude_system_source = window.exclude_system_source_check.isChecked()
    protected_settings = {
        key: settings.get(key)
        for key in (
            "audit_profiles",
            "view_preset",
            "details_panel_position",
            "show_app_icons",
            "date_format",
            "sdk_filter",
        )
    }
    destructive_calls: list[str] = []
    monkeypatch.setattr(
        compact_ui,
        "clear_cache",
        lambda: destructive_calls.append("cache"),
    )
    monkeypatch.setattr(
        device_metadata,
        "clear_history",
        lambda: destructive_calls.append("audit-history"),
    )
    monkeypatch.setattr(
        device_insights,
        "clear_device_inventory_history",
        lambda: destructive_calls.append("inventory-history"),
    )
    monkeypatch.setattr(
        window,
        "_start_audit",
        lambda: pytest.fail("Clearing filters must not start an audit"),
    )
    monkeypatch.setattr(
        window,
        "_scan_phone",
        lambda: pytest.fail("Clearing filters must not start ADB work"),
    )
    operation_status = "Auditing 4/10: com.example.app"
    window._source_operation_active = True
    window.status_label.setText(operation_status)

    window.clear_all_filters_action.trigger()

    assert window.search_edit.text() == ""
    assert window._status_filters == set()
    assert window._active_filter_preset == "All"
    assert window.proxy.v9_preset == "All"
    assert window._active_smart_query is None
    assert window.proxy.smart_query is None
    assert not window.hide_system_check.isChecked()
    assert window.proxy.rowCount() == len(rows)
    assert window.current_rows == rows
    assert destructive_calls == []
    assert window.table.horizontalHeader().sortIndicatorSection() == sort_section
    assert window.table.horizontalHeader().sortIndicatorOrder() == sort_order
    assert window._details_panel_position == details_position
    assert window.country_edit.text() == store_country
    assert window.exclude_system_source_check.isChecked() == exclude_system_source
    assert (
        window.table.currentIndex().data(Qt.ItemDataRole.UserRole)["package_name"]
        == selected_package
    )
    assert smart_queries.load_queries() == [query]
    assert {
        key: settings.get(key) for key in protected_settings
    } == protected_settings
    assert window.status_label.text() == operation_status
    assert not hasattr(window, "sdk_filter_action")
    window._source_operation_active = False
    window._sync_action_availability()


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
        device_change_index = row.field_combo.findData("device_change")
        assert row.field_combo.itemText(device_change_index) == (
            "Device App Inventory Change"
        )
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
