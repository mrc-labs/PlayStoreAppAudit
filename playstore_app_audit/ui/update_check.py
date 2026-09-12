"""Asynchronous GitHub Release checks integrated with the About surface."""

from __future__ import annotations

from contextlib import suppress
from threading import Thread
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
from playstore_app_audit.ui.about_updates import (
    AUTO_UPDATE_CHECK_LABEL,
    AboutUpdatesDialog,
)

AUTO_UPDATE_CHECK_KEY = "check_updates_on_startup"

# Existing installs without this key opt in to the v2.0 default. The About
# dialog always allows the user to change the preference immediately.
state.DEFAULT_SETTINGS.setdefault(AUTO_UPDATE_CHECK_KEY, True)


class UpdateCheckController(QObject):
    """Coordinate About-triggered and non-blocking startup release checks."""

    _result_ready = Signal(object)

    def __init__(self, parent: Any) -> None:
        qt_parent = parent if isinstance(parent, QObject) else None
        super().__init__(qt_parent)
        self._window = parent
        self._thread: Thread | None = None
        self._about_requested = False
        self._about_dialog: AboutUpdatesDialog | None = None
        self._result_ready.connect(self._handle_result)

    def schedule_startup_check(self) -> None:
        """Schedule the optional check after Qt enters the event loop."""

        QTimer.singleShot(0, self.start_startup_check)

    def startup_check_enabled(self) -> bool:
        value = state.load_settings().get(AUTO_UPDATE_CHECK_KEY, True)
        return value if isinstance(value, bool) else True

    def set_startup_check_enabled(self, enabled: bool) -> None:
        settings = state.load_settings()
        settings[AUTO_UPDATE_CHECK_KEY] = bool(enabled)
        saved = state.save_settings(settings)
        if hasattr(self._window, "user_settings") and isinstance(saved, dict):
            self._window.user_settings = saved

    def start_startup_check(self) -> None:
        """Check silently at startup when the preference is enabled."""

        if self.startup_check_enabled():
            self._request_check(about=False)

    def show_about(self) -> None:
        """Open About and always trigger or join a fresh latest-release check."""

        dialog = self._ensure_about_dialog()
        dialog.set_startup_check_enabled(self.startup_check_enabled())
        dialog.set_checking()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._request_check(about=True)

    def check_now(self) -> None:
        """Compatibility alias: update checks now live inside About."""

        self.show_about()

    def _ensure_about_dialog(self) -> AboutUpdatesDialog:
        dialog = self._about_dialog
        if dialog is not None:
            return dialog
        parent = self._window if isinstance(self._window, QWidget) else None
        dialog = AboutUpdatesDialog(parent)
        dialog.check_requested.connect(self._check_again_from_about)
        dialog.startup_check_changed.connect(self.set_startup_check_enabled)
        dialog.release_requested.connect(self._open_release_page)
        self._about_dialog = dialog
        return dialog

    def _check_again_from_about(self) -> None:
        dialog = self._ensure_about_dialog()
        dialog.set_checking()
        self._request_check(about=True)

    def _request_check(self, *, about: bool) -> None:
        if about:
            self._about_requested = True
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = Thread(
            target=self._run_check,
            name="PlayStoreAppAudit-update-check",
            daemon=True,
        )
        self._thread.start()

    def _run_check(self) -> None:
        result = device_insights.check_for_updates()
        # The application may have closed while the network request was in flight.
        with suppress(RuntimeError):
            self._result_ready.emit(result)

    def _handle_result(self, raw_result: object) -> None:
        self._thread = None
        about_requested = self._about_requested
        self._about_requested = False
        result = raw_result if isinstance(raw_result, dict) else {}

        if result.get("status") != "ok":
            if about_requested:
                self._ensure_about_dialog().set_unavailable(
                    str(result.get("message") or "Update check unavailable.")
                )
            return

        if result.get("newer"):
            tag = str(result.get("tag") or "New version")
            url = str(result.get("url") or device_insights.LATEST_RELEASE_PAGE)
            dialog = self._ensure_about_dialog()
            dialog.set_startup_check_enabled(self.startup_check_enabled())
            dialog.set_update_available(tag, url)
            if not about_requested:
                # A newer version discovered by the silent startup check uses the
                # same About surface rather than a second update-only message box.
                dialog.show()
                dialog.raise_()
                dialog.activateWindow()
            return

        if about_requested:
            self._ensure_about_dialog().set_up_to_date()

    @staticmethod
    def _open_release_page(url: str) -> None:
        QDesktopServices.openUrl(QUrl(url or device_insights.LATEST_RELEASE_PAGE))


def _about_action(window: Any):
    help_menu = getattr(window, "help_menu", None)
    if help_menu is None:
        return None
    for action in help_menu.actions():
        if action.text().replace("…", "").startswith("About Play Store App Audit"):
            return action
    return None


def _bind_about_surface(window: Any, controller: UpdateCheckController) -> None:
    legacy_check = getattr(window, "check_updates_action", None)
    if legacy_check is not None:
        legacy_check.setVisible(False)
        with suppress(TypeError, RuntimeError):
            legacy_check.triggered.disconnect()

    about = _about_action(window)
    if about is None:
        return
    about.setText("About Play Store App Audit…")
    about.setToolTip("About, current version and software updates")
    with suppress(TypeError, RuntimeError):
        about.triggered.disconnect()
    about.triggered.connect(controller.show_about)
    window.about_action = about


def install_update_check_controller(
    window: Any, *, schedule_startup: bool = True
) -> UpdateCheckController:
    """Attach the canonical async About/update controller to the window."""

    existing = getattr(window, "_update_check_controller", None)
    if isinstance(existing, UpdateCheckController):
        _bind_about_surface(window, existing)
        if schedule_startup:
            existing.schedule_startup_check()
        return existing

    controller = UpdateCheckController(window)
    window._update_check_controller = controller
    _bind_about_surface(window, controller)
    if schedule_startup:
        controller.schedule_startup_check()
    return controller
