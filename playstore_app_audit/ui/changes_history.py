from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
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

        self.store_group = self._section(
            root,
            "Store changes",
            "StoreChangesSection",
            "Compare current Google Play evidence with the previous successful comparable audit.",
        )
        store_layout = self.store_group.layout()
        assert isinstance(store_layout, QVBoxLayout)
        self.store_tracking_label = self._tracking_label(availability.store_tracking)
        self.store_tracking_label.setObjectName("StoreChangesTrackingState")
        store_layout.addWidget(self.store_tracking_label)
        if not availability.store_tracking:
            store_message = "Tracking is Off. Enable the Store child option in Advanced Settings."
        elif availability.store_review:
            store_message = "Meaningful changes are available from the current comparison."
        elif availability.store_had_baseline:
            store_message = "No meaningful Store changes were detected in the current comparison."
        else:
            store_message = (
                "The first successful comparable audit establishes a baseline; "
                "a later audit can report changes."
            )
        self.store_message_label = QLabel(store_message)
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
        self.device_tracking_label = self._tracking_label(availability.device_tracking)
        self.device_tracking_label.setObjectName("DeviceChangesTrackingState")
        device_layout.addWidget(self.device_tracking_label)
        device_message = (
            "Automatic comparison can report added or removed apps, version changes, "
            "installer changes and enabled-state changes."
        )
        if not availability.device_tracking:
            device_message += " Tracking is Off in Advanced Settings."
        elif not availability.device_review:
            device_message += " Two completed audits of the same phone establish a comparison."
        self.device_message_label = QLabel(device_message)
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        buttons.clicked.connect(self.close)
        root.addWidget(buttons)

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

    @staticmethod
    def _tracking_label(enabled: bool) -> QLabel:
        label = QLabel(f"Tracking: {'On' if enabled else 'Off'}")
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label
