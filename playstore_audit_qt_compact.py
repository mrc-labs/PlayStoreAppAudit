from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout

from app_icon import ensure_runtime_icon
from playstore_audit_multicountry import audit_apps_multicountry
import playstore_audit_qt as qt_base
from playstore_audit_qt_branch import PlayStoreAuditQtBranch


FIXED_WORKERS = 16

# Keep functional behaviour shared with the CustomTkinter branch while using
# the existing Qt worker and result pipeline.
qt_base.audit_apps = audit_apps_multicountry
_original_classify_criticality = qt_base.classify_criticality


def _classify_criticality_multicountry(row: dict[str, object]) -> None:
    status = str(row.get("play_status") or "").strip()
    if status == "not_found_in_checked_countries":
        key = "red"
    elif status == "available_in_other_country":
        key = "blue"
    elif status == "multi_country_check_inconclusive":
        key = "purple"
    else:
        _original_classify_criticality(row)
        return

    row["criticality_key"] = key
    row["criticality"] = qt_base.CRITICALITY[key]["label"]
    row["criticality_rank"] = qt_base.CRITICALITY[key]["rank"]
    row["age_days"] = ""


qt_base.classify_criticality = _classify_criticality_multicountry


def _find_layout_containing(layout, target_widget):
    """Return the nested layout that directly contains target_widget."""
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is target_widget:
            return layout
        child_layout = item.layout()
        if child_layout is not None:
            found = _find_layout_containing(child_layout, target_widget)
            if found is not None:
                return found
    return None


class PlayStoreAuditQtCompact(PlayStoreAuditQtBranch):
    """Compact Qt6 presentation with fixed audit concurrency."""

    def __init__(self) -> None:
        qt_base.COLUMN_LABELS["package_name"] = "Package Name"
        super().__init__()

        self.setWindowIcon(QIcon(str(ensure_runtime_icon())))
        self.resize(1500, 800)
        self.setMinimumHeight(620)

        self.workers_spin.setValue(FIXED_WORKERS)
        self.exclude_system_source_check.setText("Exclude system apps from source")
        self.exclude_system_source_check.setToolTip(
            "Applied while loading a CSV/TSV/TXT file or scanning a phone with ADB. "
            "Turn it off if you want system apps included in the source list."
        )

        # Keep every source control on one horizontal line:
        # path | Choose file | ADB | Store country | system-app option.
        source_card = self.path_edit.parentWidget()
        settings_card = self.country_edit.parentWidget()
        source_layout = source_card.layout()
        source_line = _find_layout_containing(source_layout, self.path_edit)

        source_layout.removeWidget(self.exclude_system_source_check)
        self.country_edit.setParent(source_card)
        self.exclude_system_source_check.setParent(source_card)

        if source_line is not None:
            source_line.addSpacing(10)
            country_label = QLabel("Store country")
            country_label.setToolTip("Google Play market, detected from Windows Region.")
            source_line.addWidget(country_label)
            self.country_edit.setFixedWidth(58)
            source_line.addWidget(self.country_edit)
            source_line.addSpacing(8)
            source_line.addWidget(self.exclude_system_source_check)

        self.country_edit.show()
        self.exclude_system_source_check.show()
        settings_card.hide()

        # Keep app_name internally/exported, but show only Package Name as the
        # canonical identifier in the interactive table.
        self.table.setColumnHidden(0, True)
        self.model.headerDataChanged.emit(
            Qt.Orientation.Horizontal, 0, self.model.columnCount() - 1
        )
        self.table.setColumnWidth(1, 300)

        self._compact_action_row()

    def _compact_action_row(self) -> None:
        """Run | progress+status | Export | Clear on one compact row."""
        root = self.centralWidget().layout()
        action_layout = _find_layout_containing(root, self.run_button)
        progress_card = self.progress.parentWidget()
        progress_layout = progress_card.layout()

        if action_layout is None or progress_layout is None:
            return

        action_layout.removeWidget(self.export_button)
        action_layout.removeWidget(self.clear_button)
        progress_layout.removeWidget(self.progress)
        progress_layout.removeWidget(self.status_label)

        self.run_button.setMinimumWidth(215)
        self.run_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        inline_progress = QVBoxLayout()
        inline_progress.setContentsMargins(0, 0, 0, 0)
        inline_progress.setSpacing(2)
        inline_progress.addWidget(self.progress)
        inline_progress.addWidget(self.status_label)

        action_layout.insertLayout(1, inline_progress, 1)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.clear_button)
        action_layout.setStretch(0, 0)
        action_layout.setStretch(1, 1)

        root.removeWidget(progress_card)
        progress_card.hide()
        progress_card.deleteLater()

    def _start_audit(self) -> None:
        self.workers_spin.setValue(FIXED_WORKERS)
        super()._start_audit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtCompact()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
