from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.menu_window as menu_ui
import playstore_app_audit.ui.update_check as update_ui
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
    assert opened[0] == "https://github.com/mrc-labs/PlayStoreAppAudit/issues/new/choose"


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

    monkeypatch.setattr(update_ui, "Thread", FakeThread)
    monkeypatch.setattr(
        device_insights,
        "check_for_updates",
        lambda: pytest.fail("network check must run only inside the worker target"),
    )

    controller.start_startup_check()

    assert len(started) == 1
    assert started[0].daemon is True
    assert started[0].name == "PlayStoreAppAudit-update-check"
    assert started[0].alive is True


def test_startup_current_or_failed_result_is_silent(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *_args, **_kwargs: pytest.fail("automatic startup check must stay silent"),
    )
    monkeypatch.setattr(
        controller,
        "_show_up_to_date",
        lambda: pytest.fail("automatic current-version check must stay silent"),
    )

    controller._handle_result({"status": "ok", "newer": False})
    controller._handle_result({"status": "error", "message": "offline"})


def test_startup_newer_result_uses_update_available_dialog(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, _settings = window_store
    controller = update_ui.UpdateCheckController(window)
    shown: list[dict[str, Any]] = []
    monkeypatch.setattr(controller, "_show_update_available", lambda result: shown.append(result))
    result = {
        "status": "ok",
        "newer": True,
        "tag": "v2.0.1",
        "url": "https://example.invalid/release",
    }

    controller._handle_result(result)

    assert shown == [result]


def test_install_rebinds_manual_help_check_to_same_async_controller(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = False
    started: list[Any] = []

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

    monkeypatch.setattr(update_ui, "Thread", FakeThread)
    controller = update_ui.install_update_check_controller(window)
    window.check_updates_action.trigger()

    assert getattr(window, "_update_check_controller") is controller
    assert controller._manual_requested is True
    assert len(started) == 1
    assert started[0].daemon is True


def test_manual_up_to_date_dialog_can_reenable_startup_checks(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    controller = update_ui.UpdateCheckController(window)
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = False

    def inspect(box: QMessageBox) -> int:
        assert box.windowTitle() == "Up to date"
        assert box.text() == (
            f"You're running Play Store App Audit {device_insights.APP_VERSION}. "
            "This is the latest available version."
        )
        checkbox = box.checkBox()
        assert checkbox is not None
        assert checkbox.text() == update_ui.AUTO_UPDATE_CHECK_LABEL
        assert not checkbox.isChecked()
        checkbox.setChecked(True)
        return int(QMessageBox.StandardButton.Ok)

    monkeypatch.setattr(QMessageBox, "exec", inspect)
    controller._show_up_to_date()

    assert settings[update_ui.AUTO_UPDATE_CHECK_KEY] is True


def test_update_available_dialog_can_disable_startup_checks(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    controller = update_ui.UpdateCheckController(window)
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = True
    opened: list[str] = []
    monkeypatch.setattr(
        update_ui.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    def inspect(box: QMessageBox) -> int:
        assert box.windowTitle() == "Update available"
        assert box.text() == "Version v2.0.1 is available."
        assert box.informativeText() == "Open the release page?"
        checkbox = box.checkBox()
        assert checkbox is not None
        assert checkbox.isChecked()
        checkbox.setChecked(False)
        return int(QMessageBox.StandardButton.No)

    monkeypatch.setattr(QMessageBox, "exec", inspect)
    controller._show_update_available(
        {
            "status": "ok",
            "newer": True,
            "tag": "v2.0.1",
            "url": "https://example.invalid/release",
        }
    )

    assert settings[update_ui.AUTO_UPDATE_CHECK_KEY] is False
    assert opened == []


def test_manual_request_reuses_inflight_startup_worker(
    window_store: tuple[MainWindow, dict[str, object]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window, settings = window_store
    settings[update_ui.AUTO_UPDATE_CHECK_KEY] = True
    controller = update_ui.UpdateCheckController(window)
    started: list[Any] = []

    class FakeThread:
        def __init__(self, *, target: Any, name: str, daemon: bool) -> None:
            self.target = target
            self.alive = False

        def start(self) -> None:
            self.alive = True
            started.append(self)

        def is_alive(self) -> bool:
            return self.alive

    monkeypatch.setattr(update_ui, "Thread", FakeThread)

    controller.start_startup_check()
    controller.check_now()

    assert len(started) == 1
    assert controller._manual_requested is True
