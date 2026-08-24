from __future__ import annotations

import subprocess
import threading

from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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

from playstore_app_audit.services.audit_engine import AuditConfig, load_apps
from playstore_app_audit.ui.base_window import (
    APP_NAME,
    CRITICALITY,
    BaseWindow,
    detect_windows_country,
    parse_adb_packages,
)


class AuditWindow(BaseWindow):
    """Qt 6 UI branch.

    Functional policy shared with the CustomTkinter branch:
    - Store language is always English and is not exposed in the UI.
    - System apps can be excluded at source-load / ADB-scan time.
    - Hide system apps remains a result-table display filter when system apps were loaded.
    """

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
        self.choose_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.choose_button.clicked.connect(self._choose_input)
        self.scan_button = QPushButton("Scan Phone with ADB")
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

        self.export_button = QPushButton("Export Results")
        self.export_button.setEnabled(False)
        self.export_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
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
        self.all_chip = QPushButton("All")
        self.all_chip.setObjectName("CriticalityButton")
        self.all_chip.setCheckable(True)
        self.all_chip.setChecked(True)
        self.all_chip.setToolTip("Show all result classifications.")
        self.all_chip.clicked.connect(lambda _checked=False: self._set_criticality_filter(None))
        chip_row.addWidget(self.all_chip)

        self.criticality_buttons: dict[str, QPushButton] = {}
        for key in ("red", "orange", "yellow", "blue", "purple", "green"):
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
        self.table.setToolTip("Double-click a result row to open its Google Play page.")
        self.table.doubleClicked.connect(self._open_selected_store_url)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        results_layout.addWidget(self.table, 1)

        widths = [160, 250, 175, 110, 90, 220, 155, 320, 150]
        for column, width in enumerate(widths):
            self.table.setColumnWidth(column, width)

    def _set_busy(self, busy: bool) -> None:
        super()._set_busy(busy)
        self.exclude_system_source_check.setEnabled(not busy)

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

    def _start_adb_scan(self, adb: str) -> None:
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Checking ADB device connection…")
        exclude_system = self.exclude_system_source_check.isChecked()
        threading.Thread(
            target=self._scan_phone_worker_branch, args=(adb, exclude_system), daemon=True
        ).start()

    def _scan_phone_worker_branch(self, adb: str, exclude_system: bool) -> None:
        try:
            devices_output = subprocess.run(
                [adb, "devices"], check=True, capture_output=True, text=True, timeout=20
            ).stdout.splitlines()
            rows = [line.split() for line in devices_output[1:] if line.strip()]
            authorised = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "device"]
            unauthorised = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "unauthorized"]
            offline = [parts[0] for parts in rows if len(parts) >= 2 and parts[1] == "offline"]
            if not authorised:
                if unauthorised:
                    raise RuntimeError(
                        "The phone is visible to ADB but is not authorised. Unlock it and accept 'Allow USB debugging?', then scan again."
                    )
                if offline:
                    raise RuntimeError(
                        "The phone is visible to ADB but is offline. Reconnect the USB cable, unlock it and try again."
                    )
                raise RuntimeError(
                    "ADB is installed, but no Android phone is visible. Check USB debugging, "
                    "cable/data mode and any operating-system USB permissions or drivers."
                )

            command = [adb, "shell", "pm", "list", "packages"]
            if exclude_system:
                command.append("-3")
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)
            packages = sorted(parse_adb_packages(result.stdout))
            if not packages:
                raise RuntimeError("ADB returned no Android packages.")
            system_packages = set() if exclude_system else self._get_system_packages_from_adb(adb)
            apps = [{"app_name": package, "package_name": package} for package in packages]
            self.signals.adb_scan_done.emit(apps, system_packages)
        except Exception as exc:
            self.signals.failed.emit(f"ADB connection error:\n\n{exc}")

    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        typed_apps = list(apps)  # type: ignore[arg-type]
        typed_system = set(system_packages)  # type: ignore[arg-type]
        self.device_apps_all = typed_apps
        self.device_system_packages = typed_system
        self.file_apps = []
        self.file_system_metadata = {}
        self.source_mode = "device"
        self.path_edit.clear()

        if self.exclude_system_source_check.isChecked():
            self.source_label.setText(
                f"Phone scan: {len(typed_apps)} third-party packages loaded • system apps excluded during ADB scan"
            )
        else:
            user_count = sum(1 for app in typed_apps if app["package_name"] not in typed_system)
            self.source_label.setText(
                f"Phone scan: {len(typed_apps)} total packages • {user_count} third-party • {len(typed_system)} system"
            )
        self.status_label.setText("Phone scan ready. Run the Play Store audit.")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_busy(False)

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
