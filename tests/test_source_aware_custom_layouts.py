from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from copy import deepcopy

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui.column_presets import CustomLayoutFamily
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window_store(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[dict[str, object], Callable[[], MainWindow]]]:
    settings: dict[str, object] = deepcopy(state.DEFAULT_SETTINGS)
    settings.update(
        {
            "view_preset": "Basic",
            "recent_sources": [],
            "custom_view_layouts_migrated_v1": True,
        }
    )
    windows: list[MainWindow] = []

    def load_settings() -> dict[str, object]:
        return deepcopy(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(deepcopy(values))
        return deepcopy(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)

    def create_window() -> MainWindow:
        window = MainWindow()
        windows.append(window)
        return window

    yield settings, create_window

    for window in windows:
        window.close()
    app.processEvents()


def _visible(window: MainWindow) -> list[str]:
    header = window.table.horizontalHeader()
    return [
        window.model.columns[header.logicalIndex(visual)]
        for visual in range(header.count())
        if not window.table.isColumnHidden(header.logicalIndex(visual))
    ]


def _family(settings: dict[str, object], family: CustomLayoutFamily) -> dict[str, object]:
    layouts = settings["custom_view_layouts"]
    assert isinstance(layouts, dict)
    entry = layouts[family.value]
    assert isinstance(entry, dict)
    return deepcopy(entry)


def _custom_actions(window: MainWindow) -> dict[str, object]:
    return {
        str(action.property("customLayoutFamily")): action
        for action in window.view_preset_actions
        if action.data() == "Custom"
    }


def test_two_custom_actions_are_explicit_and_source_enabled(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()
    actions = _custom_actions(window)

    assert [action.text() for action in actions.values()] == [
        "Custom (Phone / App List)",
        "Custom (Local APK)",
    ]
    assert actions[CustomLayoutFamily.PHONE_APP_LIST.value].isEnabled()
    assert not actions[CustomLayoutFamily.LOCAL_APK.value].isEnabled()

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()

    assert not actions[CustomLayoutFamily.PHONE_APP_LIST.value].isEnabled()
    assert actions[CustomLayoutFamily.LOCAL_APK.value].isEnabled()
    assert not actions[CustomLayoutFamily.PHONE_APP_LIST.value].isChecked()


def test_pristine_source_switch_does_not_create_custom_layout(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()

    for source in ("device", "local_apk", "file", "device"):
        window.source_mode = source
        window._apply_established_source_defaults()

    assert settings["view_preset"] == "Basic"
    assert not _family(settings, CustomLayoutFamily.PHONE_APP_LIST)["exists"]
    assert not _family(settings, CustomLayoutFamily.LOCAL_APK)["exists"]


def test_missing_target_family_uses_basic_fallback_without_persisting_it(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()
    window.source_mode = "device"
    window._apply_established_source_defaults()
    window._persist_current_custom_layout()
    phone = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()

    visible = set(_visible(window))
    assert {"local_apk_file_name", "local_apk_version_name"}.issubset(visible)
    assert not {
        "installed_version",
        "version_comparison",
        "device_change",
    }.intersection(visible)
    assert settings["view_preset"] == "Custom"
    assert not _family(settings, CustomLayoutFamily.LOCAL_APK)["exists"]
    assert _family(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone

    window.source_mode = "device"
    window._apply_established_source_defaults()
    assert _family(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone


def test_phone_and_local_custom_layouts_round_trip_and_survive_restart(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    first = create_window()

    first.source_mode = "device"
    first._apply_established_source_defaults()
    installed = first.model.columns.index("installed_version")
    play_title = first.model.columns.index("play_title")
    first.table.setColumnHidden(installed, False)
    first.table.setColumnHidden(play_title, True)
    first.table.setColumnWidth(installed, 177)
    first._persist_current_custom_layout()
    phone_layout = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)

    first.source_mode = "local_apk"
    first._apply_established_source_defaults()
    assert "installed_version" not in _visible(first)
    filename = first.model.columns.index("local_apk_file_name")
    local_label = first.model.columns.index("local_apk_label")
    first.table.setColumnHidden(filename, False)
    first.table.setColumnHidden(local_label, True)
    first.table.setColumnWidth(filename, 233)
    first._persist_current_custom_layout()
    local_layout = _family(settings, CustomLayoutFamily.LOCAL_APK)

    first.source_mode = "device"
    first._apply_established_source_defaults()
    assert _family(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone_layout
    assert "installed_version" in _visible(first)
    assert "play_title" not in _visible(first)
    assert "local_apk_file_name" not in _visible(first)
    assert first.table.columnWidth(installed) == 177

    first.source_mode = "local_apk"
    first._apply_established_source_defaults()
    assert _family(settings, CustomLayoutFamily.LOCAL_APK) == local_layout
    assert "local_apk_file_name" in _visible(first)
    assert "local_apk_label" not in _visible(first)
    assert "installed_version" not in _visible(first)
    assert first.table.columnWidth(filename) == 233

    first.close()
    app.processEvents()
    restarted = create_window()
    restarted.source_mode = "device"
    restarted._apply_established_source_defaults()
    assert "installed_version" in _visible(restarted)
    assert "play_title" not in _visible(restarted)
    restarted.source_mode = "local_apk"
    restarted._apply_established_source_defaults()
    assert "local_apk_file_name" in _visible(restarted)
    assert "local_apk_label" not in _visible(restarted)


def test_app_list_shares_phone_layout_without_mutating_phone_only_state(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()
    window.source_mode = "device"
    window._apply_established_source_defaults()
    installed = window.model.columns.index("installed_version")
    window.table.setColumnHidden(installed, False)
    window.table.setColumnWidth(installed, 181)
    window._persist_current_custom_layout()
    before = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)

    window.source_mode = "file"
    window._apply_established_source_defaults()
    assert "installed_version" not in _visible(window)
    assert "version_comparison" not in _visible(window)
    assert _family(settings, CustomLayoutFamily.PHONE_APP_LIST) == before

    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, 337)
    window._persist_current_custom_layout()
    after_app_list_edit = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)
    assert "installed_version" in after_app_list_edit["columns"]
    assert after_app_list_edit["widths"]["installed_version"] == 181

    window.source_mode = "device"
    window._apply_established_source_defaults()
    assert "installed_version" in _visible(window)
    assert window.table.columnWidth(installed) == 181


def test_legacy_single_custom_migrates_to_both_families_once(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings: dict[str, object] = deepcopy(state.DEFAULT_SETTINGS)
    settings.pop("custom_view_layouts", None)
    settings.pop("custom_view_layouts_migrated_v1", None)
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": [
                "criticality",
                "package_name",
                "installed_version",
                "local_apk_file_name",
                "change",
            ],
            "custom_view_order": [
                "installed_version",
                "local_apk_file_name",
                "criticality",
                "package_name",
                "change",
            ],
            "custom_view_widths": {
                "installed_version": 177,
                "local_apk_file_name": 233,
            },
            "recent_sources": [],
        }
    )

    def load_settings() -> dict[str, object]:
        return deepcopy(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(deepcopy(values))
        return deepcopy(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)

    first = MainWindow()
    try:
        assert settings["custom_view_layouts_migrated_v1"] is True
        phone = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)
        local = _family(settings, CustomLayoutFamily.LOCAL_APK)
        assert "installed_version" in phone["columns"]
        assert "local_apk_file_name" not in phone["columns"]
        assert "local_apk_file_name" in local["columns"]
        assert "installed_version" not in local["columns"]
        assert "change" not in phone["columns"]
        assert "change" not in local["columns"]
        assert settings["custom_view_columns"][-1] == "change"
        migrated = deepcopy(settings["custom_view_layouts"])
    finally:
        first.close()
        app.processEvents()

    restarted = MainWindow()
    try:
        assert settings["custom_view_layouts"] == migrated
    finally:
        restarted.close()
        app.processEvents()


def test_malformed_family_falls_back_without_wiping_valid_sibling(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    layouts = settings["custom_view_layouts"]
    assert isinstance(layouts, dict)
    layouts["phone_app_list"] = {
        "exists": True,
        "columns": ["criticality", "package_name", "play_title"],
        "order": ["play_title", "criticality", "package_name"],
        "widths": {"package_name": 319},
    }
    layouts["local_apk"] = {
        "exists": True,
        "columns": "malformed",
        "order": ["unknown"],
        "widths": {"local_apk_file_name": "bad"},
    }
    settings["view_preset"] = "Custom"
    valid_phone = deepcopy(layouts["phone_app_list"])
    malformed_local = deepcopy(layouts["local_apk"])
    window = create_window()

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()

    assert "local_apk_file_name" in _visible(window)
    assert layouts["phone_app_list"] == valid_phone
    assert layouts["local_apk"] == malformed_local


def test_reset_changes_only_active_custom_family(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()
    window.source_mode = "device"
    window._apply_established_source_defaults()
    window._persist_current_custom_layout()
    phone = _family(settings, CustomLayoutFamily.PHONE_APP_LIST)

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()
    window._persist_current_custom_layout()
    filename = window.model.columns.index("local_apk_file_name")
    window.table.setColumnWidth(filename, 311)
    window._persist_current_custom_layout()
    before_local = _family(settings, CustomLayoutFamily.LOCAL_APK)

    window._reset_table_layout()

    assert _family(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone
    assert _family(settings, CustomLayoutFamily.LOCAL_APK) != before_local

