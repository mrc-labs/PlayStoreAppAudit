from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QInputDialog,
    QMessageBox,
    QPushButton,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.domain import named_custom_views
from playstore_app_audit.ui.column_presets import (
    CustomLayoutFamily,
    custom_family_user_columns,
    visible_columns,
)
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


def _named_actions(window: MainWindow) -> list[object]:
    return [action for action in window.view_preset_actions if action.data() == "Custom"]


def _builtin(window: MainWindow, name: str) -> object:
    return next(action for action in window.view_preset_actions if action.data() == name)


def _add_view(
    settings: dict[str, object],
    family: CustomLayoutFamily,
    *,
    name: str,
    columns: list[str],
    order: list[str] | None = None,
    widths: dict[str, int] | None = None,
    activate: bool = True,
) -> str:
    layouts = settings["custom_view_layouts"]
    updated, view_id = named_custom_views.create_view(
        layouts,
        family.value,
        name=name,
        columns=columns,
        order=order or columns,
        widths=widths or {},
        activate=activate,
    )
    settings["custom_view_layouts"] = updated
    return view_id


def _active_id(settings: dict[str, object], family: CustomLayoutFamily) -> str:
    active = named_custom_views.active_view(settings["custom_view_layouts"], family.value)
    return str(active["id"]) if active is not None else ""


def test_v1_family_layouts_migrate_independently_to_custom_1(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    settings.update(
        {
            "custom_view_layouts_migrated_v1": False,
            "view_preset": "Custom",
            "custom_view_layouts": {
                "schema_version": 1,
                "phone_app_list": {
                    "exists": True,
                    "columns": ["criticality", "package_name", "play_title"],
                    "order": ["play_title", "criticality", "package_name"],
                    "widths": {"package_name": 319},
                },
                "local_apk": {
                    "exists": True,
                    "columns": [
                        "criticality",
                        "package_name",
                        "local_apk_file_name",
                    ],
                    "order": [
                        "local_apk_file_name",
                        "criticality",
                        "package_name",
                    ],
                    "widths": {"local_apk_file_name": 411},
                },
            },
        }
    )

    window = create_window()

    layouts = settings["custom_view_layouts"]
    assert isinstance(layouts, dict)
    assert layouts["schema_version"] == 2
    phone = named_custom_views.view_records(layouts, "phone_app_list")
    local = named_custom_views.view_records(layouts, "local_apk")
    assert len(phone) == len(local) == 1
    assert phone[0]["name"] == local[0]["name"] == "Custom 1"
    assert phone[0]["id"] != local[0]["id"]
    assert phone[0]["columns"] == ["criticality", "package_name", "play_title"]
    assert local[0]["columns"] == [
        "criticality",
        "package_name",
        "local_apk_file_name",
    ]
    assert settings["custom_view_layouts_migrated_v1"] is True
    assert set(_visible(window)) == {"criticality", "package_name", "play_title"}


@pytest.mark.parametrize("family", list(CustomLayoutFamily))
@pytest.mark.parametrize("valid", [True, False])
def test_v1_single_family_migration_is_one_time_and_restores_after_source_switch(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    family: CustomLayoutFamily,
    valid: bool,
) -> None:
    settings, create_window = window_store
    extra = "installed_version" if family is CustomLayoutFamily.PHONE_APP_LIST else "local_apk_file_name"
    sibling = CustomLayoutFamily.LOCAL_APK if family is CustomLayoutFamily.PHONE_APP_LIST else CustomLayoutFamily.PHONE_APP_LIST
    columns = ["criticality", "package_name", extra, "play_category"]
    order = [extra, "criticality", "package_name", "play_category"]
    settings.update({
        "view_preset": "Custom",
        "custom_view_layouts_migrated_v1": False,
        "custom_view_layouts": {
            "schema_version": 1,
            family.value: {"exists": True, "columns": columns if valid else "bad", "order": order, "widths": {extra: 317}},
            sibling.value: {"exists": False, "columns": [], "order": [], "widths": {}},
        },
    })
    first = create_window()
    layouts = settings["custom_view_layouts"]
    assert named_custom_views.view_records(layouts, sibling.value) == []
    views = named_custom_views.view_records(layouts, family.value)
    assert len(views) == int(valid)
    if valid:
        assert views[0]["name"] == "Custom 1"
        assert views[0]["columns"] == columns
        assert views[0]["order"][:4] == order
        assert views[0]["widths"] == {extra: 317}
        assert layouts[family.value]["active_view_id"] == views[0]["id"]
    before = deepcopy(layouts)
    first.close()
    restarted = create_window()
    restarted.source_mode = "device" if family is CustomLayoutFamily.PHONE_APP_LIST else "local_apk"
    restarted._apply_established_source_defaults()
    assert settings["custom_view_layouts"] == before
    assert settings["view_preset"] == "Custom"
    if valid:
        assert extra in _visible(restarted)
        assert restarted.table.columnWidth(restarted.model.columns.index(extra)) == 317
    else:
        assert _builtin(restarted, "Basic").isChecked()


@pytest.mark.parametrize(
    "raw_layouts",
    [
        None,
        {"schema_version": 1},
        {"schema_version": 1, "phone_app_list": [], "local_apk": {}},
        {
            "schema_version": 3,
            "phone_app_list": {"opaque": {"keep": True}},
            "local_apk": {},
        },
        {
            "schema_version": "2",
            "phone_app_list": {"opaque": {"keep": True}},
            "local_apk": {},
        },
        {
            "schema_version": 2,
            "phone_app_list": {"active_view_id": "", "views": "bad"},
            "local_apk": {"active_view_id": "", "views": []},
            "future_top_level": ["preserve"],
        },
    ],
)
def test_future_or_malformed_layout_state_is_preserved_without_rewrite(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    raw_layouts: object,
) -> None:
    settings, create_window = window_store
    expected = deepcopy(raw_layouts)
    settings.update(
        {
            "custom_view_layouts": deepcopy(raw_layouts),
            "custom_view_layouts_migrated_v1": False,
            "view_preset": "Custom",
        }
    )

    window = create_window()
    window.source_mode = "device"
    window._apply_established_source_defaults()

    assert settings["custom_view_layouts"] == expected
    assert settings["custom_view_layouts_migrated_v1"] is False
    assert _visible(window) == visible_columns(
        "Basic",
        "device",
        compare_previous=False,
        device_inventory_history=False,
        health_score_enabled=False,
    )
    assert _builtin(window, "Basic").isChecked()
    assert not window._persist_current_custom_layout()


def test_pristine_source_switch_and_manual_header_change_do_not_create_view(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    window = create_window()

    for source in ("device", "local_apk", "file", "device"):
        window.source_mode = source
        window._apply_established_source_defaults()

    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, window.table.columnWidth(package) + 19)
    app.processEvents()

    layouts = settings["custom_view_layouts"]
    assert named_custom_views.view_records(layouts, "phone_app_list") == []
    assert named_custom_views.view_records(layouts, "local_apk") == []
    assert settings["view_preset"] == "Basic"


def test_menu_lists_only_named_views_for_active_family(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    phone_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Phone Review",
        columns=["criticality", "package_name", "play_title", "play_category"],
    )
    _add_view(
        settings,
        CustomLayoutFamily.LOCAL_APK,
        name="APK Review",
        columns=["criticality", "package_name", "local_apk_file_name"],
    )
    settings["view_preset"] = "Custom"

    window = create_window()
    named = _named_actions(window)
    assert [action.text() for action in named] == ["Phone Review"]
    assert str(named[0].property("customViewId")) == phone_id
    assert named[0].isChecked()

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()
    named = _named_actions(window)
    assert [action.text() for action in named] == ["APK Review"]


def test_missing_active_view_for_target_family_falls_back_to_basic_without_mutation(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    phone_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Phone",
        columns=["criticality", "package_name", "play_title"],
    )
    settings["view_preset"] = "Custom"
    before = deepcopy(settings["custom_view_layouts"])

    window = create_window()
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone_id

    window.source_mode = "local_apk"
    window._apply_established_source_defaults()

    assert _visible(window) == visible_columns(
        "Basic",
        "local_apk",
        compare_previous=False,
        device_inventory_history=False,
        health_score_enabled=False,
    )
    assert _builtin(window, "Basic").isChecked()
    assert settings["custom_view_layouts"] == before

    window.source_mode = "device"
    window._apply_established_source_defaults()
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == phone_id
    assert [action.text() for action in _named_actions(window)] == ["Phone"]


def test_selecting_named_view_applies_it_and_survives_restart(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    first_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Compact",
        columns=["criticality", "package_name", "play_title"],
        order=["play_title", "criticality", "package_name"],
        widths={"package_name": 333},
    )
    second_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Category",
        columns=["criticality", "package_name", "play_category"],
        order=["play_category", "criticality", "package_name"],
        widths={"play_category": 177},
    )
    settings["custom_view_layouts"] = named_custom_views.select_view(
        settings["custom_view_layouts"],
        CustomLayoutFamily.PHONE_APP_LIST.value,
        first_id,
    )
    settings["view_preset"] = "Custom"

    first = create_window()
    assert set(_visible(first)) == {"criticality", "package_name", "play_title"}
    assert first._select_custom_view(second_id)
    assert set(_visible(first)) == {"criticality", "package_name", "play_category"}
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == second_id
    first.close()
    app.processEvents()

    restarted = create_window()
    assert set(_visible(restarted)) == {
        "criticality",
        "package_name",
        "play_category",
    }
    assert [action.text() for action in _named_actions(restarted)] == [
        "Compact",
        "Category",
    ]
    assert next(
        action
        for action in _named_actions(restarted)
        if str(action.property("customViewId")) == second_id
    ).isChecked()


def test_manual_header_capture_updates_only_active_named_view(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    view_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Resizable",
        columns=["criticality", "package_name", "play_title"],
        widths={"package_name": 300},
    )
    settings["view_preset"] = "Custom"

    window = create_window()
    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, 377)
    app.processEvents()

    active = named_custom_views.active_view(
        settings["custom_view_layouts"], CustomLayoutFamily.PHONE_APP_LIST.value
    )
    assert active is not None and active["id"] == view_id
    assert active["widths"]["package_name"] == 377
    assert len(
        named_custom_views.view_records(
            settings["custom_view_layouts"], CustomLayoutFamily.PHONE_APP_LIST.value
        )
    ) == 1


def test_app_list_hides_phone_only_columns_without_rewriting_shared_view(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    columns = [
        "criticality",
        "package_name",
        "play_title",
        "installed_version",
        "installer_source",
    ]
    view_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Shared",
        columns=columns,
        order=list(columns),
        widths={"installed_version": 181},
    )
    settings["view_preset"] = "Custom"
    before = deepcopy(settings["custom_view_layouts"])

    window = create_window()
    window.source_mode = "file"
    window._apply_established_source_defaults()

    assert "installed_version" not in _visible(window)
    assert "installer_source" not in _visible(window)
    assert settings["custom_view_layouts"] == before
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == view_id

    # App List manual capture and editor save must retain Phone-only fields.
    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, 337)
    monkeypatch.setattr(QDialog, "exec", lambda _dialog: QDialog.DialogCode.Accepted)
    window._show_display_settings()
    window.source_mode = "device"
    window._apply_established_source_defaults()
    assert "installed_version" in _visible(window)
    assert "installer_source" in _visible(window)
    assert window.table.columnWidth(package) == 337
    assert window.table.columnWidth(window.model.columns.index("installed_version")) == 181


def test_named_view_preserves_play_store_category_as_user_owned_field(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Category",
        columns=["criticality", "package_name", "play_category"],
    )
    settings["view_preset"] = "Custom"

    window = create_window()
    assert "play_category" in _visible(window)
    assert "play_category" in custom_family_user_columns(
        CustomLayoutFamily.PHONE_APP_LIST
    )


def test_builtin_header_changes_do_not_modify_remembered_named_view(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    app: QApplication,
) -> None:
    settings, create_window = window_store
    view_id = _add_view(
        settings,
        CustomLayoutFamily.PHONE_APP_LIST,
        name="Remembered",
        columns=["criticality", "package_name", "play_title"],
        widths={"package_name": 321},
    )
    settings["view_preset"] = "Basic"
    before = deepcopy(settings["custom_view_layouts"])

    window = create_window()
    package = window.model.columns.index("package_name")
    window.table.setColumnWidth(package, window.table.columnWidth(package) + 31)
    app.processEvents()

    assert settings["view_preset"] == "Basic"
    assert settings["custom_view_layouts"] == before
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == view_id


@pytest.mark.parametrize("rename", [False, True])
def test_editor_selection_preserves_selected_order_widths_and_checkbox_drafts(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    rename: bool,
) -> None:
    settings, create_window = window_store
    target = _add_view(
        settings, CustomLayoutFamily.PHONE_APP_LIST, name="Target",
        columns=["criticality", "package_name", "play_category"],
        order=["criticality", "play_category", "package_name"],
        widths={"play_category": 271, "package_name": 381},
    )
    other = _add_view(
        settings, CustomLayoutFamily.PHONE_APP_LIST, name="Displayed",
        columns=["criticality", "package_name", "play_title"],
        widths={"package_name": 222},
    )
    settings["view_preset"] = "Custom"
    window = create_window()
    before = deepcopy(settings["custom_view_layouts"])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Renamed", True))

    def edit(dialog: QDialog) -> int:
        combo = dialog.findChild(QComboBox, "SavedViewCombo")
        assert combo is not None
        combo.setCurrentIndex(combo.findData(target))
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        assert notes is not None and not notes.isChecked()
        notes.setChecked(True)
        if rename:
            button = dialog.findChild(QPushButton, "RenameNamedViewButton")
            assert button is not None
            button.click()
            assert notes.isChecked()
        assert settings["custom_view_layouts"] == before
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", edit)
    window._show_display_settings()
    active = named_custom_views.active_view(settings["custom_view_layouts"], "phone_app_list")
    assert active is not None and active["id"] == target
    assert "notes" in active["columns"]
    assert active["order"][:3] == ["criticality", "play_category", "package_name"]
    assert active["widths"]["play_category"] == 271
    assert active["widths"]["package_name"] == 381
    assert window.table.columnWidth(window.model.columns.index("play_category")) == 271
    assert _visible(window)[:3] == ["criticality", "play_category", "package_name"]
    assert window._custom_view_by_id(settings, other) == window._custom_view_by_id(
        {"custom_view_layouts": before}, other
    )


@pytest.mark.parametrize("preset", ["Custom", "Technical"])
@pytest.mark.parametrize("delete_active", [False, True])
def test_editor_delete_falls_back_only_when_removing_active_id(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    preset: str,
    delete_active: bool,
) -> None:
    settings, create_window = window_store
    inactive = _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="Inactive",
                         columns=["criticality", "package_name", "play_title"])
    active = _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="Active",
                       columns=["criticality", "package_name", "play_category"])
    _add_view(settings, CustomLayoutFamily.LOCAL_APK, name="APK",
              columns=["criticality", "package_name", "local_apk_file_name"])
    settings["view_preset"] = preset
    window = create_window()
    sibling = deepcopy(settings["custom_view_layouts"]["local_apk"])
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

    def delete(dialog: QDialog) -> int:
        combo = dialog.findChild(QComboBox, "SavedViewCombo")
        assert combo is not None
        combo.setCurrentIndex(combo.findData(active if delete_active else inactive))
        button = dialog.findChild(QPushButton, "DeleteNamedViewButton")
        assert button is not None
        button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", delete)
    window._show_display_settings()
    assert settings["custom_view_layouts"]["local_apk"] == sibling
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == ("" if delete_active else active)
    assert settings["view_preset"] == ("Basic" if delete_active else preset)
    if delete_active:
        assert _builtin(window, "Basic").isChecked()


@pytest.mark.parametrize("dismissal", ["cancel", "close"])
@pytest.mark.parametrize("operation", ["create", "rename", "delete", "select"])
def test_editor_draft_mutations_cancel_without_any_settings_write(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    dismissal: str,
    operation: str,
) -> None:
    settings, create_window = window_store
    first = _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="First",
                      columns=["criticality", "package_name", "play_title"])
    _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="Second",
              columns=["criticality", "package_name", "play_category"])
    settings["view_preset"] = "Custom"
    window = create_window()
    before = deepcopy(settings)
    monkeypatch.setattr(state, "save_settings", lambda _values: pytest.fail("Draft persisted"))
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Draft", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

    def dismiss(dialog: QDialog) -> int:
        combo = dialog.findChild(QComboBox, "SavedViewCombo")
        assert combo is not None
        combo.setCurrentIndex(combo.findData(first))
        notes = dialog.findChild(QCheckBox, "CustomColumnCheck_notes")
        assert notes is not None
        notes.setChecked(True)
        icons = dialog.findChild(QCheckBox, "ShowAppIconsCheck")
        assert icons is not None
        icons.setChecked(not icons.isChecked())
        if operation != "select":
            button = dialog.findChild(QPushButton, {
                "create": "NewNamedViewButton", "rename": "RenameNamedViewButton", "delete": "DeleteNamedViewButton",
            }[operation])
            assert button is not None
            button.click()
        if dismissal == "close":
            dialog.close()
            return dialog.result()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", dismiss)
    window._show_display_settings()
    assert settings == before


def test_create_then_delete_draft_does_not_clear_persisted_active_view(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings, create_window = window_store
    active = _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="Active",
                       columns=["criticality", "package_name", "play_title"])
    settings["view_preset"] = "Custom"
    window = create_window()
    before = deepcopy(settings["custom_view_layouts"])
    monkeypatch.setattr(QInputDialog, "getText", lambda *_args, **_kwargs: ("Draft", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)

    def edit(dialog: QDialog) -> int:
        for name in ("NewNamedViewButton", "DeleteNamedViewButton"):
            button = dialog.findChild(QPushButton, name)
            assert button is not None
            button.click()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", edit)
    window._show_display_settings()
    assert settings["custom_view_layouts"] == before
    assert settings["view_preset"] == "Custom"
    assert _active_id(settings, CustomLayoutFamily.PHONE_APP_LIST) == active


@pytest.mark.parametrize("family,source", [
    (CustomLayoutFamily.PHONE_APP_LIST, "device"), (CustomLayoutFamily.LOCAL_APK, "local_apk"),
])
def test_editor_three_view_limit_is_family_local(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
    monkeypatch: pytest.MonkeyPatch,
    family: CustomLayoutFamily,
    source: str,
) -> None:
    settings, create_window = window_store
    for index in range(3):
        _add_view(settings, family, name=f"View {index + 1}", columns=["criticality", "package_name", "play_title"])
    window = create_window()
    window.source_mode = source
    window._apply_established_source_defaults()

    def inspect(dialog: QDialog) -> int:
        button = dialog.findChild(QPushButton, "NewNamedViewButton")
        combo = dialog.findChild(QComboBox, "SavedViewCombo")
        assert button is not None and not button.isEnabled()
        assert combo is not None and combo.count() == 4
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect)
    window._show_display_settings()
    window.source_mode = "local_apk" if source == "device" else "device"
    window._apply_established_source_defaults()

    def inspect_sibling(dialog: QDialog) -> int:
        button = dialog.findChild(QPushButton, "NewNamedViewButton")
        combo = dialog.findChild(QComboBox, "SavedViewCombo")
        assert button is not None and button.isEnabled()
        assert combo is not None and combo.count() == 1
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect_sibling)
    window._show_display_settings()


def test_local_header_capture_and_reset_preserve_sibling_and_exclude_contextual_columns(
    window_store: tuple[dict[str, object], Callable[[], MainWindow]],
) -> None:
    settings, create_window = window_store
    _add_view(settings, CustomLayoutFamily.PHONE_APP_LIST, name="Phone",
              columns=["criticality", "package_name", "play_title"])
    local_id = _add_view(settings, CustomLayoutFamily.LOCAL_APK, name="APK",
                         columns=["criticality", "package_name", "local_apk_file_name"])
    settings["view_preset"] = "Custom"
    window = create_window()
    window.source_mode = "local_apk"
    window._apply_established_source_defaults()
    phone = deepcopy(settings["custom_view_layouts"]["phone_app_list"])
    filename = window.model.columns.index("local_apk_file_name")
    header = window.table.horizontalHeader()
    header.moveSection(header.visualIndex(filename), header.visualIndex(window.model.columns.index("package_name")))
    window.table.setColumnWidth(filename, 387)
    active = named_custom_views.active_view(settings["custom_view_layouts"], "local_apk")
    assert active is not None and active["id"] == local_id
    assert active["widths"]["local_apk_file_name"] == 387
    assert "local_apk_version_comparison" not in active["columns"] + active["order"]
    assert "local_apk_version_comparison" not in active["widths"]
    window._reset_table_layout()
    assert settings["custom_view_layouts"]["phone_app_list"] == phone
    reset = named_custom_views.active_view(settings["custom_view_layouts"], "local_apk")
    assert reset is not None and reset["id"] == local_id
    assert reset["widths"]["local_apk_file_name"] != 387


def test_named_layout_disk_round_trip_preserves_uuid_and_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(state, "settings_path", lambda: tmp_path / "settings.json")
    settings = state.load_settings()
    view_id = _add_view(settings, CustomLayoutFamily.LOCAL_APK, name="APK",
                        columns=["criticality", "package_name", "play_category"],
                        order=["play_category", "criticality", "package_name"], widths={"play_category": 201})
    settings["custom_view_layouts_migrated_v1"] = True
    state.save_settings(settings)
    reloaded = state.load_settings()
    assert reloaded["custom_view_layouts"] == settings["custom_view_layouts"]
    assert _active_id(reloaded, CustomLayoutFamily.LOCAL_APK) == view_id
