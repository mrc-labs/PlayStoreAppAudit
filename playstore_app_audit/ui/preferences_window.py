from __future__ import annotations

import sys
from typing import Any

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.app_icon_metadata as app_icon_metadata
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.alternative_distribution_settings as alternative_settings_ui
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.insights_window as insights_ui
import playstore_app_audit.ui.table_window as table_ui
from app_icon import ensure_runtime_icon


class FormattedAuditTableModel(table_ui.AuditTableModel):
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and index.isValid()
            and 0 <= index.row() < len(self.rows)
            and 0 <= index.column() < len(self.columns)
        ):
            column = self.columns[index.column()]
            if column in presentation.DATE_FIELDS:
                return presentation.display_value(column, self.rows[index.row()].get(column, ""))
        return super().data(index, role)


class AuditFilterProxy(insights_ui.AdvancedFilterProxy):
    def __init__(self) -> None:
        super().__init__()
        self.status_filters: set[str] = set()
        self.smart_query: smart_queries.SmartQuery | None = None
        self.set_v9_preset("All")
        self.set_criticality_filter(None)

    def set_status_filters(self, filters: set[str]) -> None:
        self.beginFilterChange()
        self.status_filters = set(filters)
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_smart_query(self, query: smart_queries.SmartQuery | None) -> None:
        self.beginFilterChange()
        self.smart_query = query
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        model = self.sourceModel()
        if not isinstance(model, table_ui.AuditTableModel):
            return True
        row = model.row_dict(source_row)
        if self.status_filters and str(row.get("criticality_key") or "") not in self.status_filters:
            return False
        return smart_queries.query_matches(row, self.smart_query)


class PreferencesWindow(table_ui.TableWindow):
    def __init__(self) -> None:
        self._status_filters: set[str] = set()
        settings = state.load_settings()
        settings["active_filter_preset"] = "All"
        state.save_settings(settings)
        super().__init__()

        old_proxy = self.proxy
        model = FormattedAuditTableModel()
        model.set_rows(list(self.current_rows))
        proxy = AuditFilterProxy()
        proxy.setSourceModel(model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_status_filters(self._status_filters)
        self.model = model
        self.proxy = proxy
        self.table.setModel(proxy)
        old_proxy.deleteLater()
        self._restore_table_layout()
        self._apply_column_visibility(reset_order=False)
        self._sync_status_filter_buttons()
        self._update_summary()

    # ---------- Views ----------
    def _visible_column_order(self) -> list[str]:
        settings = state.load_settings()
        preset = str(settings.get("view_preset") or "Basic")
        compare = bool(settings.get("compare_previous", False))
        health = bool(settings.get("health_score_enabled", False))

        if preset == "Technical":
            columns = list(insights_ui.V9_MODEL_COLUMNS)
            if not compare and "change" in columns:
                columns.remove("change")
        elif preset == "Source Details":
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
        elif preset == "Custom":
            configured = self._normalise_custom_columns(settings.get("custom_view_columns"))
            columns = configured or list(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS)
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
        if isinstance(self.proxy, AuditFilterProxy):
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
        self.summary_label.setText(presentation.concise_summary(list(self.current_rows), visible))

    # ---------- Menu ----------
    def _build_menu_v9(self) -> None:
        bar = self.menuBar()
        bar.clear()

        file_menu = bar.addMenu("File")
        file_menu.addAction("Choose App List…", self._choose_input)
        self._recent_menu = file_menu.addMenu("Recent Sources")
        self._populate_recent_menu()
        file_menu.addAction("Scan Phone with ADB", self._scan_phone)
        file_menu.addAction(
            "Export Current Phone Package List as CSV…", self._export_phone_packages_csv
        )
        file_menu.addSeparator()
        file_menu.addAction("Export All Results as CSV…", self._export_results)
        file_menu.addAction("Export Visible Results as CSV…", self._export_visible_results)
        file_menu.addAction("Export HTML Report…", self._export_html_report)
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)

        view_menu = bar.addMenu("View")
        presets = view_menu.addMenu("Column Preset")
        group = QActionGroup(self)
        group.setExclusive(True)
        current = str(state.load_settings().get("view_preset") or "Basic")
        for name in presentation.VIEW_PRESETS:
            action = QAction(name, self, checkable=True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _checked=False, n=name: self._set_view_preset(n))
            group.addAction(action)
            if name == "Custom":
                action.setEnabled(self._has_custom_table_layout(state.load_settings()))
            presets.addAction(action)
        self._view_action_group = group
        view_menu.addAction("Customize View…", self._show_display_settings)
        view_menu.addSeparator()
        view_menu.addAction("Reset Table Layout", self._reset_table_layout)

        tools = bar.addMenu("Tools")
        tools.addAction("Advanced Settings…", self._show_advanced_settings)
        tools.addSeparator()
        tools.addAction("Force Full Refresh (Ignore Cache)", self._force_full_refresh)
        tools.addAction("Recheck Not Found / Anomaly / Other", self._recheck_problematic)
        tools.addSeparator()
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

    # ---------- Settings ----------
    @staticmethod
    def _settings_note(text: str) -> QLabel:
        note = QLabel(text)
        note.setWordWrap(True)
        note.setObjectName("SettingsNote")
        return note

    @staticmethod
    def _settings_page(
        object_name: str, title: str, description: str
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName(object_name)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 8, 8, 8)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setObjectName("SettingsPageTitle")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)
        layout.addWidget(PreferencesWindow._settings_note(description))
        return page, layout

    def _refresh_table_presentation(self) -> None:
        """Refresh formatted values without claiming that the model layout changed."""
        rows = self.model.rowCount()
        columns = self.model.columnCount()
        if rows <= 0 or columns <= 0:
            return
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(rows - 1, columns - 1),
            [Qt.ItemDataRole.DisplayRole],
        )

    def _sync_view_preset_action(self, name: str) -> None:
        group = getattr(self, "_view_action_group", None)
        if not isinstance(group, QActionGroup):
            return
        for action in group.actions():
            action.setChecked(action.text() == name)

    def _sync_custom_preset_availability(self) -> None:
        for action in getattr(self, "view_preset_actions", []) or []:
            if action.text() == "Custom":
                action.setEnabled(self._has_custom_table_layout(state.load_settings()))
        group = getattr(self, "_view_action_group", None)
        if isinstance(group, QActionGroup):
            for action in group.actions():
                if action.text() == "Custom":
                    action.setEnabled(self._has_custom_table_layout(state.load_settings()))

    def _show_display_settings(self) -> None:
        self.user_settings = state.load_settings()
        dialog = QDialog(self)
        dialog.setObjectName("DisplaySettingsDialog")
        dialog.setWindowTitle("Customize View")
        dialog.resize(740, 640)
        dialog.setMinimumSize(620, 500)
        root = QVBoxLayout(dialog)

        heading = QLabel("Customize View")
        heading.setObjectName("SettingsPageTitle")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading.setFont(heading_font)
        root.addWidget(heading)
        root.addWidget(
            self._settings_note(
                "Choose how Play Store results are presented without changing audit behaviour."
            )
        )

        display_form = QFormLayout()
        display_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        show_icons = QCheckBox("Show Play Store App Icons")
        show_icons.setObjectName("ShowAppIconsCheck")
        show_icons.setToolTip(
            "Load icons on demand and reuse them from a bounded local cache when available."
        )
        show_icons.setChecked(
            bool(
                self.user_settings.get(
                    "show_app_icons", app_icon_metadata.DEFAULT_SHOW_APP_ICONS
                )
            )
        )
        date_format = QComboBox()
        date_format.setObjectName("DateFormatCombo")
        date_format.setMaximumWidth(260)
        date_format.setToolTip("Choose how dates are shown in the table, details and exports.")
        date_format.addItems(list(presentation.DATE_FORMATS))
        date_format.setCurrentText(
            str(self.user_settings.get("date_format") or presentation.DEFAULT_DATE_FORMAT)
        )
        display_form.addRow("Date Format", date_format)
        display_form.addRow("", show_icons)
        root.addLayout(display_form)

        custom_heading = QLabel("Custom Columns")
        custom_heading.setObjectName("SettingsSectionTitle")
        custom_font = custom_heading.font()
        custom_font.setBold(True)
        custom_heading.setFont(custom_font)
        root.addWidget(custom_heading)
        root.addWidget(
            self._settings_note(
                "Store Status and Package Name are always included. Changing this selection "
                "activates View > Column Preset > Custom."
            )
        )

        scroll = QScrollArea()
        scroll.setObjectName("CustomColumnsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        columns_host = QWidget()
        grid = QGridLayout(columns_host)
        grid.setContentsMargins(0, 4, 0, 4)
        stored_custom = self._normalise_custom_columns(
            self.user_settings.get("custom_view_columns")
        ) or list(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS)
        current_preset = str(self.user_settings.get("view_preset") or "Basic")
        initial_columns = (
            list(stored_custom) if current_preset == "Custom" else self._visible_column_order()
        )
        configured = set(initial_columns)
        custom_checks: dict[str, QCheckBox] = {}
        choices = [c for c in insights_ui.V9_MODEL_COLUMNS if c not in {"criticality", "package_name"}]
        for index, key in enumerate(choices):
            label = base_ui.COLUMN_LABELS.get(key, key)
            check = QCheckBox(label)
            check.setObjectName(f"CustomColumnCheck_{key}")
            check.setChecked(key in configured)
            custom_checks[key] = check
            grid.addWidget(check, index // 2, index % 2)
        grid.setRowStretch((len(choices) + 1) // 2, 1)
        scroll.setWidget(columns_host)
        root.addWidget(scroll, 1)

        bottom = QHBoxLayout()
        reset = QPushButton("Reset to Defaults")
        bottom.addWidget(reset)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bottom.addWidget(buttons)
        root.addLayout(bottom)

        def reset_controls() -> None:
            show_icons.setChecked(app_icon_metadata.DEFAULT_SHOW_APP_ICONS)
            date_format.setCurrentText(presentation.DEFAULT_DATE_FORMAT)
            defaults = set(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS)
            for key, check in custom_checks.items():
                check.setChecked(key in defaults)

        reset.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        custom_columns = ["criticality", "package_name"] + [
            key for key, check in custom_checks.items() if check.isChecked()
        ]
        custom_columns = list(dict.fromkeys(custom_columns))
        columns_changed = set(custom_columns) != configured
        updates: dict[str, object] = {
            "show_app_icons": show_icons.isChecked(),
            "date_format": date_format.currentText(),
        }
        if columns_changed:
            updates.update(
                {
                    "custom_view_columns": custom_columns,
                    "custom_view_exists": True,
                    "view_preset": "Custom",
                }
            )
        self.user_settings.update(updates)
        self.user_settings = state.save_settings(self.user_settings)
        if hasattr(self.model, "set_app_icons_enabled"):
            self.model.set_app_icons_enabled(
                bool(
                    self.user_settings.get(
                        "show_app_icons", app_icon_metadata.DEFAULT_SHOW_APP_ICONS
                    )
                )
            )
        if columns_changed:
            self._apply_column_visibility(reset_order=False)
            self._persist_current_custom_layout()
        else:
            self._sync_custom_preset_availability()
        self._refresh_table_presentation()
        self._update_summary()
        self._set_presentation_status("Customize View settings saved")

    def _show_advanced_settings(self) -> None:
        self.user_settings = state.load_settings()
        dialog = QDialog(self)
        dialog.setObjectName("AdvancedSettingsDialog")
        dialog.setWindowTitle("Advanced Settings")
        dialog.resize(820, 620)
        dialog.setMinimumSize(720, 520)
        root = QVBoxLayout(dialog)

        warning = QLabel(
            "⚠ Expert settings. These options can change Store interpretation, ADB collection, cache behaviour and the data shown. Change them only when genuinely necessary."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background:#FFF6E5;color:#6B4A16;border:1px solid #E9C77D;padding:10px;border-radius:6px;"
        )
        root.addWidget(warning)

        body = QHBoxLayout()
        body.setSpacing(12)
        navigation = QListWidget()
        navigation.setObjectName("AdvancedSettingsCategories")
        navigation.setAccessibleName("Advanced Settings Categories")
        navigation.setMinimumWidth(170)
        navigation.setMaximumWidth(190)
        stack = QStackedWidget()
        stack.setObjectName("AdvancedSettingsPages")
        body.addWidget(navigation)
        body.addWidget(stack, 1)
        root.addLayout(body, 1)

        def add_page(
            object_name: str, title: str, description: str
        ) -> tuple[QWidget, QVBoxLayout]:
            page, layout = self._settings_page(object_name, title, description)
            navigation.addItem(title)
            stack.addWidget(page)
            return page, layout

        _store_page, store_layout = add_page(
            "StoreCacheSettingsPage",
            "Store & Cache",
            "Configure Play Store locale resolution, request concurrency and cached results.",
        )
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        language = QLineEdit(str(self.user_settings.get("store_language") or "auto"))
        language.setObjectName("StoreLanguageEdit")
        language.setMaximumWidth(300)
        language.setPlaceholderText("auto, en, it, de, …")
        language.setToolTip(
            "Use 'auto' to follow the connected Android system language during phone audits. "
            "For file audits, Auto uses the primary language of the selected Store country. "
            "Enter a language code such as en, it, de or fr to override Auto."
        )
        fallback = QLineEdit(
            str(self.user_settings.get("fallback_countries") or device_metadata.DEFAULT_FALLBACK_COUNTRIES)
        )
        fallback.setMaximumWidth(460)
        workers = QSpinBox()
        workers.setMaximumWidth(180)
        workers.setRange(state.MIN_STORE_WORKERS, state.MAX_STORE_WORKERS)
        workers.setValue(
            state.normalise_store_workers(self.user_settings.get("store_workers"))
        )
        cache = QCheckBox("Use intelligent cache")
        cache.setObjectName("UseIntelligentCacheCheck")
        cache.setChecked(bool(self.user_settings.get("cache_enabled", True)))
        ttl = QSpinBox()
        ttl.setMaximumWidth(180)
        ttl.setRange(1, 720)
        ttl.setSuffix(" hours")
        ttl.setValue(int(self.user_settings.get("cache_ttl_hours", 72)))
        form.addRow("Store Language", language)
        form.addRow("Fallback Store Countries", fallback)
        fallback_note = QLabel(
            "Comma/space separated country codes. Used only if the selected Store country is unavailable or inconclusive. Adding many fallback countries can significantly increase audit time for apps that require regional verification."
        )
        fallback_note.setWordWrap(True)
        form.addRow("", fallback_note)
        form.addRow("Concurrent Store Workers", workers)
        workers_note = self._settings_note(
            "16 is recommended. Higher values can increase Play Store throttling, connection errors and latency; more workers are not always faster."
        )
        form.addRow("", workers_note)
        form.addRow("", cache)
        form.addRow("Healthy Result Cache TTL", ttl)
        store_layout.addLayout(form)
        store_layout.addStretch(1)

        _alternative_page, alternative_layout = add_page(
            "AlternativeDistributionSettingsPage",
            "Alternative Distribution",
            "Configure secondary exact-package evidence after a conclusive Google Play not-found result.",
        )
        provider_settings = alternative_settings_ui.AlternativeDistributionSettingsPage(
            self.user_settings
        )
        provider_scroll = QScrollArea()
        provider_scroll.setObjectName("AlternativeDistributionSettingsScroll")
        provider_scroll.setWidgetResizable(True)
        provider_scroll.setFrameShape(QFrame.Shape.NoFrame)
        provider_scroll.setWidget(provider_settings)
        alternative_layout.addWidget(provider_scroll, 1)

        _device_page, device_layout = add_page(
            "DeviceSettingsPage",
            "Device",
            "Control optional metadata collection from a connected Android device. ADB remains read-only.",
        )
        collect = QCheckBox("Collect connected-device metadata")
        collect.setObjectName("CollectDeviceMetadataCheck")
        collect.setChecked(bool(self.user_settings.get("collect_device_metadata", True)))
        device_layout.addWidget(collect)
        full_scan = QCheckBox("Collect full device metadata during Scan Phone")
        full_scan.setObjectName("CollectFullDeviceMetadataOnScanCheck")
        full_scan.setChecked(self.user_settings.get("collect_full_device_metadata_on_scan") is True)
        full_scan_note = (
            "Captures extended installed-app metadata during Scan Phone so it remains "
            "available if the device is disconnected before the audit. This can "
            "significantly increase scan time."
        )
        full_scan.setToolTip(full_scan_note)
        device_layout.addWidget(full_scan)
        device_layout.addWidget(self._settings_note(full_scan_note))
        device_layout.addStretch(1)

        _audit_page, audit_layout = add_page(
            "AuditHistorySettingsPage",
            "Audit & History",
            "Configure optional audit enrichment and comparisons with previously collected data.",
        )
        permissions = QCheckBox("Audit sensitive requested permissions (advanced)")
        permissions.setObjectName("PermissionsAuditCheck")
        permissions.setChecked(bool(self.user_settings.get("permissions_audit_enabled", False)))
        inventory = QCheckBox("Keep per-device inventory history")
        inventory.setObjectName("InventoryHistoryCheck")
        inventory.setChecked(bool(self.user_settings.get("inventory_history_enabled", True)))
        health = QCheckBox("Enable Maintenance Score")
        health.setObjectName("HealthScoreCheck")
        health.setChecked(bool(self.user_settings.get("health_score_enabled", False)))
        compare = QCheckBox("Compare with previous Play Store audit")
        compare.setObjectName("ComparePreviousAuditCheck")
        compare.setChecked(bool(self.user_settings.get("compare_previous", False)))
        audit_layout.addWidget(permissions)
        p_note = self._settings_note(
            "Permission audit checks a curated list of sensitive permissions declared/requested by each package (camera, microphone, location, contacts, SMS, phone, media, all-files access, overlays, etc.). It does not decide whether a permission is granted, justified or malicious. The same package dump is already collected for device metadata, so enabling this mainly adds parsing rather than extra per-app ADB calls."
        )
        audit_layout.addWidget(p_note)
        audit_layout.addWidget(inventory)
        audit_layout.addWidget(health)
        audit_layout.addWidget(compare)
        audit_layout.addStretch(1)

        _storage_page, storage_layout = add_page(
            "DataStorageSettingsPage",
            "Data & Storage",
            "Choose where application data is stored. Changing this setting requires a restart.",
        )
        portable = QCheckBox("Portable mode: keep app data next to the EXE")
        portable.setObjectName("PortableModeCheck")
        portable.setChecked(device_insights.portable_mode_active())
        portable_note = self._settings_note(
            "Changing portable mode migrates local app data and requires a restart. The EXE folder must be writable."
        )
        storage_layout.addWidget(portable)
        storage_layout.addWidget(portable_note)
        storage_layout.addStretch(1)

        navigation.currentRowChanged.connect(stack.setCurrentIndex)
        navigation.setCurrentRow(0)

        bottom = QHBoxLayout()
        reset = QPushButton("Reset All to Defaults")
        bottom.addWidget(reset)
        bottom.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        bottom.addWidget(buttons)
        root.addLayout(bottom)
        old_portable = device_insights.portable_mode_active()

        def reset_controls() -> None:
            language.setText(str(state.DEFAULT_SETTINGS["store_language"]))
            fallback.setText(device_metadata.DEFAULT_FALLBACK_COUNTRIES)
            workers.setValue(state.DEFAULT_STORE_WORKERS)
            cache.setChecked(True)
            ttl.setValue(72)
            collect.setChecked(True)
            full_scan.setChecked(False)
            permissions.setChecked(False)
            inventory.setChecked(True)
            health.setChecked(False)
            compare.setChecked(False)
            portable.setChecked(False)
            provider_settings.reset_to_defaults()

        reset.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fallback_text, invalid = device_metadata.normalise_country_string(fallback.text())
        previous_fallback = str(self.user_settings.get("fallback_countries") or "")
        previous_alternative = self.user_settings.get("alternative_distribution")
        self.user_settings.update(
            {
                "store_language": (
                    language.text().strip() or str(state.DEFAULT_SETTINGS["store_language"])
                ).lower(),
                "fallback_countries": fallback_text,
                "store_workers": workers.value(),
                "cache_enabled": cache.isChecked(),
                "cache_ttl_hours": ttl.value(),
                "collect_device_metadata": collect.isChecked(),
                "collect_full_device_metadata_on_scan": full_scan.isChecked(),
                "permissions_audit_enabled": permissions.isChecked(),
                "inventory_history_enabled": inventory.isChecked(),
                "health_score_enabled": health.isChecked(),
                "compare_previous": compare.isChecked(),
                "alternative_distribution": provider_settings.configuration(),
            }
        )
        self.user_settings = state.save_settings(self.user_settings)
        self.workers_spin.setValue(
            state.normalise_store_workers(self.user_settings.get("store_workers"))
        )
        if previous_fallback.strip().lower() != fallback_text.strip().lower():
            state.clear_cache()
        if previous_alternative != self.user_settings.get("alternative_distribution"):
            state.clear_alternative_distribution_cache()
        if portable.isChecked() != old_portable:
            ok, portable_msg = device_insights.migrate_portable_mode(portable.isChecked())
            if not ok:
                QMessageBox.warning(self, "Portable mode", portable_msg)
        self._apply_column_visibility(reset_order=False)
        self._update_summary()
        msg = "Advanced settings saved"
        if invalid:
            msg += " • ignored invalid country entries: " + ", ".join(invalid)
        self.status_label.setText(msg)

    # ---------- Date formatting in details/exports ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        super()._show_details(presentation.rows_for_output([row])[0])

    def _export_rows(self, rows: list[dict[str, object]], default_name: str) -> None:
        super()._export_rows(presentation.rows_for_output([dict(r) for r in rows]), default_name)

    def _export_html_report(self) -> None:
        self._export_html_rows(
            list(self.current_rows), "playstore_audit_report.html", "Export HTML report"
        )

    def _export_visible_html_report(self) -> None:
        self._export_html_rows(
            self._visible_rows(),
            "playstore_audit_visible_report.html",
            "Export visible results as HTML",
        )

    def _export_html_rows(
        self, rows: list[dict[str, Any]], default_name: str, title: str
    ) -> None:
        if not rows:
            QMessageBox.information(self, "Nothing to export", "There are no results to export.")
            return
        selected, _ = QFileDialog.getSaveFileName(
            self, title, default_name, "HTML (*.html)"
        )
        if not selected:
            return
        if not selected.lower().endswith(".html"):
            selected += ".html"
        try:
            device_insights.write_html_report(
                selected, presentation.rows_for_output(rows), self._device_summary
            )
            QMessageBox.information(self, "Export complete", f"HTML report saved to:\n{selected}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PreferencesWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
