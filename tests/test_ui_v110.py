from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QDialog, QLabel

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit import __version__
from playstore_app_audit.ui import rich_help
from playstore_app_audit.ui.main_window import MainWindow

SUBTITLE = (
    "Check Android packages against Google Play, classify update risk and inspect everything in one table."
)
RESULT_EXPORTS = [
    "Export all results as CSV…",
    "Export visible results as CSV…",
    "Export all results as HTML…",
    "Export visible results as HTML…",
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
    assert window.choose_button.text() == "Choose file"
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
        assert actions[0].text() == "No recent files"
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


def test_file_menu_and_export_results_hierarchy(window: MainWindow) -> None:
    assert _action_structure(window.file_menu) == [
        "Choose app list…",
        "Recent sources",
        "Scan phone with ADB",
        "Export current phone package list as CSV…",
        None,
        "Run Play Store audit",
        "Export Results",
        "Clear Results",
        None,
        "Exit",
    ]
    assert _action_structure(window.file_export_results_menu) == [
        "Export all results as CSV…",
        "Export visible results as CSV…",
        None,
        "Export all results as HTML…",
        "Export visible results as HTML…",
        None,
        "Export all results as versioned JSON…",
        "Export visible results as versioned JSON…",
    ]
    assert "Export current phone package list as CSV…" not in _action_texts(
        window.file_export_results_menu
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
    created.choose_button.click()
    created.scan_button.click()
    created.run_button.click()
    created.clear_button.click()
    next(action for action in created.file_menu.actions() if action.text() == "Run Play Store audit").trigger()
    next(action for action in created.file_menu.actions() if action.text() == "Clear Results").trigger()
    assert choose_calls == [created]
    assert scan_calls == [created]
    assert calls == [created, created]
    assert clear_calls == [created, created]
    created.close()
    app.processEvents()


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


def test_main_export_button_and_clear_controls_remain_available(window: MainWindow) -> None:
    assert window.export_button.text() == "Export results"
    assert window.export_button.menu() is window._export_results_menu
    assert _action_texts(window.export_button.menu()) == RESULT_EXPORTS
    assert window.clear_button.text() == "Clear"
    assert _action_structure(window.tools_menu) == [
        "Advanced settings…",
        None,
        "Force full refresh (ignore cache)",
        "Recheck Removed / Anomaly / Other",
        None,
        "Device summary…",
        "Device snapshots",
        "Device inventory changes…",
        None,
        "Data maintenance",
    ]
    assert _action_texts(window.data_maintenance_menu) == [
        "Clear audit cache",
        "Clear previous-audit history",
    ]
    assert "Force full refresh (ignore cache)" not in _action_texts(
        window.data_maintenance_menu
    )


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
    next(action for action in window.file_menu.actions() if action.text() == "Clear Results").trigger()

    assert window.current_rows == []
    assert window.device_apps_all == [
        {"app_name": "Example", "package_name": "com.example.app"}
    ]
    assert window.file_phone_package_export_action.isEnabled()
    assert window.scan_phone_package_export_action.isEnabled()
    assert persistent_deletions == []


def test_scan_phone_split_control_tracks_current_phone_inventory(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    controls = window.scan_phone_options_button.parentWidget().layout()
    assert controls.itemAt(0).widget() is window.scan_button
    assert controls.itemAt(1).widget() is window.scan_phone_options_button
    assert window.scan_button.text() == "Scan phone"
    assert _action_texts(window.scan_phone_options_menu) == [
        "Export current phone package list as CSV…"
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
    window._set_view_preset("Device")
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
        "ADB setup guide…",
        "How to import an app list…",
        None,
        "Health score methodology…",
        None,
        "Check for updates…",
        "Create diagnostic bundle…",
        None,
        "About Play Store App Audit",
    ]
    actions = {action.text(): action for action in window.help_menu.actions()}
    actions["ADB setup guide…"].trigger()
    actions["How to import an app list…"].trigger()
    actions["Health score methodology…"].trigger()

    assert [title for title, _text in opened] == [
        "ADB setup guide",
        "How to import an app list",
        "Health score methodology",
    ]
    assert "USB debugging" in opened[0][1]
    assert "Read-only use" in opened[0][1]
    assert "package_name" in opened[1][1]
    assert "Recent sources" in opened[1][1]
    assert "maintenance heuristic" in opened[2][1]
    assert "not a malware or security score" in opened[2][1]
    assert "Removed from the checked Play markets: −60" in opened[2][1]


def test_about_dialog_displays_the_canonical_version(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def inspect_dialog(dialog: QDialog) -> int:
        captured["title"] = dialog.windowTitle()
        captured["labels"] = {
            label.objectName(): label.text() for label in dialog.findChildren(QLabel)
        }
        captured["text"] = " ".join(label.text() for label in dialog.findChildren(QLabel))
        return 0

    monkeypatch.setattr(QDialog, "exec", inspect_dialog)
    window._show_about()

    assert captured["title"] == "About Play Store App Audit"
    assert captured["labels"]["AboutVersion"] == f"Version {__version__}"  # type: ignore[index]
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
