from __future__ import annotations

import sys
from typing import Any

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, QSize, QSortFilterProxyModel, Qt
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
    QGroupBox,
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
import playstore_app_audit.ui.table_layout as table_layout
import playstore_app_audit.ui.table_window as table_ui
from app_icon import ensure_runtime_icon

ADVANCED_CUSTOM_COLUMNS = frozenset(
    {
        "play_status",
        "updated_source",
        "play_http_status",
        "is_system",
        "installed_version_code",
        "installer_package",
        "target_sdk",
        "min_sdk",
        "sensitive_permissions_count",
        "sensitive_permissions",
        "local_apk_version_code",
        "local_apk_sha256",
    }
)

CUSTOMIZE_VIEW_MIN_SIZE = QSize(620, 500)
CUSTOMIZE_VIEW_NORMAL_WIDTH = 780
CUSTOMIZE_VIEW_SCREEN_MARGIN = 48
CONTEXTUAL_HISTORY_COLUMNS = frozenset({"change", "device_change"})


def customize_view_dialog_sizes(
    content_size: QSize,
    fixed_overhead: QSize,
    available_size: QSize,
) -> tuple[QSize, QSize]:
    """Return screen-bounded minimum and initial sizes for Customize View."""

    usable_width = max(1, available_size.width() - CUSTOMIZE_VIEW_SCREEN_MARGIN)
    usable_height = max(1, available_size.height() - CUSTOMIZE_VIEW_SCREEN_MARGIN)
    minimum = QSize(
        min(CUSTOMIZE_VIEW_MIN_SIZE.width(), usable_width),
        min(CUSTOMIZE_VIEW_MIN_SIZE.height(), usable_height),
    )
    desired_width = max(
        CUSTOMIZE_VIEW_NORMAL_WIDTH,
        content_size.width() + fixed_overhead.width(),
    )
    desired_height = max(
        CUSTOMIZE_VIEW_MIN_SIZE.height(),
        content_size.height() + fixed_overhead.height(),
    )
    initial = QSize(
        max(minimum.width(), min(desired_width, usable_width)),
        max(minimum.height(), min(desired_height, usable_height)),
    )
    return minimum, initial


def custom_column_groups() -> tuple[tuple[str, ...], tuple[str, ...]]:
    choices = tuple(
        column
        for column in insights_ui.V9_MODEL_COLUMNS
        if column
        not in {"criticality", "package_name", *CONTEXTUAL_HISTORY_COLUMNS}
    )
    common = tuple(column for column in choices if column not in ADVANCED_CUSTOM_COLUMNS)
    advanced = tuple(column for column in choices if column in ADVANCED_CUSTOM_COLUMNS)
    return common, advanced


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
        compare = state.store_history_enabled(settings)
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
        tools.addAction("Run with Fresh Store Results", self._force_full_refresh)
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
                action.setEnabled(True)
        group = getattr(self, "_view_action_group", None)
        if isinstance(group, QActionGroup):
            for action in group.actions():
                if action.text() == "Custom":
                    action.setEnabled(True)

    def _show_display_settings(self) -> None:
        self.user_settings = state.load_settings()
        dialog = QDialog(self)
        dialog.setObjectName("DisplaySettingsDialog")
        dialog.setWindowTitle("Customize View")
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
        custom_note = self._settings_note(
            "Store Status and Package Name are always included. Click Save to apply changes. "
            "Changing the column selection activates View > Column Preset > Custom."
        )
        custom_note.setObjectName("CustomColumnsNote")
        root.addWidget(custom_note)
        history_note = self._settings_note(
            "History columns are shown automatically when enabled in Tools > Changes & "
            "History and applicable to the current source."
        )
        history_note.setObjectName("CustomHistoryColumnsNote")
        root.addWidget(history_note)

        scroll = QScrollArea()
        scroll.setObjectName("CustomColumnsScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        columns_host = QWidget()
        groups_layout = QHBoxLayout(columns_host)
        groups_layout.setContentsMargins(0, 4, 0, 4)
        groups_layout.setSpacing(12)
        common_group = QGroupBox("Common")
        common_group.setObjectName("CustomColumnsCommonGroup")
        common_group.setToolTip("Human-readable fields for ordinary result-table use.")
        common_layout = QVBoxLayout(common_group)
        advanced_group = QGroupBox("Advanced / Technical")
        advanced_group.setObjectName("CustomColumnsAdvancedGroup")
        advanced_group.setToolTip(
            "Raw Store evidence, build identifiers, SDK values and specialist fields."
        )
        advanced_layout = QVBoxLayout(advanced_group)
        groups_layout.addWidget(common_group, 1)
        groups_layout.addWidget(advanced_group, 1)
        stored_custom = self._normalise_custom_columns(
            self.user_settings.get("custom_view_columns")
        ) or list(presentation.DEFAULT_CUSTOM_VIEW_COLUMNS)
        ordinary_stored_custom = [
            column for column in stored_custom if column not in CONTEXTUAL_HISTORY_COLUMNS
        ]
        current_preset = str(self.user_settings.get("view_preset") or "Basic")
        initial_columns = (
            list(ordinary_stored_custom)
            if current_preset == "Custom"
            else [
                column
                for column in self._visible_column_order()
                if column not in CONTEXTUAL_HISTORY_COLUMNS
            ]
        )
        configured = set(initial_columns)
        custom_checks: dict[str, QCheckBox] = {}
        common_columns, advanced_columns = custom_column_groups()
        common_set = set(common_columns)
        for key in (*common_columns, *advanced_columns):
            label = base_ui.COLUMN_LABELS.get(key, key)
            check = QCheckBox(label)
            check.setObjectName(f"CustomColumnCheck_{key}")
            check.setChecked(key in configured)
            custom_checks[key] = check
            (common_layout if key in common_set else advanced_layout).addWidget(check)
        common_layout.addStretch(1)
        advanced_layout.addStretch(1)
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

        dialog.ensurePolished()
        columns_host.ensurePolished()
        groups_layout.activate()
        root.activate()
        layout_hint = root.sizeHint()
        scroll_hint = scroll.sizeHint()
        fixed_overhead = QSize(
            max(0, layout_hint.width() - scroll_hint.width()),
            max(0, layout_hint.height() - scroll_hint.height()),
        )
        minimum_size, initial_size = customize_view_dialog_sizes(
            columns_host.sizeHint(),
            fixed_overhead,
            dialog.screen().availableGeometry().size(),
        )
        dialog.setMinimumSize(minimum_size)
        dialog.resize(initial_size)

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
        custom_columns = self._normalise_custom_columns(
            list(dict.fromkeys(custom_columns))
        ) or ["criticality", "package_name"]
        columns_changed = set(custom_columns) != configured
        custom_exists = self._has_custom_table_layout(self.user_settings)
        legacy_history_columns = bool(
            set(stored_custom).intersection(CONTEXTUAL_HISTORY_COLUMNS)
        )
        save_custom = columns_changed or not custom_exists or legacy_history_columns
        updates: dict[str, object] = {
            "show_app_icons": show_icons.isChecked(),
            "date_format": date_format.currentText(),
        }
        if save_custom:
            _visible, live_order, live_widths, encoded = self._current_table_layout()
            stored_widths = self._normalise_custom_widths(
                self.user_settings.get("custom_view_widths")
            )
            preserved_widths = {
                column: (
                    live_widths[column]
                    if live_widths.get(column, 0) >= 20
                    else stored_widths.get(
                        column,
                        table_layout.default_column_width(self.table, column),
                    )
                )
                for column in self.model.columns
            }
            updates.update(
                {
                    "custom_view_columns": custom_columns,
                    "custom_view_exists": True,
                    "custom_view_order": live_order,
                    "custom_view_widths": preserved_widths,
                    "qt_header_state": encoded,
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
        if save_custom:
            self._sync_view_preset_action("Custom")
            self._sync_custom_preset_availability()
            self._apply_column_visibility(reset_order=False)
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
        ttl.setValue(
            int(self.user_settings.get("cache_ttl_hours", state.DEFAULT_CACHE_TTL_HOURS))
        )
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
            "AuditSettingsPage",
            "Audit",
            "Configure optional audit enrichment and result scoring.",
        )
        permissions = QCheckBox("Audit sensitive requested permissions (advanced)")
        permissions.setObjectName("PermissionsAuditCheck")
        permissions.setChecked(bool(self.user_settings.get("permissions_audit_enabled", False)))
        health = QCheckBox("Enable Maintenance Score")
        health.setObjectName("HealthScoreCheck")
        health.setChecked(bool(self.user_settings.get("health_score_enabled", False)))
        audit_layout.addWidget(permissions)
        p_note = self._settings_note(
            "Permission audit checks a curated list of sensitive permissions declared/requested by each package (camera, microphone, location, contacts, SMS, phone, media, all-files access, overlays, etc.). It does not decide whether a permission is granted, justified or malicious. The same package dump is already collected for device metadata, so enabling this mainly adds parsing rather than extra per-app ADB calls."
        )
        audit_layout.addWidget(p_note)
        audit_layout.addWidget(health)
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
            ttl.setValue(state.DEFAULT_CACHE_TTL_HOURS)
            collect.setChecked(True)
            full_scan.setChecked(False)
            permissions.setChecked(False)
            health.setChecked(False)
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
                "health_score_enabled": health.isChecked(),
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
