from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSplitter,
    QVBoxLayout,
)

import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.services.store_locale as store_locale
import playstore_app_audit.services.summary as summary_service
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.change_overview as change_ui
import playstore_app_audit.ui.details_panel as details_ui
import playstore_app_audit.ui.json_export as json_export_ui
import playstore_app_audit.ui.menu_window as menu_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
import playstore_app_audit.ui.smart_queries as smart_queries_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.domain.models import AuditRunState
from playstore_app_audit.platform import runtime
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.ui.file_menu import (
    ResultExportActions,
    add_result_actions,
    populate_result_export_menu,
)


def _find_layout_containing(layout, target_widget):
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is target_widget:
            return layout
        if widget is not None and widget.layout() is not None:
            found = _find_layout_containing(widget.layout(), target_widget)
            if found is not None:
                return found
        child = item.layout()
        if child is not None:
            found = _find_layout_containing(child, target_widget)
            if found is not None:
                return found
    return None


def _clear_layout_keep_widgets(layout, keep: set[object]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if child is not None:
            _clear_layout_keep_widgets(child, keep)
        if widget is not None and widget not in keep:
            widget.deleteLater()


def _device_source_identity(summary: dict[str, Any]) -> str:
    manufacturer = str(summary.get("manufacturer") or "").strip()
    model = str(summary.get("model") or "").strip()
    name = " ".join(part for part in (manufacturer, model) if part)

    android_version = str(summary.get("android_version") or "").strip()
    android_api = str(summary.get("android_api") or "").strip()
    android = f"Android {android_version}" if android_version else ""
    if android_api:
        android = f"{android} (API {android_api})" if android else f"Android API {android_api}"

    return " • ".join(part for part in (name, android) if part)


class NumericAuditFilterProxy(preferences_ui.AuditFilterProxy):
    NUMERIC_SORT_COLUMNS = frozenset(
        {
            "age_days",
            "target_sdk",
            "min_sdk",
            "sensitive_permissions_count",
            "health_score",
        }
    )

    @staticmethod
    def _numeric_sort_value(value: object) -> float:
        if value is None:
            return -1.0
        text = str(value).strip()
        if not text:
            return -1.0
        try:
            return float(text)
        except (TypeError, ValueError):
            return -1.0

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if isinstance(model, table_ui.AuditTableModel) and 0 <= left.column() < len(model.columns):
            column = model.columns[left.column()]
            if column in self.NUMERIC_SORT_COLUMNS:
                left_row = model.row_dict(left.row())
                right_row = model.row_dict(right.row())
                return self._numeric_sort_value(left_row.get(column)) < self._numeric_sort_value(
                    right_row.get(column)
                )
        return super().lessThan(left, right)


class ResultsWindow(menu_ui.MenuWindow):
    def __init__(self) -> None:
        self._device_store_locale: store_locale.StoreLocale | None = None
        self._store_country_manual_override = False
        self._change_overview_dialog: change_ui.ChangeOverviewDialog | None = None
        self._details_panel_position = "right"
        self._details_panel_resolved_position: str | None = None
        self._source_operation_active = False
        super().__init__()
        self.country_edit.textEdited.connect(self._on_store_country_edited)
        self.country_edit.editingFinished.connect(self._on_store_country_editing_finished)
        self._apply_store_country_resolution(None)
        self.exclude_system_source_check.toggled.connect(self._persist_exclude_system_source)
        self._install_numeric_sort_proxy()
        self._setup_details_panel()
        self._setup_export_button_menu()
        self._rebuild_file_menu()
        self._update_summary()

    # ---------- Action availability ----------
    def _has_loaded_source(self) -> bool:
        if self.source_mode == "file":
            return bool(self.file_apps)
        if self.source_mode == "device":
            return bool(self.device_apps_all)
        return False

    def _operation_running(self) -> bool:
        return bool(
            self._source_operation_active
            or getattr(self, "_audit_active", False)
            or getattr(self, "_finalizing_session", None) is not None
        )

    @staticmethod
    def _set_export_actions_enabled(
        actions: ResultExportActions, *, all_results: bool, visible_results: bool
    ) -> None:
        for action in actions.all_results:
            action.setEnabled(all_results)
        for action in actions.visible_results:
            action.setEnabled(visible_results)
        actions.menu.menuAction().setEnabled(all_results or visible_results)

    def _sync_action_availability(self) -> None:
        if not hasattr(self, "run_button"):
            return

        running = self._operation_running()
        idle = not running
        source_available = self._has_loaded_source()
        inventory_available = self.source_mode == "device" and bool(self.device_apps_all)
        results_available = bool(self.current_rows)
        visible_results_available = results_available and self.proxy.rowCount() > 0
        device_results_available = self.source_mode == "device" and results_available
        device_summary_available = inventory_available and bool(
            getattr(self, "_device_summary", None)
        )
        inventory_changes_available = device_results_available and bool(
            getattr(self, "_last_inventory_changes", None)
        )
        problematic_available = any(
            device_metadata.is_problematic(row) for row in self.current_rows
        )

        if not getattr(self, "_audit_active", False):
            self.run_button.setEnabled(idle and source_available)
        self.export_button.setEnabled(idle and results_available)
        self.clear_button.setEnabled(idle and results_available)

        for name in ("file_choose_source_action", "file_scan_phone_action"):
            action = getattr(self, name, None)
            if action is not None:
                action.setEnabled(idle)
        if hasattr(self, "recent_menu"):
            self.recent_menu.menuAction().setEnabled(idle)
        recent_button = getattr(self, "recent_sources_button", None)
        if recent_button is not None:
            recent_button.setEnabled(idle)

        file_result_actions = getattr(self, "file_result_actions", None)
        if file_result_actions is not None:
            file_result_actions.run.setEnabled(idle and source_available)
            file_result_actions.clear.setEnabled(idle and results_available)
            self._set_export_actions_enabled(
                file_result_actions.exports,
                all_results=idle and results_available,
                visible_results=idle and visible_results_available,
            )
        button_exports = getattr(self, "button_result_exports", None)
        if button_exports is not None:
            self._set_export_actions_enabled(
                button_exports,
                all_results=idle and results_available,
                visible_results=idle and visible_results_available,
            )

        for name in ("file_phone_package_export_action", "scan_phone_package_export_action"):
            action = getattr(self, name, None)
            if action is not None:
                action.setEnabled(idle and inventory_available)
        scan_options_button = getattr(self, "scan_phone_options_button", None)
        if scan_options_button is not None:
            scan_options_button.setEnabled(idle and inventory_available)

        action_states = {
            "advanced_settings_action": idle,
            "force_full_refresh_action": idle and source_available,
            "recheck_problematic_action": idle and problematic_available,
            "device_summary_action": idle and device_summary_available,
            "save_device_snapshot_action": idle and device_results_available,
            "compare_device_snapshot_action": idle and device_results_available,
            "device_inventory_changes_action": idle and inventory_changes_available,
            "clear_audit_cache_action": idle,
            "clear_audit_history_action": idle,
        }
        for name, enabled in action_states.items():
            action = getattr(self, name, None)
            if action is not None:
                action.setEnabled(enabled)
        if hasattr(self, "snapshots_menu"):
            self.snapshots_menu.menuAction().setEnabled(idle and device_results_available)
        if hasattr(self, "data_maintenance_menu"):
            self.data_maintenance_menu.menuAction().setEnabled(idle)
        if hasattr(self, "audit_profiles_menu"):
            self.audit_profiles_menu.menuAction().setEnabled(idle)
        if hasattr(self, "details_panel"):
            self.details_panel.review_changes_button.setEnabled(idle and results_available)
        smart_queries_ui.sync_smart_query_action_availability(self)

    def _set_busy(self, busy: bool) -> None:
        self._source_operation_active = busy
        super()._set_busy(busy)
        self._sync_action_availability()

    def _set_audit_source_controls_enabled(self, enabled: bool) -> None:
        super()._set_audit_source_controls_enabled(enabled)
        self._sync_action_availability()

    def _start_audit(self) -> None:
        super()._start_audit()
        self._sync_action_availability()

    def _persist_exclude_system_source(self, checked: bool) -> None:
        self.user_settings["exclude_system_source"] = bool(checked)
        self.user_settings = state.save_settings(self.user_settings)

    def _install_numeric_sort_proxy(self) -> None:
        old_proxy = self.proxy
        proxy = NumericAuditFilterProxy()
        proxy.setSourceModel(self.model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_status_filters(self._status_filters)
        proxy.set_smart_query(self._active_smart_query)
        self.proxy = proxy
        self.table.setModel(proxy)
        old_proxy.deleteLater()
        self._apply_column_visibility(reset_order=False)

    # ---------- Selected-row details / changes ----------
    def _setup_details_panel(self) -> None:
        central = self.centralWidget()
        root = central.layout() if central is not None else None
        if root is None:
            return
        table_layout = _find_layout_containing(root, self.table)
        if table_layout is None:
            return
        table_index = table_layout.indexOf(self.table)
        if table_index < 0:
            return

        settings = state.load_settings()
        position = details_ui.normalise_details_panel_position(
            settings.get("details_panel_position", "right")
        )
        self.details_control = details_ui.DetailsPanelControl(position, self)
        toolbar = _find_layout_containing(root, self.search_edit)
        if toolbar is not None:
            toolbar.addWidget(self.details_control)

        self.details_panel = details_ui.AppDetailsPanel(self)
        self.details_splitter = QSplitter(self)
        self.details_splitter.setChildrenCollapsible(False)
        table_layout.removeWidget(self.table)
        self.details_splitter.addWidget(self.table)
        self.details_splitter.addWidget(self.details_panel)
        table_layout.insertWidget(table_index, self.details_splitter, 1)
        self.details_splitter.setStretchFactor(0, 4)
        self.details_splitter.setStretchFactor(1, 1)
        self._set_details_panel_position(position, persist=False)

        self.details_control.position_changed.connect(self._set_details_panel_position)
        self.details_panel.review_changes_requested.connect(self._show_change_overview)
        self.details_panel_menu = self.details_control.mode_menu
        if hasattr(self, "view_menu"):
            before_action = getattr(self, "display_settings_action", None)
            if before_action is None:
                before_action = next(
                    (action for action in self.view_menu.actions() if action.isSeparator()),
                    None,
                )
            if before_action is None:
                self.view_menu.addMenu(self.details_panel_menu)
            else:
                self.view_menu.insertMenu(before_action, self.details_panel_menu)
        selection_model = self.table.selectionModel()
        if selection_model is not None:
            selection_model.currentRowChanged.connect(self._on_details_current_row_changed)
        self.model.dataChanged.connect(self._on_details_model_data_changed)
        self.model.modelReset.connect(self._on_details_model_reset)

    def _details_available_width(self) -> int:
        central = self.centralWidget()
        if central is not None and central.width() > 0:
            return central.width()
        return self.width()

    def _set_details_panel_position(self, position: str, persist: bool = True) -> None:
        position = details_ui.normalise_details_panel_position(position)
        if not hasattr(self, "details_splitter"):
            return

        self._details_panel_position = position
        if hasattr(self, "details_control"):
            self.details_control.set_position(position, emit=False)

        if position == "hidden":
            self._details_panel_resolved_position = "hidden"
            self.details_panel.hide()
            self.details_splitter.setSizes([1, 0])
            if persist:
                settings = state.load_settings()
                settings["details_panel_position"] = position
                self.user_settings = state.save_settings(settings)
            return

        self.details_panel.show()

        resolved = details_ui.resolve_details_panel_position(
            position,
            self._details_available_width(),
            self._details_panel_resolved_position or "",
        )
        previous_resolved = self._details_panel_resolved_position
        self._details_panel_resolved_position = resolved

        orientation = (
            Qt.Orientation.Vertical if resolved == "below" else Qt.Orientation.Horizontal
        )
        if self.details_splitter.orientation() != orientation:
            self.details_splitter.setOrientation(orientation)
        if previous_resolved != resolved or previous_resolved is None:
            self.details_splitter.setSizes([560, 260] if resolved == "below" else [1080, 360])

        if persist:
            settings = state.load_settings()
            settings["details_panel_position"] = position
            self.user_settings = state.save_settings(settings)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._details_panel_position == "auto" and hasattr(self, "details_splitter"):
            self._set_details_panel_position("auto", persist=False)

    def _details_row_from_index(self, index: QModelIndex) -> dict[str, Any] | None:
        if not index.isValid():
            return None
        row = index.data(Qt.ItemDataRole.UserRole)
        return dict(row) if isinstance(row, dict) else None

    def _details_icon_for_row(self, row: dict[str, Any]) -> QIcon | None:
        if isinstance(self.model, table_ui.AuditTableModel):
            return self.model.icon_for_row(row)
        return None

    def _on_details_current_row_changed(
        self, current: QModelIndex, _previous: QModelIndex
    ) -> None:
        if not hasattr(self, "details_panel"):
            return
        row = self._details_row_from_index(current)
        if row is None:
            self.details_panel.clear()
            return
        self.details_panel.set_row(row, self._details_icon_for_row(row))

    def _on_details_model_data_changed(self, *_args) -> None:
        if not hasattr(self, "details_panel"):
            return
        index = self.table.currentIndex()
        row = self._details_row_from_index(index)
        if row is not None:
            self.details_panel.set_row(row, self._details_icon_for_row(row))

    def _on_details_model_reset(self) -> None:
        if not hasattr(self, "details_panel"):
            return
        self.details_panel.clear()
        if self.proxy.rowCount() > 0:
            self.table.selectRow(0)
        self._sync_action_availability()

    def _current_change_groups(self) -> list[dict[str, Any]]:
        return change_service.build_change_groups(
            list(self.current_rows), getattr(self, "_last_inventory_changes", None)
        )

    def _show_change_overview(self) -> None:
        if self._change_overview_dialog is None:
            dialog = change_ui.ChangeOverviewDialog(self)
            dialog.package_selected.connect(self._select_package_from_change_overview)
            self._change_overview_dialog = dialog
        self._change_overview_dialog.set_groups(self._current_change_groups())
        self._change_overview_dialog.show()
        self._change_overview_dialog.raise_()
        self._change_overview_dialog.activateWindow()

    def _select_package_from_change_overview(self, package_name: str) -> None:
        package_name = str(package_name or "").strip()
        if not package_name:
            return
        for proxy_row in range(self.proxy.rowCount()):
            index = self.proxy.index(proxy_row, 0)
            row = index.data(Qt.ItemDataRole.UserRole)
            if isinstance(row, dict) and str(row.get("package_name") or "") == package_name:
                self.table.selectRow(proxy_row)
                self.table.scrollTo(index)
                return
        if any(str(row.get("package_name") or "") == package_name for row in self.current_rows):
            self.status_label.setText(
                f"{package_name} is hidden by the current table filters. Clear filters to focus it."
            )
        else:
            self.status_label.setText(
                f"{package_name} is no longer present in the current device/results inventory."
            )

    def _on_controlled_done(self, payload: object) -> None:
        super()._on_controlled_done(payload)
        self._sync_post_audit_views()

    def _sync_post_audit_views(self) -> None:
        had_previous_inventory = bool(
            self.source_mode == "device"
            and isinstance(getattr(self, "_last_inventory_changes", None), dict)
            and self._last_inventory_changes.get("had_previous")
        )
        for row in self.current_rows:
            row[change_service.DEVICE_HISTORY_FLAG] = had_previous_inventory
        self._on_details_model_data_changed()
        if self._change_overview_dialog is not None:
            self._change_overview_dialog.set_groups(self._current_change_groups())
        self._sync_action_availability()

    # ---------- Source UX ----------
    def _choice_row(self, text: str, button) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        row.addWidget(label)
        row.addStretch(1)
        button.setFixedWidth(132)
        row.addWidget(button)
        return row

    def _store_country_resolution(
        self, android_locale: store_locale.StoreLocale | None
    ) -> store_locale.StoreCountryResolution:
        manual = self.country_edit.text() if self._store_country_manual_override else None
        return store_locale.resolve_store_country(
            manual_country=manual,
            host_country=runtime.detect_host_store_country(),
            android_locale=android_locale,
        )

    def _apply_store_country_resolution(
        self, android_locale: store_locale.StoreLocale | None
    ) -> store_locale.StoreCountryResolution:
        resolved = self._store_country_resolution(android_locale)
        self.country_edit.setText(resolved.country)

        if resolved.source == "manual_override":
            tooltip = (
                f"Manual Store country override: {resolved.country.upper()}. "
                "It is preserved across file and phone sources."
            )
        elif resolved.source == "host_region":
            tooltip = f"Store country from this computer's region: {resolved.country.upper()}."
        elif resolved.source == "android_locale_fallback":
            locale_text = android_locale.locale if android_locale is not None else resolved.country.upper()
            tooltip = (
                f"Computer region unavailable; Store country falls back to Android locale region "
                f"{resolved.country.upper()} from {locale_text}. This is not the Google Play account country."
            )
        else:
            tooltip = "Computer and Android regions unavailable; Store country falls back to US."

        if android_locale is not None and android_locale.language:
            tooltip += f" Auto Store language uses Android system language {android_locale.language}."
        self.country_edit.setToolTip(tooltip)
        return resolved

    def _on_store_country_edited(self, text: str) -> None:
        value = str(text or "").strip()
        self._store_country_manual_override = len(value) == 2 and value.isalpha()
        if self._store_country_manual_override:
            self.country_edit.setToolTip(
                f"Manual Store country override: {value.upper()}. It will be preserved across sources."
            )

    def _on_store_country_editing_finished(self) -> None:
        android_locale = self._device_store_locale if self.source_mode == "device" else None
        self._apply_store_country_resolution(android_locale)

    def _rebuild_source_area(self) -> None:
        source_card = self.path_edit.parentWidget()
        source_layout = source_card.layout() if source_card is not None else None
        if source_layout is None:
            return
        source_line = _find_layout_containing(source_layout, self.path_edit)
        if source_line is None:
            return

        keep = {
            self.path_edit,
            self.choose_button,
            self.scan_button,
            self.country_edit,
            self.exclude_system_source_check,
        }
        _clear_layout_keep_widgets(source_line, keep)
        self.path_edit.hide()

        self.choose_button.setText("Choose File")
        self.scan_button.setText("Scan Phone")

        choices = QVBoxLayout()
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(5)
        choices.addLayout(self._choice_row("Choose a CSV / TSV / TXT file", self.choose_button))

        or_label = QLabel("or")
        or_label.setObjectName("Muted")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        choices.addWidget(or_label)

        choices.addLayout(self._choice_row("Scan your Android phone with ADB", self.scan_button))
        source_line.addLayout(choices, 1)

        options = QHBoxLayout()
        options.setContentsMargins(0, 2, 0, 0)
        options.setSpacing(8)
        country_label = QLabel("Store Country")
        country_label.setToolTip(
            "Google Play market: manual override first, otherwise computer region; "
            "Android locale region is only a late phone-scan fallback."
        )
        options.addWidget(country_label)
        self.country_edit.setFixedWidth(58)
        options.addWidget(self.country_edit)
        options.addSpacing(8)
        options.addWidget(self.exclude_system_source_check)
        options.addStretch(1)

        # Keep the compact status/source label as the last line in the card.
        source_layout.insertLayout(max(0, source_layout.count() - 1), options)

    def _load_input_file(self, path: str) -> None:
        self._device_store_locale = None
        store_locale.set_active_device_store_locale(None)
        super()._load_input_file(path)
        self._apply_store_country_resolution(None)
        if self.source_mode == "file":
            text = self.source_label.text()
            if text.startswith("File selected: "):
                text = text[len("File selected: ") :]
            self.source_label.setText(f"{Path(path).name}  •  {text}")
            self.source_label.setToolTip(path)
        self._sync_action_availability()

    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        super()._on_adb_scan_done(apps, system_packages)
        detected: store_locale.StoreLocale | None = None
        adb = self._find_adb()
        if adb:
            detected = store_locale.detect_android_store_locale(adb)
        self._device_store_locale = detected
        store_locale.set_active_device_store_locale(detected)
        self._apply_store_country_resolution(detected)
        self._enrich_device_source_label()
        self._sync_action_availability()

    def _enrich_device_source_label(self) -> None:
        summary = getattr(self, "_device_summary", {})
        if not isinstance(summary, dict):
            summary = {}
        identity = _device_source_identity(summary)

        if identity:
            current = self.source_label.text().strip()
            details = current.removeprefix("Phone scan:").strip()
            self.source_label.setText(
                f"Phone scan: {identity} • {details}" if details else f"Phone scan: {identity}"
            )

        tooltip: list[str] = []
        if identity:
            tooltip.append(f"Device: {identity}")
        patch = str(summary.get("security_patch") or "").strip()
        if patch:
            tooltip.append(f"Security patch: {patch}")
        serial = str(summary.get("serial_masked") or "").strip()
        if serial:
            tooltip.append(f"Serial: {serial}")
        locale = self._device_store_locale
        if locale is not None:
            tooltip.append(f"Android system locale: {locale.locale}")
            tooltip.append(f"Auto Store language: {locale.language}")
            if locale.country:
                tooltip.append(
                    f"Android locale region: {locale.country.upper()} "
                    "(Store-country fallback only if the computer region is unavailable)"
                )
        if tooltip:
            self.source_label.setToolTip("\n".join(tooltip))

    def _sync_phone_package_export_actions(self) -> None:
        self._sync_action_availability()

    # ---------- Export UX ----------
    def _setup_export_button_menu(self) -> None:
        try:
            self.export_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        menu = QMenu(self.export_button)
        self.button_result_exports = populate_result_export_menu(
            menu,
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
        self.export_button.setText("Export Results")
        self.export_button.setMenu(menu)
        self._export_results_menu = menu

    def _rebuild_file_menu(self) -> None:
        if not hasattr(self, "file_menu"):
            return
        self.file_menu.clear()
        self.file_choose_source_action = self.file_menu.addAction(
            "Choose App List…", self._choose_input
        )
        self.recent_menu = self.file_menu.addMenu("Recent Sources")
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
        self._sync_action_availability()

    def _clear_results(self) -> None:
        if getattr(self, "_audit_state", AuditRunState.IDLE) is not AuditRunState.IDLE:
            return
        super()._clear_results()
        if hasattr(self, "details_panel"):
            self.details_panel.clear()
        if self._change_overview_dialog is not None:
            self._change_overview_dialog.set_groups([])
        self._sync_action_availability()

    # ---------- Concise summary ----------
    def _update_summary(self) -> None:
        super()._update_summary()
        if not hasattr(self, "summary_label"):
            return
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        summary = summary_service.concise_summary(
            list(self.current_rows), visible, getattr(self, "_last_inventory_changes", None)
        )
        self.summary_label.setText(self._summary_with_smart_query(summary))
        self._sync_action_availability()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = ResultsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
