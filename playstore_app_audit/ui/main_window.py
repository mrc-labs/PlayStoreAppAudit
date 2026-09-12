from __future__ import annotations

import logging
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QWidget,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.local_apk as local_apk
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_source as local_apk_source
import playstore_app_audit.services.local_package_container as local_package_container
import playstore_app_audit.services.state as state
import playstore_app_audit.services.store_locale as store_locale
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.results_window as results_ui
from playstore_app_audit.devices.adb import find_adb, install_platform_tools
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactParseFailure,
)
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.platform import runtime
from playstore_app_audit.platform.file_locations import open_file_location
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService
from playstore_app_audit.ui.action_icons import main_action_icon
from playstore_app_audit.ui.column_presets import (
    BUILTIN_PRESETS,
    normalise_view_preset,
    visible_columns,
)
from playstore_app_audit.ui.device_window import RowActionAvailability

logger = logging.getLogger(__name__)


def _detach_layout(layout, keep: set[object]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        widget = item.widget()
        if child is not None:
            _detach_layout(child, keep)
        if widget is not None and widget not in keep:
            widget.deleteLater()


class LocalApkSourceSignals(QObject):
    progress = Signal(int, int, str)
    done = Signal(int, object, str)
    failed = Signal(int, str)


class MainWindow(results_ui.ResultsWindow):
    """Current Qt desktop window.

    This is the stable public UI entry point. Platform-specific behaviour lives
    behind playstore_app_audit.platform / devices instead of in the window.
    """

    def __init__(self) -> None:
        self._local_apk_candidates: tuple[Path, ...] = ()
        self._local_apk_parse_generation = 0
        self._local_apk_parse_cancel_event = threading.Event()
        self._local_apk_parse_active = False
        self._source_establishment_generation = 0
        self._audit_cached_count = 0
        self._audit_live_count = 0
        self._audit_started_at: float | None = None
        self._audit_pre_finalize_seconds: float | None = None
        self._audit_source_at_start: str | None = None
        self._audit_performance_logged_session: int | None = None
        self._finalizing_session: int | None = None
        super().__init__()
        self.local_apk_source_signals = LocalApkSourceSignals(self)
        self.local_apk_source_signals.progress.connect(self._on_local_apk_discovery_progress)
        self.local_apk_source_signals.done.connect(self._on_local_apk_discovery_done)
        self.local_apk_source_signals.failed.connect(self._on_local_apk_discovery_failed)
        self.choose_apk_button = QToolButton()
        self.choose_apk_button.setText("Choose APK Source…")
        self.choose_apk_button.setIcon(main_action_icon("choose_file", self.palette()))
        self.choose_apk_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.choose_apk_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.choose_apk_button.setToolTip(
            "Choose .apk, .apks, .apkm, or .xapk file(s), or discover them in a folder"
        )
        self.choose_apk_button.setAccessibleName("Choose Local Package Source")
        self.file_choose_apk_action = QAction("Choose Package File(s)…", self)
        self.file_choose_apk_action.triggered.connect(self._choose_local_apks)
        self.file_menu.insertAction(self.recent_menu.menuAction(), self.file_choose_apk_action)
        self.file_choose_apk_folder_action = QAction("Choose Package Folder…", self)
        self.file_choose_apk_folder_action.triggered.connect(self._choose_local_apk_folder)
        self.file_menu.insertAction(self.recent_menu.menuAction(), self.file_choose_apk_folder_action)
        self.choose_apk_file_action = QAction("File(s)…", self)
        self.choose_apk_file_action.triggered.connect(self._choose_local_apks)
        self.choose_apk_folder_action = QAction("Folder…", self)
        self.choose_apk_folder_action.triggered.connect(self._choose_local_apk_folder)
        self.signals.adb_discovery_done.connect(self._on_adb_discovery_done)
        self._remove_redundant_content_heading()
        self._rebuild_source_area_v10()
        self._enable_table_layout_tracking()

    def _remove_redundant_content_heading(self) -> None:
        central = self.centralWidget()
        root = central.layout() if central is not None else None
        if root is None:
            return
        for label in central.findChildren(QLabel):
            if label.objectName() == "Title" and label.text().strip() == "Play Store App Audit":
                root.removeWidget(label)
                label.setParent(None)
                label.deleteLater()
                break
        self.subtitle_label = next(
            (
                label
                for label in central.findChildren(QLabel)
                if label.objectName() == "Subtitle"
                and label.text().strip()
                == "Check Android packages against Google Play, classify update risk and inspect everything in one table."
            ),
            None,
        )
        root.setSpacing(9)

    def _populate_recent_source_menu(self, menu: QMenu, paths: list[str]) -> None:
        menu.clear()
        if not paths:
            empty_action = menu.addAction("No Recent Files")
            if empty_action is not None:
                empty_action.setEnabled(False)
            return
        for path in paths:
            menu.addAction(Path(path).name, lambda _checked=False, p=path: self._load_input_file(p))

    def _populate_recent_menu(self) -> None:
        paths = device_insights.get_recent_sources()
        menus: list[QMenu] = []
        for name in ("recent_menu", "_recent_menu", "recent_sources_button_menu"):
            menu = getattr(self, name, None)
            if isinstance(menu, QMenu) and menu not in menus:
                menus.append(menu)
        for menu in menus:
            self._populate_recent_source_menu(menu, paths)

    def _file_source_controls(self) -> QWidget:
        controls = QWidget()
        controls.setObjectName("FileSourceControls")
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.choose_button.setMinimumWidth(108)
        layout.addWidget(self.choose_button)

        self.recent_sources_button = QToolButton()
        self.recent_sources_button.setObjectName("RecentSourcesButton")
        self.recent_sources_button.setToolTip("Recent sources")
        self.recent_sources_button.setAccessibleName("Recent Sources")
        self.recent_sources_button.setArrowType(Qt.ArrowType.DownArrow)
        self.recent_sources_button.setFixedWidth(30)
        self.recent_sources_button_menu = QMenu("Recent Sources", self.recent_sources_button)
        self.recent_sources_button.clicked.connect(self._show_recent_sources_menu)
        layout.addWidget(self.recent_sources_button)

        self._populate_recent_menu()
        return controls

    def _show_recent_sources_menu(self) -> None:
        self._populate_recent_menu()
        button = self.recent_sources_button
        self.recent_sources_button_menu.popup(button.mapToGlobal(QPoint(0, button.height())))

    def _phone_source_controls(self) -> QWidget:
        controls = QWidget()
        controls.setObjectName("PhoneSourceControls")
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.scan_button.setMinimumWidth(108)
        layout.addWidget(self.scan_button)

        self.scan_phone_options_button = QToolButton()
        self.scan_phone_options_button.setObjectName("ScanPhoneOptionsButton")
        self.scan_phone_options_button.setToolTip("Phone package list options")
        self.scan_phone_options_button.setAccessibleName("Phone Package List Options")
        self.scan_phone_options_button.setArrowType(Qt.ArrowType.DownArrow)
        self.scan_phone_options_button.setFixedWidth(30)
        self.scan_phone_options_menu = QMenu(
            "Phone Package List Options", self.scan_phone_options_button
        )
        self.scan_phone_package_export_action = self.scan_phone_options_menu.addAction(
            "Export Current Phone Package List as CSV…", self._export_phone_packages_csv
        )
        self.scan_phone_options_button.clicked.connect(self._show_scan_phone_options_menu)
        layout.addWidget(self.scan_phone_options_button)

        self._sync_phone_package_export_actions()
        return controls

    def _show_scan_phone_options_menu(self) -> None:
        self._sync_phone_package_export_actions()
        button = self.scan_phone_options_button
        self.scan_phone_options_menu.popup(button.mapToGlobal(QPoint(0, button.height())))

    def _apk_source_controls(self) -> QWidget:
        controls = QWidget()
        controls.setObjectName("ApkSourceControls")
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self.choose_apk_button.setMinimumWidth(145)
        layout.addWidget(self.choose_apk_button)
        self.local_apk_options_menu = QMenu("Choose Local Package Source", self.choose_apk_button)
        self.local_apk_options_menu.addAction(self.choose_apk_file_action)
        self.local_apk_options_menu.addAction(self.choose_apk_folder_action)
        self.choose_apk_button.setMenu(self.local_apk_options_menu)
        # Compatibility alias for integrations that query the source control.
        self.local_apk_options_button = self.choose_apk_button
        return controls

    def _show_local_apk_options_menu(self) -> None:
        button = self.local_apk_options_button
        self.local_apk_options_menu.popup(button.mapToGlobal(QPoint(0, button.height())))

    # ---------- UX ----------
    def _source_option(self, label_text: str, button) -> QFrame:
        frame = QFrame()
        frame.setObjectName("SourceOption")
        frame.setStyleSheet(
            "QFrame#SourceOption {background:#F8FAFC; border:1px solid #E3E9EE; border-radius:8px;}"
        )
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 6, 5)
        layout.setSpacing(8)
        label = QLabel(label_text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        layout.addWidget(label)
        layout.addStretch(1)
        button.setMinimumWidth(108)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(button)
        return frame

    def _rebuild_source_area_v10(self) -> None:
        source_card = self.path_edit.parentWidget()
        source_layout = source_card.layout() if source_card is not None else None
        if source_layout is None:
            return

        source_title = next(
            (
                child
                for child in source_card.findChildren(QLabel)
                if child.text().strip().casefold() == "app source"
            ),
            None,
        )
        keep = {
            self.path_edit,
            self.choose_button,
            self.scan_button,
            self.choose_apk_button,
            self.country_edit,
            self.exclude_system_source_check,
            self.source_label,
        }
        if source_title is not None:
            keep.add(source_title)

        _detach_layout(source_layout, keep)
        self.path_edit.hide()
        source_layout.setContentsMargins(16, 12, 16, 11)
        source_layout.setSpacing(7)

        if source_title is None:
            source_title = QLabel("App Source")
            source_title.setObjectName("SectionTitle")
        else:
            source_title.setText("App Source")
        source_layout.addWidget(source_title)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.choose_button.setText("Choose File")
        self.choose_button.setIcon(main_action_icon("choose_file", self.palette()))
        self.scan_button.setText("Scan Phone")
        self.scan_button.setIcon(main_action_icon("scan_phone", self.palette()))
        self.export_button.setIcon(main_action_icon("export_results", self.palette()))

        # Build dependent controls in lifecycle order, then present them in the
        # product order below. Phone availability synchronisation expects the
        # Local APK dropdown to exist already.
        file_controls = self._file_source_controls()
        apk_controls = self._apk_source_controls()
        phone_controls = self._phone_source_controls()
        row.addWidget(
            self._source_option("Android Phone (ADB)", phone_controls), 1
        )
        or_label = QLabel("or")
        or_label.setObjectName("Muted")
        row.addWidget(or_label)
        row.addWidget(self._source_option("Local APK(s)", apk_controls), 1)
        apk_or_label = QLabel("or")
        apk_or_label.setObjectName("Muted")
        row.addWidget(apk_or_label)
        row.addWidget(self._source_option("App List File", file_controls), 1)
        row.addSpacing(10)

        country_label = QLabel("Store Country")
        country_label.setToolTip("Google Play market detected from the desktop operating-system region.")
        row.addWidget(country_label)
        self.country_edit.setFixedWidth(54)
        row.addWidget(self.country_edit)
        row.addSpacing(4)
        row.addWidget(self.exclude_system_source_check)
        source_layout.addLayout(row)

        self.source_label.setObjectName("Muted")
        self.source_label.setWordWrap(False)
        source_layout.addWidget(self.source_label)

    # ---------- Transient Local APK source ----------
    def _has_loaded_source(self) -> bool:
        if local_apk_audit.is_local_apk_source(self.source_mode):
            return bool(self._local_apk_candidates)
        return super()._has_loaded_source()

    def _sync_action_availability(self) -> None:
        super()._sync_action_availability()
        if not hasattr(self, "choose_apk_button"):
            return
        idle = not self._operation_running()
        local_source = local_apk_audit.is_local_apk_source(self.source_mode)
        self.choose_apk_button.setEnabled(idle)
        self.file_choose_apk_action.setEnabled(idle)
        self.file_choose_apk_folder_action.setEnabled(idle)
        self.choose_apk_folder_action.setEnabled(idle)
        self.local_apk_options_button.setEnabled(idle)
        self.exclude_system_source_check.setEnabled(idle and not local_source)
        self.hide_system_check.setEnabled(idle and not local_source)
        if local_source:
            self.recheck_problematic_action.setEnabled(False)
            self.details_panel.review_changes_button.setEnabled(False)

    def _set_audit_source_controls_enabled(self, enabled: bool) -> None:
        super()._set_audit_source_controls_enabled(enabled)
        if hasattr(self, "choose_apk_button"):
            self.choose_apk_button.setEnabled(enabled)
            self.file_choose_apk_action.setEnabled(enabled)
            self.file_choose_apk_folder_action.setEnabled(enabled)
            self.choose_apk_folder_action.setEnabled(enabled)
            self.local_apk_options_button.setEnabled(enabled)
        self.exclude_system_source_check.setEnabled(
            enabled and not local_apk_audit.is_local_apk_source(self.source_mode)
        )

    def _visible_column_order(self) -> list[str]:
        settings = state.load_settings()
        preset = normalise_view_preset(settings.get("view_preset"))
        if preset == "Custom":
            return super()._visible_column_order()
        selected = settings.get("technical_columns", [])
        return visible_columns(
            preset,
            self.source_mode,
            compare_previous=bool(settings.get("compare_previous", False)),
            health_score_enabled=bool(settings.get("health_score_enabled", False)),
            optional_columns=selected if isinstance(selected, list) else (),
        )

    def _apply_established_source_defaults(self) -> None:
        settings = state.load_settings()
        preset = normalise_view_preset(settings.get("view_preset"))
        if preset in BUILTIN_PRESETS:
            self._apply_column_visibility(reset_order=True)
        self._apply_source_default_sort()

    def _apply_source_default_sort(self) -> None:
        column = (
            "local_apk_version_comparison"
            if local_apk_audit.is_local_apk_source(self.source_mode)
            else "criticality"
        )
        self.table.sortByColumn(
            self.model.columns.index(column),
            Qt.SortOrder.AscendingOrder,
        )

    def _choose_local_apks(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose local Android package files",
            "",
            "Android package files (*.apk *.apks *.apkm *.xapk)",
        )
        if selected:
            self._begin_local_apk_parse([Path(path) for path in selected])

    def _choose_local_apk_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose folder containing Android package files"
        )
        if selected:
            self._begin_local_apk_folder_discovery(Path(selected))

    def _invalidate_local_apk_parse(self, *, clear_artifacts: bool = False) -> None:
        self._local_apk_parse_cancel_event.set()
        self._local_apk_parse_generation += 1
        self._local_apk_parse_active = False
        if clear_artifacts:
            self._local_apk_candidates = ()

    def _clear_source_result_rows(self) -> None:
        self._invalidate_progressive_presentation(reset_counts=True)
        self._begin_icon_result_generation()
        self.current_rows = []
        self._results_incomplete = False
        self.current_system_packages = set()
        self._last_inventory_changes = {}
        self.model.set_rows([])
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        if hasattr(self, "details_panel"):
            self.details_panel.clear()
        self._update_summary()

    def _schedule_first_audit(self) -> None:
        """Queue exactly one audit for the source just established by the user."""

        self._source_establishment_generation += 1
        generation = self._source_establishment_generation

        def start_if_current() -> None:
            if (
                generation == self._source_establishment_generation
                and self._audit_state is AuditRunState.IDLE
                and self._has_loaded_source()
            ):
                self._start_audit()

        QTimer.singleShot(0, start_if_current)

    def _begin_local_apk_parse(self, paths: list[Path]) -> None:
        candidates = local_apk_source.normalise_explicit_apks(paths)
        self._establish_local_apk_candidates(candidates, "selected")

    def _establish_local_apk_candidates(
        self,
        candidates: tuple[Path, ...],
        description: str,
    ) -> None:
        logger.info(
            "source_established type=local_package physical_candidates=%d",
            len(candidates),
        )
        self._cancel_active_audit()
        self._invalidate_phone_scan_request(clear_session=True)
        self._invalidate_local_apk_parse(clear_artifacts=True)
        self.file_apps = []
        self.file_system_metadata = {}
        self.device_apps_all = []
        self.device_system_packages = set()
        self._device_summary = {}
        self._device_store_locale = None
        store_locale.set_active_device_store_locale(None)
        self._apply_store_country_resolution(None)
        self._local_apk_candidates = candidates
        self.source_mode = local_apk_audit.SOURCE_MODE if candidates else None
        self.path_edit.clear()
        self.source_label.setToolTip("\n".join(str(path) for path in candidates))
        self._clear_source_result_rows()
        self._set_busy(False)
        self.progress.setRange(0, max(1, len(candidates)))
        self.progress.setValue(0)
        if candidates:
            self.source_label.setText(
                f"Local package source: {len(candidates)} package file(s) {description}"
            )
            self.status_label.setText("Local package source ready. Starting audit…")
        else:
            self.source_label.setText(f"Local package source: No supported files {description}")
            self.status_label.setText("No Local APK source was established")
        self._apply_established_source_defaults()
        self._sync_action_availability()
        if candidates:
            self._schedule_first_audit()

    def _begin_local_apk_folder_discovery(self, root: Path) -> None:
        logger.info("local_package_folder_discovery started")
        self._cancel_active_audit()
        self._invalidate_phone_scan_request(clear_session=True)
        self._invalidate_local_apk_parse(clear_artifacts=True)
        self._local_apk_parse_cancel_event = threading.Event()
        request_id = self._local_apk_parse_generation
        self._local_apk_parse_active = True
        self._clear_source_result_rows()
        self._set_busy(True)
        self.stop_button.setEnabled(True)
        self.progress.setRange(0, 0)
        self.source_label.setText("Local package source: Discovering supported package files…")
        self.status_label.setText("Scanning folder names only; package contents are not being parsed.")
        self._launch_local_apk_discovery_worker(request_id, root, self._local_apk_parse_cancel_event)

    def _launch_local_apk_discovery_worker(
        self,
        request_id: int,
        root: Path,
        cancel_event: threading.Event,
    ) -> None:
        threading.Thread(
            target=self._local_apk_discovery_worker,
            args=(request_id, root, cancel_event),
            daemon=True,
        ).start()

    def _local_apk_discovery_worker(
        self,
        request_id: int,
        root: Path,
        cancel_event: threading.Event,
    ) -> None:
        try:
            result = local_apk_source.discover_folder_apks(
                root,
                cancel_event=cancel_event,
                progress_callback=lambda count, path: self.local_apk_source_signals.progress.emit(
                    request_id, count, path.name
                ),
            )
            self.local_apk_source_signals.done.emit(request_id, result, str(root))
        except Exception as exc:
            logger.exception("Local package folder discovery failed")
            if not cancel_event.is_set():
                self.local_apk_source_signals.failed.emit(request_id, str(exc))

    def _on_local_apk_discovery_progress(self, request_id: int, count: int, file_name: str) -> None:
        if request_id != self._local_apk_parse_generation or not self._local_apk_parse_active:
            return
        self.status_label.setText(f"Found {count} package file(s) • {file_name}")

    def _on_local_apk_discovery_done(self, request_id: int, value: object, selected_root: str) -> None:
        if request_id != self._local_apk_parse_generation or not self._local_apk_parse_active:
            return
        self._local_apk_parse_active = False
        self._set_busy(False)
        self.stop_button.setEnabled(False)
        if not isinstance(value, local_apk_source.LocalApkDiscoveryResult) or value.cancelled:
            self.source_label.setText("Local APK source: Folder discovery cancelled")
            self.status_label.setText("No Local APK source was established")
            self._sync_action_availability()
            return
        self._establish_local_apk_candidates(value.paths, f"found in {selected_root}")

    def _on_local_apk_discovery_failed(self, request_id: int, message: str) -> None:
        if request_id != self._local_apk_parse_generation or not self._local_apk_parse_active:
            return
        self._local_apk_parse_active = False
        self._local_apk_candidates = ()
        self.source_mode = None
        self._set_busy(False)
        self.stop_button.setEnabled(False)
        self.source_label.setText("Local package source: No supported files found")
        self.status_label.setText("Local APK folder discovery failed")
        QMessageBox.critical(self, "Local APK folder discovery failed", message)

    def _stop_audit(self) -> None:
        if self._local_apk_parse_active:
            self._invalidate_local_apk_parse(clear_artifacts=True)
            self.source_mode = None
            self._set_busy(False)
            self.stop_button.setEnabled(False)
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.source_label.setText("Local APK source: Folder discovery cancelled")
            self.status_label.setText("No Local APK source was established")
            return
        super()._stop_audit()

    def _load_input_file(self, path: str) -> None:
        previous_mode = self.source_mode
        previous_apps = self.file_apps
        self._invalidate_local_apk_parse()
        super()._load_input_file(path)
        established_now = (
            self.source_mode == "file"
            and bool(self.file_apps)
            and self.path_edit.text() == path
            and self.file_apps is not previous_apps
        )
        if established_now:
            self._invalidate_progressive_presentation(reset_counts=True)
            self._local_apk_candidates = ()
            if local_apk_audit.is_local_apk_source(previous_mode):
                self._clear_source_result_rows()
            else:
                self._begin_icon_result_generation()
            self.status_label.setText("File ready. Run the Play Store audit.")
            self._apply_established_source_defaults()
            self._set_busy(False)
            self._sync_action_availability()
            self._schedule_first_audit()

    def _set_view_preset(self, name: str) -> None:
        # View changes are presentation-only and must not overwrite a useful
        # audit/progress/result message in the native status bar.
        status_text = self.status_label.text() if hasattr(self, "status_label") else ""
        super()._set_view_preset(name)
        if hasattr(self, "status_label"):
            self.status_label.setText(status_text)

    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        if not self._is_current_scan_completion(apps, system_packages):
            return
        super()._on_adb_scan_done(apps, system_packages)
        if self.source_mode == "device":
            self._local_apk_candidates = ()
            self._apply_established_source_defaults()
            self._sync_action_availability()
            logger.info(
                "source_established type=android_phone physical_candidates=1 packages=%d",
                len(self.device_apps_all),
            )
            if self.device_apps_all and not self._audit_active:
                self._schedule_first_audit()

    # ---------- Audit progress/finalization ----------
    def _restore_device_source_identity(self) -> None:
        if self.source_mode != "device":
            return
        summary = getattr(self, "_device_summary", {})
        if not isinstance(summary, dict):
            return
        identity = results_ui._device_source_identity(summary)
        if not identity:
            return

        current = self.source_label.text().strip()
        for prefix in ("Phone scan:", "Phone source:"):
            if current.startswith(prefix):
                current = current[len(prefix) :].strip()
                break
        if current.startswith(identity):
            current = current[len(identity) :].lstrip(" •")
        self.source_label.setText(
            f"Phone source: {identity} • {current}" if current else f"Phone source: {identity}"
        )

    def _start_audit(self) -> None:
        was_active = self._audit_active
        started_at = time.perf_counter() if not was_active else None
        if (
            local_apk_audit.is_local_apk_source(self.source_mode)
            and self._audit_state is AuditRunState.IDLE
        ):
            self._start_local_apk_audit()
        else:
            super()._start_audit()
        if was_active or not self._audit_active:
            return

        self._last_inventory_changes = {}
        self._update_summary()
        self._audit_started_at = started_at
        self._audit_pre_finalize_seconds = None
        self._audit_source_at_start = str(self.source_mode or "unknown")
        self._audit_performance_logged_session = None
        self._audit_cached_count = max(0, self.progress.value())
        total = max(0, self.progress.maximum())
        self._audit_live_count = max(0, total - self._audit_cached_count)
        self._restore_device_source_identity()
        self.status_label.setText(
            "Audit running • "
            f"{self._audit_cached_count} cached • {self._audit_live_count} live"
        )

    def _start_local_apk_audit(self) -> None:
        candidates = self._local_apk_candidates
        if not candidates:
            QMessageBox.warning(self, "No APK source", "Choose APK file(s) or a folder first.")
            return
        logger.info("local_package_audit started candidates=%d", len(candidates))
        source_mode = str(self.source_mode)
        self.user_settings = state.load_settings()
        country = (
            self.country_edit.text().strip()
            or runtime.detect_host_store_country()
            or "us"
        ).lower()
        language = str(self.user_settings.get("store_language") or "en").lower()
        device_metadata.set_fallback_countries(
            self.user_settings.get(
                "fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES
            ),
            country,
        )
        config = AuditConfig(
            country=country,
            language=language,
            max_workers=state.normalise_store_workers(
                self.user_settings.get("store_workers")
            ),
        )
        force_refresh = bool(getattr(self, "_force_refresh_next", False))
        self._force_refresh_next = False
        self._apps_override = None
        self._merge_base_rows = None
        self.current_system_packages = set()
        self.criticality_filter = None
        self._sync_criticality_buttons()
        self.current_rows = []
        self._results_incomplete = True
        self._progressive_sorting_was_enabled = self.table.isSortingEnabled()
        if self._progressive_sorting_was_enabled:
            self.table.setSortingEnabled(False)
        self._begin_icon_result_generation()
        self.model.set_rows([])
        self.export_button.setEnabled(False)
        self.progress.setRange(0, len(candidates))
        self.progress.setValue(0)
        self._audit_session += 1
        session = self._audit_session
        self._begin_progressive_presentation(session, self.current_rows)
        self._audit_requested_outcome = None
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, len(candidates), "")
        self._alternative_phase_active = False
        self._set_audit_source_controls_enabled(False)
        self._set_audit_state(AuditRunState.RUNNING)
        threading.Thread(
            target=self._local_apk_audit_worker,
            args=(
                candidates,
                config,
                dict(self.user_settings),
                session,
                self._audit_pause_event,
                self._audit_cancel_event,
                force_refresh,
                source_mode,
            ),
            daemon=True,
        ).start()

    def _local_artifact_store_service(self) -> LocalArtifactStoreService:
        return LocalArtifactStoreService()

    def _local_apk_audit_worker(
        self,
        candidates: tuple[Path, ...],
        config: AuditConfig,
        settings: dict[str, object],
        session: int,
        pause_event: threading.Event,
        cancel_event: threading.Event,
        force_refresh: bool,
        source_mode: str = local_apk_audit.SOURCE_MODE,
    ) -> None:
        parse_started = time.perf_counter()
        artifacts: list[LocalArtifact] = []
        failures: list[LocalArtifactParseFailure] = []
        unexpected_failures: list[str] = []
        for index, path in enumerate(candidates, start=1):
            if cancel_event.is_set():
                break
            pause_event.wait()
            if cancel_event.is_set():
                break
            try:
                parsed = (
                    local_apk.parse_local_apk(path)
                    if path.suffix.casefold() == ".apk"
                    else local_package_container.parse_local_package(
                        path, cancel_event=cancel_event
                    )
                )
            except Exception as exc:
                logger.exception(
                    "Unexpected local package parser failure: format=%s",
                    path.suffix.casefold().lstrip("."),
                )
                unexpected_failures.append(f"{path.name}: {type(exc).__name__}")
            else:
                if parsed.artifact is not None:
                    artifacts.append(parsed.artifact)
                    if path.suffix.casefold() != ".apk":
                        logger.info(
                            "local_container_accepted format=%s",
                            path.suffix.casefold().lstrip("."),
                        )
                    self.audit_control_signals.row_available.emit(
                        session,
                        local_apk_audit.artifact_result_row(
                            parsed.artifact,
                            source_mode=source_mode,
                            provisional=True,
                        ),
                    )
                    if index == 1 or index == len(candidates) or index % 25 == 0:
                        logger.info(
                            "local_parse_progress parsed=%d total=%d provisional_rows=%d",
                            index,
                            len(candidates),
                            len(artifacts),
                        )
                elif parsed.failure is not None:
                    if parsed.failure.kind is not LocalArtifactFailureKind.CANCELLED:
                        logger.info(
                            "local_container_rejected format=%s reason=%s",
                            path.suffix.casefold().lstrip("."),
                            parsed.failure.kind.value,
                        )
                        failures.append(parsed.failure)
            self.audit_control_signals.progress.emit(
                session, index, len(candidates), f"Parsing package • {path.name}"
            )
        logger.info(
            "local_parse_complete valid=%d rejected=%d cancelled=%s",
            len(artifacts),
            len(failures) + len(unexpected_failures),
            cancel_event.is_set(),
        )
        parse_ms = round(max(0.0, time.perf_counter() - parse_started) * 1000)
        failure_lines = [
            f"{failure.path.name}: {failure.kind.value.replace('_', ' ')}"
            for failure in failures[:5]
        ]
        failure_lines.extend(unexpected_failures[: max(0, 5 - len(failure_lines))])
        omitted_failures = len(failures) + len(unexpected_failures) - len(failure_lines)
        if omitted_failures > 0:
            failure_lines.append(f"…and {omitted_failures} more")

        if not artifacts:
            outcome = AuditRunOutcome.STOPPED if cancel_event.is_set() else AuditRunOutcome.FAILED
            self.audit_control_signals.done.emit(
                AuditRunResult(
                    session=session,
                    outcome=outcome,
                    total_count=len(candidates),
                    error="No selected package file could be parsed."
                    if not cancel_event.is_set()
                    else "",
                    metadata={
                        "source_mode": source_mode,
                        "physical_count": len(candidates),
                        "package_count": 0,
                        "parse_ms": parse_ms,
                        "store_ms": 0,
                        "parse_failure_count": len(failures) + len(unexpected_failures),
                        "parse_failure_summary": "\n".join(failure_lines),
                    },
                )
            )
            return

        if cancel_event.is_set():
            self.audit_control_signals.done.emit(
                AuditRunResult(
                    session=session,
                    outcome=AuditRunOutcome.STOPPED,
                    rows=[
                        local_apk_audit.artifact_result_row(
                            artifact,
                            source_mode=source_mode,
                            provisional=True,
                        )
                        for artifact in artifacts
                    ],
                    total_count=len(candidates),
                    metadata={
                        "source_mode": source_mode,
                        "physical_count": len(candidates),
                        "package_count": len(
                            {artifact.package_lookup_key for artifact in artifacts}
                        ),
                        "parse_ms": parse_ms,
                        "store_ms": 0,
                        "parse_failure_count": len(failures) + len(unexpected_failures),
                        "parse_failure_summary": "\n".join(failure_lines),
                    },
                )
            )
            return

        artifact_counts: dict[str, int] = {}
        for artifact in artifacts:
            artifact_counts[artifact.package_lookup_key] = (
                artifact_counts.get(artifact.package_lookup_key, 0) + 1
            )
        completed_artifacts = 0
        completed_store_rows: dict[str, dict[str, Any]] = {}

        artifacts_by_package: dict[str, list[LocalArtifact]] = {}
        for artifact in artifacts:
            artifacts_by_package.setdefault(artifact.package_lookup_key, []).append(artifact)

        def row_completed(package_name: str, store_row: dict[str, Any]) -> None:
            if session != self._audit_session:
                return
            completed_store_rows[package_name] = dict(store_row)
            for artifact in artifacts_by_package.get(package_name, []):
                self.audit_control_signals.row_available.emit(
                    session,
                    local_apk_audit.artifact_result_row(
                        artifact,
                        store_row,
                        source_mode=source_mode,
                        provisional=True,
                    ),
                )

        def progress(_done: int, _total: int, package_name: str) -> None:
            nonlocal completed_artifacts
            if session != self._audit_session:
                return
            completed_artifacts += artifact_counts.get(package_name, 0)
            self.audit_control_signals.progress.emit(
                session,
                min(completed_artifacts, len(candidates)),
                len(candidates),
                package_name,
            )

        store_started = time.perf_counter()
        try:
            result = self._local_artifact_store_service().collect(
                tuple(artifacts),
                config,
                settings,
                force_refresh=force_refresh,
                pause_event=pause_event,
                cancel_event=cancel_event,
                progress_callback=progress,
                alternative_phase_callback=lambda eligible: self.audit_control_signals.alternative_phase.emit(
                    session, eligible
                ),
                row_completed_callback=row_completed,
            )
            rows = local_apk_audit.association_result_rows(
                result.associations,
                source_mode=source_mode,
            )
            cached_count = sum(1 for row in rows if row.get("cache_hit"))
            outcome = (
                AuditRunOutcome.STOPPED
                if cancel_event.is_set()
                or self._audit_requested_outcome is AuditRunOutcome.STOPPED
                else AuditRunOutcome.SUCCESS
            )
            if (
                session == self._audit_session
                and self._audit_requested_outcome is not AuditRunOutcome.ABANDONED
            ):
                self.audit_control_signals.done.emit(
                    AuditRunResult(
                        session=session,
                        outcome=outcome,
                        rows=rows,
                        cached_count=cached_count,
                        live_completed_count=max(0, len(rows) - cached_count),
                        total_count=len(candidates),
                        metadata={
                            "source_mode": source_mode,
                            "physical_count": len(candidates),
                            "package_count": len(artifacts_by_package),
                            "parse_ms": parse_ms,
                            "store_ms": round(
                                max(0.0, time.perf_counter() - store_started) * 1000
                            ),
                            "issues": list(result.issues),
                            "parse_failure_count": len(failures) + len(unexpected_failures),
                            "parse_failure_summary": "\n".join(failure_lines),
                        },
                    )
                )
        except Exception as exc:
            logger.exception("Local APK Store audit failed")
            if (
                session == self._audit_session
                and self._audit_requested_outcome is not AuditRunOutcome.ABANDONED
            ):
                partial_rows = [
                    local_apk_audit.artifact_result_row(
                        artifact,
                        completed_store_rows[artifact.package_lookup_key],
                        source_mode=source_mode,
                    )
                    for artifact in artifacts
                    if artifact.package_lookup_key in completed_store_rows
                ]
                self.audit_control_signals.done.emit(
                    AuditRunResult(
                        session=session,
                        outcome=AuditRunOutcome.FAILED,
                        rows=partial_rows,
                        cached_count=sum(
                            1 for row in partial_rows if row.get("cache_hit")
                        ),
                        live_completed_count=sum(
                            1 for row in partial_rows if not row.get("cache_hit")
                        ),
                        total_count=len(candidates),
                        error=str(exc),
                        metadata={
                            "source_mode": source_mode,
                            "physical_count": len(candidates),
                            "package_count": len(artifacts_by_package),
                            "parse_ms": parse_ms,
                            "store_ms": round(
                                max(0.0, time.perf_counter() - store_started) * 1000
                            ),
                            "parse_failure_count": len(failures)
                            + len(unexpected_failures),
                            "parse_failure_summary": "\n".join(failure_lines),
                        },
                    )
                )

    def _promote_successful_audit(self, result: AuditRunResult) -> bool:
        if local_apk_audit.is_local_apk_source(result.metadata.get("source_mode")):
            return False
        return super()._promote_successful_audit(result)

    def _row_action_availability(
        self, row: dict[str, Any]
    ) -> RowActionAvailability:
        availability = super()._row_action_availability(row)
        if local_apk_audit.is_local_apk_source(row.get("source_mode")):
            return replace(availability, recheck=False, app_info=False)
        return availability

    def _open_local_apk_location(self, location: str) -> None:
        opened, message = open_file_location(location)
        if not opened:
            QMessageBox.information(self, "File location unavailable", message)

    def _on_controlled_progress(
        self, session: int, done: int, total: int, package_name: str
    ) -> None:
        super()._on_controlled_progress(session, done, total, package_name)
        if (
            session != self._audit_session
            or not self._audit_active
            or self._audit_paused
            or self._audit_state is AuditRunState.STOPPING
        ):
            return
        if (
            local_apk_audit.is_local_apk_source(self.source_mode)
            and package_name.startswith("Parsing package • ")
        ):
            self.status_label.setText(
                f"Parsing package files • {done}/{total} • "
                f"{package_name.removeprefix('Parsing package • ')}"
            )
            return

        cached = min(max(0, self._audit_cached_count), total)
        live_total = max(0, total - cached)
        live_done = min(max(0, done - cached), live_total)
        if live_total:
            package_suffix = f" • {package_name}" if package_name else ""
            self.status_label.setText(
                f"Checking Play Store • {live_done}/{live_total} live • {cached} cached"
                f"{package_suffix}"
            )
        else:
            self.status_label.setText(f"Using cached results • {cached}/{total} cached")

    def _on_controlled_done(self, payload: object) -> None:
        result = compact_ui.coerce_audit_run_result(payload)
        if result.session != self._audit_session or result.outcome is AuditRunOutcome.ABANDONED:
            return
        self._invalidate_progressive_presentation()
        parse_failure_count = int(result.metadata.get("parse_failure_count") or 0)
        if parse_failure_count:
            summary = str(result.metadata.get("parse_failure_summary") or "").strip()
            QMessageBox.warning(
                self,
                "Some package files could not be parsed",
                f"{parse_failure_count} package file(s) were rejected. Valid files were retained."
                + (f"\n\n{summary}" if summary else ""),
            )
        if self._audit_started_at is not None:
            self._audit_pre_finalize_seconds = max(0.0, time.perf_counter() - self._audit_started_at)

        self._finalizing_session = result.session
        self._audit_pause_event.set()
        self._set_audit_source_controls_enabled(False)
        self._set_audit_state(AuditRunState.FINALIZING)
        self.export_button.setEnabled(False)
        self.progress.setRange(0, 0)
        if result.outcome is AuditRunOutcome.STOPPED:
            prefix = "Finalizing stopped audit results"
        elif result.outcome is AuditRunOutcome.FAILED:
            prefix = "Finalizing partial audit results"
        else:
            prefix = "Finalizing audit results"
        self.status_label.setText(
            f"{prefix} • {result.cached_count} cached • {result.live_completed_count} live"
        )
        QTimer.singleShot(0, lambda: self._complete_controlled_done(result))

    def _complete_controlled_done(self, payload: object) -> None:
        result = compact_ui.coerce_audit_run_result(payload)
        if (
            result.session != self._audit_session
            or self._finalizing_session != result.session
            or result.outcome is AuditRunOutcome.ABANDONED
        ):
            return
        result_finalized = False
        try:
            try:
                if self._merge_base_rows is None:
                    # Full replacement must not pair this generation's rows
                    # with the previous audit's inventory aggregate. Targeted
                    # Store rechecks retain the existing inventory/merged rows.
                    self._last_inventory_changes = {}
                super()._on_controlled_done(result)
                result_finalized = True
            except Exception as exc:
                result.outcome = AuditRunOutcome.FAILED
                result.error = str(exc)
                self._last_audit_outcome = AuditRunOutcome.FAILED
                self.status_label.setText("Audit failed during finalization")
                self.export_button.setEnabled(False)
                QMessageBox.critical(self, "Audit failed", str(exc))
            if result_finalized and result.outcome is AuditRunOutcome.SUCCESS:
                inventory_changed = False
                try:
                    inventory_changed = self._promote_successful_audit(result)
                except Exception as exc:
                    # Persistence is deliberately outside result finalization.
                    # A defensive catch keeps an unexpected save-path error
                    # from rewriting a successfully finalized audit outcome.
                    self._report_baseline_persistence_issue(
                        stage="unexpected",
                        history_status="unknown",
                        inventory_status="unknown",
                        error=exc,
                    )
                if inventory_changed:
                    try:
                        self._sync_post_audit_views()
                    except Exception as exc:
                        device_insights.log_event(
                            "audit_post_success_refresh result=error "
                            f"error={' '.join(str(exc).split())[:500] or type(exc).__name__}"
                        )
        finally:
            self._finalizing_session = None
            self._set_audit_source_controls_enabled(True)
            self._set_audit_state(AuditRunState.IDLE)
            self._restore_device_source_identity()

        if (
            self._audit_started_at is not None
            and self._audit_performance_logged_session != result.session
        ):
            total_seconds = max(0.0, time.perf_counter() - self._audit_started_at)
            physical_count = int(result.metadata.get("physical_count") or 0)
            package_count = int(
                result.metadata.get("package_count", result.total_count)
            )
            device_insights.log_event(
                "audit_performance "
                f"source={self._audit_source_at_start or self.source_mode or 'unknown'} "
                f"outcome={result.outcome.value} physical={physical_count} "
                f"packages={package_count} "
                f"parse_ms={int(result.metadata.get('parse_ms') or 0)} "
                f"store_ms={int(result.metadata.get('store_ms') or 0)} "
                f"total_ms={round(total_seconds * 1000)} "
                f"cached={result.cached_count} live={result.live_completed_count} "
                f"progressive_payloads={self._progressive_payload_count} "
                f"progressive_refreshes={self._progressive_refresh_count}"
            )
            self._audit_performance_logged_session = result.session
        self._audit_started_at = None
        self._audit_pre_finalize_seconds = None
        self._audit_source_at_start = None

    # ---------- Cross-platform ADB ----------
    def _find_adb(self) -> str | None:
        return find_adb()

    def _scan_phone(self) -> None:
        self._invalidate_progressive_presentation(reset_counts=True)
        self._invalidate_local_apk_parse(clear_artifacts=True)
        if local_apk_audit.is_local_apk_source(self.source_mode):
            self.source_mode = None
            self._clear_source_result_rows()
            self._apply_column_visibility(reset_order=False)
        else:
            self._begin_icon_result_generation()
        request_id = self._begin_phone_scan_request()
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Looking for ADB…")
        threading.Thread(target=self._find_adb_worker, args=(request_id,), daemon=True).start()

    def _find_adb_worker(self, request_id: int) -> None:
        try:
            self.signals.adb_discovery_done.emit(self._find_adb(), request_id)
        except Exception as exc:
            self.signals.adb_scan_failed.emit(
                request_id, f"ADB discovery failed:\n\n{exc}"
            )

    def _on_adb_discovery_done(self, adb: str | None, request_id: int) -> None:
        if request_id != self._active_scan_request_id:
            return
        if adb:
            self._start_adb_scan(adb, request_id)
            return

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("ADB not found")
        self._set_busy(False)
        if not runtime.managed_platform_tools_download_supported():
            self._active_scan_request_id = None
            QMessageBox.information(
                self,
                "Native ADB required",
                runtime.managed_platform_tools_unavailable_message(),
            )
            return

        choice = QMessageBox.question(
            self,
            "Install Android Platform-Tools?",
            f"ADB is not installed on this {runtime.platform_label()} computer.\n\n"
            "Play Store App Audit can download the latest Android Platform-Tools "
            "directly from Google's official download endpoint for this operating system.\n\n"
            "Continue?\n\n"
            "By continuing, you confirm that you have reviewed and accept the Android SDK terms.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if choice == QMessageBox.StandardButton.Cancel:
            self._active_scan_request_id = None
            return
        if choice == QMessageBox.StandardButton.No:
            self._active_scan_request_id = None
            QDesktopServices.openUrl(QUrl(runtime.PLATFORM_TOOLS_PAGE))
            return
        self.pending_scan_after_install = True
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Downloading Android Platform-Tools from Google…")
        threading.Thread(target=self._install_platform_tools_worker, daemon=True).start()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._source_establishment_generation += 1
        self._invalidate_local_apk_parse(clear_artifacts=True)
        super().closeEvent(event)

    def _install_platform_tools_worker(self) -> None:
        try:
            adb, version_text = install_platform_tools()
            self.signals.adb_install_done.emit(adb, version_text)
        except Exception as exc:
            self.signals.failed.emit(f"ADB installation failed:\n\n{exc}")
