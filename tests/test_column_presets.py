from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from copy import deepcopy

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
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "qt_header_state": "",
        "qt_header_schema_version": TABLE_SCHEMA_VERSION,
    }
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


def test_column_preset_naming_and_custom_starts_disabled(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    _settings, create_window = window_store
    window = create_window()

    assert window.view_presets_menu.title() == "Column Preset"
    assert [action.text() for action in window.view_preset_actions] == [
        "Basic",
        "Device",
        "Technical",
        "Custom",
    ]
    assert window.display_settings_action.text() == "Customize View…"
    assert not _custom_action(window).isEnabled()
    assert window.model._icons_enabled is True


@pytest.mark.parametrize("preset", ["Basic", "Device", "Technical"])
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
    assert settings["custom_view_columns"] == expected_visible
    assert settings["custom_view_order"] == expected_order
    assert settings["custom_view_widths"] == expected_widths
    assert "notes" not in expected_visible
    assert expected_widths["package_name"] == 333
    assert _custom_action(window).isEnabled() and _custom_action(window).isChecked()

    window._set_view_preset("Device")
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
    package = first.model.columns.index("package_name")
    title = first.model.columns.index("play_title")
    first.table.setColumnWidth(package, 347)
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
            "criticality": "Current",
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
    for key in CUSTOM_KEYS:
        settings.pop(key, None)
    settings.update(
        {
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


def test_old_custom_visibility_is_preserved_while_last_builtin_stays_active(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Device",
            "custom_view_columns": ["criticality", "package_name", "play_title"],
        }
    )
    window = create_window()

    assert settings["view_preset"] == "Device"
    assert settings["custom_view_exists"] is True
    assert _custom_action(window).isEnabled()
    window._set_view_preset("Custom")
    assert _visible_order(window) == ["criticality", "package_name", "play_title"]


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
