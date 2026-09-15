from __future__ import annotations

from collections.abc import Mapping, Sequence

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.local_apk_mass_rename as mass_rename

DEFAULT_MASS_RENAME_TEMPLATE = "{packagename}_{localversion}"

TOKEN_GUIDANCE = (
    "Tokens: {packagename}, {appname}, {playname}, "
    "{category}, {localversion}. "
    "The original package extension is preserved automatically."
)


class LocalApkMassRenameDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        rows: Sequence[Mapping[str, object]],
    ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Mass Rename Local Package Files")
        self.setModal(True)
        self.resize(980, 560)
        self.setMinimumSize(760, 420)

        self._rows = tuple(rows)
        self.plan = mass_rename.MassRenamePlan(
            template="",
            entries=(),
            error="",
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Build and review the complete filename plan before "
            "changing any files."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.template_edit = QLineEdit(
            DEFAULT_MASS_RENAME_TEMPLATE
        )
        self.template_edit.setObjectName(
            "LocalApkMassRenameTemplate"
        )
        self.template_edit.setClearButtonEnabled(True)
        self.template_edit.setAccessibleName(
            "Mass Rename Template"
        )
        layout.addWidget(self.template_edit)

        self.token_label = QLabel(TOKEN_GUIDANCE)
        self.token_label.setWordWrap(True)
        self.token_label.setObjectName("Muted")
        layout.addWidget(self.token_label)

        self.counts_label = QLabel()
        self.counts_label.setObjectName(
            "LocalApkMassRenameCounts"
        )
        layout.addWidget(self.counts_label)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setObjectName(
            "LocalApkMassRenameValidation"
        )
        layout.addWidget(self.error_label)

        self.preview_table = QTableWidget(0, 4)
        self.preview_table.setObjectName(
            "LocalApkMassRenamePreview"
        )
        self.preview_table.setHorizontalHeaderLabels(
            [
                "Current filename",
                "Proposed filename",
                "Status",
                "Reason",
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

        layout.addWidget(self.preview_table, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
        )

        self.rename_button = QPushButton("Rename Files")
        self.rename_button.setObjectName(
            "LocalApkMassRenameExecute"
        )
        self.button_box.addButton(
            self.rename_button,
            QDialogButtonBox.ButtonRole.AcceptRole,
        )

        self.button_box.rejected.connect(self.reject)
        self.rename_button.clicked.connect(self.accept)
        layout.addWidget(self.button_box)

        self.template_edit.textChanged.connect(
            self._refresh_plan
        )
        self._refresh_plan()

    @staticmethod
    def _status_counts(
        plan: mass_rename.MassRenamePlan,
    ) -> dict[mass_rename.MassRenamePlanStatus, int]:
        return {
            status: sum(
                entry.status is status
                for entry in plan.entries
            )
            for status in mass_rename.MassRenamePlanStatus
        }

    def _refresh_plan(self) -> None:
        self.plan = mass_rename.plan_local_package_mass_rename(
            self._rows,
            self.template_edit.text(),
        )

        counts = self._status_counts(self.plan)

        self.counts_label.setText(
            "Rename: "
            f"{counts[mass_rename.MassRenamePlanStatus.RENAME]}  •  "
            "Unchanged: "
            f"{counts[mass_rename.MassRenamePlanStatus.UNCHANGED]}  •  "
            "Invalid: "
            f"{counts[mass_rename.MassRenamePlanStatus.INVALID]}  •  "
            "Conflict: "
            f"{counts[mass_rename.MassRenamePlanStatus.CONFLICT]}"
        )

        if self.plan.error:
            validation_text = self.plan.error
        elif self.plan.has_blocking_issues:
            validation_text = (
                "Resolve all invalid or conflicting entries before "
                "executing Mass Rename."
            )
        elif self.plan.rename_count == 0:
            validation_text = "No files require renaming."
        else:
            validation_text = (
                "Preview valid. Review the filenames before continuing."
            )

        self.error_label.setText(validation_text)

        self.preview_table.setRowCount(
            len(self.plan.entries)
        )

        for row_index, entry in enumerate(self.plan.entries):
            proposed = (
                entry.destination.name
                if entry.destination is not None
                else entry.rendered_filename or "—"
            )

            values = (
                entry.source.name,
                proposed,
                entry.status.value.replace("_", " ").title(),
                entry.message,
            )

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if entry.message:
                    item.setToolTip(entry.message)
                self.preview_table.setItem(
                    row_index,
                    column,
                    item,
                )

        self.rename_button.setEnabled(
            self.plan.rename_count > 0
            and not self.plan.has_blocking_issues
        )
