from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit.services import local_apk_duplicates as duplicates


class LocalApkDuplicatesDialog(QDialog):
    def __init__(self, parent: QWidget | None, review: duplicates.DuplicateReview) -> None:
        super().__init__(parent)
        self.review = duplicates.snapshot_duplicate_review(review)
        self.plan = duplicates.DuplicateCleanupPlan()
        self._exact_files: list[duplicates.DuplicateFile] = []
        self.setWindowTitle("Review Local APK Duplicates")
        self.setModal(True)
        self.resize(1100, 600)
        self.setMinimumSize(780, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Exact duplicates have identical SHA-256 artifact bytes. Select physical copies explicitly. "
            "Cleanup always keeps at least one exact copy per group. "
            "Variants and versions are informational only."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.tabs = QTabWidget()
        self.exact_table = self._table(
            [
                "Remove",
                "SHA-256 group",
                "Filename",
                "App / package",
                "Local version",
                "Physical path / review",
            ]
        )
        for group in self.review.exact_groups:
            group_error = next((file.error for file in group.files if file.error), "")
            for file in group.files:
                index = self.exact_table.rowCount()
                self.exact_table.insertRow(index)
                self._exact_files.append(file)
                check = QTableWidgetItem()
                check.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                check.setCheckState(Qt.CheckState.Unchecked)
                if group_error:
                    check.setFlags(Qt.ItemFlag.NoItemFlags)
                self.exact_table.setItem(index, 0, check)
                self._fill(
                    self.exact_table,
                    index,
                    (
                        group.sha256,
                        file.source.name,
                        self._identity(file),
                        file.version_label,
                        f"{file.source}" + (f"\nBlocked: {group_error}" if group_error else ""),
                    ),
                    start_column=1,
                )
        self.exact_table.setColumnWidth(0, 65)
        self.exact_table.setColumnWidth(1, 170)
        self.tabs.addTab(self.exact_table, f"Exact Duplicates ({len(self.review.exact_groups)})")
        self.versions_table = self._table(
            ["Finding", "App / package", "Local version", "SHA-256", "Physical path"]
        )
        for finding in self.review.version_findings:
            for file in finding.files:
                index = self.versions_table.rowCount()
                self.versions_table.insertRow(index)
                self._fill(
                    self.versions_table,
                    index,
                    (
                        finding.kind.value,
                        self._identity(file),
                        file.version_label,
                        file.sha256 or "Unknown SHA-256",
                        str(file.source),
                    ),
                )
        self.tabs.addTab(self.versions_table, f"Variants / Versions ({len(self.review.version_findings)})")
        if not self.review.exact_groups:
            self.tabs.setCurrentIndex(1)
        layout.addWidget(self.tabs, 1)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.remove_button = QPushButton("Remove Selected Duplicate Copies…")
        self.remove_button.setAutoDefault(False)
        self.button_box.addButton(self.remove_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.remove_button.clicked.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.exact_table.itemChanged.connect(self._update_plan)
        self.tabs.currentChanged.connect(self._update_plan)
        self._update_plan()

    @staticmethod
    def _identity(file: duplicates.DuplicateFile) -> str:
        return f"{file.app_name or 'Unknown app'}\n{file.package_name or 'Unknown package'}"

    @staticmethod
    def _table(headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        return table

    @staticmethod
    def _fill(table: QTableWidget, row: int, values: tuple[str, ...], start_column: int = 0) -> None:
        for column, value in enumerate(values, start_column):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            table.setItem(row, column, item)
        table.resizeRowToContents(row)

    def selected_paths(self) -> tuple[Path, ...]:
        return tuple(
            file.source
            for index, file in enumerate(self._exact_files)
            if self.exact_table.item(index, 0).checkState() == Qt.CheckState.Checked
        )

    def _update_plan(self) -> None:
        self.plan = duplicates.plan_duplicate_cleanup(self.review, self.selected_paths())
        self.remove_button.setEnabled(self.plan.executable and self.tabs.currentIndex() == 0)
        self.validation_label.setText(
            self.plan.error
            or (
                f"Selected for removal: {self.plan.selected_count}. Unselected exact copies will be revalidated and kept."
                if self.plan.selected_count
                else "No copies selected. Versions and variants have no cleanup action."
            )
        )

    def accept(self) -> None:
        self._update_plan()
        if self.remove_button.isEnabled():
            super().accept()
