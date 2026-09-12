from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.menu_window as menu_ui
import playstore_app_audit.ui.update_check as update_ui
from playstore_app_audit import __version__
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window_store(
    app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[tuple[MainWindow, dict[str, object]]]:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        update_ui.AUTO_UPDATE_CHECK_KEY: False,
    }

    def load_settings() -> dict[str, object]:
        return dict(settings)

    def save_settings(values: dict[str, object]) -> dict[str, object]:
        settings.clear()
        settings.update(values)
        return dict(settings)

    monkeypatch.setattr(state, "load_settings", load_settings)
    monkeypatch.setattr(state, "save_settings", save_settings)
    monkeypatch.setattr(compact_ui, "load_settings", load_settings)
    monkeypatch.setattr(compact_ui, "save_settings", save_settings)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    yield created, settings
    created.close()
    app.processEvents()


def _fake_thread_factory(started: list[Any]):
    class FakeThread:
        def __init__(self, *, target: Any, name: str, daemon: bool) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon
            self.alive = False

        def start(self) -> None:
            self.alive = True
            started.append(self)

        def is_alive(self) -> bool:
            return self.alive

    return FakeThread


def test_help_feedback_action_opens_github_issue_chooser(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _settings = window_store
    opened: list[str] = []
    monkeypatch.setattr(
        menu_ui.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    assert window.feedback_action.text() == "Send Feedback / Report an Issue…"
    window.feedback_action.trigger()

    assert opened == [menu_ui.FEEDBACK_ISSUE_URL]


def test_startup_update_check_defaults_on() -> None:
    assert state.DEFAULT_SETTINGS[update_ui.AUTO_UPDATE_CHECK_KEY] is True


def test_disabled_startup_check_does_not_start_worker(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    assert settings[update_ui.AUTO_UPDATE_CHECK_KEY] is False
    controller = update_ui.UpdateCheckController(window)
    monkeypatch.setattr(
        update_ui,
        "Thread",
        lambda *_args, **_kwargs: pytest.fail("disabled startup check must not create a thread"),
    )

    controller.start_startup_check()


def test_startup_check_starts_daemon_worker_without_running_network_inline(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = True
    controller = update_ui.UpdateCheckController(window)
    started: list[Any] = []
    monkeypatch.setattr(update_ui, "Thread", _fake_thread_factory(started))
    monkeypatch.setattr(
        device_insights,
        "check_for_updates",
        lambda: pytest.fail("network check must run only inside the worker target"),
    )

    controller.start_startup_check()

    assert len(started) == 1
    assert started[0].daemon is True
    assert started[0].name == "PlayStoreAppAudit-update-check"


def test_install_turns_about_into_the_only_update_surface(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = False
    started: list[Any] = []
    monkeypatch.setattr(update_ui, "Thread", _fake_thread_factory(started))

    controller = update_ui.install_update_check_controller(window, schedule_startup=False)

    assert window._update_check_controller is controller
    assert not window.check_updates_action.isVisible()
    assert window.about_action.text() == "About Play Store App Audit…"

    window.about_action.trigger()

    assert len(started) == 1
    assert controller._about_requested is True
    dialog = controller._about_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.update_title.text() == "Checking for updates…"
    assert f"Version {__version__}" in dialog.update_detail.text()
    assert not dialog.startup_check.isChecked()


def test_opening_about_checks_even_when_startup_checks_are_disabled(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = False
    controller = update_ui.UpdateCheckController(window)
    started: list[Any] = []
    monkeypatch.setattr(update_ui, "Thread", _fake_thread_factory(started))

    controller.show_about()

    assert len(started) == 1
    assert controller._about_requested is True


def test_about_checkbox_persists_startup_preference_immediately(
    window_store: tuple[MainWindow, dict[str, object]],
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = False
    controller = update_ui.UpdateCheckController(window)
    dialog = controller._ensure_about_dialog()
    dialog.set_startup_check_enabled(False)

    dialog.startup_check.setChecked(True)

    assert settings[update_ui.AUTO_UPDATE_CHECK_KEY] is True


def test_manual_about_current_result_updates_same_dialog(
    window_store: tuple[MainWindow, dict[str, object]],
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)
    dialog = controller._ensure_about_dialog()
    controller._about_requested = True

    controller._handle_result({"status": "ok", "newer": False})

    assert dialog.update_title.text() == "You're up to date"
    assert dialog.update_detail.text() == (
        f"You're running Play Store App Audit {__version__}. "
        "This is the latest available version."
    )
    assert dialog.update_action.text() == "Check Again"
    assert dialog.update_action.isVisibleTo(dialog)


def test_manual_about_error_is_shown_inside_about(
    window_store: tuple[MainWindow, dict[str, object]],
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)
    dialog = controller._ensure_about_dialog()
    controller._about_requested = True

    controller._handle_result({"status": "error", "message": "offline"})

    assert dialog.update_title.text() == "Update check unavailable"
    assert dialog.update_detail.text() == "offline"
    assert dialog.update_action.text() == "Check Again"


def test_startup_current_or_failed_result_stays_silent(
    window_store: tuple[MainWindow, dict[str, object]],
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)

    controller._handle_result({"status": "ok", "newer": False})
    assert controller._about_dialog is None

    controller._handle_result({"status": "error", "message": "offline"})
    assert controller._about_dialog is None


def test_startup_newer_result_opens_about_with_update_status(
    window_store: tuple[MainWindow, dict[str, object]],
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = True
    controller = update_ui.UpdateCheckController(window)

    controller._handle_result(
        {
            "status": "ok",
            "newer": True,
            "tag": "v2.0.1",
            "url": "https://example.invalid/release",
        }
    )

    dialog = controller._about_dialog
    assert dialog is not None and dialog.isVisible()
    assert dialog.update_title.text() == "Update available: v2.0.1"
    assert dialog.update_detail.text() == (
        f"You're running version {__version__}. A newer stable release is available."
    )
    assert dialog.update_action.text() == "View Release"
    assert dialog.startup_check.isChecked()


def test_about_request_reuses_inflight_startup_worker(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = True
    controller = update_ui.UpdateCheckController(window)
    started: list[Any] = []
    monkeypatch.setattr(update_ui, "Thread", _fake_thread_factory(started))

    controller.start_startup_check()
    controller.show_about()

    assert len(started) == 1
    assert controller._about_requested is True


def test_about_view_release_opens_exact_result_url(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)
    opened: list[str] = []
    monkeypatch.setattr(
        update_ui.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )
    dialog = controller._ensure_about_dialog()
    dialog.set_update_available("v2.0.1", "https://example.invalid/release")

    dialog.update_action.click()

    assert opened == ["https://example.invalid/release"]
