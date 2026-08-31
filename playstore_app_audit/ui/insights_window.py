from __future__ import annotations

import csv
import html
import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.alternative_distribution as alternative_distribution
import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.device_window as device_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult
from playstore_app_audit.ui import schema

V9_EXTRA_COLUMNS = schema.INSIGHTS_EXTRA_COLUMNS
V9_MODEL_COLUMNS = schema.MODEL_COLUMNS


class AdvancedFilterProxy(base_ui.AppFilterProxy):
    def __init__(self) -> None:
        super().__init__()
        self.v9_preset = "All"

    def set_v9_preset(self, preset: str) -> None:
        self.beginFilterChange()
        self.v9_preset = preset if preset in device_insights.BUILTIN_FILTERS else "All"
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        model = self.sourceModel()
        if not isinstance(model, base_ui.AppTableModel):
            return True
        row = model.row_dict(source_row)
        return device_insights.row_matches_filter(row, self.v9_preset)


class InsightsWindow(device_ui.DeviceWindow):
    """Qt6 v9 with device maintenance analysis and product-style utilities."""

    def __init__(self) -> None:
        self._device_summary: dict[str, Any] = {}
        self._last_inventory_changes: dict[str, Any] = {}
        self._v9_targeted_active = False
        self._active_filter_preset = "All"
        super().__init__()

        # Replace the proxy with a v9-aware proxy so built-in filter presets can
        # combine with the existing text/status/system filters.
        old_proxy = self.proxy
        proxy = AdvancedFilterProxy()
        proxy.setSourceModel(self.model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_criticality_filter(self.criticality_filter)
        self._active_filter_preset = str(state.load_settings().get("active_filter_preset") or "All")
        proxy.set_v9_preset(self._active_filter_preset)
        self.proxy = proxy
        self.table.setModel(proxy)
        old_proxy.deleteLater()

        self.setAcceptDrops(True)
        self._build_menu_v9()
        self._apply_column_visibility(reset_order=False)
        self._update_summary()
        device_insights.log_event("Qt6 insights layer started")

    # ---------- Behaviour hooks ----------
    def _collect_device_metadata(self, adb: str, packages: list[str], cancel_event):
        return device_insights.collect_device_metadata_v9(adb, packages, cancel_event)

    def _enrich_rows_with_device_metadata(
        self, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
    ) -> None:
        device_insights.enrich_rows_with_device_metadata_v9(rows, metadata)

    def _classify_row(self, row: dict[str, Any]) -> None:
        super()._classify_row(row)
        device_insights.apply_health_score(row)

    # ---------- Column/view presets ----------
    def _visible_column_order(self) -> list[str]:
        self.user_settings = state.load_settings()
        preset = str(self.user_settings.get("view_preset") or "Basic")
        compare = bool(self.user_settings.get("compare_previous", False))
        health = bool(self.user_settings.get("health_score_enabled", False))

        if preset == "Technical":
            columns = list(V9_MODEL_COLUMNS)
            if not compare and "change" in columns:
                columns.remove("change")
        elif preset == "Device":
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns += [
                "package_name",
                "play_title",
                "play_last_update",
                "age_days",
                "compatibility_status",
                "installed_version",
                "version_comparison",
                "installer_source",
                "app_enabled",
                "device_change",
            ]
            if health:
                columns.append("health_score")
            columns.append("notes")
        else:
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns.extend(compact_ui.PRIMARY_COLUMNS[1:])

        selected = self.user_settings.get("technical_columns", [])
        if isinstance(selected, list):
            columns.extend(c for c in selected if c in V9_MODEL_COLUMNS)
        return list(dict.fromkeys(c for c in columns if c in V9_MODEL_COLUMNS))

    def _set_view_preset(self, name: str) -> None:
        if name not in presentation.VIEW_PRESETS:
            return
        settings = state.load_settings()
        settings["view_preset"] = name
        self.user_settings = state.save_settings(settings)
        self._apply_column_visibility(reset_order=True)
        self.status_label.setText(f"View preset: {name}")

    # ---------- Menus ----------
    def _build_menu_v9(self) -> None:
        bar = self.menuBar()
        bar.clear()

        file_menu = bar.addMenu("File")
        choose = QAction("Choose App List…", self)
        choose.triggered.connect(self._choose_input)
        file_menu.addAction(choose)
        self._recent_menu = file_menu.addMenu("Recent Sources")
        self._populate_recent_menu()
        scan = QAction("Scan Phone with ADB", self)
        scan.triggered.connect(self._scan_phone)
        file_menu.addAction(scan)
        export_phone = QAction("Export Current Phone Package List as CSV…", self)
        export_phone.triggered.connect(self._export_phone_packages_csv)
        file_menu.addAction(export_phone)
        file_menu.addSeparator()
        export_all = QAction("Export All Results as CSV…", self)
        export_all.triggered.connect(self._export_results)
        file_menu.addAction(export_all)
        export_visible = QAction("Export Visible Results as CSV…", self)
        export_visible.triggered.connect(self._export_visible_results)
        file_menu.addAction(export_visible)
        export_html = QAction("Export HTML Report…", self)
        export_html.triggered.connect(self._export_html_report)
        file_menu.addAction(export_html)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = bar.addMenu("View")
        view_presets = view_menu.addMenu("View Preset")
        group = QActionGroup(self)
        group.setExclusive(True)
        current_view = str(state.load_settings().get("view_preset") or "Basic")
        for name in presentation.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current_view)
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            group.addAction(action)
            view_presets.addAction(action)
        self._view_action_group = group

        self._filter_menu = view_menu.addMenu("Quick Filters")
        self._populate_filter_menu()
        view_menu.addAction("Save Current Filter as Preset…", self._save_current_filter)
        view_menu.addAction("Manage Saved Filter Presets…", self._manage_saved_filters)
        view_menu.addSeparator()
        view_menu.addAction("Reset Table Layout", self._reset_table_layout)

        tools = bar.addMenu("Tools")
        tools.addAction("Advanced Settings…", self._show_advanced_settings)
        tools.addSeparator()
        tools.addAction("Force Full Refresh (Ignore Cache)", self._force_full_refresh)
        tools.addAction("Recheck Removed / Anomaly / Other", self._recheck_problematic)
        tools.addSeparator()
        tools.addAction("Device Summary…", self._show_device_summary)
        snapshots = tools.addMenu("Device Snapshots")
        snapshots.addAction("Save Current Device Snapshot…", self._save_device_snapshot)
        snapshots.addAction("Compare Current Device with Snapshot…", self._compare_device_snapshot)
        tools.addAction("Device Inventory Changes…", self._show_inventory_changes)
        tools.addSeparator()
        tools.addAction("Clear Audit Cache", self._clear_audit_cache)
        tools.addAction("Clear Previous-Audit History", self._clear_audit_history)

        help_menu = bar.addMenu("Help")
        help_menu.addAction(
            "ADB Setup Guide…",
            lambda: self._show_text_help("ADB Setup Guide", device_insights.ADB_SETUP_GUIDE),
        )
        help_menu.addAction(
            "How to Export Package CSV…",
            lambda: self._show_text_help("Export Package CSV", presentation.CSV_EXPORT_GUIDE),
        )
        help_menu.addAction(
            "Maintenance Score Methodology…",
            lambda: self._show_text_help(
                "Maintenance Score Methodology", device_insights.HEALTH_SCORE_GUIDE
            ),
        )
        help_menu.addSeparator()
        help_menu.addAction("Check for Updates…", self._check_for_updates)
        help_menu.addAction("Create Diagnostic Bundle…", self._create_diagnostic_bundle)
        help_menu.addSeparator()
        help_menu.addAction("About Play Store App Audit", self._show_about)

    def _populate_recent_menu(self) -> None:
        self._recent_menu.clear()
        paths = device_insights.get_recent_sources()
        if not paths:
            action = self._recent_menu.addAction("No Recent Files")
            action.setEnabled(False)
            return
        for path in paths:
            self._recent_menu.addAction(
                Path(path).name, lambda _checked=False, p=path: self._load_input_file(p)
            )

    def _populate_filter_menu(self) -> None:
        self._filter_menu.clear()
        for name in device_insights.BUILTIN_FILTERS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == self._active_filter_preset)
            action.triggered.connect(lambda _checked=False, n=name: self._apply_filter_preset(n))
            self._filter_menu.addAction(action)
        saved = device_insights.get_saved_filters()
        if saved:
            self._filter_menu.addSeparator()
            for name in sorted(saved):
                self._filter_menu.addAction(
                    f"★ {name}", lambda _checked=False, n=name: self._apply_saved_filter(n)
                )

    # ---------- File loading / drag & drop ----------
    def _load_input_file(self, path: str) -> None:
        try:
            apps = base_ui.load_apps(path)
            metadata = self._read_system_metadata_from_file(path, apps)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid app list", str(exc))
            return
        self._cancel_active_audit()
        self.file_apps = apps
        self.file_system_metadata = metadata
        self.device_apps_all = []
        self.device_system_packages = set()
        self._device_summary = {}
        self._last_inventory_changes = {}
        self.source_mode = "file"
        self.path_edit.setText(path)
        meta_text = f" • system flag available for {len(metadata)} packages" if metadata else ""
        self.source_label.setText(f"File selected: {len(apps)} unique Android packages{meta_text}")
        self.status_label.setText("File ready. Run the Play Store audit.")
        device_insights.add_recent_source(path)
        self._populate_recent_menu()
        device_insights.log_event(f"Loaded file source: {Path(path).name} ({len(apps)} packages)")

    def _choose_input(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose App List",
            "",
            "App lists (*.csv *.tsv *.txt);;CSV (*.csv);;Text (*.txt);;All files (*.*)",
        )
        if selected:
            self._load_input_file(selected)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        urls = event.mimeData().urls()
        if (
            len(urls) == 1
            and urls[0].isLocalFile()
            and Path(urls[0].toLocalFile()).suffix.lower() in {".csv", ".tsv", ".txt"}
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if urls:
            self._load_input_file(urls[0].toLocalFile())
            event.acceptProposedAction()

    # ---------- ADB/device ----------
    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        super()._on_adb_scan_done(apps, system_packages)
        adb = self._get_authorised_adb()
        if adb:
            try:
                self._device_summary = device_insights.collect_device_summary(
                    adb, len(self.device_apps_all), len(self.device_system_packages)
                )
                name = " ".join(
                    filter(
                        None,
                        [
                            str(self._device_summary.get("manufacturer") or ""),
                            str(self._device_summary.get("model") or ""),
                        ],
                    )
                )
                if name:
                    self.status_label.setText(f"Phone scan ready: {name}. Run the Play Store audit.")
            except Exception as exc:
                device_insights.log_event(f"Device summary failed: {exc}")

    def _export_phone_packages_csv(self) -> None:
        if not self.device_apps_all:
            QMessageBox.information(self, "No phone scan", "Scan a phone with ADB first.")
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, "Export phone package list", "android_packages.csv", "CSV (*.csv)"
        )
        if not selected:
            return
        if not selected.lower().endswith(".csv"):
            selected += ".csv"
        with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=["package_name", "is_system"])
            writer.writeheader()
            for app in self.device_apps_all:
                package = app["package_name"]
                writer.writerow(
                    {"package_name": package, "is_system": package in self.device_system_packages}
                )
        QMessageBox.information(self, "Export complete", f"Package list saved to:\n{selected}")

    def _show_device_summary(self) -> None:
        if not self._device_summary:
            QMessageBox.information(self, "No device summary", "Scan a phone with ADB first.")
            return
        d = self._device_summary
        text = (
            f"Device: {d.get('manufacturer', '')} {d.get('model', '')}\n"
            f"Serial: {d.get('serial_masked', 'Unknown')}\n"
            f"Android: {d.get('android_version', '?')} (API {d.get('android_api', '?')})\n"
            f"Security patch: {d.get('security_patch', '?')}\n"
            f"Packages: {d.get('total_packages', 0)} total · {d.get('third_party_packages', 0)} third-party · {d.get('system_packages', 0)} system"
        )
        QMessageBox.information(self, "Device Summary", text)

    def _save_device_snapshot(self) -> None:
        if not self.current_rows or self.source_mode != "device":
            QMessageBox.information(self, "No device audit", "Run an ADB-based audit first.")
            return
        default = f"{self._device_summary.get('model', 'android')}_snapshot.psaa.json".replace(" ", "_")
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save device snapshot",
            default,
            "Play Store App Audit snapshot (*.psaa.json);;JSON (*.json)",
        )
        if not selected:
            return
        if not selected.lower().endswith(".json"):
            selected += ".psaa.json"
        device_insights.save_snapshot(selected, self.current_rows, self._device_summary)
        QMessageBox.information(self, "Snapshot saved", f"Saved to:\n{selected}")

    def _compare_device_snapshot(self) -> None:
        if not self.current_rows or self.source_mode != "device":
            QMessageBox.information(
                self, "No current device", "Run an ADB-based audit for the current phone first."
            )
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose device snapshot",
            "",
            "Play Store App Audit snapshot (*.psaa.json *.json);;JSON (*.json)",
        )
        if not selected:
            return
        try:
            comparison = device_insights.compare_snapshots(
                self.current_rows, self._device_summary, device_insights.load_snapshot(selected)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Snapshot error", str(exc))
            return
        lines = [
            f"Only in saved snapshot: {len(comparison['only_snapshot'])}",
            f"Only on current device: {len(comparison['only_current'])}",
            f"Version differences: {len(comparison['version_differences'])}",
            f"Installer differences: {len(comparison['installer_differences'])}",
            f"Enabled-state differences: {len(comparison['state_differences'])}",
            "",
        ]
        for label, key in (
            ("Only in snapshot", "only_snapshot"),
            ("Only current", "only_current"),
            ("Version differences", "version_differences"),
            ("Installer differences", "installer_differences"),
            ("State differences", "state_differences"),
        ):
            values = comparison[key]
            if values:
                lines.append(label + ":")
                lines.extend(f"  {p}" for p in values[:100])
                if len(values) > 100:
                    lines.append(f"  … {len(values) - 100} more")
                lines.append("")
        self._show_text_help("Device comparison", "\n".join(lines))

    def _show_inventory_changes(self) -> None:
        if not self._last_inventory_changes:
            QMessageBox.information(
                self,
                "No inventory comparison",
                "Run at least two ADB audits on the same device with inventory history enabled.",
            )
            return
        data = self._last_inventory_changes
        counts = data.get("counts", {})
        lines = [
            f"New on device: {counts.get('new', 0)}",
            f"Removed from device: {counts.get('removed', 0)}",
            f"Version changed: {counts.get('version', 0)}",
            f"Installer changed: {counts.get('installer', 0)}",
            f"Enabled state changed: {counts.get('state', 0)}",
        ]
        removed = data.get("removed", [])
        if removed:
            lines += ["", "Removed packages:"] + [f"  {x}" for x in removed[:150]]
        self._show_text_help("Device Inventory Changes", "\n".join(lines))

    def _clear_device_inventory_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear device inventory history?",
            "Delete all per-device comparison baselines used by Device Inventory "
            "Change? The next completed phone audit for each device will create a "
            "new baseline. Device snapshots, current phone inventory, Play Store "
            "cache and history, provider cache, settings and current results will "
            "not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            deleted = device_insights.clear_device_inventory_history()
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Could not clear device inventory history",
                str(exc),
            )
            return

        self._last_inventory_changes = {}
        for row in self.current_rows:
            row.pop("device_change", None)
            row[change_service.DEVICE_HISTORY_FLAG] = False
        if self.current_rows:
            self.model.set_rows(self.current_rows)
        self._update_summary()
        sync_post_audit_views = getattr(self, "_sync_post_audit_views", None)
        if callable(sync_post_audit_views):
            sync_post_audit_views()
        baseline_label = "baseline" if deleted == 1 else "baselines"
        self.status_label.setText(
            f"Device inventory history cleared • {deleted} {baseline_label} removed"
        )

    # ---------- Filters ----------
    def _apply_filter_preset(self, name: str) -> None:
        self._active_filter_preset = name if name in device_insights.BUILTIN_FILTERS else "All"
        self.proxy.set_v9_preset(self._active_filter_preset)
        settings = state.load_settings()
        settings["active_filter_preset"] = self._active_filter_preset
        state.save_settings(settings)
        self._populate_filter_menu()
        self._update_summary()
        self.status_label.setText(f"Quick Filter: {self._active_filter_preset}")

    def _save_current_filter(self) -> None:
        name, ok = QInputDialog.getText(self, "Save filter preset", "Preset name")
        name = name.strip()
        if not ok or not name:
            return
        device_insights.save_filter(
            name,
            self.search_edit.text(),
            self.criticality_filter,
            self.hide_system_check.isChecked(),
            self._active_filter_preset,
        )
        self._populate_filter_menu()
        self.status_label.setText(f"Saved filter preset: {name}")

    def _apply_saved_filter(self, name: str) -> None:
        data = device_insights.get_saved_filters().get(name)
        if not isinstance(data, dict):
            return
        self.search_edit.setText(str(data.get("query") or ""))
        self.hide_system_check.setChecked(bool(data.get("hide_system", True)))
        criticality = str(data.get("criticality") or "") or None
        self.criticality_filter = criticality
        self.proxy.set_criticality_filter(criticality)
        self._sync_criticality_buttons()
        self._apply_filter_preset(str(data.get("preset") or "All"))
        self.status_label.setText(f"Applied saved filter: {name}")

    def _manage_saved_filters(self) -> None:
        saved = device_insights.get_saved_filters()
        if not saved:
            QMessageBox.information(self, "Saved filters", "No custom filter presets have been saved yet.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Manage saved filter presets")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget()
        list_widget.addItems(sorted(saved))
        layout.addWidget(list_widget)
        row = QHBoxLayout()
        delete = QPushButton("Delete selected")
        close = QPushButton("Close")
        row.addWidget(delete)
        row.addStretch(1)
        row.addWidget(close)
        layout.addLayout(row)
        delete.clicked.connect(lambda: self._delete_selected_filter(list_widget))
        close.clicked.connect(dialog.accept)
        dialog.exec()
        self._populate_filter_menu()

    def _delete_selected_filter(self, widget: QListWidget) -> None:
        item = widget.currentItem()
        if not item:
            return
        device_insights.delete_filter(item.text())
        widget.takeItem(widget.row(item))

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = state.load_settings()
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Settings")
        dialog.resize(720, 760)
        root = QVBoxLayout(dialog)
        warning = QLabel(
            "⚠ Expert settings. These options can change network load, Store interpretation, ADB collection and the technical data shown. Change them only when genuinely necessary."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background:#FFF6E5;color:#6B4A16;border:1px solid #E9C77D;padding:10px;border-radius:6px;"
        )
        root.addWidget(warning)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        content = QVBoxLayout(inner)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        store = QGroupBox("Store and cache")
        form = QFormLayout(store)
        language = QLineEdit(str(self.user_settings.get("store_language") or "en"))
        fallback = QLineEdit(
            str(
                self.user_settings.get("fallback_countries")
                or device_ui.device_metadata.DEFAULT_FALLBACK_COUNTRIES
            )
        )
        cache = QCheckBox("Use intelligent cache")
        cache.setChecked(bool(self.user_settings.get("cache_enabled", True)))
        ttl = QSpinBox()
        ttl.setRange(1, 720)
        ttl.setSuffix(" hours")
        ttl.setValue(int(self.user_settings.get("cache_ttl_hours", 72)))
        form.addRow("Store language", language)
        form.addRow("Fallback Store countries", fallback)
        form.addRow(
            "",
            QLabel(
                "Comma/space separated country codes. Hidden from the normal UI; used only when the selected Store country is unavailable/inconclusive."
            ),
        )
        form.addRow("", cache)
        form.addRow("Healthy-result cache TTL", ttl)
        content.addWidget(store)

        device = QGroupBox("Connected Android device")
        d_layout = QVBoxLayout(device)
        collect_device = QCheckBox(
            "Collect installed version, installer, Target/Min SDK and local install/update metadata"
        )
        collect_device.setChecked(bool(self.user_settings.get("collect_device_metadata", True)))
        permissions = QCheckBox("Audit sensitive requested permissions (advanced, slower)")
        permissions.setChecked(bool(self.user_settings.get("permissions_audit_enabled", False)))
        inventory = QCheckBox("Keep per-device inventory history")
        inventory.setChecked(bool(self.user_settings.get("inventory_history_enabled", True)))
        health = QCheckBox("Enable Maintenance Score")
        health.setChecked(bool(self.user_settings.get("health_score_enabled", False)))
        d_layout.addWidget(collect_device)
        d_layout.addWidget(permissions)
        d_layout.addWidget(inventory)
        d_layout.addWidget(health)
        note = QLabel(
            "Permission audit is OFF by default. Maintenance Score is a maintenance heuristic, not a security rating. See Help for methodology."
        )
        note.setWordWrap(True)
        d_layout.addWidget(note)
        content.addWidget(device)

        history = QGroupBox("Audit history")
        h_layout = QVBoxLayout(history)
        compare = QCheckBox("Compare with previous Play Store audit")
        compare.setChecked(bool(self.user_settings.get("compare_previous", False)))
        h_layout.addWidget(compare)
        content.addWidget(history)

        storage = QGroupBox("Storage")
        s_layout = QVBoxLayout(storage)
        portable = QCheckBox("Portable mode: keep settings/cache/history next to the EXE")
        portable.setChecked(device_insights.portable_mode_active())
        s_layout.addWidget(portable)
        portable_note = QLabel(
            "Changing portable mode migrates local app data and requires a restart. The EXE folder must be writable."
        )
        portable_note.setWordWrap(True)
        s_layout.addWidget(portable_note)
        content.addWidget(storage)

        columns = QGroupBox("Technical columns")
        c_layout = QVBoxLayout(columns)
        checks: dict[str, QCheckBox] = {}
        selected = set(self.user_settings.get("technical_columns", []))
        for key, label in state.TECHNICAL_COLUMNS.items():
            check = QCheckBox(label)
            check.setChecked(key in selected)
            checks[key] = check
            c_layout.addWidget(check)
        content.addWidget(columns)
        content.addStretch(1)

        bottom = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        bottom.addWidget(reset)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bottom.addWidget(buttons)
        root.addLayout(bottom)

        def reset_controls() -> None:
            language.setText("en")
            fallback.setText(device_ui.device_metadata.DEFAULT_FALLBACK_COUNTRIES)
            cache.setChecked(True)
            ttl.setValue(72)
            collect_device.setChecked(True)
            permissions.setChecked(False)
            inventory.setChecked(True)
            health.setChecked(False)
            compare.setChecked(False)
            portable.setChecked(False)
            for check in checks.values():
                check.setChecked(False)

        reset.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fallback_text, invalid = device_ui.device_metadata.normalise_country_string(fallback.text())
        previous_fallback = str(self.user_settings.get("fallback_countries") or "")
        old_portable = device_insights.portable_mode_active()
        self.user_settings.update(
            {
                "store_language": (language.text().strip() or "en").lower(),
                "fallback_countries": fallback_text,
                "cache_enabled": cache.isChecked(),
                "cache_ttl_hours": ttl.value(),
                "collect_device_metadata": collect_device.isChecked(),
                "permissions_audit_enabled": permissions.isChecked(),
                "inventory_history_enabled": inventory.isChecked(),
                "health_score_enabled": health.isChecked(),
                "compare_previous": compare.isChecked(),
                "technical_columns": [k for k, check in checks.items() if check.isChecked()],
            }
        )
        self.user_settings = state.save_settings(self.user_settings)
        if previous_fallback.strip().lower() != fallback_text.strip().lower():
            state.clear_cache()
        self._apply_column_visibility(reset_order=False)
        msg = "Advanced settings saved"
        if invalid:
            msg += " • ignored invalid country entries: " + ", ".join(invalid)
        if portable.isChecked() != old_portable:
            ok, portable_msg = device_insights.migrate_portable_mode(portable.isChecked())
            if not ok:
                QMessageBox.warning(self, "Portable mode", portable_msg)
            else:
                msg += " • restart required for portable mode"
        self.status_label.setText(msg)

    # ---------- Audit completion / inventory ----------
    def _start_subset_refresh(self, packages: list[str], label: str) -> None:
        self._v9_targeted_active = True
        super()._start_subset_refresh(packages, label)
        if not self._audit_active:
            self._v9_targeted_active = False

    def _on_controlled_done(self, payload: object) -> None:
        result = compact_ui.coerce_audit_run_result(payload)
        targeted = self._v9_targeted_active
        if targeted:
            result.metadata["targeted"] = True
        super()._on_controlled_done(result)
        self._v9_targeted_active = False
        if self.current_rows:
            for row in self.current_rows:
                device_insights.apply_health_score(row)
        if self.current_rows:
            self.model.set_rows(self.current_rows)
            self._apply_column_visibility(reset_order=False)
            self._update_summary()

    def _report_baseline_persistence_issue(
        self,
        *,
        stage: str,
        history_status: str,
        inventory_status: str,
        error: Exception,
    ) -> None:
        """Report a post-success local save problem without failing the audit."""

        error_text = " ".join(str(error).split())[:500] or type(error).__name__
        device_insights.log_event(
            "audit_baseline_persistence result=partial "
            f"stage={stage} history={history_status} inventory={inventory_status} "
            f"error={error_text}"
        )
        if stage == "history":
            self.status_label.setText("Audit completed • local history baseline not saved")
            message = "The audit completed, but its local history baseline could not be saved."
            if inventory_status == "skipped":
                message += " The device inventory baseline was not updated."
        elif stage == "inventory":
            self.status_label.setText("Audit completed • device inventory baseline not saved")
            if history_status == "saved":
                message = (
                    "The audit completed and local history was saved, but the device "
                    "inventory baseline could not be saved."
                )
            else:
                message = (
                    "The audit completed, but the device inventory baseline could not be saved."
                )
        else:
            self.status_label.setText("Audit completed • local baseline not fully saved")
            message = "The audit completed, but its local baselines could not be fully saved."
        QMessageBox.warning(self, "Audit completed with a local save warning", message)

    def _promote_successful_audit(self, result: AuditRunResult) -> bool:
        """Persist post-success baselines in order; return whether inventory changed."""

        if result.outcome is not AuditRunOutcome.SUCCESS:
            return False
        targeted = bool(result.metadata.get("targeted"))
        history_requested = bool(self.user_settings.get("compare_previous", False))
        inventory_requested = bool(
            not targeted
            and self.source_mode == "device"
            and self.current_rows
            and bool(self.user_settings.get("inventory_history_enabled", True))
            and self._device_summary
        )
        history_status = "not_requested"

        if history_requested:
            try:
                if targeted:
                    device_metadata.save_history_merged(self.current_rows)
                else:
                    state.save_history(self.current_rows)
            except Exception as exc:
                self._report_baseline_persistence_issue(
                    stage="history",
                    history_status="failed",
                    inventory_status="skipped" if inventory_requested else "not_requested",
                    error=exc,
                )
                return False
            history_status = "saved"

        if not inventory_requested:
            return False
        try:
            self._last_inventory_changes = device_insights.annotate_inventory_changes_and_save(
                self.current_rows, self._device_summary
            )
        except Exception as exc:
            self._report_baseline_persistence_issue(
                stage="inventory",
                history_status=history_status,
                inventory_status="failed",
                error=exc,
            )
            return False
        self.model.set_rows(self.current_rows)
        return True

    # ---------- Details/context ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("App Details")
        dialog.resize(760, 720)
        root = QVBoxLayout(dialog)
        title = QLabel(
            f"<b>{html.escape(str(row.get('play_title') or row.get('package_name') or 'App'))}</b>"
        )
        root.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        form = QFormLayout(inner)
        fields = [
            ("Status", "criticality"),
            ("Maintenance Score", "health_score"),
            ("Change", "change"),
            ("Package Name", "package_name"),
            ("Play Store Title", "play_title"),
            ("Last update", "play_last_update"),
            ("Age (days)", "age_days"),
            ("Play Store version", "play_version"),
            ("Installed version", "installed_version"),
            ("Installed vs Store", "version_comparison"),
            ("Installer source", "installer_source"),
            ("Android compatibility", "compatibility_status"),
            ("Target SDK", "target_sdk"),
            ("Min SDK", "min_sdk"),
            ("First installed", "first_install_time"),
            ("Last local update", "last_local_update"),
            ("Enabled state", "app_enabled"),
            ("Device inventory change", "device_change"),
            ("Sensitive permissions", "sensitive_permissions"),
            ("Play status", "play_status"),
            ("Update source", "updated_source"),
            ("HTTP status", "play_http_status"),
            ("System app", "is_system"),
            ("Notes", "notes"),
        ]
        for label_text, key in fields:
            value = (
                presentation.friendly_notes(row)
                if key == "notes"
                else str(row.get(key, "") or "")
            )
            if not value and key not in {"notes", "change"}:
                continue
            display_value = f"{value}/100" if key == "health_score" else value
            label = QLabel(html.escape(display_value))
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setObjectName(f"DetailsValue_{key}")
            base_ui.apply_semantic_label_presentation(label, key, value)
            form.addRow(label_text, label)
            if key == "health_score":
                breakdown_label = QLabel(
                    "<br>".join(
                        html.escape(line)
                        for line in device_insights.health_score_breakdown_lines(row)
                    )
                )
                breakdown_label.setWordWrap(True)
                breakdown_label.setTextInteractionFlags(
                    Qt.TextInteractionFlag.TextSelectableByMouse
                )
                breakdown_label.setObjectName("DetailsValue_health_score_breakdown")
                form.addRow("Score breakdown", breakdown_label)
        alternative_results = alternative_distribution.provider_results(row)
        if alternative_results:
            alternative_label = QLabel(alternative_distribution.provider_evidence_text(row))
            alternative_label.setObjectName("DetailsValue_alternative_distribution")
            alternative_label.setWordWrap(True)
            alternative_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            form.addRow("Alternative distribution", alternative_label)
            for result in alternative_results:
                if not result.listing_url:
                    continue
                listing_button = QPushButton("Open provider listing")
                listing_button.clicked.connect(
                    lambda _checked=False, target=result.listing_url: QDesktopServices.openUrl(
                        QUrl(target)
                    )
                )
                form.addRow("", listing_button)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        row_buttons = QHBoxLayout()
        open_store = QPushButton("Open in Google Play")
        open_store.setEnabled(bool(row.get("store_url")))
        open_store.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(str(row.get("store_url") or ""))))
        open_info = QPushButton("Open App Info on Phone")
        open_info.setEnabled(self.source_mode == "device")
        open_info.clicked.connect(lambda: self._open_app_info(str(row.get("package_name") or "")))
        row_buttons.addWidget(open_store)
        row_buttons.addWidget(open_info)
        row_buttons.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        row_buttons.addWidget(close)
        root.addLayout(row_buttons)
        dialog.exec()

    def _show_row_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        row = self._row_from_proxy_index(index)
        if not row:
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        details = menu.addAction("App Details…")
        recheck = menu.addAction("Force Recheck This App")
        open_store = menu.addAction("Open in Google Play")
        open_info = menu.addAction("Open App Info on Phone")
        menu.addSeparator()
        copy_package = menu.addAction("Copy Package Name")
        copy_title = menu.addAction("Copy Play Store Title")
        copy_url = menu.addAction("Copy Store URL")
        copy_row = menu.addAction("Copy Visible Row")

        package_name = str(row.get("package_name") or "").strip()
        availability = self._row_action_availability(row)
        details.setEnabled(availability.details)
        recheck.setEnabled(availability.recheck)
        open_store.setEnabled(availability.store)
        open_info.setEnabled(availability.app_info)
        copy_package.setEnabled(availability.package)
        copy_title.setEnabled(availability.title)
        copy_url.setEnabled(availability.url)
        copy_row.setEnabled(availability.visible_row)
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is details:
            self._show_details(row)
        elif chosen is recheck:
            self._start_subset_refresh([package_name], "App recheck")
        elif chosen is open_store:
            if row.get("store_url"):
                QDesktopServices.openUrl(QUrl(str(row.get("store_url"))))
        elif chosen is open_info:
            self._open_app_info(package_name)
        elif chosen is copy_package:
            QApplication.clipboard().setText(str(row.get("package_name") or ""))
        elif chosen is copy_title:
            QApplication.clipboard().setText(str(row.get("play_title") or ""))
        elif chosen is copy_url:
            QApplication.clipboard().setText(str(row.get("store_url") or ""))
        elif chosen is copy_row:
            header = self.table.horizontalHeader()
            visible = [
                (header.visualIndex(i), V9_MODEL_COLUMNS[i])
                for i in range(len(V9_MODEL_COLUMNS))
                if not self.table.isColumnHidden(i)
            ]
            visible.sort()
            QApplication.clipboard().setText(
                "\t".join(str(row.get(column, "") or "") for _, column in visible)
            )

    def _open_app_info(self, package_name: str) -> None:
        adb = self._get_authorised_adb()
        if not adb:
            QMessageBox.warning(
                self, "ADB unavailable", "No authorised Android device is currently connected."
            )
            return
        try:
            device_insights.open_app_info_on_device(adb, package_name)
        except Exception as exc:
            QMessageBox.critical(self, "Could not open App Info", str(exc))

    # ---------- Reports/help/update/diagnostics ----------
    def _export_html_report(self) -> None:
        if not self.current_rows:
            QMessageBox.information(self, "No results", "Run an audit first.")
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, "Export HTML report", "playstore_audit_report.html", "HTML (*.html)"
        )
        if not selected:
            return
        if not selected.lower().endswith(".html"):
            selected += ".html"
        device_insights.write_html_report(selected, self.current_rows, self._device_summary)
        QMessageBox.information(self, "Report created", f"HTML report saved to:\n{selected}")

    def _show_text_help(self, title: str, text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(760, 600)
        layout = QVBoxLayout(dialog)
        box = QPlainTextEdit()
        box.setReadOnly(True)
        box.setPlainText(text)
        layout.addWidget(box, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.clicked.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    def _check_for_updates(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = device_insights.check_for_updates()
        finally:
            QApplication.restoreOverrideCursor()
        if result.get("status") != "ok":
            QMessageBox.information(
                self, "Update check", str(result.get("message") or "Update check unavailable.")
            )
            return
        if result.get("newer"):
            answer = QMessageBox.question(
                self, "Update available", f"Version {result.get('tag')} is available. Open the release page?"
            )
            if answer == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(str(result.get("url") or device_insights.LATEST_RELEASE_PAGE)))
        else:
            QMessageBox.information(
                self, "Up to date", f"You are running Play Store App Audit {device_insights.APP_VERSION}."
            )

    def _create_diagnostic_bundle(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self, "Create Diagnostic Bundle", "PlayStoreAppAudit-diagnostics.zip", "ZIP (*.zip)"
        )
        if not selected:
            return
        if not selected.lower().endswith(".zip"):
            selected += ".zip"
        device_insights.create_diagnostic_bundle(selected, self.current_rows, self._device_summary)
        QMessageBox.information(
            self,
            "Diagnostic bundle created",
            "The bundle excludes recent file paths, saved filters and the package inventory itself.",
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Play Store App Audit",
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = InsightsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
