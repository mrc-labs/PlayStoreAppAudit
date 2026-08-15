from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel

import playstore_audit_qt as qt_base
from playstore_audit_qt_branch import PlayStoreAuditQtBranch


FIXED_WORKERS = 16


class PlayStoreAuditQtCompact(PlayStoreAuditQtBranch):
    """Compact Qt6 presentation with fixed audit concurrency.

    Functional behaviour remains the same as the branch implementation; this
    class only simplifies the visible controls and result columns.
    """

    def __init__(self) -> None:
        # The base table model reads this mapping dynamically.
        qt_base.COLUMN_LABELS["package_name"] = "Package Name"
        super().__init__()

        self.workers_spin.setValue(FIXED_WORKERS)
        self.exclude_system_source_check.setText("Exclude system apps from source")
        self.exclude_system_source_check.setToolTip(
            "Applied while loading a CSV/TSV/TXT file or scanning a phone with ADB. "
            "Turn it off if you want system apps included in the source list."
        )

        # Move Store country next to the source-level system-app choice and
        # remove the now-unnecessary standalone Audit settings card.
        source_card = self.path_edit.parentWidget()
        settings_card = self.country_edit.parentWidget()
        source_layout = source_card.layout()

        source_layout.removeWidget(self.exclude_system_source_check)
        self.country_edit.setParent(source_card)
        self.exclude_system_source_check.setParent(source_card)

        source_options = QHBoxLayout()
        source_options.setSpacing(8)
        country_label = QLabel("Store country")
        country_label.setToolTip("Google Play market, detected from Windows Region.")
        source_options.addWidget(country_label)
        source_options.addWidget(self.country_edit)
        source_options.addSpacing(14)
        source_options.addWidget(self.exclude_system_source_check)
        source_options.addStretch(1)
        source_layout.insertLayout(2, source_options)

        self.country_edit.show()
        self.exclude_system_source_check.show()
        settings_card.hide()

        # Input name is retained internally/exported, but it is redundant in
        # the interactive table. Package Name is the canonical visible key.
        self.table.setColumnHidden(0, True)
        self.model.headerDataChanged.emit(
            Qt.Orientation.Horizontal, 0, self.model.columnCount() - 1
        )
        self.table.setColumnWidth(1, 300)

    def _start_audit(self) -> None:
        # Fixed hidden concurrency. English is already fixed internally by the
        # Qt branch implementation.
        self.workers_spin.setValue(FIXED_WORKERS)
        super()._start_audit()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    window = PlayStoreAuditQtCompact()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
