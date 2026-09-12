from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class ChangesHistoryAvailability:
    automatic_tracking: bool
    store_tracking: bool
    store_review: bool
    store_had_baseline: bool
    device_tracking: bool
    device_review: bool
    snapshots_available: bool


class ChangesHistoryDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        availability: ChangesHistoryAvailability,
        *,
        review_store_changes: Callable[[], None],
        review_device_changes: Callable[[], None],
        save_snapshot: Callable[[], None],
        compare_snapshot: Callable[[], None],
        save_tracking_settings: Callable[
            [bool, bool, bool], ChangesHistoryAvailability
        ],
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ChangesHistoryDialog")
        self.setWindowTitle("Changes & History")
        self.setMinimumWidth(580)

        root = QVBoxLayout(self)
        intro = QLabel(
            "Optional longitudinal analysis of Store evidence and phone inventories. "
            "Manual Device Snapshots remain separate from automatic history."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        root.addWidget(intro)

        self.automatic_tracking_check = QCheckBox("Enable automatic change tracking")
        self.automatic_tracking_check.setObjectName("ChangesHistoryEnabledCheck")
        self.automatic_tracking_check.setChecked(availability.automatic_tracking)
        root.addWidget(self.automatic_tracking_check)
        automatic_note = QLabel(
            "Automatic tracking stores local comparison baselines after eligible successful audits. "
            "Turning it off preserves retained history and does not affect manual Device Snapshots."
        )
        automatic_note.setWordWrap(True)
        automatic_note.setObjectName("Muted")
        root.addWidget(automatic_note)

        self.store_group = self._section(
            root,
            "Store changes",
            "StoreChangesSection",
            "Compare current Google Play evidence with the previous successful comparable audit.",
        )
        store_layout = self.store_group.layout()
        assert isinstance(store_layout, QVBoxLayout)
        self.store_tracking_check = QCheckBox("Track Store changes between audits")
        self.store_tracking_check.setObjectName("ComparePreviousAuditCheck")
        self.store_tracking_check.setChecked(availability.store_tracking)
        store_layout.addWidget(self.store_tracking_check)
        self.store_message_label = QLabel()
        self.store_message_label.setWordWrap(True)
        store_layout.addWidget(self.store_message_label)
        self.review_store_button = QPushButton("Review Store Changes…")
        self.review_store_button.setObjectName("ReviewStoreChangesButton")
        self.review_store_button.setVisible(availability.store_review)
        self.review_store_button.clicked.connect(
            lambda _checked=False: review_store_changes()
        )
        store_layout.addWidget(self.review_store_button)

        self.device_group = self._section(
            root,
            "Device changes",
            "DeviceChangesSection",
            "Compare the current phone inventory with the previous completed audit of the same device.",
        )
        device_layout = self.device_group.layout()
        assert isinstance(device_layout, QVBoxLayout)
        self.device_tracking_check = QCheckBox("Track changes between phone audits")
        self.device_tracking_check.setObjectName("InventoryHistoryCheck")
        self.device_tracking_check.setChecked(availability.device_tracking)
        device_layout.addWidget(self.device_tracking_check)
        self.device_message_label = QLabel()
        self.device_message_label.setWordWrap(True)
        device_layout.addWidget(self.device_message_label)
        self.review_device_button = QPushButton("Review Device Changes…")
        self.review_device_button.setObjectName("ReviewDeviceChangesButton")
        self.review_device_button.setVisible(availability.device_review)
        self.review_device_button.clicked.connect(
            lambda _checked=False: review_device_changes()
        )
        device_layout.addWidget(self.review_device_button)

        self.snapshots_group = self._section(
            root,
            "Device Snapshots",
            "DeviceSnapshotsSection",
            "Save or compare a manual point-in-time snapshot. Automatic history never overwrites snapshots.",
        )
        snapshots_layout = self.snapshots_group.layout()
        assert isinstance(snapshots_layout, QVBoxLayout)
        snapshot_actions = QHBoxLayout()
        self.save_snapshot_button = QPushButton("Save Current Snapshot…")
        self.save_snapshot_button.setObjectName("SaveCurrentSnapshotButton")
        self.save_snapshot_button.setEnabled(availability.snapshots_available)
        self.save_snapshot_button.clicked.connect(lambda _checked=False: save_snapshot())
        snapshot_actions.addWidget(self.save_snapshot_button)
        self.compare_snapshot_button = QPushButton("Compare with Snapshot…")
        self.compare_snapshot_button.setObjectName("CompareWithSnapshotButton")
        self.compare_snapshot_button.setEnabled(availability.snapshots_available)
        self.compare_snapshot_button.clicked.connect(
            lambda _checked=False: compare_snapshot()
        )
        snapshot_actions.addWidget(self.compare_snapshot_button)
        snapshot_actions.addStretch(1)
        snapshots_layout.addLayout(snapshot_actions)

        self.settings_status_label = QLabel()
        self.settings_status_label.setObjectName("ChangesHistorySettingsStatus")
        root.addWidget(self.settings_status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close
        )
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        assert self.apply_button is not None
        self.apply_button.clicked.connect(self._apply_tracking_settings)
        buttons.rejected.connect(self.close)
        root.addWidget(buttons)

        self._availability = availability
        self._save_tracking_settings = save_tracking_settings
        self.automatic_tracking_check.toggled.connect(self._tracking_setting_changed)
        self.store_tracking_check.toggled.connect(self._tracking_setting_changed)
        self.device_tracking_check.toggled.connect(self._tracking_setting_changed)
        self._refresh_tracking_state()

    def _tracking_setting_changed(self) -> None:
        self.settings_status_label.clear()
        self._refresh_tracking_state()

    def _apply_tracking_settings(self) -> None:
        self._availability = self._save_tracking_settings(
            self.automatic_tracking_check.isChecked(),
            self.store_tracking_check.isChecked(),
            self.device_tracking_check.isChecked(),
        )
        self.automatic_tracking_check.setChecked(self._availability.automatic_tracking)
        self.store_tracking_check.setChecked(self._availability.store_tracking)
        self.device_tracking_check.setChecked(self._availability.device_tracking)
        self.settings_status_label.setText("Settings saved.")
        self._refresh_tracking_state()

    def _refresh_tracking_state(self) -> None:
        automatic = self.automatic_tracking_check.isChecked()
        store_tracking = automatic and self.store_tracking_check.isChecked()
        device_tracking = automatic and self.device_tracking_check.isChecked()
        self.store_tracking_check.setEnabled(automatic)
        self.device_tracking_check.setEnabled(automatic)

        if not store_tracking:
            store_message = "Tracking is Off."
        elif self._availability.store_review:
            store_message = "Meaningful changes are available from the current comparison."
        elif self._availability.store_had_baseline:
            store_message = "No meaningful Store changes were detected in the current comparison."
        else:
            store_message = (
                "The first successful comparable audit establishes a baseline; "
                "a later audit can report changes."
            )
        self.store_message_label.setText(store_message)
        self.review_store_button.setVisible(
            store_tracking and self._availability.store_review
        )

        device_message = (
            "Automatic comparison can report added or removed apps, version changes, "
            "installer changes and enabled-state changes."
        )
        if not device_tracking:
            device_message += " Tracking is Off."
        elif not self._availability.device_review:
            device_message += " Two completed audits of the same phone establish a comparison."
        self.device_message_label.setText(device_message)
        self.review_device_button.setVisible(
            device_tracking and self._availability.device_review
        )

    @staticmethod
    def _section(
        root: QVBoxLayout, title: str, object_name: str, purpose: str
    ) -> QGroupBox:
        group = QGroupBox(title)
        group.setObjectName(object_name)
        layout = QVBoxLayout(group)
        purpose_label = QLabel(purpose)
        purpose_label.setWordWrap(True)
        layout.addWidget(purpose_label)
        root.addWidget(group)
        return group
