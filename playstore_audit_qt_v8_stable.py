from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication

from app_icon import ensure_runtime_icon
import playstore_audit_qt_v8 as v8


class PlayStoreAuditQtV8Stable(v8.PlayStoreAuditQtV8):
    """Qt v8 with persistent QMenu references.

    Keeping the menu wrappers on self avoids their Python wrappers being
    garbage-collected while the native menu bar still owns the C++ objects.
    """

    def _build_menu_v8(self) -> None:
        menu = self.menuBar()
        menu.clear()

        self.file_menu = menu.addMenu("File")
        self.choose_action = QAction("Choose app list…", self)
        self.choose_action.triggered.connect(self._choose_input)
        self.file_menu.addAction(self.choose_action)
        self.scan_action = QAction("Scan phone with ADB", self)
        self.scan_action.triggered.connect(self._scan_phone)
        self.file_menu.addAction(self.scan_action)
        self.file_menu.addSeparator()
        self.export_all_action = QAction("Export all results…", self)
        self.export_all_action.triggered.connect(self._export_results)
        self.file_menu.addAction(self.export_all_action)
        self.export_visible_action = QAction("Export visible results…", self)
        self.export_visible_action.triggered.connect(self._export_visible_results)
        self.file_menu.addAction(self.export_visible_action)
        self.file_menu.addSeparator()
        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

        self.tools_menu = menu.addMenu("Tools")
        self.advanced_action = QAction("Advanced settings…", self)
        self.advanced_action.triggered.connect(self._show_advanced_settings)
        self.tools_menu.addAction(self.advanced_action)
        self.tools_menu.addSeparator()
        self.force_refresh_action = QAction("Force full refresh (ignore cache)", self)
        self.force_refresh_action.triggered.connect(self._force_full_refresh)
        self.tools_menu.addAction(self.force_refresh_action)
        self.retry_problematic_action = QAction("Recheck Removed / Anomaly / Other", self)
        self.retry_problematic_action.triggered.connect(self._recheck_problematic)
        self.tools_menu.addAction(self.retry_problematic_action)
        self.tools_menu.addSeparator()
        self.clear_cache_action = QAction("Clear audit cache", self)
        self.clear_cache_action.triggered.connect(self._clear_audit_cache)
        self.tools_menu.addAction(self.clear_cache_action)
        self.clear_history_action = QAction("Clear previous-audit history", self)
        self.clear_history_action.triggered.connect(self._clear_audit_history)
        self.tools_menu.addAction(self.clear_history_action)
        self.reset_layout_action = QAction("Reset table layout", self)
        self.reset_layout_action.triggered.connect(self._reset_table_layout)
        self.tools_menu.addAction(self.reset_layout_action)

        self.help_menu = menu.addMenu("Help")
        self.about_action = QAction("About Play Store App Audit", self)
        self.about_action.triggered.connect(self._show_about)
        self.help_menu.addAction(self.about_action)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(v8.v7.qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtV8Stable()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
