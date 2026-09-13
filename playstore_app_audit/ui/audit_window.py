from __future__ import annotations

import threading

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit.services import scan_session as scan_sessions
from playstore_app_audit.services import state
from playstore_app_audit.services.audit_engine import AuditConfig, load_apps
from playstore_app_audit.ui import schema
from playstore_app_audit.ui.action_icons import main_action_icon
from playstore_app_audit.ui.base_window import (
    APP_NAME,
    CRITICALITY,
    BaseWindow,
    detect_windows_country,
)


class AuditWindow(BaseWindow):
    """Qt 6 UI branch.

    Functional policy shared with the CustomTkinter branch:
    - Store language is always English and is not exposed in the UI.
    - System apps can be excluded at source-load / ADB-scan time.
    - Hide system apps remains a result-table display filter when system apps were loaded.
    """

    def __init__(self) -> None:
        self._apk_relationship_filters: set[str] = set()
        self._scan_request_sequence = 0
        self._active_scan_request_id: int | None = None
        self._scan_session: scan_sessions.ScanSession | None = None
        self._scan_cancel_event = threading.Event()
        super().__init__()

    def _begin_phone_scan_request(self) -> int:
        self._scan_cancel_event.set()
        self._scan_cancel_event = threading.Event()
        self._scan_request_sequence += 1
        self._active_scan_request_id = self._scan_request_sequence
        return self._scan_request_sequence

    def _invalidate_phone_scan_request(self, *, clear_session: bool = False) -> None:
        self._scan_cancel_event.set()
        self._scan_request_sequence += 1
        self._active_scan_request_id = None
        self.pending_scan_after_install = False
        if clear_session:
            self._scan_session = None

    def _is_current_scan_completion(self, payload: object, request: object) -> bool:
        if not isinstance(payload, scan_sessions.ScanSession):
            return True
        try:
            request_id = int(request)
        except (TypeError, ValueError):
            return False
        return request_id == self._active_scan_request_id

    def _set_apk_relationship_filter(self, relationship: str) -> None:
        if relationship == "All":
            self._apk_relationship_filters.clear()
        elif relationship in self._apk_relationship_filters:
            self._apk_relationship_filters.remove(relationship)
        else:
            self._apk_relationship_filters.add(relationship)
        setter = getattr(self.proxy, "set_relationship_filters", None)
        if callable(setter):
            setter(self._apk_relationship_filters)
        self._sync_apk_relationship_buttons()
        self._update_summary()

    def _sync_apk_relationship_buttons(self) -> None:
        for relationship, button in self.apk_relationship_buttons.items():
            button.setChecked(
                not self._apk_relationship_filters
                if relationship == "All"
                else relationship in self._apk_relationship_filters
            )
        hidden = self._apk_relationship_filters & {"Different", "Unknown"}
        self.apk_relationship_more.setChecked(bool(hidden))
        self.apk_relationship_more.setText(
            f"More ({len(hidden)}) ▾" if hidden else "More ▾"
        )
        for relationship, action in self.apk_relationship_more_actions.items():
            action.setChecked(relationship in hidden)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("Central")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)

        title = QLabel("Play Store App Audit")
        title.setObjectName("Title")
        subtitle = QLabel(
            "Check Android packages against Google Play, classify update risk and inspect everything in one table."
        )
        subtitle.setObjectName("Subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        top_row = QHBoxLayout()
        top_row.setSpacing(12)
        root.addLayout(top_row)

        source_card, source_layout = self._card()
        top_row.addWidget(source_card, 3)
        source_title = QLabel("App Source")
        source_title.setObjectName("SectionTitle")
        source_layout.addWidget(source_title)

        source_line = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Choose a CSV / TSV / TXT file, or scan your Android phone")
        self.path_edit.setReadOnly(True)
        self.choose_button = QPushButton("Choose File")
        self.choose_button.setIcon(main_action_icon("choose_file", self.palette()))
        self.choose_button.clicked.connect(self._choose_input)
        self.scan_button = QPushButton("Scan Phone with ADB")
        self.scan_button.setIcon(main_action_icon("scan_phone", self.palette()))
        self.scan_button.clicked.connect(self._scan_phone)
        source_line.addWidget(self.path_edit, 1)
        source_line.addWidget(self.choose_button)
        source_line.addWidget(self.scan_button)
        source_layout.addLayout(source_line)

        self.exclude_system_source_check = QCheckBox("Exclude System Apps When Loading / Scanning")
        source_settings = getattr(self, "user_settings", {})
        self.exclude_system_source_check.setChecked(
            bool(source_settings.get("exclude_system_source", True))
        )
        self.exclude_system_source_check.setToolTip(
            "ADB: load third-party packages only. CSV: remove packages classified as system while loading. "
            "Leave disabled to load everything and use 'Hide System Apps' only as a table filter."
        )
        source_layout.addWidget(self.exclude_system_source_check)

        self.source_label = QLabel("No app list selected")
        self.source_label.setObjectName("Muted")
        self.source_label.setWordWrap(True)
        source_layout.addWidget(self.source_label)

        settings_card, settings_layout = self._card()
        top_row.addWidget(settings_card, 2)
        settings_title = QLabel("Audit settings")
        settings_title.setObjectName("SectionTitle")
        settings_layout.addWidget(settings_title)

        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(10)
        settings_grid.setVerticalSpacing(8)
        settings_grid.addWidget(QLabel("Country"), 0, 0)
        self.country_edit = QLineEdit(detect_windows_country())
        self.country_edit.setMaxLength(2)
        self.country_edit.setFixedWidth(70)
        self.country_edit.setToolTip("Google Play market detected from the Windows region.")
        settings_grid.addWidget(self.country_edit, 0, 1)

        settings_grid.addWidget(QLabel("Parallel threads"), 0, 2)
        self.workers_spin = QSpinBox()
        self.workers_spin.setRange(1, 32)
        self.workers_spin.setValue(16)
        self.workers_spin.setFixedWidth(80)
        settings_grid.addWidget(self.workers_spin, 0, 3)

        hint = QLabel("Country controls Store availability. Store language is fixed internally to English.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        settings_grid.addWidget(hint, 1, 0, 1, 4)
        settings_layout.addLayout(settings_grid)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        root.addLayout(action_row)
        self.run_button = QPushButton("Run Play Store Audit")
        self.run_button.setObjectName("Primary")
        self.run_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.run_button.clicked.connect(self._start_audit)
        action_row.addWidget(self.run_button, 1)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setEnabled(False)
        self.stop_button.setToolTip(
            "Stop cooperatively after already-running Store and ADB operations finish."
        )
        self.stop_button.clicked.connect(self._stop_audit)
        action_row.addWidget(self.stop_button)

        self.export_button = QPushButton("Export Results")
        self.export_button.setEnabled(False)
        self.export_button.setIcon(main_action_icon("export_results", self.palette()))
        self.export_button.clicked.connect(self._export_results)
        action_row.addWidget(self.export_button)

        self.clear_button = QPushButton("Clear Results")
        self.clear_button.clicked.connect(self._clear_results)
        action_row.addWidget(self.clear_button)

        progress_card, progress_layout = self._card()
        root.addWidget(progress_card)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("Muted")
        progress_layout.addWidget(self.progress)
        progress_layout.addWidget(self.status_label)

        results_card, results_layout = self._card()
        root.addWidget(results_card, 1)

        toolbar = QHBoxLayout()
        self.summary_label = QLabel("No Results Yet")
        self.summary_label.setObjectName("SectionTitle")
        toolbar.addWidget(self.summary_label)
        toolbar.addStretch(1)

        self.hide_system_check = QCheckBox("Hide System Apps")
        self.hide_system_check.setChecked(True)
        self.hide_system_check.toggled.connect(self._on_hide_system_changed)
        toolbar.addWidget(self.hide_system_check)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter apps…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setFixedWidth(280)
        self.search_edit.textChanged.connect(self._on_search_changed)
        toolbar.addWidget(self.search_edit)
        results_layout.addLayout(toolbar)

        chip_row = QHBoxLayout()
        chip_row.setSpacing(6)
        self.store_status_filter_label = QLabel("Store Status:")
        self.store_status_filter_label.setObjectName("StoreStatusFilterLabel")
        self.store_status_filter_label.setToolTip(
            "These filters use Store Status only; version relationships remain independent."
        )
        chip_row.addWidget(self.store_status_filter_label)
        self.all_chip = QPushButton("All")
        self.all_chip.setObjectName("CriticalityButton")
        self.all_chip.setCheckable(True)
        self.all_chip.setChecked(True)
        self.all_chip.setToolTip("Show all result classifications.")
        self.all_chip.clicked.connect(lambda _checked=False: self._set_criticality_filter(None))
        chip_row.addWidget(self.all_chip)

        self.criticality_buttons: dict[str, QPushButton] = {}
        for key in ("red", "orange", "yellow", "blue", "green"):
            info = CRITICALITY[key]
            button = QPushButton(f"{info['button']} 0")
            button.setObjectName("CriticalityButton")
            button.setCheckable(True)
            button.setToolTip(str(info["tooltip"]))
            button.setStyleSheet(
                f"QPushButton {{background:{info['background']}; color:{info['foreground']}; "
                f"border:1px solid {info['background']};}}"
                f"QPushButton:hover {{border:1px solid {info['accent']};}}"
                f"QPushButton:checked {{border:2px solid {info['accent']}; font-weight:650;}}"
            )
            button.clicked.connect(lambda checked=False, k=key: self._set_criticality_filter(k))
            self.criticality_buttons[key] = button
            chip_row.addWidget(button)
        chip_row.addStretch(1)
        results_layout.addLayout(chip_row)

        self.apk_relationship_filter_row = QWidget()
        self.apk_relationship_filter_row.setObjectName("ApkRelationshipFilterRow")
        relationship_row = QHBoxLayout(self.apk_relationship_filter_row)
        relationship_row.setContentsMargins(0, 0, 0, 0)
        relationship_row.setSpacing(6)
        relationship_row.addWidget(QLabel("APK vs Store:"))
        self.apk_relationship_buttons: dict[str, QPushButton] = {}
        for value, label in (
            ("All", "All"), ("Outdated", "Outdated"), ("Newer", "Newer"),
            ("Match", "Match"), ("Device-specific", "Device"), ("N/A", "N/A"),
        ):
            button = QPushButton(label)
            button.setObjectName(f"ApkRelationship{value.replace('-', '').replace('/', '')}Button")
            button.setCheckable(True)
            button.setToolTip(
                "The Store version varies by device; a direct order is unsafe."
                if value == "Device-specific" else f"Show Local APK results with {value} relationship."
            )
            button.clicked.connect(
                lambda _checked=False, relationship=value: self._set_apk_relationship_filter(relationship)
            )
            self.apk_relationship_buttons[value] = button
            relationship_row.addWidget(button)
        self.apk_relationship_more = QPushButton("More ▾")
        self.apk_relationship_more.setObjectName("ApkRelationshipMoreButton")
        self.apk_relationship_more.setCheckable(True)
        more_menu = QMenu(self.apk_relationship_more)
        self.apk_relationship_more_actions: dict[str, QAction] = {}
        for value in ("Different", "Unknown"):
            action = more_menu.addAction(value)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, relationship=value: self._set_apk_relationship_filter(relationship)
            )
            self.apk_relationship_more_actions[value] = action
        def show_more_menu() -> None:
            self._sync_apk_relationship_buttons()
            more_menu.popup(
                self.apk_relationship_more.mapToGlobal(
                    self.apk_relationship_more.rect().bottomLeft()
                )
            )

        self.apk_relationship_more.clicked.connect(show_more_menu)
        relationship_row.addWidget(self.apk_relationship_more)
        relationship_row.addStretch(1)
        self.apk_relationship_filter_row.setVisible(False)
        results_layout.addWidget(self.apk_relationship_filter_row)
        self._sync_apk_relationship_buttons()

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setShowGrid(True)
        self.table.setWordWrap(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setToolTip(
            "Click a column header to sort, or drag it to reorder columns."
        )
        self.table.setToolTip(
            "Double-click to open Google Play when available. Right-click for more options."
        )
        self.table.doubleClicked.connect(self._open_selected_store_url)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        results_layout.addWidget(self.table, 1)

        for column, key in enumerate(schema.MODEL_COLUMNS):
            self.table.setColumnWidth(column, schema.DEFAULT_WIDTHS.get(key, 140))

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        self.exclude_system_source_check.setEnabled(not busy)

    def _stop_audit(self) -> None:
        """Lifecycle-aware subclasses provide cooperative Stop semantics."""

    def _choose_input(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Choose App List",
            "",
            "App lists (*.csv *.tsv *.txt);;CSV (*.csv);;Text (*.txt);;All files (*.*)",
        )
        if not selected:
            return
        try:
            apps = load_apps(selected)
            metadata = self._read_system_metadata_from_file(selected, apps)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid app list", str(exc))
            return

        self.file_system_metadata = metadata
        system_packages, method = self._classify_file_system_packages(apps)
        original_count = len(apps)
        skipped = 0
        if self.exclude_system_source_check.isChecked():
            apps = [app for app in apps if app["package_name"] not in system_packages]
            skipped = original_count - len(apps)

        self.file_apps = apps
        self._invalidate_phone_scan_request(clear_session=True)
        self.device_apps_all = []
        self.device_system_packages = set()
        self.source_mode = "file"
        self.path_edit.setText(selected)
        suffix = (
            f" • {skipped} system excluded during load"
            if self.exclude_system_source_check.isChecked()
            else f" • {len(system_packages)} classified as system"
        )
        self.source_label.setText(f"File loaded: {len(apps)}/{original_count} packages{suffix} • {method}")
        self.status_label.setText("File ready. Run the Play Store audit.")

    def _start_adb_scan(self, adb: str, request_id: int | None = None) -> None:
        if request_id is None:
            request_id = self._active_scan_request_id or self._begin_phone_scan_request()
        elif request_id != self._active_scan_request_id:
            return
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Checking ADB device connection…")
        exclude_system = self.exclude_system_source_check.isChecked()
        full_scan = state.load_settings().get("collect_full_device_metadata_on_scan") is True
        if full_scan:
            self.status_label.setText("Scanning phone with extended device metadata…")
        threading.Thread(
            target=self._scan_phone_worker_branch,
            args=(adb, exclude_system, request_id, full_scan, self._scan_cancel_event),
            daemon=True,
        ).start()

    def _scan_phone_worker_branch(
        self, adb: str, exclude_system: bool, request_id: int,
        full_scan: bool = False, cancel_event: threading.Event | None = None,
    ) -> None:
        try:
            if full_scan:
                session = scan_sessions.collect_scan_session(
                    adb, exclude_system=exclude_system,
                    collect_full_metadata=True, cancel_event=cancel_event,
                )
            else:
                session = scan_sessions.collect_scan_session(adb, exclude_system=exclude_system)
            if cancel_event is not None and cancel_event.is_set():
                return
            self.signals.adb_scan_done.emit(session, request_id)
        except Exception as exc:
            if cancel_event is not None and cancel_event.is_set():
                return
            self.signals.adb_scan_failed.emit(
                request_id, f"ADB connection error:\n\n{exc}"
            )

    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        if not self._is_current_scan_completion(apps, system_packages):
            return
        session = apps if isinstance(apps, scan_sessions.ScanSession) else None
        if session is not None:
            typed_apps = [
                {"app_name": package, "package_name": package}
                for package in session.packages
            ]
            typed_system = set(session.system_packages)
            exclude_system = session.excludes_system_packages
            self._scan_session = session
            self._active_scan_request_id = None
        else:
            typed_apps = list(apps)  # type: ignore[arg-type]
            typed_system = set(system_packages)  # type: ignore[arg-type]
            exclude_system = self.exclude_system_source_check.isChecked()
        self.device_apps_all = typed_apps
        self.device_system_packages = typed_system
        self.file_apps = []
        self.file_system_metadata = {}
        self.source_mode = "device"
        self.path_edit.clear()

        if exclude_system:
            self.source_label.setText(
                f"Phone scan: {len(typed_apps)} third-party packages loaded • system apps excluded during ADB scan"
            )
        else:
            user_count = sum(1 for app in typed_apps if app["package_name"] not in typed_system)
            self.source_label.setText(
                f"Phone scan: {len(typed_apps)} total packages • {user_count} third-party • {len(typed_system)} system"
            )
        self.status_label.setText("Phone scan ready. Run the Play Store audit.")
        if session is not None and session.full_metadata_status is scan_sessions.FullMetadataStatus.INCOMPLETE:
            self.status_label.setText(
                "Phone scan ready with compact metadata. Extended metadata could not be captured."
            )
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_busy(False)

    def _on_adb_scan_failed(self, request_id: int, message: str) -> None:
        if request_id != self._active_scan_request_id:
            return
        self._active_scan_request_id = None
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("Operation failed")
        self._set_busy(False)
        QMessageBox.critical(self, "Operation failed", message)

    def _on_worker_failed(self, message: str) -> None:
        self._active_scan_request_id = None
        super()._on_worker_failed(message)

    def closeEvent(self, event) -> None:
        self._invalidate_phone_scan_request()
        super().closeEvent(event)

    def _start_audit(self) -> None:
        try:
            apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            QMessageBox.warning(self, "No app list", str(exc))
            return
        if not apps:
            QMessageBox.warning(self, "Nothing to audit", "No packages are loaded.")
            return

        country = (self.country_edit.text().strip() or detect_windows_country()).lower()
        workers = self.workers_spin.value()
        self.current_system_packages = system_packages
        self.criticality_filter = None
        self._sync_criticality_buttons()

        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_label.setText(
            f"{source_label} source: {len(apps)} packages • {len(system_packages)} classified as system • {classification_method}"
        )
        self.current_rows = []
        self.model.set_rows([])
        self._set_busy(True)
        self.progress.setRange(0, len(apps))
        self.progress.setValue(0)
        self.status_label.setText(f"Starting audit for {len(apps)} packages in Store country '{country}'…")

        config = AuditConfig(country=country, language="en", max_workers=workers)
        threading.Thread(target=self._audit_worker, args=(apps, config), daemon=True).start()


def main() -> int:
    import sys

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MRC")
    window = AuditWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
