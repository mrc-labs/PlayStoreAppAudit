from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu

from app_icon import ensure_runtime_icon
import playstore_audit_qt_v9_2 as v92ui
import playstore_audit_v9_2_features as v92
import playstore_audit_user_state as user_state


class PlayStoreAuditQtV92Stable(v92ui.PlayStoreAuditQtV92):
    """Stable v9.2 Qt wrapper keeping native menu objects referenced by Python."""

    def __init__(self) -> None:
        self._defer_v92_menu_build = True
        super().__init__()
        self._defer_v92_menu_build = False
        self._build_menu_v9()

    def _build_menu_v9(self) -> None:
        if getattr(self, "_defer_v92_menu_build", False):
            return

        bar = self.menuBar()
        bar.clear()

        # Construct QMenu objects explicitly with a persistent parent. This is
        # more robust across PySide ownership transitions than the addMenu(str)
        # convenience overload when an inheritance chain rebuilt the menu bar.
        self.file_menu = QMenu("File", bar)
        bar.addMenu(self.file_menu)
        self.file_menu.addAction("Choose app list…", self._choose_input)
        self.recent_menu = QMenu("Recent sources", self.file_menu)
        self.file_menu.addMenu(self.recent_menu)
        self._recent_menu = self.recent_menu
        self._populate_recent_menu()
        self.file_menu.addAction("Scan phone with ADB", self._scan_phone)
        self.file_menu.addAction("Export current phone package list as CSV…", self._export_phone_packages_csv)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Export all results as CSV…", self._export_results)
        self.file_menu.addAction("Export visible results as CSV…", self._export_visible_results)
        self.file_menu.addAction("Export HTML report…", self._export_html_report)
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)

        self.view_menu = QMenu("View", bar)
        bar.addMenu(self.view_menu)
        self.view_presets_menu = QMenu("View preset", self.view_menu)
        self.view_menu.addMenu(self.view_presets_menu)
        self.view_action_group = QActionGroup(self)
        self.view_action_group.setExclusive(True)
        current = str(user_state.load_settings().get("view_preset") or "Basic")
        self.view_preset_actions = []
        for name in v92.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            self.view_action_group.addAction(action)
            self.view_presets_menu.addAction(action)
            self.view_preset_actions.append(action)
        self._view_action_group = self.view_action_group
        self.view_menu.addSeparator()
        self.reset_layout_action = self.view_menu.addAction("Reset table layout", self._reset_table_layout)

        self.tools_menu = QMenu("Tools", bar)
        bar.addMenu(self.tools_menu)
        self.tools_menu.addAction("Advanced settings…", self._show_advanced_settings)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Force full refresh (ignore cache)", self._force_full_refresh)
        self.tools_menu.addAction("Recheck Removed / Anomaly / Other", self._recheck_problematic)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Device summary…", self._show_device_summary)
        self.snapshots_menu = QMenu("Device snapshots", self.tools_menu)
        self.tools_menu.addMenu(self.snapshots_menu)
        self.snapshots_menu.addAction("Save current device snapshot…", self._save_device_snapshot)
        self.snapshots_menu.addAction("Compare current device with snapshot…", self._compare_device_snapshot)
        self.tools_menu.addAction("Device inventory changes…", self._show_inventory_changes)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction("Clear audit cache", self._clear_audit_cache)
        self.tools_menu.addAction("Clear previous-audit history", self._clear_audit_history)

        self.help_menu = QMenu("Help", bar)
        bar.addMenu(self.help_menu)
        self.help_menu.addAction("ADB setup guide…", lambda: self._show_text_help("ADB setup guide", v92ui.v9.features.ADB_SETUP_GUIDE))
        self.help_menu.addAction("How to export package CSV…", lambda: self._show_text_help("Export package CSV", v92.CSV_EXPORT_GUIDE))
        self.help_menu.addAction("Health score methodology…", lambda: self._show_text_help("Health score methodology", v92ui.v9.features.HEALTH_SCORE_GUIDE))
        self.help_menu.addSeparator()
        self.help_menu.addAction("Check for updates…", self._check_for_updates)
        self.help_menu.addAction("Create diagnostic bundle…", self._create_diagnostic_bundle)
        self.help_menu.addSeparator()
        self.help_menu.addAction("About Play Store App Audit", self._show_about)

    def _update_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        base_rows = self._rows_before_criticality_filter()
        criticality = v92ui.v9.v8.v7.qt_base.CRITICALITY
        counts = {
            key: sum(1 for row in base_rows if str(row.get("criticality_key") or "") == key)
            for key in criticality
        }
        if hasattr(self, "criticality_buttons"):
            for key, button in self.criticality_buttons.items():
                button.setText(f"{criticality[key]['button']} {counts[key]}")
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        self.summary_label.setText(v92.concise_summary(list(self.current_rows), visible))

    def _clear_results(self) -> None:
        self._status_filters.clear()
        super()._clear_results()
        if isinstance(self.proxy, v92ui.V92FilterProxy):
            self.proxy.set_status_filters(set())
        self._sync_status_filter_buttons()
        self._update_summary()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(v92ui.v9.v8.v7.qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtV92Stable()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
