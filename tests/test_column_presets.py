from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui import table_layout
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.table_window import TABLE_SCHEMA_VERSION

CUSTOM_KEYS = (
    "custom_view_exists",
    "custom_view_columns",
    "custom_view_order",
    "custom_view_widths",
    "qt_header_state",
)


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
            "qt_header_state": "",
            "qt_header_schema_version": TABLE_SCHEMA_VERSION,
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


def _visual_order(window: MainWindow) -> list[str]:
    header = window.table.horizontalHeader()
    return [window.model.columns[header.logicalIndex(visual)] for visual in range(header.count())]


def _visible_order(window: MainWindow) -> list[str]:
    return [
        column
        for column in _visual_order(window)
        if not window.table.isColumnHidden(window.model.columns.index(column))
    ]


def _widths(window: MainWindow) -> dict[str, int]:
    return {
        column: window.table.columnWidth(logical)
        for logical, column in enumerate(window.model.columns)
    }


def _custom_snapshot(settings: dict[str, object]) -> dict[str, object]:
    return {key: deepcopy(settings.get(key)) for key in CUSTOM_KEYS}


def _custom_action(window: MainWindow):
    return next(action for action in window.view_preset_actions if action.text() == "Custom")


def test_pristine_settings_remain_basic_without_custom_across_restart(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)

    first = MainWindow()
    first.show()
    app.processEvents()
    try:
        fresh = state.load_settings()
        basic = next(action for action in first.view_preset_actions if action.text() == "Basic")
        assert fresh["view_preset"] == "Basic"
        assert fresh["custom_view_exists"] is False
        assert basic.isChecked()
        assert not _custom_action(first).isEnabled()
    finally:
        first.close()
        app.processEvents()

    restarted = MainWindow()
    restarted.show()
    app.processEvents()
    try:
        second = state.load_settings()
        basic = next(
            action for action in restarted.view_preset_actions if action.text() == "Basic"
        )
        assert second["view_preset"] == "Basic"
        assert second["custom_view_exists"] is False
        assert basic.isChecked()
        assert not _custom_action(restarted).isEnabled()
    finally:
        restarted.close()
        app.processEvents()


def test_column_preset_naming_and_custom_starts_disabled(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()

    assert window.view_presets_menu.title() == "Column Preset"
    assert [action.text() for action in window.view_preset_actions] == [
        "Basic",
        "Source Details",
        "Technical",
        "Custom",
    ]
    assert window.display_settings_action.text() == "Customize View…"
    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_exists"] is False
    assert not _custom_action(window).isEnabled()
    assert window.model._icons_enabled is True


def test_programmatic_builtin_presets_do_not_create_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    window = create_window()

    for preset in ("Basic", "Source Details", "Technical"):
        window._set_view_preset(preset)
        app.processEvents()

        assert settings["view_preset"] == preset
        assert settings["custom_view_exists"] is False
        assert not _custom_action(window).isEnabled()
        for logical, column in enumerate(window.model.columns):
            if window.table.isColumnHidden(logical):
                continue
            assert window.table.columnWidth(logical) == table_layout.default_column_width(
                window.table, column
            )


@pytest.mark.parametrize("preset", ["Basic", "Source Details", "Technical"])
def test_builtin_column_presets_remain_immutable_after_manual_resize(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    preset: str,
) -> None:
    settings, create_window = window_store
    window = create_window()
    window._set_view_preset(preset)
    canonical_visible = _visible_order(window)
    canonical_order = _visual_order(window)
    canonical_widths = _widths(window)

    package = window.model.columns.index("package_name")
    wanted = canonical_widths["package_name"] + 37
    window.table.setColumnWidth(package, wanted)
    app.processEvents()

    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_widths"]["package_name"] == wanted  # type: ignore[index]
    saved_custom = _custom_snapshot(settings)

    window._set_view_preset(preset)

    assert _visible_order(window) == canonical_visible
    assert _visual_order(window) == canonical_order
    assert _widths(window) == canonical_widths
    assert _custom_snapshot(settings) == saved_custom


def test_manual_reorder_creates_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    window = create_window()
    title = window.model.columns.index("play_title")
    header = window.table.horizontalHeader()

    header.moveSection(header.visualIndex(title), 0)
    app.processEvents()

    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_exists"] is True
    assert settings["custom_view_order"][0] == "play_title"  # type: ignore[index]
    assert _custom_action(window).isEnabled() and _custom_action(window).isChecked()


def test_customize_view_visibility_change_creates_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    window = create_window()

    def hide_notes(dialog: QDialog) -> int:
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        store_change = dialog.findChild(QCheckBox, "CustomColumnCheck_change")
        device_change = dialog.findChild(QCheckBox, "CustomColumnCheck_device_change")
        assert notes is not None and notes.isChecked()
        assert store_change is not None
        assert store_change.text() == "Play Store Listing Change"
        assert device_change is not None
        assert device_change.text() == "Device App Inventory Change"
        notes.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", hide_notes)
    window._show_display_settings()
    app.processEvents()

    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_exists"] is True
    assert "notes" not in settings["custom_view_columns"]  # type: ignore[operator]
    assert window.table.isColumnHidden(window.model.columns.index("notes"))
    assert _custom_action(window).isEnabled() and _custom_action(window).isChecked()


def test_restoring_custom_does_not_persist_recursively(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    window = create_window()
    package = window.model.columns.index("package_name")
    wanted = window.table.columnWidth(package) + 43
    window.table.setColumnWidth(package, wanted)
    app.processEvents()
    saved_custom = _custom_snapshot(settings)
    window._set_view_preset("Source Details")

    persist_calls: list[bool] = []
    original_persist = window._persist_current_custom_layout

    def track_persist(*, activate: bool = True) -> None:
        persist_calls.append(activate)
        original_persist(activate=activate)

    monkeypatch.setattr(window, "_persist_current_custom_layout", track_persist)
    window._set_view_preset("Custom")
    app.processEvents()

    assert persist_calls == []
    assert _custom_snapshot(settings) == saved_custom
    assert window.table.columnWidth(package) == wanted


def test_manual_order_width_and_customize_visibility_round_trip(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    window = create_window()
    package = window.model.columns.index("package_name")
    title = window.model.columns.index("play_title")
    window.table.setColumnWidth(package, 333)
    header = window.table.horizontalHeader()
    header.moveSection(header.visualIndex(title), 0)
    app.processEvents()

    def hide_notes(dialog: QDialog) -> int:
        assert dialog.windowTitle() == "Customize View"
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        assert notes is not None and notes.isChecked()
        notes.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", hide_notes)
    window._show_display_settings()
    app.processEvents()

    expected_visible = _visible_order(window)
    expected_order = _visual_order(window)
    expected_widths = _widths(window)
    saved_custom = _custom_snapshot(settings)
    assert settings["view_preset"] == "Custom"
    assert set(settings["custom_view_columns"]) == set(expected_visible)  # type: ignore[arg-type]
    assert settings["custom_view_order"] == expected_order
    saved_widths = settings["custom_view_widths"]
    assert isinstance(saved_widths, dict)
    assert all(saved_widths[column] == expected_widths[column] for column in expected_visible)
    assert saved_widths["notes"] > 0
    assert "notes" not in expected_visible
    assert expected_widths["package_name"] == 333
    assert _custom_action(window).isEnabled() and _custom_action(window).isChecked()

    window._set_view_preset("Source Details")
    assert _custom_snapshot(settings) == saved_custom
    window._set_view_preset("Custom")

    assert _visible_order(window) == expected_visible
    assert _visual_order(window) == expected_order
    assert _widths(window) == expected_widths


def test_custom_layout_survives_refresh_sort_filter_and_restart(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    first = create_window()
    first._set_view_preset("Technical")
    package = first.model.columns.index("package_name")
    title = first.model.columns.index("play_title")
    score = first.model.columns.index("health_score")
    first.table.setColumnWidth(package, 347)
    first.table.setColumnWidth(score, 140)
    first.table.horizontalHeader().moveSection(
        first.table.horizontalHeader().visualIndex(title), 0
    )
    app.processEvents()
    expected = _custom_snapshot(settings)
    expected_visible = _visible_order(first)
    expected_order = _visual_order(first)
    expected_widths = _widths(first)

    first.current_rows = [
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "package_name": "com.example.persist",
            "play_title": "Persist",
        }
    ]
    first.model.set_rows(first.current_rows)
    first.search_edit.setText("persist")
    first.table.sortByColumn(package, Qt.SortOrder.DescendingOrder)
    first._apply_column_visibility(reset_order=False)
    app.processEvents()

    assert _custom_snapshot(settings) == expected
    first._set_criticality_filter("green")
    first._apply_filter_preset("Old apps")
    first.hide_system_check.setChecked(True)
    first._clear_all_filters()
    app.processEvents()

    assert _custom_snapshot(settings) == expected
    assert _visible_order(first) == expected_visible
    assert _visual_order(first) == expected_order
    assert _widths(first) == expected_widths
    first.close()
    app.processEvents()

    restarted = create_window()
    assert settings["view_preset"] == "Custom"
    assert _custom_action(restarted).isEnabled() and _custom_action(restarted).isChecked()
    assert _visible_order(restarted) == expected_visible
    assert _visual_order(restarted) == expected_order
    assert _widths(restarted) == expected_widths
    assert restarted.table.columnWidth(score) == 140


def test_rc2_header_state_migrates_without_losing_manual_widths_or_preferences(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    settings["show_app_icons"] = False
    first = create_window()
    package = first.model.columns.index("package_name")
    title = first.model.columns.index("play_title")
    first.table.setColumnWidth(package, 361)
    first.table.horizontalHeader().moveSection(
        first.table.horizontalHeader().visualIndex(title), 0
    )
    app.processEvents()
    legacy_header = settings["qt_header_state"]
    legacy_order = _visual_order(first)
    settings.pop("custom_view_order", None)
    settings.pop("custom_view_widths", None)
    settings.update(
        {
            "custom_view_exists": False,
            "custom_view_columns": deepcopy(state.DEFAULT_SETTINGS["custom_view_columns"]),
            "qt_header_state": legacy_header,
            "qt_header_schema_version": TABLE_SCHEMA_VERSION,
            "view_preset": "Basic",
        }
    )
    first.close()
    app.processEvents()

    migrated = create_window()
    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_exists"] is True
    assert migrated.table.columnWidth(package) == 361
    assert _visual_order(migrated) == legacy_order
    assert settings["show_app_icons"] is False
    assert migrated.model._icons_enabled is False


def test_default_legacy_header_state_does_not_imply_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    first = create_window()
    expected_visible = _visible_order(first)
    expected_order = _visual_order(first)
    expected_widths = _widths(first)
    _visible, _order, _widths_by_name, default_header = first._current_table_layout()
    first.close()
    app.processEvents()
    settings.pop("custom_view_order", None)
    settings.pop("custom_view_widths", None)
    settings.update(
        {
            "custom_view_exists": False,
            "custom_view_columns": deepcopy(state.DEFAULT_SETTINGS["custom_view_columns"]),
            "qt_header_state": default_header,
            "view_preset": "Basic",
        }
    )

    restarted = create_window()

    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_exists"] is False
    assert not _custom_action(restarted).isEnabled()
    assert _visible_order(restarted) == expected_visible
    assert _visual_order(restarted) == expected_order
    assert _widths(restarted) == expected_widths


def test_old_custom_visibility_is_preserved_while_last_builtin_stays_active(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Source Details",
            "custom_view_columns": ["criticality", "package_name", "play_title"],
        }
    )
    window = create_window()

    assert settings["view_preset"] == "Source Details"
    assert settings["custom_view_exists"] is True
    assert _custom_action(window).isEnabled()
    window._set_view_preset("Custom")
    assert _visible_order(window) == ["criticality", "package_name", "play_title"]


def test_custom_history_choices_survive_runtime_gates_and_source_changes(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": [
                "criticality",
                "change",
                "device_change",
                "package_name",
            ],
            "custom_view_order": [
                "criticality",
                "change",
                "device_change",
                "package_name",
            ],
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window = create_window()
    saved_custom = _custom_snapshot(settings)

    window.source_mode = "device"
    window._apply_column_visibility(reset_order=False)
    assert _visible_order(window) == [
        "criticality",
        "change",
        "device_change",
        "package_name",
    ]

    settings["changes_history_enabled"] = False
    window._apply_column_visibility(reset_order=False)
    assert _visible_order(window) == ["criticality", "package_name"]
    assert _custom_snapshot(settings) == saved_custom

    settings["changes_history_enabled"] = True
    window.source_mode = "file"
    window._apply_column_visibility(reset_order=False)
    assert _visible_order(window) == ["criticality", "change", "package_name"]
    assert _custom_snapshot(settings) == saved_custom

    window.source_mode = "device"
    window._apply_column_visibility(reset_order=False)
    assert _visible_order(window) == [
        "criticality",
        "change",
        "device_change",
        "package_name",
    ]
    assert _custom_snapshot(settings) == saved_custom


def test_legacy_custom_preset_with_default_columns_migrates(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": False,
            "custom_view_columns": deepcopy(state.DEFAULT_SETTINGS["custom_view_columns"]),
        }
    )

    window = create_window()

    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_exists"] is True
    assert _custom_action(window).isEnabled() and _custom_action(window).isChecked()
    assert _visible_order(window) == state.DEFAULT_SETTINGS["custom_view_columns"]


def test_malformed_custom_state_falls_back_safely_to_basic(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": "not-a-list",
            "custom_view_order": ["unknown"],
            "custom_view_widths": {"package_name": "invalid"},
            "qt_header_state": "not-valid-base64",
            "show_app_icons": False,
        }
    )
    window = create_window()

    assert settings["view_preset"] == "Basic"
    assert not _custom_action(window).isEnabled()
    assert window.model._icons_enabled is False


def test_partial_custom_widths_use_phase_a_semantic_defaults(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name", "play_title"],
            "custom_view_order": ["play_title", "criticality", "package_name"],
            "custom_view_widths": {"package_name": 319, "play_title": "bad"},
        }
    )
    window = create_window()

    package = window.model.columns.index("package_name")
    title = window.model.columns.index("play_title")
    assert window.table.columnWidth(package) == 319
    assert window.table.columnWidth(title) == table_layout.default_column_width(
        window.table, "play_title"
    )


def test_customize_view_global_preferences_do_not_mutate_custom_layout(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    window = create_window()
    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, 329)
    app.processEvents()
    before = _custom_snapshot(settings)

    def global_only(dialog: QDialog) -> int:
        icons = dialog.findChild(QCheckBox, "ShowAppIconsCheck")
        date_format = dialog.findChild(QComboBox, "DateFormatCombo")
        assert icons is not None and date_format is not None
        icons.setChecked(False)
        date_format.setCurrentText("DD.MM.YYYY")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", global_only)
    window._show_display_settings()

    assert settings["show_app_icons"] is False
    assert settings["date_format"] == "DD.MM.YYYY"
    assert window.model._icons_enabled is False
    assert _custom_snapshot(settings) == before
