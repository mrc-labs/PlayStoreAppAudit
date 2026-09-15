from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.local_apk_mass_remove as mass_remove


class LocalApkMassRemoveDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        plan: mass_remove.MassRemovePlan,
    ) -> None:
        super().__init__(parent)

        self.plan = plan

        self.setWindowTitle(
            f"Remove All {plan.target.value} Local Package Files"
        )
        self.setModal(True)
        self.resize(1040, 560)
        self.setMinimumSize(780, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Review the exact physical files selected for permanent "
            "deletion. Opening this preview does not modify any file."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.counts_label = QLabel(
            f"Selected: {plan.runnable_count}  •  "
            f"Blocked: {plan.blocked_count}  •  "
            f"Active source files: {plan.active_candidate_count}"
        )
        self.counts_label.setObjectName(
            "LocalApkMassRemoveCounts"
        )
        layout.addWidget(self.counts_label)

        if plan.error:
            validation_text = plan.error
        elif plan.blocked_count:
            validation_text = (
                "Blocked entries will not be deleted. "
                "Only runnable physical files can be confirmed."
            )
        elif plan.runnable_count:
            validation_text = (
                "Preview valid. Review every path before continuing."
            )
        else:
            validation_text = (
                "No files are eligible for removal."
            )

        self.validation_label = QLabel(validation_text)
        self.validation_label.setWordWrap(True)
        self.validation_label.setObjectName(
            "LocalApkMassRemoveValidation"
        )
        layout.addWidget(self.validation_label)

        self.preview_table = QTableWidget(0, 5)
        self.preview_table.setObjectName(
            "LocalApkMassRemovePreview"
        )
        self.preview_table.setHorizontalHeaderLabels(
            [
                "Filename",
                "App / package",
                "APK vs Store",
                "Physical path",
                "Status / reason",
            ]
        )
        self.preview_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.preview_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setVisible(False)

        header = self.preview_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )

        self.preview_table.setRowCount(
            len(plan.entries)
        )

        for row_index, entry in enumerate(plan.entries):
            identity = (
                entry.app_name
                or entry.package_name
                or "—"
            )

            if (
                entry.app_name
                and entry.package_name
                and entry.app_name != entry.package_name
            ):
                identity = (
                    f"{entry.app_name} "
                    f"({entry.package_name})"
                )

            status_text = (
                "Ready to remove"
                if (
                    entry.status
                    is mass_remove.MassRemovePlanStatus.RUNNABLE
                )
                else entry.message or "Blocked"
            )

            values = (
                entry.file_name,
                identity,
                entry.relationship,
                str(entry.source),
                status_text,
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))

                if column in {3, 4}:
                    item.setToolTip(str(value))

                self.preview_table.setItem(
                    row_index,
                    column,
                    item,
                )

        layout.addWidget(
            self.preview_table,
            1,
        )

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
        )

        self.remove_button = QPushButton(
            "Remove Files Permanently"
        )
        self.remove_button.setObjectName(
            "LocalApkMassRemoveExecute"
        )
        self.remove_button.setAccessibleName(
            "Remove Local Package Files Permanently"
        )

        self.button_box.addButton(
            self.remove_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )

        self.button_box.rejected.connect(
            self.reject
        )
        self.remove_button.clicked.connect(
            self.accept
        )

        self.remove_button.setEnabled(
            plan.runnable_count > 0
        )

        layout.addWidget(self.button_box)
