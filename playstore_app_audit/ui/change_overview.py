from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.change_overview as change_service

PACKAGE_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class ChangeOverviewDialog(QDialog):
    package_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Audit changes")
        self.resize(760, 620)
        self.setModal(False)

        root = QVBoxLayout(self)
        self.summary_label = QLabel()
        summary_font = QFont(self.summary_label.font())
        summary_font.setBold(True)
        self.summary_label.setFont(summary_font)
        root.addWidget(self.summary_label)

        self.hint_label = QLabel(
            "Select an app to focus its current result and inspect the full evidence in the details panel."
        )
        self.hint_label.setWordWrap(True)
        self.hint_label.setObjectName("Muted")
        root.addWidget(self.hint_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Change / app", "Details"])
        self.tree.setRootIsDecorated(True)
        self.tree.setAlternatingRowColors(True)
        self.tree.itemClicked.connect(self._on_item_selected)
        self.tree.itemActivated.connect(self._on_item_selected)
        self.tree.header().setStretchLastSection(True)
        self.tree.setColumnWidth(0, 360)
        root.addWidget(self.tree, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        buttons.clicked.connect(self.close)
        root.addWidget(buttons)
        self.set_groups([])

    def set_groups(self, groups: list[dict[str, Any]]) -> None:
        self.tree.clear()
        total = change_service.total_change_count(groups)
        if not groups:
            self.summary_label.setText("No meaningful changes recorded against the available baselines.")
            self.hint_label.setText(
                "Play Store changes require previous-audit comparison; device install/remove changes require at least two inventories of the same phone."
            )
            return

        group_word = "group" if len(groups) == 1 else "groups"
        change_word = "change" if total == 1 else "changes"
        self.summary_label.setText(f"{total} {change_word} across {len(groups)} {group_word}")
        self.hint_label.setText(
            "Select an app to focus its current result and inspect the full evidence in the details panel. Removed-from-device entries remain listed even though they no longer have a current row."
        )

        for group in groups:
            label = str(group.get("label") or group.get("key") or "Changes")
            count = int(group.get("count") or 0)
            parent = QTreeWidgetItem([f"{label} ({count})", ""])
            font = QFont(parent.font(0))
            font.setBold(True)
            parent.setFont(0, font)
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.tree.addTopLevelItem(parent)

            items = group.get("items")
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                package = str(item.get("package_name") or "").strip()
                title = str(item.get("title") or package).strip()
                detail = str(item.get("detail") or "").strip()
                display = title if title == package or not package else f"{title}\n{package}"
                child = QTreeWidgetItem([display, detail])
                child.setData(0, PACKAGE_ROLE, package)
                parent.addChild(child)
            parent.setExpanded(True)

    def _on_item_selected(self, item: QTreeWidgetItem, _column: int) -> None:
        package = str(item.data(0, PACKAGE_ROLE) or "").strip()
        if package:
            self.package_selected.emit(package)
