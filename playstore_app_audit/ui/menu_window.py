from __future__ import annotations

import sys

from PySide6.QtGui import QAction, QActionGroup, QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.sdk_maintenance as sdk_maintenance
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.audit_profiles as audit_profiles_ui
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.json_export as json_export_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
from playstore_app_audit import help_texts
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.ui import rich_help
from playstore_app_audit.ui.file_menu import add_result_actions


class MenuWindow(preferences_ui.PreferencesWindow):
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
        self.file_choose_source_action = self.file_menu.addAction(
            "Choose App List…", self._choose_input
        )
        self.recent_menu = QMenu("Recent Sources", self.file_menu)
        self.file_menu.addMenu(self.recent_menu)
        self._recent_menu = self.recent_menu
        self._populate_recent_menu()
        self.file_scan_phone_action = self.file_menu.addAction(
            "Scan Phone with ADB", self._scan_phone
        )
        self.file_phone_package_export_action = self.file_menu.addAction(
            "Export Current Phone Package List as CSV…", self._export_phone_packages_csv
        )
        self.file_menu.addSeparator()
        self.file_result_actions = add_result_actions(
            self.file_menu,
            run_audit=self._start_audit,
            export_all_csv=self._export_results,
            export_visible_csv=self._export_visible_results,
            clear_results=self._clear_results,
            export_all_html=self._export_html_report,
            export_visible_html=self._export_visible_html_report,
            export_all_json=lambda: json_export_ui.export_window_results_json(
                self, visible=False
            ),
            export_visible_json=lambda: json_export_ui.export_window_results_json(
                self, visible=True
            ),
        )
        self.file_export_results_menu = self.file_result_actions.exports.menu
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)

        self.view_menu = QMenu("View", bar)
        bar.addMenu(self.view_menu)
        self.view_presets_menu = QMenu("View Preset", self.view_menu)
        self.view_menu.addMenu(self.view_presets_menu)
        self.view_action_group = QActionGroup(self)
        self.view_action_group.setExclusive(True)
        current = str(state.load_settings().get("view_preset") or "Basic")
        self.view_preset_actions = []
        for name in presentation.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            self.view_action_group.addAction(action)
            self.view_presets_menu.addAction(action)
            self.view_preset_actions.append(action)
        self._view_action_group = self.view_action_group

        self.display_settings_action = self.view_menu.addAction(
            "Display Settings…", self._show_display_settings
        )

        self.view_menu.addSeparator()
        self._filter_menu = QMenu("Filter Preset", self.view_menu)
        self.view_menu.addMenu(self._filter_menu)
        self._populate_filter_menu()
        self.sdk_filter_action = self.view_menu.addAction(
            "SDK Maintenance Filter…", self._show_sdk_filter_dialog
        )
        self.clear_sdk_filter_action = self.view_menu.addAction(
            "Clear SDK Filter", self._clear_sdk_filter
        )
        self.clear_sdk_filter_action.setEnabled(sdk_maintenance.active_sdk_filter().active())

        self.view_menu.addSeparator()
        self.reset_layout_action = self.view_menu.addAction(
            "Reset Table Layout", self._reset_table_layout
        )

        self.tools_menu = QMenu("Tools", bar)
        bar.addMenu(self.tools_menu)
        self.advanced_settings_action = self.tools_menu.addAction(
            "Advanced Settings…", self._show_advanced_settings
        )
        self.audit_profiles_menu = QMenu("Audit Profiles", self.tools_menu)
        self.tools_menu.addMenu(self.audit_profiles_menu)
        audit_profiles_ui.populate_audit_profiles_menu(self, self.audit_profiles_menu)
        self.tools_menu.addSeparator()
        self.force_full_refresh_action = self.tools_menu.addAction(
            "Force Full Refresh (Ignore Cache)", self._force_full_refresh
        )
        self.recheck_problematic_action = self.tools_menu.addAction(
            "Recheck Removed / Anomaly / Other", self._recheck_problematic
        )
        self.tools_menu.addSeparator()
        self.device_summary_action = self.tools_menu.addAction(
            "Device Summary…", self._show_device_summary
        )
        self.snapshots_menu = QMenu("Device Snapshots", self.tools_menu)
        self.tools_menu.addMenu(self.snapshots_menu)
        self.save_device_snapshot_action = self.snapshots_menu.addAction(
            "Save Current Device Snapshot…", self._save_device_snapshot
        )
        self.compare_device_snapshot_action = self.snapshots_menu.addAction(
            "Compare Current Device with Snapshot…", self._compare_device_snapshot
        )
        self.device_inventory_changes_action = self.tools_menu.addAction(
            "Device Inventory Changes…", self._show_inventory_changes
        )
        self.tools_menu.addSeparator()
        self.data_maintenance_menu = QMenu("Data Maintenance", self.tools_menu)
        self.tools_menu.addMenu(self.data_maintenance_menu)
        self.clear_audit_cache_action = self.data_maintenance_menu.addAction(
            "Clear Audit Cache", self._clear_audit_cache
        )
        self.clear_audit_history_action = self.data_maintenance_menu.addAction(
            "Clear Previous-Audit History", self._clear_audit_history
        )

        self.help_menu = QMenu("Help", bar)
        bar.addMenu(self.help_menu)
        self.help_menu.addAction(
            "ADB Setup Guide…",
            lambda: rich_help.show_rich_help(
                self, "ADB Setup Guide", help_texts.ADB_SETUP_GUIDE_HTML
            ),
        )
        self.help_menu.addAction(
            "How to Import an App List…",
            lambda: rich_help.show_rich_help(
                self, "How to Import an App List", help_texts.IMPORT_APP_LIST_GUIDE_HTML
            ),
        )
        self.help_menu.addSeparator()
        self.help_menu.addAction(
            "Health Score Methodology…",
            lambda: rich_help.show_rich_help(
                self, "Health Score Methodology", help_texts.HEALTH_SCORE_GUIDE_HTML
            ),
        )
        self.help_menu.addSeparator()
        self.help_menu.addAction("Check for Updates…", self._check_for_updates)
        self.help_menu.addAction("Create Diagnostic Bundle…", self._create_diagnostic_bundle)
        self.help_menu.addSeparator()
        self.help_menu.addAction("About Play Store App Audit", self._show_about)

    def _populate_filter_menu(self) -> None:
        if not hasattr(self, "_filter_menu"):
            return
        self._filter_menu.clear()
        self.filter_action_group = QActionGroup(self)
        self.filter_action_group.setExclusive(True)
        for name in device_insights.BUILTIN_FILTERS:
            action = QAction(name.title(), self, checkable=True)
            action.setChecked(name == self._active_filter_preset)
            action.triggered.connect(lambda _checked=False, n=name: self._apply_filter_preset(n))
            self.filter_action_group.addAction(action)
            self._filter_menu.addAction(action)

    def _apply_filter_preset(self, name: str) -> None:
        # Built-in filters are intentionally session-level here. The older saved
        # filter/smart-query UX remains hidden until its v1.7 interaction model
        # is explicitly settled.
        self._active_filter_preset = name if name in device_insights.BUILTIN_FILTERS else "All"
        self.proxy.set_v9_preset(self._active_filter_preset)
        self._populate_filter_menu()
        self._update_summary()
        self.status_label.setText(f"Filter preset: {self._active_filter_preset}")

    @staticmethod
    def _observed_sdk_default(rows: list[dict[str, object]], key: str, fallback: int) -> int:
        values: list[int] = []
        for row in rows:
            try:
                value = int(str(row.get(key) or "").strip())
            except (TypeError, ValueError):
                continue
            if value > 0:
                values.append(value)
        return max(values) if values else fallback

    @staticmethod
    def _threshold_control(enabled: bool, value: int) -> tuple[QWidget, QCheckBox, QSpinBox]:
        host = QWidget()
        layout = QHBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        check = QCheckBox("Enable")
        check.setChecked(enabled)
        spin = QSpinBox()
        spin.setRange(1, 100)
        spin.setValue(max(1, value))
        spin.setEnabled(enabled)
        check.toggled.connect(spin.setEnabled)
        layout.addWidget(check)
        layout.addWidget(spin)
        layout.addStretch(1)
        return host, check, spin

    def _show_sdk_filter_dialog(self) -> None:
        current = sdk_maintenance.active_sdk_filter()
        dialog = QDialog(self)
        dialog.setWindowTitle("SDK Maintenance Filter")
        dialog.setMinimumWidth(500)
        root = QVBoxLayout(dialog)

        note = QLabel(
            "Filter observed connected-device SDK metadata. targetSdk and minSdk describe Android "
            "compatibility and maintenance context only; they are not security or trust scores. "
            "Rows without a numeric value are excluded when the corresponding threshold is enabled."
        )
        note.setWordWrap(True)
        root.addWidget(note)

        form = QFormLayout()
        target_default = current.target_sdk_max or self._observed_sdk_default(
            list(self.current_rows), "target_sdk", 35
        )
        target_host, target_enabled, target_spin = self._threshold_control(
            current.target_sdk_max is not None, target_default
        )
        form.addRow("targetSdk at or below", target_host)

        min_default = current.min_sdk_max or self._observed_sdk_default(
            list(self.current_rows), "min_sdk", 23
        )
        min_host, min_enabled, min_spin = self._threshold_control(
            current.min_sdk_max is not None, min_default
        )
        form.addRow("minSdk at or below", min_host)

        compatibility = QComboBox()
        compatibility.addItem("All compatibility states", "")
        for value in sdk_maintenance.COMPATIBILITY_VALUES[1:]:
            compatibility.addItem(value, value)
        wanted = current.compatibility
        for index in range(compatibility.count()):
            if compatibility.itemData(index) == wanted:
                compatibility.setCurrentIndex(index)
                break
        form.addRow("Target compatibility", compatibility)
        root.addLayout(form)

        buttons_row = QHBoxLayout()
        clear = QPushButton("Clear Filter")
        buttons_row.addWidget(clear)
        buttons_row.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons_row.addWidget(buttons)
        root.addLayout(buttons_row)

        clear.clicked.connect(lambda: (self._clear_sdk_filter(), dialog.reject()))
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not target_enabled.isChecked() and not min_enabled.isChecked() and not compatibility.currentData():
            self._clear_sdk_filter()
            return

        value = sdk_maintenance.SdkMaintenanceFilter(
            target_sdk_max=target_spin.value() if target_enabled.isChecked() else None,
            min_sdk_max=min_spin.value() if min_enabled.isChecked() else None,
            compatibility=str(compatibility.currentData() or ""),
        )
        self._set_sdk_filter(value)

    def _set_sdk_filter(self, value: sdk_maintenance.SdkMaintenanceFilter | None) -> None:
        current = sdk_maintenance.set_active_sdk_filter(value)
        # Reapply the active built-in preset to trigger Qt's modern filter-change
        # lifecycle without deprecated invalidateFilter() calls.
        self.proxy.set_v9_preset(self._active_filter_preset)
        if hasattr(self, "clear_sdk_filter_action"):
            self.clear_sdk_filter_action.setEnabled(current.active())
        self._update_summary()
        self.status_label.setText(sdk_maintenance.describe_sdk_filter(current))

    def _clear_sdk_filter(self) -> None:
        self._set_sdk_filter(None)

    @staticmethod
    def _fit_status_chip_to_selected_text(button: QPushButton) -> None:
        selected_font = QFont(button.font())
        selected_font.setBold(True)
        metrics = QFontMetrics(selected_font)
        margins = button.contentsMargins()
        style = button.style()
        button_margin = max(
            0, style.pixelMetric(QStyle.PixelMetric.PM_ButtonMargin, None, button)
        )
        frame_width = max(
            0, style.pixelMetric(QStyle.PixelMetric.PM_DefaultFrameWidth, None, button)
        )
        required_width = (
            metrics.horizontalAdvance(button.text())
            + margins.left()
            + margins.right()
            + 2 * button_margin
            + 2 * frame_width
        )
        button.setMinimumWidth(required_width)

    def _update_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        base_rows = self._rows_before_criticality_filter()
        criticality = base_ui.CRITICALITY
        counts = {
            key: sum(1 for row in base_rows if str(row.get("criticality_key") or "") == key)
            for key in criticality
        }
        if hasattr(self, "criticality_buttons"):
            for key, button in self.criticality_buttons.items():
                button.setText(f"{criticality[key]['button']} {counts[key]}")
                self._fit_status_chip_to_selected_text(button)
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        self.summary_label.setText(presentation.concise_summary(list(self.current_rows), visible))

    def _clear_results(self) -> None:
        self._status_filters.clear()
        super()._clear_results()
        if isinstance(self.proxy, preferences_ui.AuditFilterProxy):
            self.proxy.set_status_filters(set())
        self._sync_status_filter_buttons()
        self._update_summary()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = MenuWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
