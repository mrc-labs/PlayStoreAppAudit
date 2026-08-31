from __future__ import annotations

import csv
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager, suppress

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
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.countries import audit_apps_multicountry
from playstore_app_audit.services.state import (
    DEFAULT_SETTINGS,
    TECHNICAL_COLUMNS,
    clear_cache,
    compare_with_history,
    load_fresh_cache,
    load_history,
    load_settings,
    normalise_store_workers,
    save_settings,
    update_cache,
)
from playstore_app_audit.ui import schema, table_layout
from playstore_app_audit.ui.audit_window import AuditWindow

PRIMARY_COLUMNS = schema.PRIMARY_COLUMNS
MODEL_COLUMNS = schema.MODEL_COLUMNS
DEFAULT_WIDTHS = dict(schema.DEFAULT_WIDTHS)

OPERATION_PROGRESS_MIN_WIDTH = 120
OPERATION_PROGRESS_MAX_WIDTH = 320
OPERATION_STATUS_LEFT_INSET = 16
OPERATION_STATUS_RIGHT_INSET = 12
OPERATION_STATUS_MIN_VERTICAL_PADDING = 2

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
    alternative_phase = Signal(int, int)
    done = Signal(object)


def coerce_audit_run_result(payload: object) -> AuditRunResult:
    """Accept pre-v1.99 tuple payloads while production emits typed results."""

    if isinstance(payload, AuditRunResult):
        return payload
    session, rows, error, cached_count, live_count = payload  # type: ignore[misc]
    typed_rows = list(rows or [])
    cached = max(0, int(cached_count or 0))
    live = max(0, int(live_count or 0))
    return AuditRunResult(
        session=int(session),
        outcome=AuditRunOutcome.FAILED if error else AuditRunOutcome.SUCCESS,
        rows=typed_rows,
        cached_count=cached,
        live_completed_count=live,
        total_count=len(typed_rows),
        error=str(error or ""),
    )


class CompactWindow(AuditWindow):
    """Qt6 desktop UI with pausable audits, cache and advanced controls."""

    def __init__(self) -> None:
        self.user_settings = load_settings()
        self._table_layout_tracking_enabled = False
        self._table_layout_change_depth = 0
        self._custom_layout_migration_checked = False
        self._audit_session = 0
        self._audit_active = False
        self._audit_paused = False
        self._audit_state = AuditRunState.IDLE
        self._audit_requested_outcome: AuditRunOutcome | None = None
        self._last_audit_outcome: AuditRunOutcome | None = None
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, 0, "")
        self._alternative_phase_active = False

        super().__init__()

        self.audit_control_signals = ControlledAuditSignals()
        self.audit_control_signals.progress.connect(self._on_controlled_progress)
        self.audit_control_signals.alternative_phase.connect(self._on_alternative_phase)
        self.audit_control_signals.done.connect(self._on_controlled_done)

        self.setWindowIcon(QIcon(str(ensure_runtime_icon())))
        self.resize(1500, 800)
        self.setMinimumHeight(620)
        self.workers_spin.setValue(normalise_store_workers(self.user_settings.get("store_workers")))

        self.exclude_system_source_check.setText("Exclude System Apps from Source")
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
            country_label = QLabel("Store Country")
            country_label.setToolTip("Google Play market detected from the Windows region.")
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
        table_layout.configure_header(self.table)
        self._build_menu()
        self._setup_context_menu()
        self._restore_table_layout()
        self._apply_column_visibility()
        self._set_audit_state(AuditRunState.IDLE)

    # ---------- Behaviour hooks ----------
    def _classify_row(self, row: dict[str, object]) -> None:
        _classify_criticality_multicountry(row)

    def _load_fresh_cache(
        self,
        apps: list[dict[str, str]],
        country: str,
        language: str,
        ttl_hours: int,
    ) -> dict[str, dict[str, object]]:
        return load_fresh_cache(apps, country, language, ttl_hours)

    # ---------- Layout ----------
    def _compact_action_row(self) -> None:
        root = self.centralWidget().layout()
        action_layout = _find_layout_containing(root, self.run_button)
        progress_card = self.progress.parentWidget()
        progress_layout = progress_card.layout()
        if action_layout is None or progress_layout is None:
            return

        action_buttons = (
            self.run_button,
            self.stop_button,
            self.export_button,
            self.clear_button,
        )
        for button in action_buttons:
            action_layout.removeWidget(button)
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Run changes its label throughout the lifecycle. The native prototype
        # established 180 px as sufficient for its longest label; keeping that
        # width fixed prevents Pause/Resume/Stopping/Finalizing from moving the
        # adjacent commands at compact window sizes.
        self.run_button.setFixedWidth(180)

        root.removeItem(action_layout)
        while action_layout.count():
            action_layout.takeAt(0)
        action_layout.deleteLater()

        progress_layout.removeWidget(self.progress)
        progress_layout.removeWidget(self.status_label)

        self.status_bar = self.statusBar()
        self.status_bar.setObjectName("OperationalStatusBar")
        self.status_bar.setAccessibleName("Operational Status Bar")
        self.status_label.setAccessibleName("Operational Status")
        vertical_padding = max(
            OPERATION_STATUS_MIN_VERTICAL_PADDING,
            self.status_label.fontMetrics().leading(),
        )
        self.status_label.setContentsMargins(
            OPERATION_STATUS_LEFT_INSET,
            vertical_padding,
            OPERATION_STATUS_RIGHT_INSET,
            vertical_padding,
        )
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.status_bar.setSizeGripEnabled(True)
        self.progress.setAccessibleName("Operation Progress")
        self.status_bar.addWidget(self.status_label, 1)

        # The original card-only layout left a full content margin below the
        # results card. With a native status bar that margin reads as unused
        # footer height, so retain only the same small metric-derived inset as
        # the status label's vertical padding.
        left, top, right, _bottom = root.getContentsMargins()
        root.setContentsMargins(left, top, right, vertical_padding)

        results_card = self.summary_label.parentWidget()
        results_layout = results_card.layout() if results_card is not None else None
        toolbar = (
            _find_layout_containing(results_layout, self.summary_label)
            if results_layout is not None
            else None
        )
        chips = (
            _find_layout_containing(results_layout, self.all_chip)
            if results_layout is not None
            else None
        )
        if toolbar is not None and chips is not None:
            toolbar.removeWidget(self.hide_system_check)
            toolbar.removeWidget(self.search_edit)
            toolbar.addWidget(self.run_button)
            toolbar.addWidget(self.stop_button)

            self.progress.setMinimumWidth(OPERATION_PROGRESS_MIN_WIDTH)
            self.progress.setMaximumWidth(OPERATION_PROGRESS_MAX_WIDTH)
            self.progress.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
            )
            toolbar.addWidget(self.progress, 1, Qt.AlignmentFlag.AlignVCenter)
            toolbar.addWidget(self.export_button)
            toolbar.addWidget(self.clear_button)
            toolbar.setObjectName("ResultsOperationsHeader")

            self.search_edit.setMinimumWidth(180)
            self.search_edit.setMaximumWidth(280)
            self.search_edit.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            chips.addWidget(self.hide_system_check)
            chips.addWidget(self.search_edit)
            chips.setObjectName("ResultsFiltersHeader")

        self._sync_progress_presentation()

        root.removeWidget(progress_card)
        progress_card.hide()
        progress_card.deleteLater()

    def _sync_progress_presentation(self) -> None:
        operation_running = getattr(self, "_operation_running", None)
        running = (
            bool(operation_running())
            if callable(operation_running)
            else bool(self._audit_active)
        )

        self.progress.setVisible(True)
        if not running:
            self.progress.setRange(0, 100)
            self.progress.setValue(0)

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

    def _visible_column_order(self) -> list[str]:
        columns = ["criticality"]
        if self.user_settings.get("compare_previous"):
            columns.append("change")
        columns.extend(PRIMARY_COLUMNS[1:])
        selected = self.user_settings.get("technical_columns", [])
        columns.extend(column for column in TECHNICAL_COLUMNS if column in selected)
        return columns

    def _apply_column_visibility(self, reset_order: bool = False) -> None:
        with self._suspend_table_layout_tracking():
            visible = set(self._visible_column_order())
            for logical, column in enumerate(MODEL_COLUMNS):
                hidden = column not in visible
                self.table.setColumnHidden(logical, hidden)
                if reset_order or (not hidden and self.table.columnWidth(logical) <= 0):
                    self.table.setColumnWidth(
                        logical,
                        table_layout.default_column_width(self.table, column),
                    )
            if not reset_order:
                return
            header = self.table.horizontalHeader()
            for visual, column in enumerate(self._visible_column_order()):
                logical = MODEL_COLUMNS.index(column)
                current_visual = header.visualIndex(logical)
                if current_visual != visual:
                    header.moveSection(current_visual, visual)
            for logical, column in enumerate(MODEL_COLUMNS):
                self.table.setColumnWidth(
                    logical,
                    table_layout.default_column_width(self.table, column),
                )

    @contextmanager
    def _suspend_table_layout_tracking(self) -> Iterator[None]:
        self._table_layout_change_depth += 1
        try:
            yield
        finally:
            self._table_layout_change_depth -= 1

    @staticmethod
    def _normalise_custom_columns(value: object) -> list[str] | None:
        if not isinstance(value, list):
            return None
        columns = list(dict.fromkeys(column for column in value if column in MODEL_COLUMNS))
        if not columns:
            return None
        if "criticality" not in columns:
            columns.insert(0, "criticality")
        if "package_name" not in columns:
            columns.insert(1, "package_name")
        return columns

    @staticmethod
    def _normalise_custom_order(value: object, visible: list[str]) -> list[str]:
        configured = (
            list(dict.fromkeys(column for column in value if column in MODEL_COLUMNS))
            if isinstance(value, list)
            else []
        )
        order = list(dict.fromkeys(configured + visible + list(MODEL_COLUMNS)))
        return [column for column in order if column in MODEL_COLUMNS]

    @staticmethod
    def _normalise_custom_widths(value: object) -> dict[str, int]:
        if not isinstance(value, dict):
            return {}
        widths: dict[str, int] = {}
        for column, raw_width in value.items():
            if column not in MODEL_COLUMNS:
                continue
            try:
                width = int(raw_width)
            except (TypeError, ValueError):
                continue
            if 20 <= width <= 10000:
                widths[column] = width
        return widths

    def _has_custom_table_layout(self, settings: dict[str, object] | None = None) -> bool:
        current = settings if settings is not None else self.user_settings
        return bool(current.get("custom_view_exists")) and self._normalise_custom_columns(
            current.get("custom_view_columns")
        ) is not None

    def _current_table_layout(self) -> tuple[list[str], list[str], dict[str, int], str]:
        header = self.table.horizontalHeader()
        order = [
            MODEL_COLUMNS[header.logicalIndex(visual)]
            for visual in range(header.count())
            if 0 <= header.logicalIndex(visual) < len(MODEL_COLUMNS)
        ]
        visible = [
            column
            for column in order
            if not self.table.isColumnHidden(MODEL_COLUMNS.index(column))
        ]
        visible = self._normalise_custom_columns(visible) or ["criticality", "package_name"]
        widths = {
            column: self.table.columnWidth(logical)
            for logical, column in enumerate(MODEL_COLUMNS)
        }
        encoded = bytes(header.saveState().toBase64()).decode("ascii")
        return visible, order, widths, encoded

    def _persist_current_custom_layout(self, *, activate: bool = True) -> None:
        visible, order, widths, encoded = self._current_table_layout()
        settings = load_settings()
        settings.update(
            {
                "custom_view_exists": True,
                "custom_view_columns": visible,
                "custom_view_order": order,
                "custom_view_widths": widths,
                # Preserve the RC2/Phase A header blob as a compatibility alias.
                "qt_header_state": encoded,
            }
        )
        if activate:
            settings["view_preset"] = "Custom"
        self.user_settings = save_settings(settings)
        sync = getattr(self, "_sync_view_preset_action", None)
        if activate and callable(sync):
            sync("Custom")
        availability = getattr(self, "_sync_custom_preset_availability", None)
        if callable(availability):
            availability()

    def _restore_custom_table_layout(self) -> bool:
        self.user_settings = load_settings()
        visible = self._normalise_custom_columns(self.user_settings.get("custom_view_columns"))
        if not self.user_settings.get("custom_view_exists") or visible is None:
            return False
        order = self._normalise_custom_order(self.user_settings.get("custom_view_order"), visible)
        widths = self._normalise_custom_widths(self.user_settings.get("custom_view_widths"))
        with self._suspend_table_layout_tracking():
            visible_set = set(visible)
            for logical, column in enumerate(MODEL_COLUMNS):
                self.table.setColumnHidden(logical, column not in visible_set)
            header = self.table.horizontalHeader()
            for visual, column in enumerate(order):
                logical = MODEL_COLUMNS.index(column)
                current_visual = header.visualIndex(logical)
                if current_visual != visual:
                    header.moveSection(current_visual, visual)
            for logical, column in enumerate(MODEL_COLUMNS):
                self.table.setColumnWidth(
                    logical,
                    widths.get(column, table_layout.default_column_width(self.table, column)),
                )
        return True

    def _migrate_legacy_custom_layout(self) -> bool:
        if self._custom_layout_migration_checked:
            return False
        self._custom_layout_migration_checked = True

        self.user_settings = load_settings()
        legacy_columns = self._normalise_custom_columns(
            self.user_settings.get("custom_view_columns")
        )
        legacy_state = str(self.user_settings.get("qt_header_state") or "")
        current_preset = str(self.user_settings.get("view_preset") or "Basic")
        restored = False
        if legacy_state:
            try:
                with self._suspend_table_layout_tracking():
                    restored = self.table.horizontalHeader().restoreState(
                        QByteArray.fromBase64(legacy_state.encode("ascii"))
                    )
            except Exception:
                restored = False

        if not restored and legacy_columns is None:
            return False

        with self._suspend_table_layout_tracking():
            if legacy_columns is not None:
                visible = set(legacy_columns)
                for logical, column in enumerate(MODEL_COLUMNS):
                    self.table.setColumnHidden(logical, column not in visible)
            elif not restored:
                return False

        # An old explicit Custom column list remains a saved Custom while the
        # user's last built-in selection stays active. A lone header blob is
        # ambiguous, so preserve its live manual widths/order as active Custom.
        activate = current_preset == "Custom" or legacy_columns is None
        self._persist_current_custom_layout(activate=activate)
        return True

    def _enable_table_layout_tracking(self) -> None:
        if self._table_layout_tracking_enabled:
            return
        header = self.table.horizontalHeader()
        header.sectionMoved.connect(self._on_manual_table_layout_change)
        header.sectionResized.connect(self._on_manual_table_layout_change)
        self._table_layout_tracking_enabled = True
        availability = getattr(self, "_sync_custom_preset_availability", None)
        if callable(availability):
            availability()

    def _on_manual_table_layout_change(self, *_args: object) -> None:
        if not self._table_layout_tracking_enabled or self._table_layout_change_depth:
            return
        self._persist_current_custom_layout()

    def _restore_table_layout(self) -> None:
        self.user_settings = load_settings()
        preset = str(self.user_settings.get("view_preset") or "Basic")
        if self._has_custom_table_layout() and preset == "Custom":
            if self._restore_custom_table_layout():
                return
        elif (
            not self._has_custom_table_layout()
            and self._migrate_legacy_custom_layout()
            and str(self.user_settings.get("view_preset") or "Basic") == "Custom"
        ):
            self._restore_custom_table_layout()
            return

        if preset == "Custom":
            self.user_settings["view_preset"] = "Basic"
            self.user_settings = save_settings(self.user_settings)
        self._apply_column_visibility(reset_order=True)

    def _save_table_layout(self) -> None:
        try:
            self.user_settings = load_settings()
            if (
                str(self.user_settings.get("view_preset") or "Basic") == "Custom"
                and self._has_custom_table_layout()
            ):
                self._persist_current_custom_layout()
        except Exception:
            pass

    def _reset_table_layout(self) -> None:
        self._apply_column_visibility(reset_order=True)
        self.user_settings = load_settings()
        if str(self.user_settings.get("view_preset") or "Basic") == "Custom":
            self._persist_current_custom_layout()
        self._set_presentation_status("Table layout reset to defaults")

    def _set_presentation_status(self, message: str) -> None:
        operation_running = getattr(self, "_operation_running", None)
        if callable(operation_running):
            if operation_running():
                return
        elif getattr(self, "_audit_active", False):
            return
        self.status_label.setText(message)

    # ---------- Menus / settings ----------
    def _build_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        choose = QAction("Choose App List…", self)
        choose.triggered.connect(self._choose_input)
        file_menu.addAction(choose)
        scan = QAction("Scan Phone with ADB", self)
        scan.triggered.connect(self._scan_phone)
        file_menu.addAction(scan)
        file_menu.addSeparator()
        export_all = QAction("Export All Results…", self)
        export_all.triggered.connect(self._export_results)
        file_menu.addAction(export_all)
        export_visible = QAction("Export Visible Results…", self)
        export_visible.triggered.connect(self._export_visible_results)
        file_menu.addAction(export_visible)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        tools = menu.addMenu("Tools")
        advanced = QAction("Advanced Settings…", self)
        advanced.triggered.connect(self._show_advanced_settings)
        tools.addAction(advanced)
        clear_cache_action = QAction("Clear Audit Cache", self)
        clear_cache_action.triggered.connect(self._clear_audit_cache)
        tools.addAction(clear_cache_action)
        reset_layout = QAction("Reset Table Layout", self)
        reset_layout.triggered.connect(self._reset_table_layout)
        tools.addAction(reset_layout)

        help_menu = menu.addMenu("Help")
        about = QAction("About Play Store App Audit", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    def _show_advanced_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Advanced Settings")
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
            "Audit Android packages against public Google Play listings, update dates and regional availability.<br><br>"
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
        copy_package = menu.addAction("Copy Package Name")
        copy_title = menu.addAction("Copy Play Store Title")
        copy_url = menu.addAction("Copy Store URL")
        copy_row = menu.addAction("Copy Visible Row")
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
    def _set_audit_state(self, state: AuditRunState) -> None:
        self._audit_state = state
        self._audit_active = state is not AuditRunState.IDLE
        self._audit_paused = state is AuditRunState.PAUSED

        if state is AuditRunState.RUNNING:
            self._set_run_mode("pause")
            self.stop_button.setEnabled(True)
        elif state is AuditRunState.PAUSED:
            self._set_run_mode("resume")
            self.stop_button.setEnabled(True)
        elif state is AuditRunState.STOPPING:
            self.run_button.setText("Stopping…")
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        elif state is AuditRunState.FINALIZING:
            self.run_button.setText("Finalizing…")
            self.run_button.setEnabled(False)
            self.stop_button.setEnabled(False)
        else:
            self._set_run_mode("run")
            self.stop_button.setEnabled(False)

        self._sync_progress_presentation()
        sync_actions = getattr(self, "_sync_action_availability", None)
        if callable(sync_actions):
            sync_actions()

    def _set_run_mode(self, mode: str) -> None:
        if mode == "pause":
            self.run_button.setText("Pause")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        elif mode == "resume":
            self.run_button.setText("Resume")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.run_button.setText("Run Play Store Audit")
            self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_button.setEnabled(True)

    def _set_audit_source_controls_enabled(self, enabled: bool) -> None:
        self.choose_button.setEnabled(enabled)
        self.scan_button.setEnabled(enabled)
        self.country_edit.setEnabled(enabled)
        self.exclude_system_source_check.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        self._sync_progress_presentation()

    def _toggle_pause(self) -> None:
        if self._audit_state not in {AuditRunState.RUNNING, AuditRunState.PAUSED}:
            return
        done, total, _package = self._last_progress
        if self._audit_state is AuditRunState.PAUSED:
            self._audit_pause_event.set()
            self._set_audit_state(AuditRunState.RUNNING)
            if self._alternative_phase_active:
                self.status_label.setText("Resumed • checking alternative distribution")
            else:
                self.status_label.setText(f"Resumed • {done}/{total} completed")
        else:
            self._audit_pause_event.clear()
            self._set_audit_state(AuditRunState.PAUSED)
            if self._alternative_phase_active:
                self.status_label.setText("Paused • no new alternative-provider requests will start")
            else:
                self.status_label.setText(f"Paused • {done}/{total} completed")

    def _start_audit(self) -> None:
        if self._audit_state in {AuditRunState.RUNNING, AuditRunState.PAUSED}:
            self._toggle_pause()
            return
        if self._audit_state is not AuditRunState.IDLE:
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
        store_workers = normalise_store_workers(self.user_settings.get("store_workers"))
        self.workers_spin.setValue(store_workers)
        cache_enabled = bool(self.user_settings.get("cache_enabled", True))
        ttl = int(self.user_settings.get("cache_ttl_hours", 72))
        cached = self._load_fresh_cache(apps, country, language, ttl) if cache_enabled else {}
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
        self.export_button.setEnabled(False)
        self.progress.setRange(0, len(apps))
        self.progress.setValue(cached_count)
        cache_text = f" • {cached_count} from cache" if cached_count else ""
        self.status_label.setText(
            f"Starting audit for {len(apps)} packages in Store country '{country}'{cache_text}…"
        )

        self._audit_session += 1
        session = self._audit_session
        self._audit_requested_outcome = None
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (cached_count, len(apps), "")
        self._alternative_phase_active = False
        self._set_audit_source_controls_enabled(False)
        self._set_audit_state(AuditRunState.RUNNING)

        config = AuditConfig(country=country, language=language, max_workers=store_workers)
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
        completed_live: dict[int, dict[str, object]] = {}

        def row_completed(index: int, row: dict[str, object]) -> None:
            completed_live[index] = dict(row)

        def ordered_live_rows(returned: list[dict[str, object]]) -> list[dict[str, object]]:
            by_package = {
                str(row.get("package_name") or ""): dict(row)
                for row in completed_live.values()
            }
            by_package.update(
                {str(row.get("package_name") or ""): dict(row) for row in returned}
            )
            return [
                by_package[app["package_name"]]
                for app in live_apps
                if app["package_name"] in by_package
            ]

        def all_rows(live_rows: list[dict[str, object]]) -> list[dict[str, object]]:
            by_package = {package: dict(row) for package, row in cached.items()}
            by_package.update(
                {str(row.get("package_name") or ""): dict(row) for row in live_rows}
            )
            return [
                by_package[app["package_name"]]
                for app in all_apps
                if app["package_name"] in by_package
            ]

        def emit_result(
            outcome: AuditRunOutcome,
            live_rows: list[dict[str, object]],
            error: str = "",
        ) -> None:
            if session != self._audit_session or self._audit_requested_outcome is AuditRunOutcome.ABANDONED:
                return
            self.audit_control_signals.done.emit(
                AuditRunResult(
                    session=session,
                    outcome=outcome,
                    rows=all_rows(live_rows),
                    cached_count=len(cached),
                    live_completed_count=len(live_rows),
                    total_count=len(all_apps),
                    error=error,
                )
            )

        try:
            cached_count = len(cached)
            total_count = len(all_apps)

            def progress(done: int, _total: int, package_name: str) -> None:
                if session != self._audit_session:
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
                    row_completed_callback=row_completed,
                )
                if live_apps
                else []
            )
            live_rows = ordered_live_rows(list(live_rows))
            if cache_enabled and live_rows:
                update_cache(live_rows, config.country, config.language)
            outcome = (
                AuditRunOutcome.STOPPED
                if cancel_event.is_set()
                or self._audit_requested_outcome is AuditRunOutcome.STOPPED
                else AuditRunOutcome.SUCCESS
            )
            emit_result(outcome, live_rows)
        except Exception as exc:
            live_rows = ordered_live_rows([])
            if cache_enabled and live_rows:
                with suppress(Exception):
                    update_cache(live_rows, config.country, config.language)
            # A fatal exception that reaches the worker wins over a concurrent
            # user Stop. Cancellation paths return normally and therefore keep
            # the distinct STOPPED outcome.
            emit_result(AuditRunOutcome.FAILED, live_rows, str(exc))

    def _on_controlled_progress(self, session: int, done: int, total: int, package_name: str) -> None:
        if session != self._audit_session or not self._audit_active:
            return
        self._last_progress = (done, total, package_name)
        self._alternative_phase_active = False
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        if self._audit_state is AuditRunState.STOPPING:
            self.status_label.setText(f"Stopping… {done}/{total} completed")
        elif self._audit_state is AuditRunState.PAUSED:
            self.status_label.setText(f"Paused • {done}/{total} completed")
        else:
            self.status_label.setText(f"Completed {done}/{total}: {package_name}")

    def _on_alternative_phase(self, session: int, eligible_count: int) -> None:
        if session != self._audit_session or not self._audit_active:
            return
        self._alternative_phase_active = True
        self.progress.setRange(0, 0)
        self.status_label.setText(
            f"Checking alternative distribution for {eligible_count} package(s)…"
        )

    def _on_controlled_done(self, payload: object) -> None:
        result = coerce_audit_run_result(payload)
        if result.session != self._audit_session or result.outcome is AuditRunOutcome.ABANDONED:
            return
        # A worker may have queued SUCCESS immediately before the UI processed
        # the user's Stop click. Once Stop is accepted while the run is active,
        # it remains authoritative unless the worker reports a fatal failure.
        if (
            self._audit_requested_outcome is AuditRunOutcome.STOPPED
            and result.outcome is AuditRunOutcome.SUCCESS
        ):
            result.outcome = AuditRunOutcome.STOPPED
        self._last_audit_outcome = result.outcome
        self._audit_pause_event.set()
        self._alternative_phase_active = False

        typed_rows = list(result.rows)
        compare_enabled = bool(self.user_settings.get("compare_previous", False))
        history = load_history() if compare_enabled else {}
        for row in typed_rows:
            row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
            self._classify_row(row)
            row["change"] = compare_with_history(row, history) if compare_enabled else ""

        self.current_rows = typed_rows
        self.model.set_rows(typed_rows)
        self.progress.setRange(0, max(result.total_count, 1))
        self.progress.setValue(result.completed_count)
        self.export_button.setEnabled(bool(typed_rows))
        cache_summary = (
            f" • {result.cached_count} cached • {result.live_completed_count} live"
            if result.cached_count
            else f" • {result.live_completed_count} live"
        )
        if result.outcome is AuditRunOutcome.SUCCESS:
            self.status_label.setText(f"Audit completed{cache_summary}")
        elif result.outcome is AuditRunOutcome.STOPPED:
            self.status_label.setText(
                f"Audit stopped • {result.completed_count}/{result.total_count} completed"
                f"{cache_summary}"
            )
        else:
            partial = (
                f" • {result.completed_count}/{result.total_count} completed"
                if result.completed_count
                else ""
            )
            self.status_label.setText(f"Audit failed{partial}")
        self._update_summary()
        self._apply_column_visibility(reset_order=False)

        deferred_idle = getattr(self, "_finalizing_session", None) == result.session
        if not deferred_idle:
            self._set_audit_source_controls_enabled(True)
            self._set_audit_state(AuditRunState.IDLE)
        if result.outcome is AuditRunOutcome.FAILED:
            QMessageBox.critical(self, "Audit failed", result.error or "Unknown audit failure")

    def _stop_audit(self) -> None:
        """Request cooperative Stop; bounded in-flight operations drain before idle."""

        if self._audit_state not in {AuditRunState.RUNNING, AuditRunState.PAUSED}:
            return
        self._audit_requested_outcome = AuditRunOutcome.STOPPED
        self._audit_cancel_event.set()
        self._audit_pause_event.set()
        done, total, _package = self._last_progress
        self._set_audit_state(AuditRunState.STOPPING)
        if self._alternative_phase_active:
            self.status_label.setText("Stopping alternative-distribution checks…")
        else:
            self.status_label.setText(f"Stopping… {done}/{total} completed")

    def _abandon_active_audit(self) -> None:
        if self._audit_state is AuditRunState.IDLE:
            return
        self._audit_requested_outcome = AuditRunOutcome.ABANDONED
        self._last_audit_outcome = AuditRunOutcome.ABANDONED
        self._audit_cancel_event.set()
        self._audit_pause_event.set()
        self._audit_session += 1
        if hasattr(self, "_finalizing_session"):
            self._finalizing_session = None
        if hasattr(self, "_merge_base_rows"):
            self._merge_base_rows = None
        if hasattr(self, "_v9_targeted_active"):
            self._v9_targeted_active = False
        self._set_audit_source_controls_enabled(True)
        self._set_audit_state(AuditRunState.IDLE)

    def _cancel_active_audit(self) -> None:
        """Compatibility name for non-user abandonment paths."""

        self._abandon_active_audit()

    def _clear_results(self) -> None:
        if self._audit_state is not AuditRunState.IDLE:
            return
        base_ui.BaseWindow._clear_results(self)
        self._set_audit_state(AuditRunState.IDLE)

    def closeEvent(self, event) -> None:
        self._abandon_active_audit()
        self._save_table_layout()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = CompactWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
