from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit.domain.local_apk_library import (
    LibraryRootScanStatus,
    LibraryScanIssueKind,
    LocalApkLibrary,
    LocalApkLibraryArtifact,
    LocalApkLibraryScanProgress,
    LocalApkLibraryScanResult,
)
from playstore_app_audit.domain.local_artifacts import LocalArtifact
from playstore_app_audit.services.local_apk_library import LocalApkLibraryService


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _normalise_selected_root(path: str | Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.path.expanduser(str(path)))))


def root_overlap_message(library: LocalApkLibrary, candidate: Path) -> str | None:
    """Explain why a newly selected root would create redundant coverage."""

    candidate = _normalise_selected_root(candidate)
    candidate_key = _path_key(candidate)
    for registered in library.roots:
        registered_key = _path_key(registered.path)
        if candidate_key == registered_key:
            return "This folder is already registered in the Local APK Library."
        try:
            common = os.path.commonpath([candidate_key, registered_key])
        except ValueError:
            continue
        if common == registered_key:
            return f"This folder is already covered by a registered parent folder:\n\n{registered.path}"
        if common == candidate_key:
            return (
                "This folder contains an already registered folder. Remove or adjust the existing "
                "registration first:\n\n"
                f"{registered.path}"
            )
    return None


def _format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "Never"
    return value.astimezone().strftime("%Y-%m-%d %H:%M")


class LocalApkLibrarySignals(QObject):
    progress = Signal(int, object)
    done = Signal(int, object)
    failed = Signal(int, str)


class LocalApkLibraryDialog(QDialog):
    audit_requested = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: LocalApkLibraryService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Local APK Library")
        self.setMinimumSize(880, 620)
        self.resize(1040, 720)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.finished.connect(lambda _result: self.deleteLater())
        self.service = service or LocalApkLibraryService()
        self.library: LocalApkLibrary | None = None
        self._scan_generation = 0
        self._scan_active = False
        self._scan_cancel_event = threading.Event()
        self._build_ui()
        self.scan_signals = LocalApkLibrarySignals(self)
        self.scan_signals.progress.connect(self._on_scan_progress)
        self.scan_signals.done.connect(self._on_scan_done)
        self.scan_signals.failed.connect(self._on_scan_failed)
        self._load_library()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        intro = QLabel(
            "Register local folders, scan standalone APK files, and audit one row per exact "
            "SHA-256 artifact. Scanning occurs only when you request it."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.error_label = QLabel()
        self.error_label.setObjectName("LibraryError")
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(
            "background:#FDECEC; color:#7A1F1F; border:1px solid #E5A7A7; padding:8px; border-radius:5px;"
        )
        self.error_label.hide()
        layout.addWidget(self.error_label)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter, 1)

        roots_group = QGroupBox("Registered folders")
        roots_layout = QVBoxLayout(roots_group)
        self.roots_table = QTableWidget(0, 3)
        self.roots_table.setHorizontalHeaderLabels(["Folder", "Last Scan Status", "Last Scan"])
        self.roots_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.roots_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.roots_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.roots_table.verticalHeader().setVisible(False)
        self.roots_table.horizontalHeader().setStretchLastSection(False)
        self.roots_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.roots_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.roots_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.roots_table.itemSelectionChanged.connect(self._sync_action_availability)
        roots_layout.addWidget(self.roots_table)

        root_actions = QHBoxLayout()
        self.add_folder_button = QPushButton("Add Folder…")
        self.add_folder_button.clicked.connect(self._add_folder)
        root_actions.addWidget(self.add_folder_button)
        self.remove_folder_button = QPushButton("Remove Folder…")
        self.remove_folder_button.clicked.connect(self._remove_selected_folder)
        root_actions.addWidget(self.remove_folder_button)
        root_actions.addStretch(1)
        self.rescan_button = QPushButton("Rescan")
        self.rescan_button.clicked.connect(self._rescan_selected)
        root_actions.addWidget(self.rescan_button)
        self.rescan_all_button = QPushButton("Rescan All")
        self.rescan_all_button.clicked.connect(self._rescan_all)
        root_actions.addWidget(self.rescan_all_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_scan)
        root_actions.addWidget(self.cancel_button)
        roots_layout.addLayout(root_actions)
        splitter.addWidget(roots_group)

        artifacts_group = QGroupBox("Artifacts")
        artifacts_layout = QVBoxLayout(artifacts_group)
        self.artifacts_table = QTableWidget(0, 6)
        self.artifacts_table.setHorizontalHeaderLabels(
            ["App / Label", "Package", "Version", "Version Code", "Locations", "Status"]
        )
        self.artifacts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.artifacts_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.artifacts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.artifacts_table.verticalHeader().setVisible(False)
        self.artifacts_table.horizontalHeader().setStretchLastSection(True)
        self.artifacts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            self.artifacts_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self.artifacts_table.itemSelectionChanged.connect(self._show_selected_artifact)
        artifacts_layout.addWidget(self.artifacts_table)
        self.artifact_details = QPlainTextEdit()
        self.artifact_details.setReadOnly(True)
        self.artifact_details.setPlaceholderText("Select an artifact to inspect its metadata and locations.")
        self.artifact_details.setMinimumHeight(145)
        artifacts_layout.addWidget(self.artifact_details)
        splitter.addWidget(artifacts_group)
        splitter.setSizes([230, 390])

        self.status_label = QLabel("Loading Library…")
        self.status_label.setObjectName("Muted")
        layout.addWidget(self.status_label)

        bottom = QHBoxLayout()
        self.audit_button = QPushButton("Audit Library")
        self.audit_button.setDefault(True)
        self.audit_button.clicked.connect(self._audit_library)
        bottom.addWidget(self.audit_button)
        bottom.addStretch(1)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        bottom.addWidget(self.close_button)
        layout.addLayout(bottom)

    def _load_library(self) -> None:
        result = self.service.load()
        if result.library is None:
            self.library = None
            message = result.failure.message if result.failure is not None else "Unknown load failure."
            self.error_label.setText(
                f"The Local APK Library could not be loaded. {message} "
                "Writing is disabled so the existing file remains unchanged."
            )
            self.error_label.show()
            self.status_label.setText("Library unavailable")
            self._refresh_tables()
            self._sync_action_availability()
            QMessageBox.critical(self, "Local APK Library could not be loaded", self.error_label.text())
            return
        self.library = result.library
        self.error_label.hide()
        self.status_label.setText(
            f"{len(self.library.roots)} folder(s) • {len(self.library.artifacts)} artifact(s)"
        )
        self._refresh_tables()
        self._sync_action_availability()

    def _refresh_tables(self) -> None:
        library = self.library
        self.roots_table.setRowCount(0)
        self.artifacts_table.setRowCount(0)
        self.artifact_details.clear()
        if library is None:
            return

        for row_index, root in enumerate(library.roots):
            self.roots_table.insertRow(row_index)
            path_item = QTableWidgetItem(str(root.path))
            path_item.setData(Qt.ItemDataRole.UserRole, str(root.path))
            self.roots_table.setItem(row_index, 0, path_item)
            self.roots_table.setItem(
                row_index,
                1,
                QTableWidgetItem(root.last_scan_status.value.replace("_", " ").title()),
            )
            self.roots_table.setItem(row_index, 2, QTableWidgetItem(_format_timestamp(root.last_scan_at)))

        for row_index, artifact in enumerate(library.artifacts):
            self.artifacts_table.insertRow(row_index)
            locations = [
                location
                for location in library.locations
                if location.artifact_sha256 == artifact.artifact_sha256
            ]
            present_count = sum(location.present for location in locations)
            if present_count and present_count == len(locations):
                status = "Present"
            elif present_count:
                status = "Present / Missing"
            elif locations:
                status = "Missing"
            else:
                status = "No registered location"
            values = (
                artifact.application_label or artifact.package_id,
                artifact.package_id,
                artifact.version_name or "Unknown",
                str(artifact.version_code) if artifact.version_code is not None else "Unknown",
                f"{present_count}/{len(locations)} present",
                status,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, artifact.artifact_sha256)
                self.artifacts_table.setItem(row_index, column, item)
        if self.artifacts_table.rowCount():
            self.artifacts_table.selectRow(0)

    def _selected_root(self) -> Path | None:
        row = self.roots_table.currentRow()
        item = self.roots_table.item(row, 0) if row >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return Path(value) if isinstance(value, str) and value else None

    def _selected_artifact(self) -> LocalApkLibraryArtifact | None:
        if self.library is None:
            return None
        row = self.artifacts_table.currentRow()
        item = self.artifacts_table.item(row, 0) if row >= 0 else None
        sha256 = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        return next(
            (artifact for artifact in self.library.artifacts if artifact.artifact_sha256 == sha256),
            None,
        )

    def _show_selected_artifact(self) -> None:
        artifact = self._selected_artifact()
        if artifact is None or self.library is None:
            self.artifact_details.clear()
            return
        lines = [
            f"SHA-256: {artifact.artifact_sha256}",
            f"Package: {artifact.package_id}",
            f"Label: {artifact.application_label or 'Unknown'}",
            f"Version: {artifact.version_name or 'Unknown'}",
            f"Version code: {artifact.version_code if artifact.version_code is not None else 'Unknown'}",
            f"Min SDK: {artifact.min_sdk if artifact.min_sdk is not None else 'Unknown'}",
            f"Target SDK: {artifact.target_sdk if artifact.target_sdk is not None else 'Unknown'}",
            f"Compile SDK: {artifact.compile_sdk if artifact.compile_sdk is not None else 'Unknown'}",
            "",
            "Known locations:",
        ]
        locations = sorted(
            (
                location
                for location in self.library.locations
                if location.artifact_sha256 == artifact.artifact_sha256
            ),
            key=lambda location: _path_key(location.path),
        )
        if not locations:
            lines.append("  No registered locations")
        for location in locations:
            lines.extend(
                [
                    f"  {'Present' if location.present else 'Missing'}: {location.path}",
                    f"    Root: {location.root_path}",
                    f"    Modified: {_format_timestamp(location.modified_at)}",
                    f"    Last seen: {_format_timestamp(location.last_seen_at)}",
                ]
            )
        self.artifact_details.setPlainText("\n".join(lines))

    def _sync_action_availability(self) -> None:
        usable = self.library is not None
        idle = usable and not self._scan_active
        root_selected = self._selected_root() is not None
        root_count = len(self.library.roots) if self.library is not None else 0
        auditable = bool(self.service.auditable_artifacts(self.library) if self.library is not None else ())
        self.add_folder_button.setEnabled(idle)
        self.remove_folder_button.setEnabled(idle and root_selected)
        self.rescan_button.setEnabled(idle and root_selected)
        self.rescan_all_button.setEnabled(idle and root_count > 0)
        self.cancel_button.setEnabled(usable and self._scan_active)
        self.audit_button.setEnabled(idle and auditable)

    def _add_folder(self) -> None:
        if self.library is None or self._scan_active:
            return
        selected = QFileDialog.getExistingDirectory(self, "Add Local APK Library folder")
        if not selected:
            return
        candidate = _normalise_selected_root(selected)
        try:
            invalid_directory_link = candidate.is_symlink() or candidate.is_junction()
            valid_directory = candidate.is_dir() and not invalid_directory_link
        except OSError:
            valid_directory = False
        if not valid_directory:
            QMessageBox.information(
                self,
                "Folder not added",
                "Choose an accessible physical directory. Directory links are not registered.",
            )
            return
        overlap = root_overlap_message(self.library, candidate)
        if overlap:
            QMessageBox.information(self, "Folder not added", overlap)
            return
        updated = self.service.register_roots(self.library, [candidate])
        saved = self.service.save(updated)
        if not saved.succeeded:
            message = saved.failure.message if saved.failure is not None else "Unknown save failure."
            QMessageBox.critical(self, "Library registration was not saved", message)
            return
        self.library = updated
        self._refresh_tables()
        self._start_scan((candidate,))

    def _remove_selected_folder(self) -> None:
        if self.library is None or self._scan_active:
            return
        selected = self._selected_root()
        if selected is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove folder from Library?",
            f"Remove this folder registration and its Library location metadata?\n\n"
            f"{selected}\n\nAPK files and directories on disk will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        updated = self.service.remove_root(self.library, selected)
        saved = self.service.save(updated)
        if not saved.succeeded:
            message = saved.failure.message if saved.failure is not None else "Unknown save failure."
            QMessageBox.critical(self, "Library folder was not removed", message)
            return
        self.library = updated
        self._refresh_tables()
        self.status_label.setText("Folder registration removed; files on disk were untouched.")
        self._sync_action_availability()

    def _rescan_selected(self) -> None:
        selected = self._selected_root()
        if selected is not None:
            self._start_scan((selected,))

    def _rescan_all(self) -> None:
        if self.library is not None and self.library.roots:
            self._start_scan(tuple(root.path for root in self.library.roots))

    def _start_scan(self, roots: tuple[Path, ...]) -> None:
        if self.library is None or self._scan_active or not roots:
            return
        self._scan_generation += 1
        request_id = self._scan_generation
        self._scan_active = True
        self._scan_cancel_event = threading.Event()
        self.status_label.setText(f"Scanning {len(roots)} folder(s)…")
        self._sync_action_availability()
        self._launch_scan_worker(
            request_id,
            self.library,
            roots,
            self._scan_cancel_event,
        )

    def _launch_scan_worker(
        self,
        request_id: int,
        library: LocalApkLibrary,
        roots: tuple[Path, ...],
        cancel_event: threading.Event,
    ) -> None:
        threading.Thread(
            target=self._scan_worker,
            args=(request_id, library, roots, cancel_event),
            daemon=True,
        ).start()

    def _scan_worker(
        self,
        request_id: int,
        library: LocalApkLibrary,
        roots: tuple[Path, ...],
        cancel_event: threading.Event,
    ) -> None:
        try:
            result = self.service.rescan(
                library,
                roots=roots,
                cancel_event=cancel_event,
                progress_callback=lambda progress: self.scan_signals.progress.emit(request_id, progress),
            )
            self.scan_signals.done.emit(request_id, result)
        except Exception as exc:
            if not cancel_event.is_set():
                self.scan_signals.failed.emit(
                    request_id, f"The Local APK Library scan could not be completed: {exc}"
                )

    def _on_scan_progress(self, request_id: int, value: object) -> None:
        if request_id != self._scan_generation or not self._scan_active:
            return
        if not isinstance(value, LocalApkLibraryScanProgress):
            return
        self.status_label.setText(
            f"Scanning {value.root_path.name or value.root_path} • "
            f"{value.discovered_apks} APK(s) found • {value.parsed_artifacts} parsed"
        )

    def _on_scan_done(self, request_id: int, value: object) -> None:
        if request_id != self._scan_generation or not self._scan_active:
            return
        if not isinstance(value, LocalApkLibraryScanResult):
            self._on_scan_failed(request_id, "The Library scan returned an invalid result.")
            return
        self._scan_active = False
        if value.cancelled:
            self._reload_after_cancel()
            self.status_label.setText("Library scan cancelled; partial changes were not saved.")
            self._sync_action_availability()
            return

        saved = self.service.save(value.library)
        if not saved.succeeded:
            message = saved.failure.message if saved.failure is not None else "Unknown save failure."
            self._reload_last_persisted()
            QMessageBox.critical(self, "Library scan was not saved", message)
            return
        self.library = value.library
        self._refresh_tables()
        self.status_label.setText(self._scan_summary(value))
        self._sync_action_availability()
        if value.issues or value.omitted_issue_count:
            QMessageBox.warning(
                self, "Local APK Library scan completed with issues", self._issue_summary(value)
            )

    @staticmethod
    def _scan_summary(result: LocalApkLibraryScanResult) -> str:
        completed = sum(root.status is LibraryRootScanStatus.COMPLETED for root in result.roots)
        partial = sum(root.status is LibraryRootScanStatus.PARTIAL for root in result.roots)
        failed = sum(root.status is LibraryRootScanStatus.FAILED for root in result.roots)
        parsed = sum(root.parsed_artifacts for root in result.roots)
        return (
            f"Scan saved • {parsed} artifact parse(s) • {completed} completed • "
            f"{partial} partial • {failed} failed"
        )

    @staticmethod
    def _issue_summary(result: LocalApkLibraryScanResult) -> str:
        parser_failures = sum(issue.kind is LibraryScanIssueKind.PARSER_FAILURE for issue in result.issues)
        root_failures = sum(issue.kind is LibraryScanIssueKind.ROOT_UNAVAILABLE for issue in result.issues)
        access_failures = sum(
            issue.kind
            in {
                LibraryScanIssueKind.DIRECTORY_INACCESSIBLE,
                LibraryScanIssueKind.FILE_INACCESSIBLE,
            }
            for issue in result.issues
        )
        lines = [
            f"Recorded issues: {len(result.issues)}",
            f"Parser failures: {parser_failures}",
            f"Unavailable roots: {root_failures}",
            f"Filesystem access issues: {access_failures}",
        ]
        if result.omitted_issue_count:
            lines.append(f"Additional omitted issues: {result.omitted_issue_count}")
        return "\n".join(lines)

    def _reload_after_cancel(self) -> None:
        self._reload_last_persisted(show_error=True)

    def _reload_last_persisted(self, *, show_error: bool = False) -> None:
        result = self.service.load()
        if result.library is not None:
            self.library = result.library
            self._refresh_tables()
            self._sync_action_availability()
            return
        self.library = None
        self._refresh_tables()
        self._sync_action_availability()
        if show_error:
            message = result.failure.message if result.failure is not None else "Unknown load failure."
            QMessageBox.critical(self, "Saved Library could not be reloaded", message)

    def _on_scan_failed(self, request_id: int, message: str) -> None:
        if request_id != self._scan_generation or not self._scan_active:
            return
        self._scan_active = False
        self._reload_last_persisted()
        self.status_label.setText("Library scan failed; persisted state was retained.")
        QMessageBox.critical(self, "Local APK Library scan failed", message)

    def _cancel_scan(self) -> None:
        if not self._scan_active:
            return
        self._scan_cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Cancelling Library scan…")

    def _audit_library(self) -> None:
        if self.library is None or self._scan_active:
            return
        artifacts: tuple[LocalArtifact, ...] = self.service.auditable_artifacts(self.library)
        if not artifacts:
            QMessageBox.information(
                self,
                "No auditable Library artifacts",
                "The Library has no currently verified APK artifacts to audit.",
            )
            return
        self.audit_requested.emit(artifacts)
        self.accept()

    def reject(self) -> None:
        self._scan_cancel_event.set()
        self._scan_generation += 1
        self._scan_active = False
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._scan_cancel_event.set()
        self._scan_generation += 1
        self._scan_active = False
        super().closeEvent(event)
