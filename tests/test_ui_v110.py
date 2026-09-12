from __future__ import annotations

import inspect
import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QStackedWidget,
)

import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.json_export as json_export_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
from playstore_app_audit import __version__
from playstore_app_audit.ui import rich_help
from playstore_app_audit.ui.main_window import MainWindow

SUBTITLE = (
    "Check Android packages against Google Play, classify update risk and inspect everything in one table."
)
RESULT_EXPORTS = [
    "All CSV",
    "Visible CSV",
    "All JSON",
    "Visible JSON",
    "All HTML",
    "Visible HTML",
]


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(
    app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> MainWindow:
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    recent = tmp_path / "recent.csv"
    recent.write_text("package_name\ncom.example.app\n", encoding="utf-8")
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [str(recent)])
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def _action_texts(menu) -> list[str]:
    return [action.text() for action in menu.actions() if not action.isSeparator()]


def _action_structure(menu) -> list[str | None]:
    return [None if action.isSeparator() else action.text() for action in menu.actions()]


def test_final_main_window_has_subtitle_without_redundant_h1(window: MainWindow) -> None:
    labels = window.findChildren(QLabel)
    assert not any(label.objectName() == "Title" for label in labels)
    assert window.subtitle_label is not None
    assert window.subtitle_label.text() == SUBTITLE


def test_recent_sources_split_control_and_file_menu_stay_synchronised(
    window: MainWindow,
) -> None:
    controls = window.recent_sources_button.parentWidget().layout()
    assert controls.itemAt(0).widget() is window.choose_button
    assert controls.itemAt(1).widget() is window.recent_sources_button
    assert window.choose_button.text() == "Choose File"
    assert window.recent_sources_button.toolTip() == "Recent sources"
    assert _action_texts(window.recent_menu) == ["recent.csv"]
    assert _action_texts(window.recent_sources_button_menu) == ["recent.csv"]


def test_empty_recent_source_menus_have_disabled_placeholder(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    window._populate_recent_menu()
    for menu in (window.recent_menu, window.recent_sources_button_menu):
        actions = menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "No Recent Files"
        assert not actions[0].isEnabled()


def test_missing_recent_files_are_still_filtered(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("com.example.app\n", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    monkeypatch.setattr(
        state,
        "load_settings",
        lambda: {"recent_sources": [str(missing), str(existing)]},
    )
    assert device_insights.get_recent_sources() == [str(existing)]


def test_final_file_and_audit_menu_hierarchy(window: MainWindow) -> None:
    assert [
        action.text() for action in window.menuBar().actions() if action.menu() is not None
    ] == ["File", "Audit", "View", "Tools", "Help"]
    assert _action_structure(window.file_menu) == [
        "Choose App List…",
        "Choose Package File(s)…",
        "Choose Package Folder…",
        "Recent Sources",
        "Scan Phone",
        "Export Phone Package List…",
        None,
        "Exit",
    ]
    assert _action_structure(window.audit_menu) == [
        "Run Audit",
        "Recheck Not Found / Anomaly / Other",
        "Run with Fresh Store Results",
        None,
        "Audit Presets",
        None,
        "Export Results",
        "Clear Results",
    ]
    assert _action_structure(window.audit_export_results_menu) == [
        "All CSV",
        "Visible CSV",
        None,
        "All JSON",
        "Visible JSON",
        None,
        "All HTML",
        "Visible HTML",
    ]
    assert "Export Results" not in _action_texts(window.file_menu)
    assert "Export Phone Package List…" not in _action_texts(
        window.audit_export_results_menu
    )


def test_file_and_main_run_actions_use_same_canonical_handler(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[MainWindow] = []
    choose_calls: list[MainWindow] = []
    clear_calls: list[MainWindow] = []
    scan_calls: list[MainWindow] = []
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(MainWindow, "_start_audit", lambda self: calls.append(self))
    monkeypatch.setattr(MainWindow, "_choose_input", lambda self: choose_calls.append(self))
    monkeypatch.setattr(MainWindow, "_clear_results", lambda self: clear_calls.append(self))
    monkeypatch.setattr(MainWindow, "_scan_phone", lambda self: scan_calls.append(self))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    created.source_mode = "file"
    created.file_apps = [{"app_name": "Example", "package_name": "com.example.app"}]
    created.current_rows = [{"package_name": "com.example.app", "criticality_key": "green"}]
    created.model.set_rows(created.current_rows)
    created._sync_action_availability()
    created.choose_button.click()
    created.scan_button.click()
    created.run_button.click()
    created.clear_button.click()
    created.run_audit_action.trigger()
    created.clear_results_action.trigger()
    assert choose_calls == [created]
    assert scan_calls == [created]
    assert calls == [created, created]
    assert clear_calls == [created, created]
    created.close()
    app.processEvents()


def test_file_and_main_export_surfaces_use_the_same_handlers(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])

    def export_handler(marker: str):
        def handler(_self, *_args) -> None:
            calls.append(marker)

        return handler

    monkeypatch.setattr(MainWindow, "_export_results", export_handler("all-csv"))
    monkeypatch.setattr(
        MainWindow, "_export_visible_results", export_handler("visible-csv")
    )
    monkeypatch.setattr(MainWindow, "_export_html_report", export_handler("all-html"))
    monkeypatch.setattr(
        MainWindow, "_export_visible_html_report", export_handler("visible-html")
    )
    monkeypatch.setattr(
        json_export_ui,
        "export_window_results_json",
        lambda _window, *, visible: calls.append(
            "visible-json" if visible else "all-json"
        ),
    )

    created = MainWindow()
    created.current_rows = [{"package_name": "com.example.app"}]
    created.model.set_rows(created.current_rows)
    created._sync_action_availability()
    try:
        for menu in (created.audit_export_results_menu, created.export_button.menu()):
            for action in menu.actions():
                if not action.isSeparator():
                    action.trigger()
    finally:
        created.close()
        app.processEvents()

    expected = [
        "all-csv",
        "visible-csv",
        "all-json",
        "visible-json",
        "all-html",
        "visible-html",
    ]
    assert calls == expected * 2


def test_status_chips_are_sized_for_selected_bold_text(window: MainWindow) -> None:
    rows = [
        {"package_name": f"com.example.removed{index}", "criticality_key": "red"}
        for index in range(125)
    ]
    window.current_rows = rows
    window.model.set_rows(rows)
    window._update_summary()

    button = window.criticality_buttons["red"]
    button.setChecked(True)
    selected_font = QFont(button.font())
    selected_font.setBold(True)
    text_width = QFontMetrics(selected_font).horizontalAdvance(button.text())

    assert button.text().endswith("125")
    assert button.minimumWidth() > text_width


def test_operational_naming_density_and_icon_policy(window: MainWindow) -> None:
    assert _action_structure(window.view_menu) == [
        "Column Preset",
        "Details Panel",
        "Reset Table Layout",
        None,
        "Quick Filters",
        "Smart Queries",
        "Clear All Filters",
    ]
    assert "Old Apps" in _action_texts(window._filter_menu)
    assert "Alternative Stores" in _action_texts(window._filter_menu)

    visible_labels = [
        label.text()
        for label in window.centralWidget().findChildren(QLabel)
        if label.isVisibleTo(window.centralWidget())
    ]
    assert not any(text.startswith("Removed =") for text in visible_labels)
    assert not any(text.startswith("Tip: click headers") for text in visible_labels)

    main_action_icons = [
        window.choose_button.icon(),
        window.scan_button.icon(),
        window.export_button.icon(),
    ]
    assert all(not icon.isNull() for icon in main_action_icons)
    icon_sizes = [
        [(size.width(), size.height()) for size in icon.availableSizes()]
        for icon in main_action_icons
    ]
    assert icon_sizes[0] == icon_sizes[1] == icon_sizes[2]
    assert (32, 32) in icon_sizes[0]
    assert not window.table.wordWrap()
    assert window.all_chip.toolTip() == "Show all result classifications."
    assert window.criticality_buttons["red"].toolTip().startswith("Show apps")
    assert "sort" in window.table.horizontalHeader().toolTip()
    assert "Double-click" in window.table.toolTip()
    assert window.recent_sources_button.toolTip() == "Recent sources"
    assert window.scan_phone_options_button.toolTip() == "Phone package list options"


def test_display_and_advanced_settings_have_distinct_hierarchies(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def inspect_display(dialog: QDialog) -> int:
        assert dialog.objectName() == "DisplaySettingsDialog"
        icons = dialog.findChild(QCheckBox, "ShowAppIconsCheck")
        assert icons is not None
        assert icons.isChecked()
        assert dialog.findChild(QComboBox, "DateFormatCombo") is not None
        assert dialog.findChild(QCheckBox, "CustomColumnCheck_play_title") is not None
        assert dialog.findChild(QCheckBox, "CustomColumnCheck_change") is None
        assert dialog.findChild(QCheckBox, "CustomColumnCheck_device_change") is None
        note = dialog.findChild(QLabel, "CustomColumnsNote")
        assert note is not None
        assert note.text() == (
            "Store Status and Package Name are always included. Click Save to apply "
            "changes. Changing the column selection activates View > Column Preset > Custom."
        )
        history_note = dialog.findChild(QLabel, "CustomHistoryColumnsNote")
        assert history_note is not None
        assert history_note.text() == (
            "History columns are shown automatically when enabled in Tools > Changes & "
            "History and applicable to the current source."
        )
        scroll = dialog.findChild(QScrollArea, "CustomColumnsScrollArea")
        assert scroll is not None
        assert scroll.verticalScrollBarPolicy() is Qt.ScrollBarPolicy.ScrollBarAsNeeded
        available = dialog.screen().availableGeometry()
        assert dialog.width() <= available.width() - preferences_ui.CUSTOMIZE_VIEW_SCREEN_MARGIN
        assert dialog.height() <= available.height() - preferences_ui.CUSTOMIZE_VIEW_SCREEN_MARGIN
        assert dialog.findChild(QLineEdit, "StoreLanguageEdit") is None
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect_display)
    window._show_display_settings()

    def inspect_advanced(dialog: QDialog) -> int:
        assert dialog.objectName() == "AdvancedSettingsDialog"
        navigation = dialog.findChild(QListWidget, "AdvancedSettingsCategories")
        pages = dialog.findChild(QStackedWidget, "AdvancedSettingsPages")
        assert navigation is not None
        assert pages is not None
        assert [navigation.item(index).text() for index in range(navigation.count())] == [
            "Store & Cache",
            "Alternative Distribution",
            "Device",
            "Audit",
            "Data & Storage",
        ]
        assert [pages.widget(index).objectName() for index in range(pages.count())] == [
            "StoreCacheSettingsPage",
            "AlternativeDistributionSettingsPage",
            "DeviceSettingsPage",
            "AuditSettingsPage",
            "DataStorageSettingsPage",
        ]
        health = dialog.findChild(QCheckBox, "HealthScoreCheck")
        assert health is not None
        assert health.parentWidget().objectName() == "AuditSettingsPage"
        assert dialog.findChild(QCheckBox, "ChangesHistoryEnabledCheck") is None
        assert dialog.findChild(QCheckBox, "ComparePreviousAuditCheck") is None
        assert dialog.findChild(QCheckBox, "InventoryHistoryCheck") is None
        assert dialog.findChild(QLineEdit, "StoreLanguageEdit") is not None
        assert dialog.findChild(QCheckBox, "ShowAppIconsCheck") is None
        assert dialog.findChild(QComboBox, "DateFormatCombo") is None
        assert not dialog.findChildren(QGroupBox)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect_advanced)
    window._show_advanced_settings()


def test_customize_view_content_aware_size_fits_or_clamps_for_scrolling() -> None:
    content = QSize(700, 620)
    overhead = QSize(60, 180)

    minimum, initial = preferences_ui.customize_view_dialog_sizes(
        content, overhead, QSize(1920, 1080)
    )

    assert minimum == preferences_ui.CUSTOMIZE_VIEW_MIN_SIZE
    assert initial.width() >= content.width() + overhead.width()
    assert initial.height() == content.height() + overhead.height()

    small_screen = QSize(800, 650)
    small_minimum, small_initial = preferences_ui.customize_view_dialog_sizes(
        content, overhead, small_screen
    )
    usable_height = (
        small_screen.height() - preferences_ui.CUSTOMIZE_VIEW_SCREEN_MARGIN
    )

    assert small_minimum.height() <= usable_height
    assert small_initial.height() == usable_height
    assert small_initial.height() < content.height() + overhead.height()


def test_display_settings_save_existing_presentation_keys(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[dict[str, object]] = []
    monkeypatch.setattr(state, "load_settings", lambda: dict(window.user_settings))
    monkeypatch.setattr(
        state,
        "save_settings",
        lambda values: saved.append(dict(values)) or dict(values),
    )

    def accept_display(dialog: QDialog) -> int:
        icons = dialog.findChild(QCheckBox, "ShowAppIconsCheck")
        date_format = dialog.findChild(QComboBox, "DateFormatCombo")
        title_column = dialog.findChild(QCheckBox, "CustomColumnCheck_play_title")
        technical_column = dialog.findChild(
            QCheckBox, "CustomColumnCheck_installed_version_code"
        )
        common_group = dialog.findChild(QGroupBox, "CustomColumnsCommonGroup")
        advanced_group = dialog.findChild(QGroupBox, "CustomColumnsAdvancedGroup")
        assert icons is not None
        assert date_format is not None
        assert title_column is not None
        assert technical_column is not None
        assert common_group is not None and common_group.title() == "Common"
        assert advanced_group is not None and advanced_group.title() == "Advanced / Technical"
        for check in dialog.findChildren(QCheckBox):
            if check.objectName().startswith("CustomColumnCheck_"):
                check.setChecked(False)
        icons.setChecked(True)
        date_format.setCurrentText("DD/MM/YYYY")
        title_column.setChecked(True)
        technical_column.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept_display)
    window._show_display_settings()

    assert saved[-1]["show_app_icons"] is True
    assert saved[-1]["date_format"] == "DD/MM/YYYY"
    assert saved[-1]["custom_view_columns"] == [
        "criticality",
        "package_name",
        "play_title",
        "installed_version_code",
    ]
    assert window.model._icons_enabled is True
    assert window.status_label.text() == "Customize View settings saved"


def test_display_settings_toggle_columns_with_populated_sorted_table(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fields = {
        "notes",
        "health_score",
        "version_comparison",
        "compatibility_status",
        "play_title",
    }
    settings = dict(window.user_settings)
    settings.update(
        {
            "view_preset": "Source Details",
            "health_score_enabled": True,
            "show_app_icons": False,
            "custom_view_columns": list(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS),
        }
    )

    def load_settings() -> dict[str, object]:
        return dict(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    window.user_settings = load_settings()
    window.source_mode = "device"
    window._sync_view_preset_action("Source Details")
    window._apply_column_visibility(reset_order=False)

    rows = [
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "package_name": "com.example.alpha",
            "play_title": "Alpha",
            "play_status": "available",
            "compatibility_status": "Aging target",
            "version_comparison": "Different",
            "health_score": 72,
            "notes": "raw-alpha-note",
        },
        {
            "criticality": "Stale",
            "criticality_key": "orange",
            "package_name": "com.example.beta",
            "play_title": "Beta",
            "play_status": "available",
            "compatibility_status": "Legacy target",
            "version_comparison": "Same",
            "health_score": 41,
            "notes": "raw-beta-note",
        },
    ]
    window.current_rows = rows
    window.model.set_rows(rows)
    window.search_edit.setText("com.example")
    title_column = window.model.columns.index("play_title")
    window.table.sortByColumn(title_column, Qt.SortOrder.DescendingOrder)
    window.table.selectRow(0)
    app.processEvents()

    selected_package = window.table.currentIndex().data(Qt.ItemDataRole.UserRole)["package_name"]
    for offset, key in enumerate(sorted(fields)):
        window.table.setColumnWidth(window.model.columns.index(key), 210 + offset)
    original_widths = {
        key: window.table.columnWidth(window.model.columns.index(key)) for key in fields
    }
    layout_changes: list[None] = []
    presentation_changes: list[None] = []
    window.model.layoutChanged.connect(lambda: layout_changes.append(None))
    window.model.dataChanged.connect(lambda *_args: presentation_changes.append(None))

    desired_fields: set[str] = set()
    first_dialog = True

    def accept_display(dialog: QDialog) -> int:
        nonlocal first_dialog
        for key in fields:
            check = dialog.findChild(QCheckBox, f"CustomColumnCheck_{key}")
            assert check is not None
            if first_dialog:
                assert check.isChecked()
            check.setChecked(key in desired_fields)
        first_dialog = False
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept_display)

    window._show_display_settings()
    app.processEvents()

    assert settings["view_preset"] == "Custom"
    assert next(
        action for action in window.view_preset_actions if action.data() == "Custom"
    ).isChecked()
    assert all(window.table.isColumnHidden(window.model.columns.index(key)) for key in fields)
    assert window.proxy.rowCount() == 2
    assert window.search_edit.text() == "com.example"
    assert window.table.horizontalHeader().sortIndicatorSection() == title_column
    assert window.table.currentIndex().data(Qt.ItemDataRole.UserRole)["package_name"] == selected_package
    assert window.details_panel._row is not None
    assert window.details_panel._row["package_name"] == selected_package

    desired_fields.update(fields)
    window._show_display_settings()
    app.processEvents()

    assert all(not window.table.isColumnHidden(window.model.columns.index(key)) for key in fields)
    assert fields.issubset(set(settings["custom_view_columns"]))
    assert window.proxy.rowCount() == 2
    assert window.table.currentIndex().data(Qt.ItemDataRole.UserRole)["package_name"] == selected_package
    assert window.details_panel._row is not None
    assert window.details_panel._row["package_name"] == selected_package
    assert {
        key: window.table.columnWidth(window.model.columns.index(key)) for key in fields
    } == original_widths
    assert layout_changes == []
    assert presentation_changes


def test_display_settings_restart_keeps_checkboxes_view_and_columns_consistent(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = dict(window.user_settings)
    settings.update(
        {
            "view_preset": "Source Details",
            "health_score_enabled": True,
            "show_app_icons": False,
            "custom_view_columns": list(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS),
        }
    )

    def load_settings() -> dict[str, object]:
        return dict(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    window.user_settings = load_settings()
    window.source_mode = "device"
    window._sync_view_preset_action("Source Details")
    window._apply_column_visibility(reset_order=False)
    window.current_rows = [
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "package_name": "com.example.persisted",
            "play_title": "Persisted",
            "play_status": "available",
            "compatibility_status": "Aging target",
            "version_comparison": "Different",
            "health_score": 80,
            "notes": "raw-persisted-note",
        }
    ]
    window.model.set_rows(window.current_rows)
    app.processEvents()

    unchecked = {"notes", "play_title"}

    def save_display(dialog: QDialog) -> int:
        for key in unchecked:
            check = dialog.findChild(QCheckBox, f"CustomColumnCheck_{key}")
            assert check is not None
            assert check.isChecked()
            check.setChecked(False)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", save_display)
    window._show_display_settings()
    app.processEvents()
    window.close()
    app.processEvents()

    restarted = MainWindow()
    try:
        custom_action = next(
            action for action in restarted.view_preset_actions if action.data() == "Custom"
        )
        assert settings["view_preset"] == "Custom"
        assert custom_action.isChecked()
        for key in unchecked:
            logical = restarted.model.columns.index(key)
            assert restarted.table.isColumnHidden(logical)
        compatibility = restarted.model.columns.index("compatibility_status")
        assert not restarted.table.isColumnHidden(compatibility)

        def inspect_display(dialog: QDialog) -> int:
            for key in unchecked:
                check = dialog.findChild(QCheckBox, f"CustomColumnCheck_{key}")
                assert check is not None
                assert not check.isChecked()
            compatibility_check = dialog.findChild(
                QCheckBox, "CustomColumnCheck_compatibility_status"
            )
            assert compatibility_check is not None
            assert compatibility_check.isChecked()
            return QDialog.DialogCode.Rejected

        monkeypatch.setattr(QDialog, "exec", inspect_display)
        restarted._show_display_settings()

        restarted.current_rows = list(window.current_rows)
        restarted.model.set_rows(restarted.current_rows)
        app.processEvents()
        for key in unchecked:
            logical = restarted.model.columns.index(key)
            assert restarted.table.isColumnHidden(logical)
        assert not restarted.table.isColumnHidden(compatibility)
    finally:
        restarted.close()
        app.processEvents()


def test_advanced_settings_preserve_display_preferences(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = dict(window.user_settings)
    settings.update(
        {
            "fallback_countries": device_metadata.DEFAULT_FALLBACK_COUNTRIES,
            "show_app_icons": True,
            "date_format": "DD.MM.YYYY",
            "custom_view_columns": ["criticality", "package_name", "notes"],
        }
    )
    saved: list[dict[str, object]] = []
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(
        state,
        "save_settings",
        lambda values: saved.append(dict(values)) or dict(values),
    )
    window.current_rows = [
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "package_name": "com.example.populated",
        }
    ]
    window.model.set_rows(window.current_rows)
    layout_changes: list[None] = []
    window.model.layoutChanged.connect(lambda: layout_changes.append(None))

    def accept_advanced(dialog: QDialog) -> int:
        cache = dialog.findChild(QCheckBox, "UseIntelligentCacheCheck")
        health = dialog.findChild(QCheckBox, "HealthScoreCheck")
        assert cache is not None
        assert health is not None
        cache.setChecked(False)
        health.setChecked(True)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept_advanced)
    window._show_advanced_settings()

    assert saved[-1]["cache_enabled"] is False
    assert saved[-1]["health_score_enabled"] is True
    assert saved[-1]["show_app_icons"] is True
    assert saved[-1]["date_format"] == "DD.MM.YYYY"
    assert saved[-1]["custom_view_columns"] == ["criticality", "package_name", "notes"]
    assert layout_changes == []


def test_details_control_and_view_menu_share_modes_and_persistence(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: list[dict[str, object]] = []
    monkeypatch.setattr(state, "load_settings", lambda: dict(window.user_settings))
    monkeypatch.setattr(
        state,
        "save_settings",
        lambda values: saved.append(dict(values)) or dict(values),
    )

    assert window.details_control.text() == "Details"
    assert window.details_control.accessibleName() == "Details Panel"
    assert window.details_control.menu() is window.details_panel_menu
    assert window.details_panel_menu.menuAction() in window.view_menu.actions()
    assert set(window.details_control.position_actions) == {
        "auto",
        "right",
        "below",
        "hidden",
    }

    window.details_control.position_actions["hidden"].trigger()
    app.processEvents()
    assert window._details_panel_position == "hidden"
    assert window._details_panel_resolved_position == "hidden"
    assert window.details_panel.isHidden()
    assert window.details_control.position_actions["hidden"].isChecked()
    assert saved[-1]["details_panel_position"] == "hidden"

    window.details_control.position_actions["below"].trigger()
    app.processEvents()
    assert window._details_panel_position == "below"
    assert window.details_splitter.orientation() == Qt.Orientation.Vertical
    assert not window.details_panel.isHidden()
    assert window.details_control.position_actions["below"].isChecked()
    assert saved[-1]["details_panel_position"] == "below"


def test_details_internal_reflow_preserves_results_and_outer_layout_state(
    window: MainWindow,
    app: QApplication,
) -> None:
    rows = [
        {
            "criticality": "Stale",
            "criticality_key": "orange",
            "package_name": "com.example.alpha",
            "play_title": "Alpha",
            "play_status": "available",
            "installed_version": "1.0",
            "play_version": "2.0",
            "notes": "raw alpha note",
        },
        {
            "criticality": "Recent Update",
            "criticality_key": "green",
            "package_name": "com.example.beta",
            "play_title": "Beta",
            "play_status": "available",
            "installed_version": "2.0",
            "play_version": "2.0",
            "notes": "raw beta note",
        },
    ]
    window.current_rows = rows
    window.model.set_rows(rows)
    window.search_edit.setText("com.example")
    title_column = window.model.columns.index("play_title")
    window.table.sortByColumn(title_column, Qt.SortOrder.DescendingOrder)
    window.table.selectRow(0)
    window._set_details_panel_position("below", persist=False)
    app.processEvents()

    selected_package = window.table.currentIndex().data(Qt.ItemDataRole.UserRole)[
        "package_name"
    ]
    expected_order = [
        window.proxy.index(row, title_column).data()
        for row in range(window.proxy.rowCount())
    ]
    splitter_sizes = window.details_splitter.sizes()

    for width, expected_mode in (
        (500, "narrow"),
        (800, "wide"),
        (1180, "extra-wide"),
        (1080, "extra-wide"),
        (1079, "wide"),
    ):
        window.details_panel._update_adaptive_layout(width)
        app.processEvents()
        assert window.details_panel.content_layout_mode() == expected_mode
        assert window.current_rows == rows
        assert window.proxy.rowCount() == 2
        assert window.search_edit.text() == "com.example"
        assert [
            window.proxy.index(row, title_column).data()
            for row in range(window.proxy.rowCount())
        ] == expected_order
        assert window.table.horizontalHeader().sortIndicatorSection() == title_column
        assert (
            window.table.currentIndex().data(Qt.ItemDataRole.UserRole)["package_name"]
            == selected_package
        )
        assert window.details_panel._row is not None
        assert window.details_panel._row["package_name"] == selected_package
        assert window._details_panel_position == "below"
        assert window._details_panel_resolved_position == "below"
        assert window.details_splitter.orientation() == Qt.Orientation.Vertical
        assert window.details_splitter.sizes() == splitter_sizes


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (1100, 700, "below"),
        (1200, 760, "below"),
        (1500, 900, "right"),
        (1600, 900, "right"),
    ],
)
def test_details_auto_mode_is_responsive_at_supported_resolutions(
    window: MainWindow,
    app: QApplication,
    width: int,
    height: int,
    expected: str,
) -> None:
    window.resize(width, height)
    window.show()
    app.processEvents()
    window._set_details_panel_position("auto", persist=False)
    app.processEvents()

    expected_orientation = (
        Qt.Orientation.Horizontal if expected == "right" else Qt.Orientation.Vertical
    )
    assert window._details_panel_resolved_position == expected
    assert window.details_splitter.orientation() == expected_orientation
    assert window.details_control.isVisible()
    assert window.details_panel.isVisible()
    assert window.table.isVisible()
    assert all(size > 0 for size in window.details_splitter.sizes())


def test_main_export_button_exposes_canonical_menu_and_starts_disabled(
    window: MainWindow,
) -> None:
    assert window.export_button.text() == "Export Results"
    assert window.export_button.menu() is window._export_results_menu
    assert _action_texts(window.export_button.menu()) == RESULT_EXPORTS
    assert window.clear_button.text() == "Clear Results"
    assert not window.run_button.isEnabled()
    assert not window.export_button.isEnabled()
    assert not window.clear_button.isEnabled()
    assert _action_structure(window.tools_menu) == [
        "Advanced Settings…",
        "Changes & History…",
        None,
        "Data Maintenance…",
    ]
    assert window.changes_history_action.text() == "Changes & History…"
    assert not hasattr(window, "device_history_menu")
    assert not hasattr(window, "snapshots_menu")
    assert not hasattr(window, "device_inventory_changes_action")
    assert window.data_maintenance_action.text() == "Data Maintenance…"
    assert window.data_maintenance_action.menu() is None
    assert not hasattr(window, "data_maintenance_menu")
    assert not hasattr(window, "clear_audit_cache_action")
    assert not hasattr(window, "clear_audit_history_action")
    assert not hasattr(window, "clear_device_inventory_history_action")
    assert window.audit_profiles_menu.menuAction() in window.audit_menu.actions()
    assert window.audit_profiles_menu.menuAction() not in window.tools_menu.actions()
    assert window.audit_result_actions.run is window.run_audit_action
    assert window.audit_result_actions.exports.menu is window.audit_export_results_menu
    assert window.audit_result_actions.clear is window.clear_results_action
    all_menu_text = {
        action.text()
        for menu in (
            window.file_menu,
            window.audit_menu,
            window.view_menu,
            window.tools_menu,
            window.help_menu,
        )
        for action in menu.actions()
    }
    assert not {
        "View Presets",
        "Display Settings",
        "Audit Profiles",
        "Device Summary…",
        "SDK Maintenance Filter…",
    }.intersection(all_menu_text)
    assert "Device Summary…" not in _action_texts(window.tools_menu)
    assert not hasattr(window, "device_summary_action")
    assert not hasattr(window, "_show_device_summary")


def test_action_availability_tracks_source_results_visibility_device_and_busy_state(
    window: MainWindow,
) -> None:
    run_action = window.audit_result_actions.run
    clear_action = window.audit_result_actions.clear
    all_exports = (
        window.audit_result_actions.exports.all_results
        + window.button_result_exports.all_results
    )
    visible_exports = (
        window.audit_result_actions.exports.visible_results
        + window.button_result_exports.visible_results
    )

    assert window.file_choose_source_action.isEnabled()
    assert window.file_scan_phone_action.isEnabled()
    assert window.advanced_settings_action.isEnabled()
    assert window.audit_profiles_menu.menuAction().isEnabled()
    assert window.changes_history_action.isEnabled()
    assert not run_action.isEnabled()
    assert not window.force_full_refresh_action.isEnabled()
    assert not any(action.isEnabled() for action in all_exports + visible_exports)

    window.source_mode = "file"
    window.file_apps = [{"app_name": "Example", "package_name": "com.example.app"}]
    window._sync_action_availability()
    assert window.run_button.isEnabled()
    assert run_action.isEnabled()
    assert window.force_full_refresh_action.isEnabled()
    assert not clear_action.isEnabled()

    window.current_rows = [
        {
            "app_name": "Example",
            "package_name": "com.example.app",
            "criticality_key": "red",
        }
    ]
    window.model.set_rows(window.current_rows)
    window._update_summary()
    assert window.export_button.isEnabled()
    assert window.clear_button.isEnabled()
    assert clear_action.isEnabled()
    assert window.recheck_problematic_action.isEnabled()
    assert all(action.isEnabled() for action in all_exports + visible_exports)

    window.search_edit.setText("not-present")
    assert all(action.isEnabled() for action in all_exports)
    assert not any(action.isEnabled() for action in visible_exports)
    window.search_edit.clear()

    window.source_mode = "device"
    window.file_apps = []
    window.device_apps_all = [
        {"app_name": "Example", "package_name": "com.example.app"}
    ]
    window._device_summary = {"model": "Pixel"}
    window._last_inventory_changes = {}
    window._sync_action_availability()
    assert window.file_phone_package_export_action.isEnabled()
    assert window.scan_phone_package_export_action.isEnabled()
    window._last_inventory_changes = {"had_previous": True}
    window._sync_action_availability()

    window._source_operation_active = True
    window._sync_action_availability()
    assert not window.file_choose_source_action.isEnabled()
    assert not window.file_scan_phone_action.isEnabled()
    assert not run_action.isEnabled()
    assert not window.export_button.isEnabled()
    assert not window.clear_button.isEnabled()
    assert not window.advanced_settings_action.isEnabled()
    assert not window.audit_profiles_menu.menuAction().isEnabled()
    assert not window.data_maintenance_action.isEnabled()
    assert not any(action.isEnabled() for action in all_exports + visible_exports)

    window._source_operation_active = False
    window._sync_action_availability()
    assert window.advanced_settings_action.isEnabled()
    assert window.audit_profiles_menu.menuAction().isEnabled()


def test_presentation_actions_preserve_running_operation_status(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_status = "Auditing 4/10: com.example.app"
    window._source_operation_active = True
    window.status_label.setText(operation_status)

    window._apply_filter_preset("Old Apps")
    assert window.status_label.text() == operation_status

    window._reset_table_layout()
    assert window.status_label.text() == operation_status

    monkeypatch.setattr(QDialog, "exec", lambda _dialog: QDialog.DialogCode.Accepted)
    window._show_display_settings()
    assert window.status_label.text() == operation_status


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("_source_operation_active", True),
        ("_audit_active", True),
        ("_finalizing_session", 1),
    ],
)
def test_technical_settings_are_disabled_for_every_running_operation_state(
    window: MainWindow,
    attribute: str,
    value: object,
) -> None:
    setattr(window, attribute, value)
    window._sync_action_availability()

    assert not window.advanced_settings_action.isEnabled()
    assert not window.audit_profiles_menu.menuAction().isEnabled()


def test_row_context_actions_require_their_fields_and_idle_state(window: MainWindow) -> None:
    window.source_mode = "file"
    row = {
        "package_name": "com.example.app",
        "play_title": "",
        "store_url": "",
        "criticality_key": "green",
    }
    availability = window._row_action_availability(row)

    assert availability.details
    assert availability.recheck
    assert availability.package
    assert availability.visible_row
    assert not availability.store
    assert not availability.app_info
    assert not availability.title
    assert not availability.url

    window.source_mode = "device"
    assert window._row_action_availability(row).app_info

    window._audit_active = True
    running_availability = window._row_action_availability(row)
    assert not running_availability.recheck
    assert not running_availability.app_info
    window._audit_active = False


def test_clear_current_results_preserves_phone_inventory_and_persistent_data(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    persistent_deletions: list[str] = []
    monkeypatch.setattr(compact_ui, "clear_cache", lambda: persistent_deletions.append("cache"))
    monkeypatch.setattr(
        device_metadata, "clear_history", lambda: persistent_deletions.append("history")
    )
    monkeypatch.setattr(window, "_get_authorised_adb", lambda: None)

    window._on_adb_scan_done(
        [{"app_name": "Example", "package_name": "com.example.app"}], set()
    )
    window.current_rows = [{"package_name": "com.example.app", "criticality_key": "green"}]
    window.model.set_rows(window.current_rows)
    window.clear_results_action.trigger()

    assert window.current_rows == []
    assert window.device_apps_all == [
        {"app_name": "Example", "package_name": "com.example.app"}
    ]
    assert window.file_phone_package_export_action.isEnabled()
    assert window.scan_phone_package_export_action.isEnabled()
    assert persistent_deletions == []


def test_clear_device_inventory_history_deletes_only_comparison_baselines(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    baselines = [
        tmp_path / "inventory_phone_one.json",
        tmp_path / "inventory_phone_two.json",
    ]
    for path in baselines:
        path.write_text("{}", encoding="utf-8")

    preserved = [
        tmp_path / "settings.json",
        tmp_path / "audit_cache.json",
        tmp_path / "audit_history.json",
        tmp_path / "alternative_distribution_cache.json",
        tmp_path / "inventory_notes.txt",
        tmp_path / "manual_snapshot.psaa.json",
    ]
    for path in preserved:
        path.write_text("preserve", encoding="utf-8")
    snapshots = tmp_path / "device_snapshots"
    snapshots.mkdir()
    snapshot = snapshots / "saved.psaa.json"
    snapshot.write_text("preserve", encoding="utf-8")
    colliding_snapshot = tmp_path / "inventory_manual_snapshot.json"
    colliding_snapshot.write_text(
        json.dumps({"format": device_insights.DEVICE_SNAPSHOT_FORMAT, "apps": []}),
        encoding="utf-8",
    )

    assert device_insights.clear_device_inventory_history() == 2
    assert all(not path.exists() for path in baselines)
    assert all(path.read_text(encoding="utf-8") == "preserve" for path in preserved)
    assert snapshot.read_text(encoding="utf-8") == "preserve"
    assert colliding_snapshot.is_file()

    rows = [{"package_name": "com.example.app", "installed_version": "1"}]
    comparison = device_insights.annotate_inventory_changes_and_save(
        rows,
        {"device_id": "phone one"},
    )
    assert comparison["had_previous"] is False


def test_clear_device_inventory_history_requires_confirmation_and_refreshes_ui(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.user_settings.update(
        {"changes_history_enabled": True, "inventory_history_enabled": True}
    )
    row = {
        "package_name": "com.example.app",
        "criticality_key": "green",
        "device_change": "Version changed",
        change_service.DEVICE_HISTORY_FLAG: True,
    }
    window.source_mode = "device"
    window.current_rows = [row]
    window.model.set_rows(window.current_rows)
    window._last_inventory_changes = {
        "had_previous": True,
        "counts": {"version": 1},
        "removed": [],
    }
    window._sync_action_availability()
    calls: list[None] = []
    prompts: list[tuple[str, str]] = []
    answers = [
        QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    ]

    def question(
        _parent: object,
        title: str,
        message: str,
        *_args: object,
    ) -> QMessageBox.StandardButton:
        prompts.append((title, message))
        return answers.pop(0)

    monkeypatch.setattr(QMessageBox, "question", question)
    monkeypatch.setattr(
        device_insights,
        "clear_device_inventory_history",
        lambda: calls.append(None) or 2,
    )

    window._clear_device_inventory_history()
    assert calls == []
    assert row["device_change"] == "Version changed"

    window._clear_device_inventory_history()

    assert calls == [None]
    assert prompts[0] == prompts[1]
    assert prompts[0][0] == "Clear device inventory history?"
    confirmation = prompts[0][1]
    assert "Device Inventory Change" in confirmation
    assert "Device snapshots" in confirmation
    assert "provider cache" in confirmation
    assert "settings" in confirmation
    assert "device_change" not in row
    assert row[change_service.DEVICE_HISTORY_FLAG] is False
    assert window._last_inventory_changes == {}
    assert not hasattr(window, "device_inventory_changes_action")
    assert window.status_label.text() == (
        "Device Inventory History cleared • 2 baselines removed"
    )


def test_scan_phone_split_control_tracks_current_phone_inventory(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controls = window.scan_phone_options_button.parentWidget().layout()
    assert controls.itemAt(0).widget() is window.scan_button
    assert controls.itemAt(1).widget() is window.scan_phone_options_button
    assert window.scan_button.text() == "Scan Phone"
    assert _action_texts(window.scan_phone_options_menu) == [
        "Export Current Phone Package List as CSV…"
    ]
    assert not window.scan_phone_package_export_action.isEnabled()
    assert not window.file_phone_package_export_action.isEnabled()

    monkeypatch.setattr(window, "_get_authorised_adb", lambda: None)
    window._on_adb_scan_done(
        [{"app_name": "First", "package_name": "com.example.first"}], set()
    )
    assert window.scan_phone_package_export_action.isEnabled()
    assert window.file_phone_package_export_action.isEnabled()

    window._on_adb_scan_done(
        [{"app_name": "Second", "package_name": "com.example.second"}], set()
    )
    window.search_edit.setText("second")
    window._set_view_preset("Source Details")
    assert window.scan_phone_package_export_action.isEnabled()
    assert window.file_phone_package_export_action.isEnabled()

    source = tmp_path / "source.csv"
    source.write_text("package_name\ncom.example.file\n", encoding="utf-8")
    monkeypatch.setattr(device_insights, "log_event", lambda _message: None)
    window._load_input_file(str(source))
    assert window.source_mode == "file"
    assert window.device_apps_all == []
    assert not window.scan_phone_package_export_action.isEnabled()
    assert not window.file_phone_package_export_action.isEnabled()


def test_static_adb_and_import_help_open_as_rich_dialogs(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str]] = []

    def record(dialog: rich_help.RichHelpDialog) -> int:
        opened.append((dialog.windowTitle(), dialog.browser.toPlainText()))
        return 0

    monkeypatch.setattr(rich_help.RichHelpDialog, "exec", record)
    monkeypatch.setattr(
        window,
        "_show_text_help",
        lambda *_args: pytest.fail("Static guides must use the rich-help dialog"),
    )
    assert _action_structure(window.help_menu) == [
        "ADB Setup Guide…",
        "App List Import Guide…",
        None,
        "Maintenance Score Methodology…",
        None,
        "Check for Updates…",
        "Create Diagnostic Bundle…",
        None,
        "About Play Store App Audit",
    ]
    actions = {action.text(): action for action in window.help_menu.actions()}
    actions["ADB Setup Guide…"].trigger()
    actions["App List Import Guide…"].trigger()
    actions["Maintenance Score Methodology…"].trigger()

    assert [title for title, _text in opened] == [
        "ADB Setup Guide",
        "App List Import Guide",
        "Maintenance Score Methodology",
    ]
    assert "USB debugging" in opened[0][1]
    assert "Read-only use" in opened[0][1]
    assert "package_name" in opened[1][1]
    assert "Recent sources" in opened[1][1]
    assert "maintenance heuristic" in opened[2][1]
    assert "not a malware or security score" in opened[2][1]
    assert "Not found in the configured/checked Google Play markets: −60" in opened[2][1]
    assert "F-Droid main availability recovery: +10" in opened[2][1]
    assert "Aptoide availability recovery: +5" in opened[2][1]


def test_about_dialog_displays_the_canonical_version(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def inspect_dialog(dialog: QDialog) -> int:
        labels = dialog.findChildren(QLabel)
        captured["title"] = dialog.windowTitle()
        captured["labels"] = {label.objectName(): label.text() for label in labels}
        captured["label_order"] = [label.objectName() for label in labels]
        captured["tagline_bold"] = next(
            label.font().bold() for label in labels if label.objectName() == "AboutTagline"
        )
        captured["font_sizes"] = {
            label.objectName(): label.font().pointSizeF() for label in labels
        }
        captured["text"] = " ".join(label.text() for label in labels)
        return 0

    monkeypatch.setattr(QDialog, "exec", inspect_dialog)
    window._show_about()

    assert captured["title"] == "About Play Store App Audit"
    assert captured["labels"]["AboutVersion"] == f"Version {__version__}"  # type: ignore[index]
    assert captured["labels"]["AboutTagline"] == (  # type: ignore[index]
        "Android App Inventory, Store Analysis & Maintenance Toolkit"
    )
    assert captured["label_order"][:3] == [  # type: ignore[index]
        "AboutTitle",
        "AboutTagline",
        "AboutVersion",
    ]
    assert captured["tagline_bold"] is False
    font_sizes = captured["font_sizes"]
    assert font_sizes["AboutTitle"] > font_sizes["AboutTagline"] > font_sizes["AboutVersion"]  # type: ignore[index]
    assert "Created by MRC" in str(captured["text"])
    assert "Not affiliated with or endorsed by Google" in str(captured["text"])
    assert f'"{__version__}"' not in inspect.getsource(window._show_about)


def test_linkedin_url_and_link_are_removed() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "playstore_app_audit").rglob("*.py")
    )
    assert "PROJECT_URL" not in sources
    assert "linkedin.com" not in sources.lower()
    assert "Created by MRC" in inspect.getsource(compact_ui.CompactWindow._show_about)
