from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
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
        self.setMinimumWidth(680)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        intro = QLabel(
            "Track changes across audits or save manual device snapshots. "
            "Disabling automatic tracking never deletes retained data."
        )
        intro.setWordWrap(True)
        intro.setObjectName("Muted")
        root.addWidget(intro)

        self.automatic_tracking_check = QCheckBox("Enable automatic change tracking")
        self.automatic_tracking_check.setObjectName("ChangesHistoryEnabledCheck")
        self.automatic_tracking_check.setChecked(availability.automatic_tracking)
        master_font = self.automatic_tracking_check.font()
        master_font.setBold(True)
        self.automatic_tracking_check.setFont(master_font)
        root.addWidget(self.automatic_tracking_check)

        automatic_note = QLabel(
            "Automatic tracking saves local comparison baselines after eligible successful audits. "
            "Manual Device Snapshots remain independent."
        )
        automatic_note.setWordWrap(True)
        automatic_note.setObjectName("Muted")
        root.addWidget(automatic_note)

        self._add_separator(root)

        self.store_section, store_layout = self._section(
            root,
            "Play Store changes",
            "StoreChangesSection",
        )
        self.store_tracking_check = QCheckBox("Track Play Store listing changes")
        self.store_tracking_check.setObjectName("ComparePreviousAuditCheck")
        self.store_tracking_check.setChecked(availability.store_tracking)
        store_layout.addWidget(self.store_tracking_check)
        store_note = QLabel(
            "Detect availability, Store version and update-status changes between audits."
        )
        store_note.setWordWrap(True)
        store_note.setObjectName("Muted")
        store_layout.addWidget(store_note)
        self.store_message_label = QLabel()
        self.store_message_label.setWordWrap(True)
        store_layout.addWidget(self.store_message_label)
        store_actions = QHBoxLayout()
        store_actions.addStretch(1)
        self.review_store_button = QPushButton("Review Play Store Changes…")
        self.review_store_button.setObjectName("ReviewStoreChangesButton")
        self.review_store_button.setVisible(availability.store_review)
        self.review_store_button.clicked.connect(
            lambda _checked=False: review_store_changes()
        )
        store_actions.addWidget(self.review_store_button)
        store_layout.addLayout(store_actions)

        self._add_separator(root)

        self.device_section, device_layout = self._section(
            root,
            "Device changes",
            "DeviceChangesSection",
        )
        self.device_tracking_check = QCheckBox("Track device app inventory changes")
        self.device_tracking_check.setObjectName("InventoryHistoryCheck")
        self.device_tracking_check.setChecked(availability.device_tracking)
        device_layout.addWidget(self.device_tracking_check)
        device_note = QLabel(
            "Detect installed, removed, version, installer and enabled-state changes "
            "between scans of the same phone."
        )
        device_note.setWordWrap(True)
        device_note.setObjectName("Muted")
        device_layout.addWidget(device_note)
        self.device_message_label = QLabel()
        self.device_message_label.setWordWrap(True)
        device_layout.addWidget(self.device_message_label)
        device_actions = QHBoxLayout()
        device_actions.addStretch(1)
        self.review_device_button = QPushButton("Review Device Changes…")
        self.review_device_button.setObjectName("ReviewDeviceChangesButton")
        self.review_device_button.setVisible(availability.device_review)
        self.review_device_button.clicked.connect(
            lambda _checked=False: review_device_changes()
        )
        device_actions.addWidget(self.review_device_button)
        device_layout.addLayout(device_actions)

        self._add_separator(root)

        self.snapshots_section, snapshots_layout = self._section(
            root,
            "Device Snapshots",
            "DeviceSnapshotsSection",
        )
        snapshots_note = QLabel(
            "Save or compare a manual point-in-time snapshot. Automatic history never "
            "overwrites snapshots."
        )
        snapshots_note.setWordWrap(True)
        snapshots_note.setObjectName("Muted")
        snapshots_layout.addWidget(snapshots_note)
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
        self.settings_status_label.setVisible(False)
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
        self.settings_status_label.setVisible(False)
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
        self.settings_status_label.setVisible(True)
        self._refresh_tracking_state()

    def _refresh_tracking_state(self) -> None:
        automatic = self.automatic_tracking_check.isChecked()
        store_tracking = automatic and self.store_tracking_check.isChecked()
        device_tracking = automatic and self.device_tracking_check.isChecked()
        self.store_tracking_check.setEnabled(automatic)
        self.device_tracking_check.setEnabled(automatic)

        if not store_tracking:
            store_message = "Automatic Play Store tracking is Off."
        elif self._availability.store_review:
            store_message = "Meaningful Play Store changes are available from the current comparison."
        elif self._availability.store_had_baseline:
            store_message = "No meaningful Play Store changes were detected in the current comparison."
        else:
            store_message = (
                "The first successful comparable audit establishes a baseline; "
                "a later audit can report changes."
            )
        self.store_message_label.setText(store_message)
        self.review_store_button.setVisible(
            store_tracking and self._availability.store_review
        )

        if not device_tracking:
            device_message = "Automatic device app inventory tracking is Off."
        elif self._availability.device_review:
            device_message = "Device inventory changes are available from the current comparison."
        else:
            device_message = "Two completed audits of the same phone establish a comparison."
        self.device_message_label.setText(device_message)
        self.review_device_button.setVisible(
            device_tracking and self._availability.device_review
        )

    @staticmethod
    def _add_separator(root: QVBoxLayout) -> None:
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        root.addWidget(separator)

    @staticmethod
    def _section(
        root: QVBoxLayout, title: str, object_name: str
    ) -> tuple[QWidget, QVBoxLayout]:
        section = QWidget()
        section.setObjectName(object_name)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        heading = QLabel(title)
        heading.setObjectName(f"{object_name}Title")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)

        root.addWidget(section)
        return section, layout
