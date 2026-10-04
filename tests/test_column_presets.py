from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QInputDialog, QPushButton

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.ui import column_presets, named_custom_views, table_layout
from playstore_app_audit.ui.main_window import MainWindow
from playstore_app_audit.ui.table_window import TABLE_SCHEMA_VERSION

CUSTOM_KEYS = (
    "custom_view_layouts",
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


def _ordinary_visual_order(window: MainWindow) -> list[str]:
    return [
        column
        for column in _visual_order(window)
        if column not in column_presets.CUSTOM_AUTOMATIC_COLUMNS
    ]


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
    return next(
        (action for action in window.view_preset_actions if action.data() == "Custom"),
        getattr(window, "customize_view_action"),
    )


def _seed_named_view(
    settings: dict[str, object],
    *,
    family: column_presets.CustomLayoutFamily = column_presets.CustomLayoutFamily.PHONE_APP_LIST,
    name: str = "Custom 1",
    columns: list[str] | None = None,
    order: list[str] | None = None,
    widths: dict[str, int] | None = None,
) -> str:
    selected = columns or ["criticality", "package_name", "play_title"]
    layouts, view_id = named_custom_views.create_view(
        settings["custom_view_layouts"],
        family.value,
        name=name,
        columns=selected,
        order=order or list(selected),
        widths=widths or {},
        activate=True,
    )
    settings["custom_view_layouts"] = layouts
    settings["custom_view_exists"] = True
    return view_id


def _active_id_for_test(settings: dict[str, object], family: str) -> str:
    active = named_custom_views.active_view(settings["custom_view_layouts"], family)
    return str(active["id"]) if active is not None else ""


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
        assert fresh["view_preset"] == "Basic"
        assert fresh["custom_view_exists"] is False
        assert next(action for action in first.view_preset_actions if action.text() == "Basic").isChecked()
        assert not [action for action in first.view_preset_actions if action.data() == "Custom"]
        assert first.customize_view_action.isEnabled()
    finally:
        first.close()
        app.processEvents()

    restarted = MainWindow()
    restarted.show()
    app.processEvents()
    try:
        second = state.load_settings()
        assert second["view_preset"] == "Basic"
        assert second["custom_view_exists"] is False
        assert next(action for action in restarted.view_preset_actions if action.text() == "Basic").isChecked()
        assert not [action for action in restarted.view_preset_actions if action.data() == "Custom"]
        assert restarted.customize_view_action.isEnabled()
    finally:
        restarted.close()
        app.processEvents()

def test_column_preset_naming_and_custom_starts_enabled(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    window = create_window()

    assert window.view_presets_menu.title() == "Column Preset"
    assert [action.text() for action in window.view_preset_actions] == [
        "Basic",
        "Source Details",
        "Technical",
    ]
    assert window.customize_view_action.text() == "Customize View…"
    assert window.customize_view_action.isEnabled()
    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_exists"] is False
    assert named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    ) == []
    assert window.model._icons_enabled is True

def test_existing_custom_action_restores_gates_and_opens_editor(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    view_id = _seed_named_view(settings)
    settings.update(
        {
            "view_preset": "Basic",
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window = create_window()
    window.source_mode = "device"
    opened: list[None] = []
    monkeypatch.setattr(window, "_show_display_settings", lambda: opened.append(None))

    action = next(
        action
        for action in window.view_preset_actions
        if str(action.property("customViewId")) == view_id
    )
    action.trigger()

    assert opened == []
    assert settings["view_preset"] == "Custom"
    assert action.isChecked()
    assert {"change", "device_change"}.issubset(set(_visible_order(window)))

def test_new_custom_action_cancel_or_close_keeps_builtin_and_creates_nothing(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    dismissal: str,
) -> None:
    settings, create_window = window_store
    window = create_window()
    before = deepcopy(settings["custom_view_layouts"])

    def dismiss(dialog: QDialog) -> int:
        if dismissal == "close":
            dialog.close()
            return dialog.result()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", dismiss)
    window.customize_view_action.trigger()

    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_exists"] is False
    assert settings["custom_view_layouts"] == before
    assert next(
        action for action in window.view_preset_actions if action.text() == "Basic"
    ).isChecked()
    assert not [action for action in window.view_preset_actions if action.data() == "Custom"]

def test_new_custom_action_save_creates_and_activates_ordinary_custom_base(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    settings["view_preset"] = "Source Details"
    window = create_window()
    expected_ordinary = set(_visible_order(window)) - {"change", "device_change"}

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *_args, **_kwargs: ("Review", True),
    )

    def create_and_accept(dialog: QDialog) -> int:
        checked = {
            check.objectName().removeprefix("CustomColumnCheck_")
            for check in dialog.findChildren(QCheckBox)
            if check.objectName().startswith("CustomColumnCheck_") and check.isChecked()
        }
        assert checked == expected_ordinary - {"criticality", "package_name"}
        button = dialog.findChild(QPushButton, "NewNamedViewButton")
        assert button is not None
        button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", create_and_accept)
    window.customize_view_action.trigger()

    assert settings["view_preset"] == "Custom"
    assert settings["custom_view_exists"] is True
    views = named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert [view["name"] for view in views] == ["Review"]
    assert set(views[0]["columns"]) == expected_ordinary
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(
        views[0]["columns"]
    )
    assert next(
        action for action in window.view_preset_actions if action.data() == "Custom"
    ).isChecked()

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
        assert named_custom_views.view_records(
            settings["custom_view_layouts"], "phone_app_list"
        ) == []
        for logical, column in enumerate(window.model.columns):
            if window.table.isColumnHidden(logical):
                continue
            assert window.table.columnWidth(logical) == table_layout.default_column_width(
                window.table, column
            )

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
    window.table.setColumnWidth(package, canonical_widths["package_name"] + 37)
    app.processEvents()

    assert settings["view_preset"] == preset
    assert named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    ) == []

    window._set_view_preset(preset)
    assert _visible_order(window) == canonical_visible
    assert _visual_order(window) == canonical_order
    assert _widths(window) == canonical_widths

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

    assert settings["view_preset"] == "Basic"
    assert named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    ) == []

def test_manual_layout_capture_keeps_history_out_of_custom_base(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    view_id = _seed_named_view(
        settings,
        columns=["criticality", "package_name", "play_title"],
    )
    settings.update(
        {
            "view_preset": "Custom",
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window = create_window()
    window.source_mode = "device"
    window._apply_column_visibility(reset_order=False)
    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, window.table.columnWidth(package) + 17)
    app.processEvents()

    assert settings["view_preset"] == "Custom"
    active = named_custom_views.active_view(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert active is not None and active["id"] == view_id
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(active["columns"])
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(active["order"])
    assert {"change", "device_change"}.issubset(set(_visible_order(window)))

def test_customize_view_visibility_change_creates_custom(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    window = create_window()
    before = deepcopy(settings["custom_view_layouts"])

    def hide_notes(dialog: QDialog) -> int:
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        assert notes is not None and notes.isChecked()
        notes.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", hide_notes)
    window._show_display_settings()
    app.processEvents()

    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_layouts"] == before
    assert "notes" in _visible_order(window)

def test_customize_view_automatic_columns_reflect_current_context(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    source_mode: str,
    master: bool,
    store: bool,
    device: bool,
    expected: set[str],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "changes_history_enabled": master,
            "compare_previous": store,
            "inventory_history_enabled": device,
        }
    )
    window = create_window()
    window.source_mode = source_mode

    def inspect(dialog: QDialog) -> int:
        checked: set[str] = set()
        for key in (
            "criticality",
            "package_name",
            "change",
            "device_change",
            "local_apk_version_comparison",
        ):
            check = dialog.findChild(QCheckBox, f"AutomaticColumnCheck_{key}")
            assert check is not None
            assert not check.isEnabled()
            if check.isChecked():
                checked.add(key)
        assert checked == expected
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._show_display_settings()


@pytest.mark.parametrize("source_mode", ["device", "local_apk"])
def test_customize_view_save_cannot_remove_applicable_automatic_columns(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    source_mode: str,
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name", "play_title"],
            "custom_view_order": ["criticality", "package_name", "play_title"],
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window = create_window()
    window.source_mode = source_mode

    def clear_every_checkbox(dialog: QDialog) -> int:
        for check in dialog.findChildren(QCheckBox):
            check.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", clear_every_checkbox)
    window._show_display_settings()

    visible = set(_visible_order(window))
    expected = (
        {"criticality", "package_name", "local_apk_version_comparison"}
        if source_mode == "local_apk"
        else {"criticality", "package_name", "change", "device_change"}
    )
    assert visible == expected
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(
        settings["custom_view_columns"]  # type: ignore[arg-type]
    )
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(
        settings["custom_view_order"]  # type: ignore[arg-type]
    )


def test_restoring_custom_does_not_persist_recursively(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    view_id = _seed_named_view(
        settings,
        columns=["criticality", "package_name", "play_title"],
        widths={"package_name": 343},
    )
    settings["view_preset"] = "Custom"
    window = create_window()
    package = window.model.columns.index("package_name")
    assert window.table.columnWidth(package) == 343
    saved_custom = _custom_snapshot(settings)
    window._set_view_preset("Source Details")

    persist_calls: list[bool] = []
    original_persist = window._persist_current_custom_layout

    def track_persist(*, activate: bool = True) -> bool:
        persist_calls.append(activate)
        return original_persist(activate=activate)

    monkeypatch.setattr(window, "_persist_current_custom_layout", track_persist)
    assert window._select_custom_view(view_id)
    app.processEvents()

    assert persist_calls == []
    assert _custom_snapshot(settings) == saved_custom
    assert window.table.columnWidth(package) == 343

def test_manual_order_width_and_customize_visibility_round_trip(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    view_id = _seed_named_view(
        settings,
        columns=["criticality", "package_name", "play_title", "notes"],
    )
    settings["view_preset"] = "Custom"
    window = create_window()
    package = window.model.columns.index("package_name")
    title = window.model.columns.index("play_title")
    window.table.setColumnWidth(package, 333)
    header = window.table.horizontalHeader()
    header.moveSection(header.visualIndex(title), 0)
    app.processEvents()

    def hide_notes(dialog: QDialog) -> int:
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        assert notes is not None and notes.isChecked()
        notes.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", hide_notes)
    window._show_display_settings()
    app.processEvents()

    active = named_custom_views.active_view(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert active is not None and active["id"] == view_id
    assert "notes" not in active["columns"]
    assert active["widths"]["package_name"] == 333
    expected_visible = _visible_order(window)
    expected_widths = _widths(window)

    window._set_view_preset("Source Details")
    assert window._select_custom_view(view_id)

    assert _visible_order(window) == expected_visible
    assert _widths(window) == expected_widths

def test_custom_layout_survives_refresh_sort_filter_and_restart(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    view_id = _seed_named_view(
        settings,
        name="Technical Review",
        columns=[
            "criticality",
            "package_name",
            "play_title",
            "health_score",
        ],
        order=["play_title", "criticality", "package_name", "health_score"],
        widths={"package_name": 347, "health_score": 140},
    )
    settings["view_preset"] = "Custom"
    first = create_window()
    expected = _custom_snapshot(settings)
    expected_visible = _visible_order(first)
    expected_widths = _widths(first)
    package = first.model.columns.index("package_name")

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
    first.close()
    app.processEvents()

    restarted = create_window()
    assert settings["view_preset"] == "Custom"
    assert _active_id_for_test(settings, "phone_app_list") == view_id
    assert _visible_order(restarted) == expected_visible
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
    _visible, legacy_order, _widths_by_name, legacy_header = first._current_table_layout()
    first.close()
    app.processEvents()

    settings.pop("custom_view_layouts", None)
    settings.pop("custom_view_layouts_migrated_v1", None)
    settings.update(
        {
            "custom_view_exists": False,
            "custom_view_columns": deepcopy(state.DEFAULT_SETTINGS.get("custom_view_columns", [])),
            "qt_header_state": legacy_header,
            "qt_header_schema_version": TABLE_SCHEMA_VERSION,
            "view_preset": "Basic",
        }
    )

    migrated = create_window()
    assert settings["view_preset"] == "Custom"
    views = named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert len(views) == 1 and views[0]["name"] == "Custom 1"
    assert migrated.table.columnWidth(package) == 361
    applicable = column_presets.custom_family_user_columns(
        column_presets.CustomLayoutFamily.PHONE_APP_LIST
    )
    assert [
        column for column in _ordinary_visual_order(migrated) if column in applicable
    ] == [
        column
        for column in legacy_order
        if column not in column_presets.CUSTOM_AUTOMATIC_COLUMNS
        and column in applicable
    ]
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

    settings.pop("custom_view_layouts", None)
    settings.pop("custom_view_layouts_migrated_v1", None)
    settings.update(
        {
            "custom_view_exists": False,
            "custom_view_columns": deepcopy(state.DEFAULT_SETTINGS.get("custom_view_columns", [])),
            "qt_header_state": default_header,
            "view_preset": "Basic",
        }
    )

    restarted = create_window()

    assert settings["view_preset"] == "Basic"
    assert named_custom_views.view_records(
        settings["custom_view_layouts"], "phone_app_list"
    ) == []
    assert not [action for action in restarted.view_preset_actions if action.data() == "Custom"]
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


@pytest.mark.parametrize("preset", ["Basic", "Source Details", "Technical", "Custom"])
@pytest.mark.parametrize("source_mode", ["file", "device", "local_apk"])
@pytest.mark.parametrize(
    ("master", "store", "device"),
    [
        (True, True, False),
        (True, False, True),
        (True, True, True),
        (False, True, True),
    ],
)
def test_history_columns_are_contextual_across_presets_sources_and_gates(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    preset: str,
    source_mode: str,
    master: bool,
    store: bool,
    device: bool,
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": preset,
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name", "play_title"],
            "custom_view_order": ["criticality", "package_name", "play_title"],
            "changes_history_enabled": master,
            "compare_previous": store,
            "inventory_history_enabled": device,
        }
    )
    window = create_window()
    window.source_mode = source_mode
    window._apply_column_visibility(reset_order=False)
    visible = set(_visible_order(window))

    assert ("change" in visible) is (master and store and source_mode != "local_apk")
    assert ("device_change" in visible) is (
        master and device and source_mode == "device"
    )
    if preset == "Custom":
        assert settings["custom_view_columns"] == [
            "criticality",
            "package_name",
            "play_title",
        ]


def test_custom_visibility_is_independent_of_activation_event_order(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Basic",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name", "play_title"],
            "custom_view_order": ["criticality", "package_name", "play_title"],
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    state_then_custom = create_window()
    state_then_custom.source_mode = "device"
    state_then_custom._apply_column_visibility(reset_order=False)
    state_then_custom._set_view_preset("Custom")
    first_visibility = set(_visible_order(state_then_custom))

    settings["view_preset"] = "Basic"
    custom_then_state = create_window()
    custom_then_state._set_view_preset("Custom")
    custom_then_state.source_mode = "device"
    custom_then_state._apply_column_visibility(reset_order=False)
    second_visibility = set(_visible_order(custom_then_state))

    assert first_visibility == second_visibility
    assert {"change", "device_change"}.issubset(first_visibility)


def test_custom_overlay_positioning_preserves_user_order_widths_and_settings(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": [
                "criticality",
                "package_name",
                "play_title",
                "notes",
            ],
            "custom_view_order": [
                "play_title",
                "criticality",
                "package_name",
                "notes",
            ],
            "custom_view_widths": {
                "play_title": 287,
                "criticality": 173,
                "package_name": 331,
                "notes": 245,
            },
            "changes_history_enabled": True,
            "compare_previous": False,
            "inventory_history_enabled": False,
        }
    )
    window = create_window()
    window.source_mode = "device"
    window._apply_column_visibility(reset_order=False)
    ordinary_columns = {"play_title", "criticality", "package_name", "notes"}
    ordinary_order = [
        column for column in _visible_order(window) if column in ordinary_columns
    ]
    ordinary_widths = {
        column: window.table.columnWidth(window.model.columns.index(column))
        for column in ordinary_columns
    }
    custom_state = _custom_snapshot(settings)

    window._save_changes_history_settings(True, True, True)

    visible = _visible_order(window)
    store_status = visible.index("criticality")
    assert visible[store_status + 1 : store_status + 3] == ["change", "device_change"]
    assert [column for column in visible if column in ordinary_columns] == ordinary_order
    assert {
        column: window.table.columnWidth(window.model.columns.index(column))
        for column in ordinary_columns
    } == ordinary_widths
    assert _custom_snapshot(settings) == custom_state

    window._save_changes_history_settings(True, False, True)
    visible = _visible_order(window)
    assert visible[visible.index("criticality") + 1] == "device_change"
    assert "change" not in visible
    window._save_changes_history_settings(False, True, True)
    assert not {"change", "device_change"}.intersection(_visible_order(window))
    window._save_changes_history_settings(True, True, True)

    window.source_mode = "file"
    window._apply_established_source_defaults()
    visible = _visible_order(window)
    assert visible[visible.index("criticality") + 1] == "change"
    assert "device_change" not in visible
    window.source_mode = "device"
    window._apply_established_source_defaults()
    positioned = _visual_order(window)
    window._apply_column_visibility(reset_order=False)
    assert _visual_order(window) == positioned
    window.source_mode = "local_apk"
    window._apply_established_source_defaults()
    visible = _visible_order(window)
    assert visible[:2] == ["local_apk_version_comparison", "criticality"]
    assert not {"change", "device_change"}.intersection(visible)
    positioned = _visual_order(window)
    window._apply_column_visibility(reset_order=False)
    assert _visual_order(window) == positioned
    window.source_mode = "file"
    window._apply_established_source_defaults()

    assert _custom_snapshot(settings) == custom_state
    assert "local_apk_version_comparison" not in _visible_order(window)
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(
        settings["custom_view_columns"]  # type: ignore[arg-type]
    )
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(
        settings["custom_view_order"]  # type: ignore[arg-type]
    )
    assert [
        column for column in _visible_order(window) if column in ordinary_columns
    ] == ordinary_order
    assert {
        column: window.table.columnWidth(window.model.columns.index(column))
        for column in ordinary_columns
    } == ordinary_widths


def test_legacy_custom_history_fields_load_without_rewrite_and_normalize_on_save(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    legacy_columns = [
        "criticality",
        "change",
        "device_change",
        "local_apk_version_comparison",
        "package_name",
        "play_title",
    ]
    settings.pop("custom_view_layouts", None)
    settings.pop("custom_view_layouts_migrated_v1", None)
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": list(legacy_columns),
            "custom_view_order": list(legacy_columns),
            "changes_history_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
        }
    )
    window = create_window()
    window.source_mode = "device"
    window._apply_column_visibility(reset_order=False)
    assert {"change", "device_change"}.issubset(set(_visible_order(window)))

    active = named_custom_views.active_view(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert active is not None
    assert active["columns"] == ["criticality", "package_name", "play_title"]
    assert not column_presets.CUSTOM_CONTEXTUAL_COLUMNS.intersection(active["order"])

    def accept_without_history_checks(dialog: QDialog) -> int:
        assert dialog.findChild(QCheckBox, "CustomColumnCheck_change") is None
        assert dialog.findChild(QCheckBox, "CustomColumnCheck_device_change") is None
        assert dialog.findChild(
            QCheckBox, "CustomColumnCheck_local_apk_version_comparison"
        ) is None
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept_without_history_checks)
    window._show_display_settings()

    saved = named_custom_views.active_view(
        settings["custom_view_layouts"], "phone_app_list"
    )
    assert saved is not None
    assert saved["columns"] == ["criticality", "package_name", "play_title"]
    assert {"change", "device_change"}.issubset(set(_visible_order(window)))

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
    malformed = {
        "schema_version": 2,
        "phone_app_list": {"active_view_id": "bad", "views": "not-a-list"},
        "local_apk": {"active_view_id": "", "views": []},
        "opaque": {"preserve": True},
    }
    settings.update(
        {
            "view_preset": "Custom",
            "custom_view_layouts": deepcopy(malformed),
            "custom_view_layouts_migrated_v1": False,
            "show_app_icons": False,
        }
    )
    window = create_window()

    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_layouts"] == malformed
    assert not [action for action in window.view_preset_actions if action.data() == "Custom"]
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
