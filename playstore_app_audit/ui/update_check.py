from __future__ import annotations

from contextlib import suppress
from threading import Thread
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QMessageBox, QWidget

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state

AUTO_UPDATE_CHECK_KEY = "check_updates_on_startup"
AUTO_UPDATE_CHECK_LABEL = "Check for updates automatically at startup"

# The startup check is an ordinary preference. Existing installs that do not
# have the key opt in to the v2.0 default and can disable it from update dialogs.
state.DEFAULT_SETTINGS.setdefault(AUTO_UPDATE_CHECK_KEY, True)


class UpdateCheckController(QObject):
    """Coordinate manual and non-blocking startup release checks."""

    _result_ready = Signal(object)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._window = parent
        self._thread: Thread | None = None
        self._manual_requested = False
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
            self._window.user_settings = saved  # type: ignore[attr-defined]

    def start_startup_check(self) -> None:
        if self.startup_check_enabled():
            self._request_check(manual=False)

    def check_now(self) -> None:
        """Run the Help-menu check without blocking the Qt GUI thread."""

        self._request_check(manual=True)

    def _request_check(self, *, manual: bool) -> None:
        if manual:
            self._manual_requested = True
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
        try:
            self._result_ready.emit(result)
        except RuntimeError:
            # The application may have closed while the network request was in flight.
            pass

    def _handle_result(self, raw_result: object) -> None:
        self._thread = None
        manual = self._manual_requested
        self._manual_requested = False
        result = raw_result if isinstance(raw_result, dict) else {}

        if result.get("status") != "ok":
            if manual:
                QMessageBox.information(
                    self._window,
                    "Update check",
                    str(result.get("message") or "Update check unavailable."),
                )
            return

        if result.get("newer"):
            self._show_update_available(result)
            return

        if manual:
            self._show_up_to_date()

    def _preference_checkbox(self, box: QMessageBox) -> QCheckBox:
        checkbox = QCheckBox(AUTO_UPDATE_CHECK_LABEL, box)
        checkbox.setChecked(self.startup_check_enabled())
        checkbox.setToolTip(
            "Disable this to stop background update checks when Play Store App Audit starts."
        )
        box.setCheckBox(checkbox)
        return checkbox

    def _persist_checkbox(self, checkbox: QCheckBox) -> None:
        enabled = checkbox.isChecked()
        if enabled != self.startup_check_enabled():
            self.set_startup_check_enabled(enabled)

    def _show_update_available(self, result: dict[str, Any]) -> None:
        box = QMessageBox(self._window)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Update available")
        box.setText(f"Version {result.get('tag')} is available.")
        box.setInformativeText("Open the release page?")
        box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        box.setDefaultButton(QMessageBox.StandardButton.Yes)
        checkbox = self._preference_checkbox(box)
        answer = box.exec()
        self._persist_checkbox(checkbox)
        if answer == int(QMessageBox.StandardButton.Yes):
            QDesktopServices.openUrl(
                QUrl(str(result.get("url") or device_insights.LATEST_RELEASE_PAGE))
            )

    def _show_up_to_date(self) -> None:
        box = QMessageBox(self._window)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Up to date")
        box.setText(
            f"You're running Play Store App Audit {device_insights.APP_VERSION}. "
            "This is the latest available version."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        checkbox = self._preference_checkbox(box)
        box.exec()
        self._persist_checkbox(checkbox)


def install_update_check_controller(
    window: QWidget, *, schedule_startup: bool = True
) -> UpdateCheckController:
    """Attach the canonical async update checker to the production window."""

    controller = UpdateCheckController(window)
    action = getattr(window, "check_updates_action", None)
    if action is not None:
        with suppress(TypeError, RuntimeError):
            action.triggered.disconnect()
        action.triggered.connect(controller.check_now)
    setattr(window, "_update_check_controller", controller)
    if schedule_startup:
        controller.schedule_startup_check()
    return controller
