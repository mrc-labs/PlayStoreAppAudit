from __future__ import annotations

import csv
import sys
import threading

from PySide6.QtCore import QByteArray, QObject, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QVBoxLayout,
)

import playstore_app_audit.ui.base_window as base_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.countries import audit_apps_multicountry
from playstore_app_audit.services.persistence import (
    DEFAULT_SETTINGS,
    TECHNICAL_COLUMNS,
    clear_cache,
    compare_with_history,
    load_fresh_cache,
    load_history,
    load_settings,
    save_history,
    save_settings,
    update_cache,
)
from playstore_app_audit.ui.audit_window import AuditWindow

# Transitional internal alias for inherited code that still follows the old layer graph.
qt_base = base_ui

FIXED_WORKERS = 16
PRIMARY_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
)
MODEL_COLUMNS = (
    "criticality",
    "change",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
    "play_status",
    "updated_source",
    "play_http_status",
    "app_name",
    "store_url",
    "is_system",
)
DEFAULT_WIDTHS = {
    "criticality": 145,
    "change": 105,
    "package_name": 300,
    "play_title": 265,
    "play_last_update": 120,
    "age_days": 92,
    "notes": 460,
    "play_status": 190,
    "updated_source": 180,
    "play_http_status": 90,
    "app_name": 220,
    "store_url": 350,
    "is_system": 90,
}
PROJECT_URL = "https://github.com/mrc-labs/PlayStoreAppAudit"

base_ui.COLUMNS = MODEL_COLUMNS
base_ui.COLUMN_LABELS.update(
    {
        "criticality": "Status",
        "change": "Change",
        "package_name": "Package Name",
        "play_title": "Play Store Title",
        "play_last_update": "Last update",
        "age_days": "Age (days)",
        "notes": "Notes",
        "play_status": "Play status",
        "updated_source": "Update source",
        "play_http_status": "HTTP status",
        "app_name": "Input name",
        "store_url": "Store URL",
        "is_system": "System app",
    }
)
base_ui.EXPORT_FIELDS = list(dict.fromkeys(base_ui.EXPORT_FIELDS + ["change", "cache_hit"]))
base_ui.audit_apps = audit_apps_multicountry
_original_classify_criticality = base_ui.classify_criticality


def _classify_criticality_multicountry(row: dict[str, object]) -> None:
    status = str(row.get("play_status") or "").strip()
    if status == "not_found_in_checked_countries":
        key = "red"
    elif status == "available_in_other_country":
        key = "blue"
    elif status == "multi_country_check_inconclusive":
        key = "purple"
    else:
        _original_classify_criticality(row)
        return
    row["criticality_key"] = key
    row["criticality"] = base_ui.CRITICALITY[key]["label"]
    row["criticality_rank"] = base_ui.CRITICALITY[key]["rank"]
    row["age_days"] = ""


base_ui.classify_criticality = _classify_criticality_multicountry


def _find_layout_containing(layout, target_widget):
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is target_widget:
            return layout
        child_layout = item.layout()
        if child_layout is not None:
            found = _find_layout_containing(child_layout, target_widget)
            if found is not None:
                return found
    return None


class ControlledAuditSignals(QObject):
    progress = Signal(int, int, int, str)
    done = Signal(object)


class CompactWindow(AuditWindow):
    """Qt6 desktop UI with pausable audits, cache and advanced controls."""

    def __init__(self) -> None:
        self.user_settings = load_settings()
        self._audit_session = 0
        self._audit_active = False
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, 0, "")

        super().__init__()

        self.audit_control_signals = ControlledAuditSignals()
        self.audit_control_signals.progress.connect(self._on_controlled_progress)
        self.audit_control_signals.done.connect(self._on_controlled_done)

        self.setWindowIcon(QIcon(str(ensure_runtime_icon())))
        self.resize(1500, 800)
        self.setMinimumHeight(620)
        self.workers_spin.setValue(FIXED_WORKERS)

        self.exclude_system_source_check.setText("Exclude system apps from source")
        self.exclude_system_source_check.setToolTip(
            "Applied while loading a CSV/TSV/TXT file or scanning a phone with ADB. "
            "Turn it off if you want system apps included in the source list."
        )

        source_card = self.path_edit.parentWidget()
        settings_card = self.country_edit.parentWidget()
        source_layout = source_card.layout()
        source_line = _find_layout_containing(source_layout, self.path_edit)
        source_layout.removeWidget(self.exclude_system_source_check)
        self.country_edit.setParent(source_card)
        self.exclude_system_source_check.setParent(source_card)
        if source_line is not None:
            source_line.addSpacing(10)
            country_label = QLabel("Store country")
            country_label.setToolTip("Google Play market, detected from Windows Region.")
            source_line.addWidget(country_label)
            self.country_edit.setFixedWidth(58)
            source_line.addWidget(self.country_edit)
            source_line.addSpacing(8)
            source_line.addWidget(self.exclude_system_source_check)
        self.country_edit.show()
        self.exclude_system_source_check.show()
        settings_card.hide()

        self.table.verticalHeader().setMinimumSectionSize(20)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self._compact_action_row()
        self._compact_results_area()
        self._build_menu()
        self._setup_context_menu()
        self._restore_table_layout()
        self._apply_column_visibility()
        self._set_run_mode("run")

    # ---------- Layout ----------
    def _compact_action_row(self) -> None:
        root = self.centralWidget().layout()
        action_layout = _find_layout_containing(root, self.run_button)
        progress_card = self.progress.parentWidget()
        progress_layout = progress_card.layout()
        if action_layout is None or progress_layout is None:
            return
        action_layout.removeWidget(self.export_button)
        action_layout.removeWidget(self.clear_button)
        progress_layout.removeWidget(self.progress)
        progress_layout.removeWidget(self.status_label)
        self.run_button.setMinimumWidth(215)
        self.run_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        inline_progress = QVBoxLayout()
        inline_progress.setContentsMargins(0, 0, 0, 0)
        inline_progress.setSpacing(2)
        inline_progress.addWidget(self.progress)
        inline_progress.addWidget(self.status_label)
        action_layout.insertLayout(1, inline_progress, 1)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.clear_button)
        action_layout.setStretch(0, 0)
        action_layout.setStretch(1, 1)
        root.removeWidget(progress_card)
        progress_card.hide()
        progress_card.deleteLater()

    def _compact_results_area(self) -> None:
        results_card = self.table.parentWidget()
        results_layout = results_card.layout() if results_card is not None else None
        if results_layout is None:
            return
        results_layout.setContentsMargins(12, 9, 12, 10)
        results_layout.setSpacing(5)
        toolbar = _find_layout_containing(results_layout, self.summary_label)
        if toolbar is not None:
            toolbar.setContentsMargins(0, 0, 0, 0)
            toolbar.setSpacing(8)
        chips = _find_layout_containing(results_layout, self.all_chip)
        if chips is not None:
            chips.setContentsMargins(0, 0, 0, 0)
            chips.setSpacing(5)
        summary_font = QFont(self.summary_label.font())
        summary_font.setPointSizeF(10.5)
        summary_font.setBold(True)
        self.summary_label.setFont(summary_font)
        self.search_edit.setFixedHeight(32)
        self.all_chip.setFixedHeight(28)
        for button in self.criticality_buttons.values():
            button.setFixedHeight(28)
        for index in range(results_layout.count()):
            widget = results_layout.itemAt(index).widget()
            if isinstance(widget, QLabel) and widget.text().startswith("Removed ="):
                legend_font = QFont(widget.font())
                legend_font.setPointSizeF(8.8)
                widget.setFont(legend_font)
                break

    def _visible_column_order(self) -> list[str]:
        columns = ["criticality"]
        if self.user_settings.get("compare_previous"):
            columns.append("change")
        columns.extend(PRIMARY_COLUMNS[1:])
        selected = self.user_settings.get("technical_columns", [])
        columns.extend(column for column in TECHNICAL_COLUMNS if column in selected)
        return columns

    def _apply_column_visibility(self, reset_order: bool = False) -> None:
        visible = set(self._visible_column_order())
        for logical, column in enumerate(MODEL_COLUMNS):
            self.table.setColumnHidden(logical, column not in visible)
            if reset_order or self.table.columnWidth(logical) <= 0:
                self.table.setColumnWidth(logical, DEFAULT_WIDTHS.get(column, 140))
        if reset_order:
            header = self.table.horizontalHeader()
            for visual, column in enumerate(self._visible_column_order()):
                logical = MODEL_COLUMNS.index(column)
                current_visual = header.visualIndex(logical)
                if current_visual != visual:
                    header.moveSection(current_visual, visual)
            for logical, column in enumerate(MODEL_COLUMNS):
                self.table.setColumnWidth(logical, DEFAULT_WIDTHS.get(column, 140))

    def _restore_table_layout(self) -> None:
        encoded = str(self.user_settings.get("qt_header_state") or "")
        restored = False
        if encoded:
            try:
                restored = self.table.horizontalHeader().restoreState(
                    QByteArray.fromBase64(encoded.encode("ascii"))
                )
            except Exception:
                restored = False
        if not restored:
            self._apply_column_visibility(reset_order=True)

    def _save_table_layout(self) -> None:
        try:
            encoded = bytes(self.table.horizontalHeader().saveState().toBase64()).decode("ascii")
            self.user_settings["qt_header_state"] = encoded
            save_settings(self.user_settings)
        except Exception:
            pass

    def _reset_table_layout(self) -> None:
        self.user_settings["qt_header_state"] = ""
        self.user_settings = save_settings(self.user_settings)
        self._apply_column_visibility(reset_order=True)
        self.status_label.setText("Table layout reset to defaults")

    # ---------- Menus / settings ----------
    def _build_menu(self) -> None:
        menu = self.menuBar()
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
        clear_cache_action = QAction("Clear audit cache", self)
        clear_cache_action.triggered.connect(self._clear_audit_cache)
        tools.addAction(clear_cache_action)
        reset_layout = QAction("Reset table layout", self)
        reset_layout.triggered.connect(self._reset_table_layout)
        tools.addAction(reset_layout)

        help_menu = menu.addMenu("Help")
        about = QAction("About Play Store App Audit", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _show_advanced_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced settings")
        dialog.setMinimumWidth(560)
        root = QVBoxLayout(dialog)

        warning = QLabel(
            "⚠ Advanced settings can change accuracy, network behaviour and the amount of technical data shown. "
            "Change them only when necessary and if you understand the effect."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background:#FFF6E5; color:#6B4A16; border:1px solid #E9C77D; padding:10px; border-radius:6px;"
        )
        root.addWidget(warning)

        store_group = QGroupBox("Store and cache")
        store_form = QFormLayout(store_group)
        language = QLineEdit(str(self.user_settings.get("store_language") or "en"))
        language.setMaxLength(8)
        language.setToolTip(
            "Google Play UI language. Default: en. This normally does not change market availability."
        )
        store_form.addRow("Store language", language)
        cache_enabled = QCheckBox("Use intelligent cache")
        cache_enabled.setChecked(bool(self.user_settings.get("cache_enabled", True)))
        store_form.addRow("", cache_enabled)
        ttl = QSpinBox()
        ttl.setRange(1, 720)
        ttl.setValue(int(self.user_settings.get("cache_ttl_hours", 72)))
        ttl.setSuffix(" hours")
        ttl.setToolTip(
            "Only healthy available listings are cached. Removed/anomaly/error results are always checked live."
        )
        store_form.addRow("Healthy-result cache TTL", ttl)
        cache_note = QLabel(
            "Default: 72 hours. Only normal available apps with a valid update date are reused; risky or uncertain states always bypass the cache."
        )
        cache_note.setWordWrap(True)
        cache_note.setStyleSheet("color:#6F7C87;")
        store_form.addRow("", cache_note)
        root.addWidget(store_group)

        history_group = QGroupBox("Audit history")
        history_layout = QVBoxLayout(history_group)
        compare = QCheckBox("Compare with previous audit")
        compare.setChecked(bool(self.user_settings.get("compare_previous", False)))
        history_layout.addWidget(compare)
        history_note = QLabel(
            "Off by default. When enabled, the first completed audit creates a local baseline; later audits show Change = New / Same / Better / Worse."
        )
        history_note.setWordWrap(True)
        history_note.setStyleSheet("color:#6F7C87;")
        history_layout.addWidget(history_note)
        root.addWidget(history_group)

        columns_group = QGroupBox("Technical columns")
        columns_layout = QVBoxLayout(columns_group)
        technical_checks: dict[str, QCheckBox] = {}
        selected = set(self.user_settings.get("technical_columns", []))
        for key, label in TECHNICAL_COLUMNS.items():
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
            language.setText(str(DEFAULT_SETTINGS["store_language"]))
            cache_enabled.setChecked(bool(DEFAULT_SETTINGS["cache_enabled"]))
            ttl.setValue(int(DEFAULT_SETTINGS["cache_ttl_hours"]))
            compare.setChecked(bool(DEFAULT_SETTINGS["compare_previous"]))
            for check in technical_checks.values():
                check.setChecked(False)

        reset_button.clicked.connect(reset_controls)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.user_settings.update(
            {
                "store_language": (language.text().strip() or "en").lower(),
                "cache_enabled": cache_enabled.isChecked(),
                "cache_ttl_hours": ttl.value(),
                "compare_previous": compare.isChecked(),
                "technical_columns": [key for key, check in technical_checks.items() if check.isChecked()],
            }
        )
        self.user_settings = save_settings(self.user_settings)
        self._apply_column_visibility(reset_order=False)
        self.status_label.setText("Advanced settings saved; audit-related changes apply from the next run")

    def _clear_audit_cache(self) -> None:
        answer = QMessageBox.question(
            self,
            "Clear audit cache?",
            "Delete locally cached healthy Play Store results? Audit history and settings will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            clear_cache()
            self.status_label.setText("Audit cache cleared")

    def _show_about(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("About Play Store App Audit")
        dialog.setMinimumWidth(480)
        layout = QVBoxLayout(dialog)
        title = QLabel("Play Store App Audit")
        font = QFont(title.font())
        font.setPointSizeF(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        info = QLabel(
            "<b>Created by MRC</b><br>"
            "Development assistance: OpenAI ChatGPT<br><br>"
            "Audit Android packages against public Google Play listings, update dates and regional availability.<br><br>"
            f'<a href="{PROJECT_URL}">MRC on GitHub</a><br><br>'
            "Unofficial utility. Not affiliated with or endorsed by Google."
        )
        info.setWordWrap(True)
        info.setOpenExternalLinks(True)
        layout.addWidget(info)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(dialog.reject)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    # ---------- Context menu / export ----------
    def _setup_context_menu(self) -> None:
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_row_context_menu)

    def _row_from_proxy_index(self, proxy_index):
        if not proxy_index.isValid():
            return None
        source_index = self.proxy.mapToSource(proxy_index)
        return self.model.row_dict(source_index.row())

    def _show_row_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        row = self._row_from_proxy_index(index)
        if not row:
            return
        self.table.selectRow(index.row())
        menu = QMenu(self)
        open_store = menu.addAction("Open in Google Play")
        menu.addSeparator()
        copy_package = menu.addAction("Copy package name")
        copy_title = menu.addAction("Copy Play Store title")
        copy_url = menu.addAction("Copy Store URL")
        copy_row = menu.addAction("Copy visible row")
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is open_store:
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
                (header.visualIndex(i), MODEL_COLUMNS[i])
                for i in range(len(MODEL_COLUMNS))
                if not self.table.isColumnHidden(i)
            ]
            visible_columns.sort()
            QApplication.clipboard().setText(
                "\t".join(str(row.get(column, "") or "") for _, column in visible_columns)
            )

    def _visible_rows(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for proxy_row in range(self.proxy.rowCount()):
            proxy_index = self.proxy.index(proxy_row, 0)
            source_index = self.proxy.mapToSource(proxy_index)
            rows.append(self.model.row_dict(source_index.row()))
        return rows

    def _export_rows(self, rows: list[dict[str, object]], default_name: str) -> None:
        if not rows:
            QMessageBox.information(self, "Nothing to export", "There are no rows to export.")
            return
        selected, _ = QFileDialog.getSaveFileName(self, "Export audit results", default_name, "CSV (*.csv)")
        if not selected:
            return
        if not selected.lower().endswith(".csv"):
            selected += ".csv"
        try:
            with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(handle, fieldnames=base_ui.EXPORT_FIELDS, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(rows)
            QMessageBox.information(self, "Export complete", f"Results saved to:\n{selected}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _export_results(self) -> None:
        self._export_rows(self.current_rows, "playstore_audit_results.csv")

    def _export_visible_results(self) -> None:
        self._export_rows(self._visible_rows(), "playstore_audit_visible_results.csv")

    # ---------- Audit ----------
    def _set_run_mode(self, mode: str) -> None:
        if mode == "pause":
            self.run_button.setText("Pause")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        elif mode == "resume":
            self.run_button.setText("Resume")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.run_button.setText("Run Play Store audit")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_button.setEnabled(True)

    def _set_audit_source_controls_enabled(self, enabled: bool) -> None:
        self.choose_button.setEnabled(enabled)
        self.scan_button.setEnabled(enabled)
        self.country_edit.setEnabled(enabled)
        self.exclude_system_source_check.setEnabled(enabled)

    def _toggle_pause(self) -> None:
        if not self._audit_active:
            return
        done, total, _package = self._last_progress
        if self._audit_paused:
            self._audit_pause_event.set()
            self._audit_paused = False
            self._set_run_mode("pause")
            self.status_label.setText(f"Resumed • {done}/{total} completed")
        else:
            self._audit_pause_event.clear()
            self._audit_paused = True
            self._set_run_mode("resume")
            self.status_label.setText(f"Paused • {done}/{total} completed")

    def _start_audit(self) -> None:
        if self._audit_active:
            self._toggle_pause()
            return
        try:
            apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            QMessageBox.warning(self, "No app list", str(exc))
            return
        if not apps:
            QMessageBox.warning(self, "Nothing to audit", "No packages are loaded.")
            return

        self.user_settings = load_settings()
        country = (self.country_edit.text().strip() or base_ui.detect_windows_country()).lower()
        language = str(self.user_settings.get("store_language") or "en").lower()
        cache_enabled = bool(self.user_settings.get("cache_enabled", True))
        ttl = int(self.user_settings.get("cache_ttl_hours", 72))
        cached = load_fresh_cache(apps, country, language, ttl) if cache_enabled else {}
        live_apps = [app for app in apps if app["package_name"] not in cached]
        cached_count = len(cached)

        self.current_system_packages = system_packages
        self.criticality_filter = None
        self._sync_criticality_buttons()
        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_label.setText(
            f"{source_label} source: {len(apps)} packages • {len(system_packages)} classified as system • {classification_method}"
        )
        self.current_rows = []
        self.model.set_rows([])
        self.proxy.invalidateFilter()
        self.export_button.setEnabled(False)
        self.progress.setRange(0, len(apps))
        self.progress.setValue(cached_count)
        cache_text = f" • {cached_count} from cache" if cached_count else ""
        self.status_label.setText(
            f"Starting audit for {len(apps)} packages in Store country '{country}'{cache_text}…"
        )

        self._audit_session += 1
        session = self._audit_session
        self._audit_active = True
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (cached_count, len(apps), "")
        self._set_audit_source_controls_enabled(False)
        self._set_run_mode("pause")

        config = AuditConfig(country=country, language=language, max_workers=FIXED_WORKERS)
        threading.Thread(
            target=self._controlled_audit_worker,
            args=(
                apps,
                live_apps,
                cached,
                config,
                session,
                self._audit_pause_event,
                self._audit_cancel_event,
                cache_enabled,
            ),
            daemon=True,
        ).start()

    def _controlled_audit_worker(
        self,
        all_apps: list[dict[str, str]],
        live_apps: list[dict[str, str]],
        cached: dict[str, dict[str, object]],
        config: AuditConfig,
        session: int,
        pause_event: threading.Event,
        cancel_event: threading.Event,
        cache_enabled: bool,
    ) -> None:
        try:
            cached_count = len(cached)
            total_count = len(all_apps)

            def progress(done: int, _total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.audit_control_signals.progress.emit(
                    session, cached_count + done, total_count, package_name
                )

            live_rows = (
                audit_apps_multicountry(
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
                update_cache(live_rows, config.country, config.language)
            by_package = {package: dict(row) for package, row in cached.items()}
            by_package.update({str(row.get("package_name") or ""): row for row in live_rows})
            rows = [by_package[app["package_name"]] for app in all_apps if app["package_name"] in by_package]
            self.audit_control_signals.done.emit((session, rows, "", cached_count, len(live_rows)))
        except Exception as exc:
            if not cancel_event.is_set() and session == self._audit_session:
                self.audit_control_signals.done.emit((session, None, str(exc), 0, 0))

    def _on_controlled_progress(self, session: int, done: int, total: int, package_name: str) -> None:
        if session != self._audit_session or not self._audit_active:
            return
        self._last_progress = (done, total, package_name)
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        if self._audit_paused:
            self.status_label.setText(f"Paused • {done}/{total} completed")
        else:
            self.status_label.setText(f"Completed {done}/{total}: {package_name}")

    def _on_controlled_done(self, payload: object) -> None:
        session, rows, error, cached_count, live_count = payload  # type: ignore[misc]
        if session != self._audit_session:
            return
        self._audit_active = False
        self._audit_paused = False
        self._audit_pause_event.set()
        self._set_audit_source_controls_enabled(True)
        self._set_run_mode("run")
        if error:
            self.status_label.setText("Audit failed")
            self.export_button.setEnabled(bool(self.current_rows))
            QMessageBox.critical(self, "Audit failed", str(error))
            return

        typed_rows = list(rows or [])
        compare_enabled = bool(self.user_settings.get("compare_previous", False))
        history = load_history() if compare_enabled else {}
        for row in typed_rows:
            row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
            base_ui.classify_criticality(row)
            row["change"] = compare_with_history(row, history) if compare_enabled else ""
        if compare_enabled:
            save_history(typed_rows)

        self.current_rows = typed_rows
        self.model.set_rows(typed_rows)
        self.proxy.invalidateFilter()
        self.progress.setRange(0, max(len(typed_rows), 1))
        self.progress.setValue(len(typed_rows))
        self.export_button.setEnabled(bool(typed_rows))
        cache_summary = (
            f" • {cached_count} cached • {live_count} live" if cached_count else f" • {live_count} live"
        )
        self.status_label.setText(f"Audit completed{cache_summary}")
        self._update_summary()
        self._apply_column_visibility(reset_order=False)

    def _cancel_active_audit(self) -> None:
        if not self._audit_active:
            self._set_run_mode("run")
            return
        self._audit_cancel_event.set()
        self._audit_pause_event.set()
        self._audit_session += 1
        self._audit_active = False
        self._audit_paused = False
        self._set_audit_source_controls_enabled(True)
        self._set_run_mode("run")

    def _clear_results(self) -> None:
        self._cancel_active_audit()
        base_ui.BaseWindow._clear_results(self)
        self._set_run_mode("run")

    def closeEvent(self, event) -> None:
        self._cancel_active_audit()
        self._save_table_layout()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = CompactWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
