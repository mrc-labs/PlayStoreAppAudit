from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
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
    file_actions = _action_texts(window.file_menu)
    assert "Recent sources" in file_actions
    assert "Run Play Store audit" in file_actions
    assert "Export results" in file_actions
    assert "Export current phone package list as CSV…" in file_actions
    assert _action_texts(window.file_export_results_menu) == RESULT_EXPORTS
    assert "Export current phone package list as CSV…" not in _action_texts(
        window.file_export_results_menu
    )


def test_file_and_main_run_actions_use_same_canonical_handler(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[MainWindow] = []
    choose_calls: list[MainWindow] = []
    settings: dict[str, object] = {"view_preset": "Basic", "recent_sources": []}
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(MainWindow, "_start_audit", lambda self: calls.append(self))
    monkeypatch.setattr(MainWindow, "_choose_input", lambda self: choose_calls.append(self))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    created.choose_button.click()
    created.run_button.click()
    next(action for action in created.file_menu.actions() if action.text() == "Run Play Store audit").trigger()
    assert choose_calls == [created]
    assert calls == [created, created]
    created.close()
    app.processEvents()


def test_main_export_button_and_clear_controls_remain_available(window: MainWindow) -> None:
    assert window.export_button.text() == "Export results"
    assert window.export_button.menu() is window._export_results_menu
    assert _action_texts(window.export_button.menu()) == RESULT_EXPORTS
    assert window.clear_button.text() == "Clear"
    tools = _action_texts(window.tools_menu)
    assert "Clear audit cache" in tools
    assert "Clear previous-audit history" in tools
    assert "Force full refresh (ignore cache)" in tools


def test_static_adb_and_import_help_open_as_rich_dialogs(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str]] = []

    def record(dialog: rich_help.RichHelpDialog) -> int:
        opened.append((dialog.windowTitle(), dialog.browser.toPlainText()))
        return 0

    monkeypatch.setattr(rich_help.RichHelpDialog, "exec", record)
    actions = {action.text(): action for action in window.help_menu.actions()}
    actions["ADB setup guide…"].trigger()
    actions["How to import an app list…"].trigger()

    assert [title for title, _text in opened] == [
        "ADB setup guide",
        "How to import an app list",
    ]
    assert "USB debugging" in opened[0][1]
    assert "Read-only use" in opened[0][1]
    assert "package_name" in opened[1][1]
    assert "Recent sources" in opened[1][1]


def test_linkedin_url_and_link_are_removed() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "playstore_app_audit").rglob("*.py")
    )
    assert "PROJECT_URL" not in sources
    assert "linkedin.com" not in sources.lower()
    assert "Created by MRC" in inspect.getsource(compact_ui.CompactWindow._show_about)
