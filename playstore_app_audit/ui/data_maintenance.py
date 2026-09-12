from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MaintenanceCallback = Callable[[], str | None]
StatusCallback = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class MaintenanceAction:
    key: str
    title: str
    description: str
    confirmation_title: str
    confirmation: str
    success_status: str


CACHE_ACTIONS = (
    MaintenanceAction(
        "store_results",
        "Store Results Cache",
        "Healthy reusable Google Play audit results.",
        "Clear Store Results Cache?",
        "Delete cached healthy Google Play results? Current results, history and "
        "settings will not be deleted.",
        "Store Results Cache cleared",
    ),
    MaintenanceAction(
        "app_icons",
        "App Icon Cache",
        "Downloaded Google Play artwork held in memory and on disk.",
        "Clear App Icon Cache?",
        "Delete downloaded app icons from memory and disk? Audit evidence, scores, "
        "history and settings will not be changed.",
        "App Icon Cache cleared",
    ),
    MaintenanceAction(
        "alternative_store",
        "Alternative Store Cache",
        "Reusable F-Droid and Aptoide provider lookup results.",
        "Clear Alternative Store Cache?",
        "Delete cached F-Droid/Aptoide lookup results? Google Play results, history "
        "and settings will not be deleted.",
        "Alternative Store Cache cleared",
    ),
)

HISTORY_ACTIONS = (
    MaintenanceAction(
        "previous_audit_history",
        "Previous Audit History",
        "Baseline used to compare a completed audit with the previous audit.",
        "Clear Previous Audit History?",
        "Delete the previous-audit comparison baseline? The next successful "
        "comparison run will create a new baseline. Caches, settings, current "
        "results, Device Inventory History and Device Snapshots will not be deleted.",
        "Previous Audit History cleared; the next comparison run will create a new baseline",
    ),
    MaintenanceAction(
        "device_inventory_history",
        "Device Inventory History",
        "Per-device comparison baselines. Device Snapshots are not deleted.",
        "Clear Device Inventory History?",
        "Delete per-device inventory comparison baselines? The next completed phone "
        "audit for each device will create a new baseline. Device Snapshots, caches, "
        "settings, current results and Previous Audit History will not be deleted.",
        "Device Inventory History cleared",
    ),
)

CLEAR_ALL_CONFIRMATION = (
    "Delete Store results, app icons and alternative-store caches? History, Device "
    "Snapshots, settings and current results will not be deleted."
)


class DataMaintenanceDialog(QDialog):
    """Native, scope-explicit controls for the application's persistent stores."""

    def __init__(
        self,
        parent: QWidget,
        callbacks: Mapping[str, MaintenanceCallback],
        status_callback: StatusCallback,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DataMaintenanceDialog")
        self.setWindowTitle("Data Maintenance")
        self.setMinimumWidth(660)
        self.setModal(True)
        self._callbacks = dict(callbacks)
        self._status_callback = status_callback
        self.action_buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        intro = QLabel(
            "Clear reusable cached data or comparison history independently. "
            "Current audit results remain until you use Clear Results."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.cached_data_group = QGroupBox("Cached data")
        self.cached_data_group.setObjectName("CachedDataSection")
        cache_layout = QGridLayout(self.cached_data_group)
        self._add_rows(cache_layout, CACHE_ACTIONS)
        clear_all_row = len(CACHE_ACTIONS)
        cache_layout.setRowMinimumHeight(clear_all_row, 6)
        clear_all = QPushButton("Clear All Caches…")
        clear_all.setObjectName("ClearAllCachesButton")
        clear_all.clicked.connect(self._clear_all_caches)
        cache_layout.addWidget(
            clear_all,
            clear_all_row + 1,
            2,
            alignment=Qt.AlignmentFlag.AlignRight,
        )
        self.action_buttons["all_caches"] = clear_all
        root.addWidget(self.cached_data_group)

        self.history_group = QGroupBox("History")
        self.history_group.setObjectName("HistorySection")
        history_layout = QGridLayout(self.history_group)
        self._add_rows(history_layout, HISTORY_ACTIONS)
        root.addWidget(self.history_group)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _add_rows(
        self,
        layout: QGridLayout,
        actions: tuple[MaintenanceAction, ...],
    ) -> None:
        layout.setColumnStretch(1, 1)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        for row, action in enumerate(actions):
            title = QLabel(action.title)
            title_font = title.font()
            title_font.setBold(True)
            title.setFont(title_font)
            description = QLabel(action.description)
            description.setWordWrap(True)
            button = QPushButton("Clear…")
            button.setObjectName(f"Clear{action.key.title().replace('_', '')}Button")
            button.setMinimumWidth(86)
            button.clicked.connect(lambda _checked=False, item=action: self._run(item))
            self.action_buttons[action.key] = button
            layout.addWidget(title, row, 0)
            layout.addWidget(description, row, 1)
            layout.addWidget(button, row, 2, alignment=Qt.AlignmentFlag.AlignRight)

    def set_destructive_enabled(self, enabled: bool) -> None:
        for button in self.action_buttons.values():
            button.setEnabled(enabled)

    def _confirmed(self, title: str, message: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _run(self, action: MaintenanceAction) -> None:
        if not self._confirmed(action.confirmation_title, action.confirmation):
            return
        callback = self._callbacks[action.key]
        try:
            status = callback() or action.success_status
        except Exception as exc:
            QMessageBox.critical(
                self,
                f"Could not clear {action.title}",
                str(exc),
            )
            return
        self._status_callback(status)

    def _clear_all_caches(self) -> None:
        if not self._confirmed("Clear All Caches?", CLEAR_ALL_CONFIRMATION):
            return

        cleared: list[str] = []
        failures: list[str] = []
        for action in CACHE_ACTIONS:
            try:
                self._callbacks[action.key]()
            except Exception as exc:
                failures.append(f"{action.title}: {exc}")
            else:
                cleared.append(action.title)

        if failures:
            cleared_text = ", ".join(cleared) if cleared else "None"
            self._status_callback(
                f"Cache clear incomplete • cleared: {cleared_text} • failed: "
                + ", ".join(action.split(":", 1)[0] for action in failures)
            )
            QMessageBox.critical(
                self,
                "Could not clear all caches",
                "Some independent caches could not be cleared.\n\n"
                + "\n".join(failures)
                + f"\n\nSuccessfully cleared: {cleared_text}.",
            )
            return

        self._status_callback(
            "Store Results Cache, App Icon Cache and Alternative Store Cache cleared"
        )
