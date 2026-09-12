from __future__ import annotations

import sys
from contextlib import suppress
from typing import Any

from PySide6.QtGui import QAction, QActionGroup, QFont, QFontMetrics, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPushButton,
    QStyle,
)

import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.audit_profiles as audit_profiles_ui
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.changes_history as changes_history_ui
import playstore_app_audit.ui.data_maintenance as data_maintenance_ui
import playstore_app_audit.ui.json_export as json_export_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
import playstore_app_audit.ui.smart_queries as smart_queries_ui
from playstore_app_audit import help_texts
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.ui import rich_help
from playstore_app_audit.ui.file_menu import (
    ResultActions,
    populate_result_export_menu,
)


class MenuWindow(preferences_ui.PreferencesWindow):
    """Stable v9.2 Qt wrapper keeping native menu objects referenced by Python."""

    def __init__(self) -> None:
        self._defer_v92_menu_build = True
        self._active_smart_query: smart_queries.SmartQuery | None = None
        self._data_maintenance_dialog: (
            data_maintenance_ui.DataMaintenanceDialog | None
        ) = None
        self._changes_history_dialog: changes_history_ui.ChangesHistoryDialog | None = None
        self.changes_history_action: QAction | None = None
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
            "Scan Phone", self._scan_phone
        )
        self.file_phone_package_export_action = self.file_menu.addAction(
            "Export Phone Package List…", self._export_phone_packages_csv
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)

        self.audit_menu = QMenu("Audit", bar)
        bar.addMenu(self.audit_menu)
        self.run_audit_action = self.audit_menu.addAction("Run Audit", self._start_audit)
        self.recheck_problematic_action = self.audit_menu.addAction(
            "Recheck Not Found / Anomaly / Other", self._recheck_problematic
        )
        self.force_full_refresh_action = self.audit_menu.addAction(
            "Run with Fresh Store Results", self._force_full_refresh
        )
        fresh_results_help = (
            "Ignore cached Google Play and alternative-store results for this run. "
            "No cache files are deleted; app icons may still come from the icon cache."
        )
        self.force_full_refresh_action.setToolTip(fresh_results_help)
        self.force_full_refresh_action.setStatusTip(fresh_results_help)
        self.audit_menu.addSeparator()
        self.audit_profiles_menu = QMenu("Audit Presets", self.audit_menu)
        self.audit_menu.addMenu(self.audit_profiles_menu)
        audit_profiles_ui.populate_audit_profiles_menu(self, self.audit_profiles_menu)
        self.audit_menu.addSeparator()
        self.audit_export_results_menu = QMenu("Export Results", self.audit_menu)
        self.audit_menu.addMenu(self.audit_export_results_menu)
        exports = populate_result_export_menu(
            self.audit_export_results_menu,
            export_all_csv=self._export_results,
            export_visible_csv=self._export_visible_results,
            export_all_html=self._export_html_report,
            export_visible_html=self._export_visible_html_report,
            export_all_json=lambda: json_export_ui.export_window_results_json(
                self, visible=False
            ),
            export_visible_json=lambda: json_export_ui.export_window_results_json(
                self, visible=True
            ),
        )
        self.clear_results_action = self.audit_menu.addAction(
            "Clear Results", self._clear_results
        )
        self.audit_result_actions = ResultActions(
            run=self.run_audit_action,
            exports=exports,
            clear=self.clear_results_action,
        )

        self.view_menu = QMenu("View", bar)
        bar.addMenu(self.view_menu)
        self.view_presets_menu = QMenu("Column Preset", self.view_menu)
        self.view_menu.addMenu(self.view_presets_menu)
        self.view_action_group = QActionGroup(self)
        self.view_action_group.setExclusive(True)
        current = str(state.load_settings().get("view_preset") or "Basic")
        self.view_preset_actions = []
        for name in presentation.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current)
            if name == "Custom":
                action.setEnabled(self._has_custom_table_layout(state.load_settings()))
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            self.view_action_group.addAction(action)
            self.view_presets_menu.addAction(action)
            self.view_preset_actions.append(action)
        self._view_action_group = self.view_action_group

        self.display_settings_action = self.view_menu.addAction(
            "Customize View…", self._show_display_settings
        )
        self.reset_layout_action = self.view_menu.addAction(
            "Reset Table Layout", self._reset_table_layout
        )

        self.view_menu.addSeparator()
        self._filter_menu = QMenu("Quick Filters", self.view_menu)
        self.view_menu.addMenu(self._filter_menu)
        self._populate_filter_menu()
        self.smart_queries_menu = QMenu("Smart Queries", self.view_menu)
        self.view_menu.addMenu(self.smart_queries_menu)
        smart_queries_ui.populate_smart_queries_menu(self, self.smart_queries_menu)
        self.clear_all_filters_action = self.view_menu.addAction(
            "Clear All Filters", self._clear_all_filters
        )

        self.tools_menu = QMenu("Tools", bar)
        bar.addMenu(self.tools_menu)
        self.advanced_settings_action = self.tools_menu.addAction(
            "Advanced Settings…", self._show_advanced_settings
        )
        self.changes_history_action = None
        if state.changes_history_enabled(self.user_settings):
            self.changes_history_action = self.tools_menu.addAction(
                "Changes & History…", self._show_changes_history
            )
        self.history_maintenance_separator_action = self.tools_menu.addSeparator()
        self.data_maintenance_action = self.tools_menu.addAction(
            "Data Maintenance…", self._show_data_maintenance
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
            "App List Import Guide…",
            lambda: rich_help.show_rich_help(
                self, "App List Import Guide", help_texts.IMPORT_APP_LIST_GUIDE_HTML
            ),
        )
        self.help_menu.addSeparator()
        self.help_menu.addAction(
            "Maintenance Score Methodology…",
            lambda: rich_help.show_rich_help(
                self, "Maintenance Score Methodology", help_texts.HEALTH_SCORE_GUIDE_HTML
            ),
        )
        self.help_menu.addSeparator()
        self.help_menu.addAction("Check for Updates…", self._check_for_updates)
        self.help_menu.addAction("Create Diagnostic Bundle…", self._create_diagnostic_bundle)
        self.help_menu.addSeparator()
        self.help_menu.addAction("About Play Store App Audit", self._show_about)

    def _sync_changes_history_action(self) -> None:
        enabled = state.changes_history_enabled(self.user_settings)
        action = self.changes_history_action
        if enabled and action is None:
            action = QAction("Changes & History…", self)
            action.triggered.connect(self._show_changes_history)
            self.tools_menu.insertAction(self.history_maintenance_separator_action, action)
            self.changes_history_action = action
        elif not enabled and action is not None:
            self.tools_menu.removeAction(action)
            action.deleteLater()
            self.changes_history_action = None
            if self._changes_history_dialog is not None:
                self._changes_history_dialog.close()
                self._changes_history_dialog = None
        sync_availability = getattr(self, "_sync_action_availability", None)
        if callable(sync_availability):
            sync_availability()

    def _show_changes_history(self) -> None:
        if not state.changes_history_enabled(self.user_settings):
            return
        results_available = bool(self.current_rows) and not bool(
            getattr(self, "_results_incomplete", False)
        )
        device_results_available = self.source_mode == "device" and results_available
        inventory_changes = getattr(self, "_last_inventory_changes", None)
        review_store_changes = getattr(self, "_show_store_change_overview", None)
        if not callable(review_store_changes):
            return
        availability = changes_history_ui.ChangesHistoryAvailability(
            store_tracking=state.store_history_enabled(self.user_settings),
            store_review=(
                state.store_history_enabled(self.user_settings)
                and results_available
                and change_service.has_store_change_evidence(self.current_rows)
            ),
            store_had_baseline=bool(
                state.store_history_enabled(self.user_settings)
                and getattr(self, "_store_comparison_had_baseline", False)
            ),
            device_tracking=state.device_inventory_history_enabled(self.user_settings),
            device_review=bool(
                state.device_inventory_history_enabled(self.user_settings)
                and device_results_available
                and isinstance(inventory_changes, dict)
                and inventory_changes.get("had_previous")
            ),
            snapshots_available=device_results_available,
        )
        if self._changes_history_dialog is not None:
            self._changes_history_dialog.close()
        dialog = changes_history_ui.ChangesHistoryDialog(
            self,
            availability,
            review_store_changes=review_store_changes,
            review_device_changes=self._show_inventory_changes,
            save_snapshot=self._save_device_snapshot,
            compare_snapshot=self._compare_device_snapshot,
        )
        self._changes_history_dialog = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _show_data_maintenance(self) -> None:
        model: Any = self.model
        operation_running = getattr(self, "_operation_running", None)
        if callable(operation_running) and operation_running():
            return
        if model.icon_loader_busy():
            return

        dialog = data_maintenance_ui.DataMaintenanceDialog(
            self,
            {
                "store_results": self._perform_clear_audit_cache,
                "app_icons": self._perform_clear_app_icon_cache,
                "alternative_store": self._perform_clear_alternative_store_cache,
                "previous_audit_history": self._perform_clear_audit_history,
                "device_inventory_history": self._perform_clear_device_inventory_history,
            },
            self.status_label.setText,
        )
        self._data_maintenance_dialog = dialog

        def sync_dialog_availability(_busy: bool = False) -> None:
            running = bool(callable(operation_running) and operation_running())
            dialog.set_destructive_enabled(
                not running and not model.icon_loader_busy()
            )

        model.icon_loader_busy_changed.connect(sync_dialog_availability)
        sync_dialog_availability()
        dialog.exec()
        with suppress(RuntimeError):
            model.icon_loader_busy_changed.disconnect(sync_dialog_availability)
        self._data_maintenance_dialog = None

    def _perform_clear_app_icon_cache(self) -> str:
        model: Any = self.model
        model.clear_app_icon_cache()
        return "App Icon Cache cleared"

    @staticmethod
    def _perform_clear_alternative_store_cache() -> str:
        state.clear_alternative_distribution_cache()
        return "Alternative Store Cache cleared"

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
        # Built-in Quick Filters remain independent from saved Smart Queries.
        self._active_filter_preset = name if name in device_insights.BUILTIN_FILTERS else "All"
        self.proxy.set_v9_preset(self._active_filter_preset)
        self._populate_filter_menu()
        self._update_summary()
        self._set_presentation_status(f"Quick Filter: {self._active_filter_preset}")

    def _show_new_smart_query(self) -> None:
        smart_queries_ui.show_smart_query_dialog(self, new_query=True)

    def _show_manage_smart_queries(self) -> None:
        active_id = self._active_smart_query.query_id if self._active_smart_query else None
        smart_queries_ui.show_smart_query_dialog(
            self, new_query=False, selected_query_id=active_id
        )

    def _apply_smart_query(self, query: smart_queries.SmartQuery) -> None:
        self._active_smart_query = query
        if isinstance(self.proxy, preferences_ui.AuditFilterProxy):
            self.proxy.set_smart_query(query)
        smart_queries_ui.populate_smart_queries_menu(self, self.smart_queries_menu)
        self._update_summary()

    def _clear_smart_query(self) -> None:
        self._active_smart_query = None
        if isinstance(self.proxy, preferences_ui.AuditFilterProxy):
            self.proxy.set_smart_query(None)
        smart_queries_ui.populate_smart_queries_menu(self, self.smart_queries_menu)
        self._update_summary()

    def _clear_all_filters(self) -> None:
        """Reset only session-level controls that can hide current result rows."""
        self.search_edit.clear()
        self._set_criticality_filter(None)
        self._apply_filter_preset("All")
        self._clear_smart_query()
        self.hide_system_check.setChecked(False)
        self._update_summary()
        self._set_presentation_status("All result filters cleared")

    def _on_smart_query_deleted(self, query_id: str) -> None:
        if self._active_smart_query and self._active_smart_query.query_id == query_id:
            self._clear_smart_query()

    def _summary_with_smart_query(self, summary: str) -> str:
        active = self._active_smart_query
        if active is None:
            if hasattr(self, "summary_label"):
                self.summary_label.setToolTip("")
            return summary
        name = active.name or "Custom Query"
        compact_name = name if len(name) <= 40 else name[:37] + "..."
        if hasattr(self, "summary_label"):
            self.summary_label.setToolTip(f"Active Smart Query: {name}")
        return f"{summary} | Smart Query: {compact_name}"

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
        summary = presentation.concise_summary(list(self.current_rows), visible)
        self.summary_label.setText(self._summary_with_smart_query(summary))

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
