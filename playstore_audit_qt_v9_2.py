from __future__ import annotations

import csv
import sys
from typing import Any

from playstore_audit_process import install_hidden_subprocess_windows
install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app_icon import ensure_runtime_icon
import playstore_audit_qt_v9 as v9
import playstore_audit_qt_v9_fixed as fixed
import playstore_audit_user_state as user_state
import playstore_audit_v9_2_features as v92

v9.features.VIEW_PRESETS = v92.VIEW_PRESETS
v9.features.CSV_EXPORT_GUIDE = v92.CSV_EXPORT_GUIDE
v9.features.APP_VERSION = v92.APP_VERSION


class V92TableModel(fixed.StableV9TableModel):
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and index.isValid()
            and 0 <= index.row() < len(self.rows)
            and 0 <= index.column() < len(self.columns)
        ):
            column = self.columns[index.column()]
            if column in v92.DATE_FIELDS:
                return v92.display_value(column, self.rows[index.row()].get(column, ""))
        return super().data(index, role)


class V92FilterProxy(v9.V9FilterProxy):
    def __init__(self) -> None:
        super().__init__()
        self.status_filters: set[str] = set()
        self.set_v9_preset("All")
        self.set_criticality_filter(None)

    def set_status_filters(self, filters: set[str]) -> None:
        self.status_filters = set(filters)
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        if not self.status_filters:
            return True
        model = self.sourceModel()
        if not isinstance(model, fixed.StableV9TableModel):
            return True
        row = model.row_dict(source_row)
        return str(row.get("criticality_key") or "") in self.status_filters


class PlayStoreAuditQtV92(fixed.PlayStoreAuditQtV9Fixed):
    def __init__(self) -> None:
        self._status_filters: set[str] = set()
        settings = user_state.load_settings()
        settings["active_filter_preset"] = "All"
        user_state.save_settings(settings)
        super().__init__()

        old_proxy = self.proxy
        model = V92TableModel()
        model.set_rows(list(self.current_rows))
        proxy = V92FilterProxy()
        proxy.setSourceModel(model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_status_filters(self._status_filters)
        self.model = model
        self.proxy = proxy
        self.table.setModel(proxy)
        old_proxy.deleteLater()
        self._apply_column_visibility(reset_order=True)
        self._sync_status_filter_buttons()
        self._update_summary()

    # ---------- Views ----------
    def _visible_column_order(self) -> list[str]:
        settings = user_state.load_settings()
        preset = str(settings.get("view_preset") or "Basic")
        compare = bool(settings.get("compare_previous", False))
        health = bool(settings.get("health_score_enabled", False))

        if preset == "Technical":
            columns = list(v9.V9_MODEL_COLUMNS)
            if not compare and "change" in columns:
                columns.remove("change")
        elif preset == "Device":
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns += [
                "package_name", "play_title", "play_last_update", "age_days",
                "compatibility_status", "installed_version", "version_comparison",
                "installer_source", "app_enabled", "device_change",
            ]
            if health:
                columns.append("health_score")
            columns.append("notes")
        elif preset == "Custom":
            configured = settings.get("custom_view_columns", v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            columns = [c for c in configured if c in v9.V9_MODEL_COLUMNS] if isinstance(configured, list) else list(v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            if "criticality" not in columns:
                columns.insert(0, "criticality")
            if "package_name" not in columns:
                columns.insert(1, "package_name")
            if compare and "change" not in columns:
                columns.insert(1, "change")
        else:
            columns = ["criticality"]
            if compare:
                columns.append("change")
            columns += ["package_name", "play_title", "play_last_update", "age_days", "notes"]
        return list(dict.fromkeys(columns))

    # ---------- Multi-status chips ----------
    def _set_criticality_filter(self, key: str | None) -> None:
        if key is None:
            self._status_filters.clear()
        elif key in self._status_filters:
            self._status_filters.remove(key)
        else:
            self._status_filters.add(key)
        self.criticality_filter = None
        if isinstance(self.proxy, V92FilterProxy):
            self.proxy.set_status_filters(self._status_filters)
        self._sync_status_filter_buttons()
        self._update_summary()

    def _sync_criticality_buttons(self) -> None:
        self._sync_status_filter_buttons()

    def _sync_status_filter_buttons(self) -> None:
        if hasattr(self, "all_chip"):
            self.all_chip.setChecked(not self._status_filters)
        if hasattr(self, "criticality_buttons"):
            for key, button in self.criticality_buttons.items():
                button.setChecked(key in self._status_filters)

    # ---------- Concise summary ----------
    def _update_summary(self) -> None:
        if not hasattr(self, "summary_label"):
            return
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        self.summary_label.setText(v92.concise_summary(list(self.current_rows), visible))

    # ---------- Menu ----------
    def _build_menu_v9(self) -> None:
        bar = self.menuBar()
        bar.clear()

        file_menu = bar.addMenu("File")
        file_menu.addAction("Choose app list…", self._choose_input)
        self._recent_menu = file_menu.addMenu("Recent sources")
        self._populate_recent_menu()
        file_menu.addAction("Scan phone with ADB", self._scan_phone)
        file_menu.addAction("Export current phone package list as CSV…", self._export_phone_packages_csv)
        file_menu.addSeparator()
        file_menu.addAction("Export all results as CSV…", self._export_results)
        file_menu.addAction("Export visible results as CSV…", self._export_visible_results)
        file_menu.addAction("Export HTML report…", self._export_html_report)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        view_menu = bar.addMenu("View")
        presets = view_menu.addMenu("View preset")
        group = QActionGroup(self)
        group.setExclusive(True)
        current = str(user_state.load_settings().get("view_preset") or "Basic")
        for name in v92.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            group.addAction(action)
            presets.addAction(action)
        self._view_action_group = group
        view_menu.addSeparator()
        view_menu.addAction("Reset table layout", self._reset_table_layout)

        tools = bar.addMenu("Tools")
        tools.addAction("Advanced settings…", self._show_advanced_settings)
        tools.addSeparator()
        tools.addAction("Force full refresh (ignore cache)", self._force_full_refresh)
        tools.addAction("Recheck Removed / Anomaly / Other", self._recheck_problematic)
        tools.addSeparator()
        tools.addAction("Device summary…", self._show_device_summary)
        snapshots = tools.addMenu("Device snapshots")
        snapshots.addAction("Save current device snapshot…", self._save_device_snapshot)
        snapshots.addAction("Compare current device with snapshot…", self._compare_device_snapshot)
        tools.addAction("Device inventory changes…", self._show_inventory_changes)
        tools.addSeparator()
        tools.addAction("Clear audit cache", self._clear_audit_cache)
        tools.addAction("Clear previous-audit history", self._clear_audit_history)

        help_menu = bar.addMenu("Help")
        help_menu.addAction("ADB setup guide…", lambda: self._show_text_help("ADB setup guide", v9.features.ADB_SETUP_GUIDE))
        help_menu.addAction("How to export package CSV…", lambda: self._show_text_help("Export package CSV", v92.CSV_EXPORT_GUIDE))
        help_menu.addAction("Health score methodology…", lambda: self._show_text_help("Health score methodology", v9.features.HEALTH_SCORE_GUIDE))
        help_menu.addSeparator()
        help_menu.addAction("Check for updates…", self._check_for_updates)
        help_menu.addAction("Create diagnostic bundle…", self._create_diagnostic_bundle)
        help_menu.addSeparator()
        help_menu.addAction("About Play Store App Audit", self._show_about)

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = user_state.load_settings()
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced settings")
        dialog.resize(780, 800)
        dialog.setMinimumWidth(680)
        root = QVBoxLayout(dialog)

        warning = QLabel(
            "⚠ Expert settings. These options can change Store interpretation, ADB collection, cache behaviour and the data shown. Change them only when genuinely necessary."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("background:#FFF6E5;color:#6B4A16;border:1px solid #E9C77D;padding:10px;border-radius:6px;")
        root.addWidget(warning)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        content = QVBoxLayout(inner)
        content.setContentsMargins(8, 8, 8, 8)
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        store = QGroupBox("Store, dates and cache")
        form = QFormLayout(store)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        language = QLineEdit(str(self.user_settings.get("store_language") or "en"))
        fallback = QLineEdit(str(self.user_settings.get("fallback_countries") or v9.v8.features.DEFAULT_FALLBACK_COUNTRIES))
        date_format = QComboBox()
        date_format.addItems(list(v92.DATE_FORMATS))
        date_format.setCurrentText(str(self.user_settings.get("date_format") or v92.DEFAULT_DATE_FORMAT))
        cache = QCheckBox("Use intelligent cache")
        cache.setChecked(bool(self.user_settings.get("cache_enabled", True)))
        ttl = QSpinBox()
        ttl.setRange(1, 720)
        ttl.setSuffix(" hours")
        ttl.setValue(int(self.user_settings.get("cache_ttl_hours", 72)))
        form.addRow("Store language", language)
        form.addRow("Fallback Store countries", fallback)
        fallback_note = QLabel("Comma/space separated country codes. Used only if the selected Store country is unavailable or inconclusive.")
        fallback_note.setWordWrap(True)
        form.addRow("", fallback_note)
        form.addRow("Date display format", date_format)
        form.addRow("", cache)
        form.addRow("Healthy-result cache TTL", ttl)
        content.addWidget(store)

        device = QGroupBox("Connected Android device")
        d_layout = QVBoxLayout(device)
        collect = QCheckBox("Collect connected-device metadata")
        collect.setChecked(bool(self.user_settings.get("collect_device_metadata", True)))
        permissions = QCheckBox("Audit sensitive requested permissions (advanced)")
        permissions.setChecked(bool(self.user_settings.get("permissions_audit_enabled", False)))
        inventory = QCheckBox("Keep per-device inventory history")
        inventory.setChecked(bool(self.user_settings.get("inventory_history_enabled", True)))
        health = QCheckBox("Enable experimental Health score")
        health.setChecked(bool(self.user_settings.get("health_score_enabled", False)))
        d_layout.addWidget(collect)
        d_layout.addWidget(permissions)
        p_note = QLabel(
            "Permission audit checks a curated list of sensitive permissions declared/requested by each package (camera, microphone, location, contacts, SMS, phone, media, all-files access, overlays, etc.). It does not decide whether a permission is granted, justified or malicious. The same package dump is already collected for device metadata, so enabling this mainly adds parsing rather than extra per-app ADB calls."
        )
        p_note.setWordWrap(True)
        d_layout.addWidget(p_note)
        d_layout.addWidget(inventory)
        d_layout.addWidget(health)
        content.addWidget(device)

        history = QGroupBox("Audit history")
        h_layout = QVBoxLayout(history)
        compare = QCheckBox("Compare with previous Play Store audit")
        compare.setChecked(bool(self.user_settings.get("compare_previous", False)))
        h_layout.addWidget(compare)
        content.addWidget(history)

        storage = QGroupBox("Storage")
        s_layout = QVBoxLayout(storage)
        portable = QCheckBox("Portable mode: keep app data next to the EXE")
        portable.setChecked(v9.features.portable_mode_active())
        portable_note = QLabel("Changing portable mode migrates local app data and requires a restart. The EXE folder must be writable.")
        portable_note.setWordWrap(True)
        s_layout.addWidget(portable)
        s_layout.addWidget(portable_note)
        content.addWidget(storage)

        custom = QGroupBox("Custom view columns")
        grid = QGridLayout(custom)
        configured = set(self.user_settings.get("custom_view_columns", v92.DEFAULT_CUSTOM_VIEW_COLUMNS))
        custom_checks: dict[str, QCheckBox] = {}
        choices = [c for c in v9.V9_MODEL_COLUMNS if c not in {"criticality", "package_name"}]
        for i, key in enumerate(choices):
            label = v9.v8.v7.qt_base.COLUMN_LABELS.get(key, key)
            check = QCheckBox(label)
            check.setChecked(key in configured)
            custom_checks[key] = check
            grid.addWidget(check, i // 2, i % 2)
        note = QLabel("Status and Package Name are always included. Choose View → View preset → Custom to use this selection.")
        note.setWordWrap(True)
        grid.addWidget(note, (len(choices) + 1) // 2, 0, 1, 2)
        content.addWidget(custom)
        content.addStretch(1)

        bottom = QHBoxLayout()
        reset = QPushButton("Reset to defaults")
        bottom.addWidget(reset)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bottom.addWidget(buttons)
        root.addLayout(bottom)
        old_portable = v9.features.portable_mode_active()

        def reset_controls() -> None:
            language.setText("en")
            fallback.setText(v9.v8.features.DEFAULT_FALLBACK_COUNTRIES)
            date_format.setCurrentText(v92.DEFAULT_DATE_FORMAT)
            cache.setChecked(True)
            ttl.setValue(72)
            collect.setChecked(True)
            permissions.setChecked(False)
            inventory.setChecked(True)
            health.setChecked(False)
            compare.setChecked(False)
            portable.setChecked(False)
            defaults = set(v92.DEFAULT_CUSTOM_VIEW_COLUMNS)
            for key, check in custom_checks.items():
                check.setChecked(key in defaults)

        reset.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fallback_text, invalid = v9.v8.features.normalise_country_string(fallback.text())
        previous_fallback = str(self.user_settings.get("fallback_countries") or "")
        custom_columns = ["criticality", "package_name"] + [k for k, check in custom_checks.items() if check.isChecked()]
        self.user_settings.update({
            "store_language": (language.text().strip() or "en").lower(),
            "fallback_countries": fallback_text,
            "date_format": date_format.currentText(),
            "cache_enabled": cache.isChecked(),
            "cache_ttl_hours": ttl.value(),
            "collect_device_metadata": collect.isChecked(),
            "permissions_audit_enabled": permissions.isChecked(),
            "inventory_history_enabled": inventory.isChecked(),
            "health_score_enabled": health.isChecked(),
            "compare_previous": compare.isChecked(),
            "custom_view_columns": list(dict.fromkeys(custom_columns)),
        })
        self.user_settings = user_state.save_settings(self.user_settings)
        if previous_fallback.strip().lower() != fallback_text.strip().lower():
            user_state.clear_cache()
        if portable.isChecked() != old_portable:
            ok, portable_msg = v9.features.migrate_portable_mode(portable.isChecked())
            if not ok:
                QMessageBox.warning(self, "Portable mode", portable_msg)
        self._apply_column_visibility(reset_order=False)
        self.model.layoutChanged.emit()
        self._update_summary()
        msg = "Advanced settings saved"
        if invalid:
            msg += " • ignored invalid country entries: " + ", ".join(invalid)
        self.status_label.setText(msg)

    # ---------- Date formatting in details/exports ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        super()._show_details(v92.rows_for_output([row])[0])

    def _export_rows(self, rows: list[dict[str, object]], default_name: str) -> None:
        super()._export_rows(v92.rows_for_output([dict(r) for r in rows]), default_name)

    def _export_html_report(self) -> None:
        if not self.current_rows:
            QMessageBox.information(self, "Nothing to export", "There are no results to export.")
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Export HTML report", "playstore_audit_report.html", "HTML (*.html)")
        if not selected:
            return
        if not selected.lower().endswith(".html"):
            selected += ".html"
        try:
            v9.features.write_html_report(selected, v92.rows_for_output(list(self.current_rows)), self._device_summary)
            QMessageBox.information(self, "Export complete", f"HTML report saved to:\n{selected}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(v9.v8.v7.qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtV92()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
