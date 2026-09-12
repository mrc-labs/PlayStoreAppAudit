from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.menu_window as menu_ui
from playstore_app_audit.ui.main_window import MainWindow


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
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def test_help_feedback_action_opens_github_issue_chooser(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        menu_ui.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    assert window.feedback_action.text() == "Send Feedback / Report an Issue…"
    window.feedback_action.trigger()

    assert opened == [menu_ui.FEEDBACK_ISSUE_URL]
    assert opened[0] == "https://github.com/mrc-labs/PlayStoreAppAudit/issues/new/choose"


def test_up_to_date_message_explicitly_says_installed_version_is_latest(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    messages: list[tuple[str, str]] = []
    monkeypatch.setattr(
        device_insights,
        "check_for_updates",
        lambda: {"status": "ok", "newer": False},
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, title, message, *_args: messages.append((title, message)),
    )

    window.check_updates_action.trigger()

    assert messages == [
        (
            "Up to date",
            (
                f"You're running Play Store App Audit {device_insights.APP_VERSION}. "
                "This is the latest available version."
            ),
        )
    ]
