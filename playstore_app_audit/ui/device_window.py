from __future__ import annotations

import html
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit.ui import schema

# Stable device-layer schema aliases. The canonical definitions live in ui.schema.
V8_EXTRA_COLUMNS = schema.DEVICE_EXTRA_COLUMNS
V8_MODEL_COLUMNS = schema.DEVICE_MODEL_COLUMNS


class DeviceWindow(compact_ui.CompactWindow):
    """Qt6 v8: expert fallbacks, rechecks, details and ADB device metadata."""

    def __init__(self) -> None:
        self._force_refresh_next = False
        self._apps_override: list[dict[str, str]] | None = None
        self._merge_base_rows: list[dict[str, Any]] | None = None
        self._subset_label = ""
        self._pending_device_metadata: dict[str, dict[str, str]] = {}
        super().__init__()
        self._build_menu_v8()
        self._apply_column_visibility(reset_order=False)
        self._update_summary()

    # ---------- Behaviour hooks ----------
    def _load_fresh_cache(
        self,
        apps: list[dict[str, str]],
        country: str,
        language: str,
        ttl_hours: int,
    ) -> dict[str, dict[str, object]]:
        if self._force_refresh_next:
            return {}
        return super()._load_fresh_cache(apps, country, language, ttl_hours)

    def _collect_device_metadata(self, adb: str, packages: list[str], cancel_event):
        return device_metadata.collect_device_metadata(adb, packages, cancel_event)

    def _enrich_rows_with_device_metadata(
        self, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
    ) -> None:
        device_metadata.enrich_rows_with_device_metadata(rows, metadata)

    # ---------- Menus ----------
    def _build_menu_v8(self) -> None:
        menu = self.menuBar()
        menu.clear()

        file_menu = menu.addMenu("File")
        choose = QAction("Choose app list…", self)
        choose.triggered.connect(self._choose_input)
        file_menu.addAction(choose)
        scan = QAction("Scan phone with ADB", self)
        scan.triggered.connect(self._scan_phone)
        file_menu.addAction(scan)
        file_menu.addSeparator()
        export_all = QAction("Export all results…", self)
        export_all.triggered.connect(self._export_results)
        file_menu.addAction(export_all)
        export_visible = QAction("Export visible results…", self)
        export_visible.triggered.connect(self._export_visible_results)
        file_menu.addAction(export_visible)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools = menu.addMenu("Tools")
        advanced = QAction("Advanced settings…", self)
        advanced.triggered.connect(self._show_advanced_settings)
        tools.addAction(advanced)
        tools.addSeparator()
        force_refresh = QAction("Force full refresh (ignore cache)", self)
        force_refresh.triggered.connect(self._force_full_refresh)
        tools.addAction(force_refresh)
        retry_problematic = QAction("Recheck Removed / Anomaly / Other", self)
        retry_problematic.triggered.connect(self._recheck_problematic)
        tools.addAction(retry_problematic)
        tools.addSeparator()
        clear_cache_action = QAction("Clear audit cache", self)
        clear_cache_action.triggered.connect(self._clear_audit_cache)
        tools.addAction(clear_cache_action)
        clear_history_action = QAction("Clear previous-audit history", self)
        clear_history_action.triggered.connect(self._clear_audit_history)
        tools.addAction(clear_history_action)
        reset_layout = QAction("Reset table layout", self)
        reset_layout.triggered.connect(self._reset_table_layout)
        tools.addAction(reset_layout)

        help_menu = menu.addMenu("Help")
        about = QAction("About Play Store App Audit", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _clear_audit_history(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear previous-audit history?",
            "Delete the local comparison baseline? The cache, settings and current results will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            device_metadata.clear_history()
            self.status_label.setText(
                "Previous-audit history cleared; the next comparison run will create a new baseline"
            )

    # ---------- Advanced settings ----------
    def _show_advanced_settings(self) -> None:
        self.user_settings = state.load_settings()
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced settings")
        dialog.setMinimumWidth(620)
        root = QVBoxLayout(dialog)

        warning = QLabel(
            "⚠ Expert settings. These options can change network load, Store interpretation and the technical data shown. "
            "Change them only when genuinely necessary. Reset to defaults if you are unsure."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background:#FFF6E5; color:#6B4A16; border:1px solid #E9C77D; padding:10px; border-radius:6px;"
        )
        root.addWidget(warning)

        store_group = QGroupBox("Store, fallback markets and cache")
        store_form = QFormLayout(store_group)
        language = QLineEdit(str(self.user_settings.get("store_language") or "en"))
        language.setMaxLength(8)
        store_form.addRow("Store language", language)

        fallback = QLineEdit(
            str(self.user_settings.get("fallback_countries") or device_metadata.DEFAULT_FALLBACK_COUNTRIES)
        )
        fallback.setPlaceholderText("us, gb, de, fr, it, ch, es, ca, au, jp")
        fallback.setToolTip(
            "Used only when the selected Store country cannot provide a conclusive result. "
            "Comma/space separated 2-letter country codes. The main Store country is skipped automatically."
        )
        store_form.addRow("Fallback Store countries", fallback)

        fallback_note = QLabel(
            "No fallback countries are shown in the normal UI. This list is used only behind the scenes when the selected Store country is unavailable or inconclusive."
        )
        fallback_note.setWordWrap(True)
        fallback_note.setStyleSheet("color:#6F7C87;")
        store_form.addRow("", fallback_note)

        cache_enabled = QCheckBox("Use intelligent cache")
        cache_enabled.setChecked(bool(self.user_settings.get("cache_enabled", True)))
        store_form.addRow("", cache_enabled)
        ttl = QSpinBox()
        ttl.setRange(1, 720)
        ttl.setValue(int(self.user_settings.get("cache_ttl_hours", 72)))
        ttl.setSuffix(" hours")
        store_form.addRow("Healthy-result cache TTL", ttl)
        cache_note = QLabel(
            "Default: 72 hours. Only healthy available listings with a valid update date are reused. Removed, anomaly and error states always run live."
        )
        cache_note.setWordWrap(True)
        cache_note.setStyleSheet("color:#6F7C87;")
        store_form.addRow("", cache_note)
        root.addWidget(store_group)

        device_group = QGroupBox("Connected Android device")
        device_layout = QVBoxLayout(device_group)
        collect_device = QCheckBox("Collect installed version and installer source during ADB audits")
        collect_device.setChecked(bool(self.user_settings.get("collect_device_metadata", True)))
        device_layout.addWidget(collect_device)
        device_note = QLabel(
            "Enabled by default. This reads package metadata locally through ADB. Version comparison reports Match / Different / Device-specific / Unknown; it does not assume that a different version is necessarily outdated."
        )
        device_note.setWordWrap(True)
        device_note.setStyleSheet("color:#6F7C87;")
        device_layout.addWidget(device_note)
        root.addWidget(device_group)

        history_group = QGroupBox("Audit history")
        history_layout = QVBoxLayout(history_group)
        compare = QCheckBox("Compare with previous audit")
        compare.setChecked(bool(self.user_settings.get("compare_previous", False)))
        history_layout.addWidget(compare)
        history_note = QLabel(
            "Off by default. The first completed audit creates a local baseline; later audits can show New / Same / Better / Worse."
        )
        history_note.setWordWrap(True)
        history_note.setStyleSheet("color:#6F7C87;")
        history_layout.addWidget(history_note)
        root.addWidget(history_group)

        columns_group = QGroupBox("Technical columns")
        columns_layout = QVBoxLayout(columns_group)
        technical_checks: dict[str, QCheckBox] = {}
        selected = set(self.user_settings.get("technical_columns", []))
        for key, label in state.TECHNICAL_COLUMNS.items():
            check = QCheckBox(label)
            check.setChecked(key in selected)
            technical_checks[key] = check
            columns_layout.addWidget(check)
        root.addWidget(columns_group)

        button_row = QHBoxLayout()
        reset_button = QPushButton("Reset to defaults")
        button_row.addWidget(reset_button)
        button_row.addStretch(1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        button_row.addWidget(buttons)
        root.addLayout(button_row)

        def reset_controls() -> None:
            language.setText("en")
            fallback.setText(device_metadata.DEFAULT_FALLBACK_COUNTRIES)
            cache_enabled.setChecked(True)
            ttl.setValue(72)
            collect_device.setChecked(True)
            compare.setChecked(False)
            for check in technical_checks.values():
                check.setChecked(False)

        reset_button.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        fallback_text, invalid = device_metadata.normalise_country_string(fallback.text())
        previous_fallback = str(self.user_settings.get("fallback_countries") or "")
        self.user_settings.update(
            {
                "store_language": (language.text().strip() or "en").lower(),
                "fallback_countries": fallback_text,
                "cache_enabled": cache_enabled.isChecked(),
                "cache_ttl_hours": ttl.value(),
                "collect_device_metadata": collect_device.isChecked(),
                "compare_previous": compare.isChecked(),
                "technical_columns": [key for key, check in technical_checks.items() if check.isChecked()],
            }
        )
        self.user_settings = state.save_settings(self.user_settings)
        if previous_fallback.strip().lower() != fallback_text.strip().lower():
            state.clear_cache()
        self._apply_column_visibility(reset_order=False)
        message = "Advanced settings saved; audit-related changes apply from the next run"
        if invalid:
            message += " • ignored invalid country entries: " + ", ".join(invalid)
        self.status_label.setText(message)

    # ---------- Dashboard ----------
    def _update_summary(self) -> None:
        # Keep the standard chip counters/filter state, then replace only the
        # compact summary text with the richer dashboard line.
        base_ui.BaseWindow._update_summary(self)
        if not self.current_rows:
            return
        rows = self._rows_before_criticality_filter()
        self.summary_label.setText(device_metadata.dashboard_summary(rows, self.proxy.rowCount()))

    # ---------- Details / context menu ----------
    def _show_details(self, row: dict[str, Any]) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("App details")
        dialog.setMinimumWidth(680)
        root = QVBoxLayout(dialog)
        title = QLabel(
            f"<b>{html.escape(str(row.get('play_title') or row.get('package_name') or 'App'))}</b>"
        )
        root.addWidget(title)
        form = QFormLayout()
        fields = [
            ("Status", "criticality"),
            ("Change", "change"),
            ("Package Name", "package_name"),
            ("Play Store Title", "play_title"),
            ("Last update", "play_last_update"),
            ("Age (days)", "age_days"),
            ("Play Store version", "play_version"),
            ("Installed version", "installed_version"),
            ("Installed vs Store", "version_comparison"),
            ("Installer source", "installer_source"),
            ("Play status", "play_status"),
            ("Update source", "updated_source"),
            ("HTTP status", "play_http_status"),
            ("System app", "is_system"),
            ("Notes", "notes"),
        ]
        for label_text, key in fields:
            value = str(row.get(key, "") or "")
            if not value and key not in {"notes", "change"}:
                continue
            label = QLabel(html.escape(value))
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(label_text, label)
        root.addLayout(form)

        buttons_row = QHBoxLayout()
        open_store = QPushButton("Open in Google Play")
        open_store.setEnabled(bool(row.get("store_url")))
        open_store.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(str(row.get("store_url") or ""))))
        buttons_row.addWidget(open_store)
        buttons_row.addStretch(1)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        buttons_row.addWidget(close)
        root.addLayout(buttons_row)
        dialog.exec()

    def _show_row_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        row = self._row_from_proxy_index(index)
        if not row:
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        details = menu.addAction("App details…")
        force_recheck = menu.addAction("Force recheck this app")
        open_store = menu.addAction("Open in Google Play")
        menu.addSeparator()
        copy_package = menu.addAction("Copy package name")
        copy_title = menu.addAction("Copy Play Store title")
        copy_url = menu.addAction("Copy Store URL")
        copy_row = menu.addAction("Copy visible row")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is details:
            self._show_details(row)
        elif chosen is force_recheck:
            self._start_subset_refresh([str(row.get("package_name") or "")], "App recheck")
        elif chosen is open_store:
            url = str(row.get("store_url") or "")
            if url:
                QDesktopServices.openUrl(QUrl(url))
        elif chosen is copy_package:
            QApplication.clipboard().setText(str(row.get("package_name") or ""))
        elif chosen is copy_title:
            QApplication.clipboard().setText(str(row.get("play_title") or ""))
        elif chosen is copy_url:
            QApplication.clipboard().setText(str(row.get("store_url") or ""))
        elif chosen is copy_row:
            header = self.table.horizontalHeader()
            visible_columns = [
                (header.visualIndex(i), V8_MODEL_COLUMNS[i])
                for i in range(len(V8_MODEL_COLUMNS))
                if not self.table.isColumnHidden(i)
            ]
            visible_columns.sort()
            QApplication.clipboard().setText(
                "\t".join(str(row.get(column, "") or "") for _, column in visible_columns)
            )

    # ---------- Recheck / force refresh ----------
    def _force_full_refresh(self) -> None:
        if self._audit_active:
            QMessageBox.information(
                self, "Audit running", "Pause/resume or wait for the current audit to finish first."
            )
            return
        self._force_refresh_next = True
        self._merge_base_rows = None
        self._subset_label = "Full refresh"
        self._start_audit()

    def _recheck_problematic(self) -> None:
        packages = [
            str(row.get("package_name") or "")
            for row in self.current_rows
            if device_metadata.is_problematic(row)
        ]
        if not packages:
            QMessageBox.information(
                self,
                "No problematic apps",
                "There are no Removed, Store anomaly or Other results to recheck.",
            )
            return
        self._start_subset_refresh(packages, "Problematic-app recheck")

    def _start_subset_refresh(self, packages: list[str], label: str) -> None:
        if self._audit_active:
            QMessageBox.information(
                self,
                "Audit running",
                "Wait for the current audit to finish before starting a targeted recheck.",
            )
            return
        wanted = {package for package in packages if package}
        source_rows = [row for row in self.current_rows if str(row.get("package_name") or "") in wanted]
        if not source_rows:
            QMessageBox.information(
                self, "Nothing to recheck", "No matching app is present in the current results."
            )
            return
        self._merge_base_rows = [dict(row) for row in self.current_rows]
        self._subset_label = label
        self._apps_override = [
            {
                "app_name": str(
                    row.get("app_name") or row.get("play_title") or row.get("package_name") or ""
                ),
                "package_name": str(row.get("package_name") or ""),
            }
            for row in source_rows
        ]
        self._force_refresh_next = True
        self._start_audit()
        if self._audit_active and self._merge_base_rows is not None:
            self.current_rows = [dict(row) for row in self._merge_base_rows]
            self.model.set_rows(self.current_rows)
            self._update_summary()

    def _get_apps_to_audit(self):
        if self._apps_override is not None:
            system = {
                str(row.get("package_name") or "")
                for row in (self._merge_base_rows or self.current_rows)
                if row.get("is_system")
            }
            return list(self._apps_override), system, "targeted manual recheck"
        return super()._get_apps_to_audit()

    def _start_audit(self) -> None:
        if self._audit_active:
            super()._start_audit()
            return
        settings = state.load_settings()
        selected_country = (self.country_edit.text().strip() or "").lower()
        device_metadata.set_fallback_countries(
            settings.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),
            selected_country,
        )
        try:
            super()._start_audit()
        finally:
            self._force_refresh_next = False
            self._apps_override = None

    # ---------- Worker / device metadata ----------
    def _controlled_audit_worker(
        self,
        all_apps,
        live_apps,
        cached,
        config,
        session,
        pause_event,
        cancel_event,
        cache_enabled,
    ) -> None:
        metadata_executor: ThreadPoolExecutor | None = None
        metadata_future = None
        try:
            settings = state.load_settings()
            if self.source_mode == "device" and settings.get("collect_device_metadata", True):
                adb = self._get_authorised_adb()
                if adb:
                    metadata_executor = ThreadPoolExecutor(max_workers=1)
                    metadata_future = metadata_executor.submit(
                        self._collect_device_metadata,
                        adb,
                        [app["package_name"] for app in all_apps],
                        cancel_event,
                    )

            cached_count = len(cached)
            total_count = len(all_apps)

            def progress(done: int, _total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.audit_control_signals.progress.emit(
                    session, cached_count + done, total_count, package_name
                )

            live_rows = (
                device_metadata.audit_apps_v8(
                    live_apps,
                    config,
                    progress,
                    pause_event=pause_event,
                    cancel_event=cancel_event,
                )
                if live_apps
                else []
            )
            if cancel_event.is_set() or session != self._audit_session:
                return
            if cache_enabled and live_rows:
                compact_ui.update_cache(live_rows, config.country, config.language)

            by_package = {package: dict(row) for package, row in cached.items()}
            by_package.update({str(row.get("package_name") or ""): row for row in live_rows})
            rows = [by_package[app["package_name"]] for app in all_apps if app["package_name"] in by_package]

            metadata = metadata_future.result() if metadata_future is not None else {}
            self._enrich_rows_with_device_metadata(rows, metadata)
            self._pending_device_metadata = metadata
            self.audit_control_signals.done.emit((session, rows, "", cached_count, len(live_rows)))
        except Exception as exc:
            if not cancel_event.is_set() and session == self._audit_session:
                self.audit_control_signals.done.emit((session, None, str(exc), 0, 0))
        finally:
            if metadata_executor is not None:
                metadata_executor.shutdown(wait=False, cancel_futures=True)

    def _on_controlled_done(self, payload: object) -> None:
        if self._merge_base_rows is None:
            super()._on_controlled_done(payload)
            self._update_summary()
            return

        session, rows, error, _cached_count, live_count = payload  # type: ignore[misc]
        if session != self._audit_session:
            return
        old_rows = self._merge_base_rows
        label = self._subset_label or "Recheck"
        self._merge_base_rows = None
        self._subset_label = ""

        self._audit_active = False
        self._audit_paused = False
        self._audit_pause_event.set()
        self._set_audit_source_controls_enabled(True)
        self._set_run_mode("run")

        if error:
            self.current_rows = old_rows
            self.model.set_rows(old_rows)
            self.status_label.setText(f"{label} failed")
            QMessageBox.critical(self, "Recheck failed", str(error))
            self._update_summary()
            return

        new_rows = list(rows or [])
        compare_enabled = bool(self.user_settings.get("compare_previous", False))
        history = state.load_history() if compare_enabled else {}
        for row in new_rows:
            row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
            self._classify_row(row)
            row["change"] = state.compare_with_history(row, history) if compare_enabled else ""

        replacements = {str(row.get("package_name") or ""): row for row in new_rows}
        merged = [replacements.get(str(row.get("package_name") or ""), row) for row in old_rows]
        if compare_enabled:
            device_metadata.save_history_merged(merged)

        self.current_rows = merged
        self.model.set_rows(merged)
        self.export_button.setEnabled(bool(merged))
        self.progress.setRange(0, max(live_count, 1))
        self.progress.setValue(live_count)
        self.status_label.setText(f"{label} completed • {len(new_rows)} app(s) refreshed live")
        self._apply_column_visibility(reset_order=False)
        self._update_summary()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = DeviceWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
