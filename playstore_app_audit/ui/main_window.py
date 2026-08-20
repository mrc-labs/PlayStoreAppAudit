from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QPoint, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStyle,
    QToolButton,
    QWidget,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.ui.results_window as results_ui
from playstore_app_audit.devices.adb import find_adb, install_platform_tools
from playstore_app_audit.platform import runtime


def _detach_layout(layout, keep: set[object]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        widget = item.widget()
        if child is not None:
            _detach_layout(child, keep)
        if widget is not None and widget not in keep:
            widget.deleteLater()


class MainWindow(results_ui.ResultsWindow):
    """Current Qt desktop window.

    This is the stable public UI entry point. Platform-specific behaviour lives
    behind playstore_app_audit.platform / devices instead of in the window.
    """

    def __init__(self) -> None:
        self._audit_cached_count = 0
        self._audit_live_count = 0
        self._finalizing_session: int | None = None
        super().__init__()
        self.signals.adb_discovery_done.connect(self._on_adb_discovery_done)
        self._remove_redundant_content_heading()
        self._rebuild_source_area_v10()

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
            menu.addAction("No recent files").setEnabled(False)
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
        self.recent_sources_button.setAccessibleName("Recent sources")
        self.recent_sources_button.setArrowType(Qt.ArrowType.DownArrow)
        self.recent_sources_button.setFixedWidth(30)
        self.recent_sources_button_menu = QMenu("Recent sources", self.recent_sources_button)
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
        self.scan_phone_options_button.setAccessibleName("Phone package list options")
        self.scan_phone_options_button.setArrowType(Qt.ArrowType.DownArrow)
        self.scan_phone_options_button.setFixedWidth(30)
        self.scan_phone_options_menu = QMenu("Phone package list options", self.scan_phone_options_button)
        self.scan_phone_package_export_action = self.scan_phone_options_menu.addAction(
            "Export current phone package list as CSV…", self._export_phone_packages_csv
        )
        self.scan_phone_options_button.clicked.connect(self._show_scan_phone_options_menu)
        layout.addWidget(self.scan_phone_options_button)

        self._sync_phone_package_export_actions()
        return controls

    def _show_scan_phone_options_menu(self) -> None:
        self._sync_phone_package_export_actions()
        button = self.scan_phone_options_button
        self.scan_phone_options_menu.popup(button.mapToGlobal(QPoint(0, button.height())))

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
            (child for child in source_card.findChildren(QLabel) if child.text().strip() == "App source"),
            None,
        )
        keep = {
            self.path_edit,
            self.choose_button,
            self.scan_button,
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
            source_title = QLabel("App source")
            source_title.setObjectName("SectionTitle")
        source_layout.addWidget(source_title)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.choose_button.setText("Choose file")
        self.choose_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.scan_button.setText("Scan phone")
        self.scan_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))

        row.addWidget(self._source_option("CSV / TSV / TXT file", self._file_source_controls()), 1)
        or_label = QLabel("or")
        or_label.setObjectName("Muted")
        row.addWidget(or_label)
        row.addWidget(self._source_option("Android phone (ADB)", self._phone_source_controls()), 1)
        row.addSpacing(10)

        country_label = QLabel("Store country")
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

    def _set_view_preset(self, name: str) -> None:
        # View changes are presentation-only and must not overwrite a useful
        # audit/progress/result message below the progress bar.
        status_text = self.status_label.text() if hasattr(self, "status_label") else ""
        super()._set_view_preset(name)
        if hasattr(self, "status_label"):
            self.status_label.setText(status_text)

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
            f"Phone scan: {identity} • {current}" if current else f"Phone scan: {identity}"
        )

    def _start_audit(self) -> None:
        was_active = self._audit_active
        super()._start_audit()
        if was_active or not self._audit_active:
            return

        self._audit_cached_count = max(0, self.progress.value())
        total = max(0, self.progress.maximum())
        self._audit_live_count = max(0, total - self._audit_cached_count)
        self._restore_device_source_identity()
        self.status_label.setText(
            "Audit running • "
            f"{self._audit_cached_count} cached • {self._audit_live_count} live"
        )

    def _on_controlled_progress(
        self, session: int, done: int, total: int, package_name: str
    ) -> None:
        super()._on_controlled_progress(session, done, total, package_name)
        if session != self._audit_session or not self._audit_active or self._audit_paused:
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
        session, _rows, error, cached_count, live_count = payload  # type: ignore[misc]
        if session != self._audit_session:
            return
        if error:
            super()._on_controlled_done(payload)
            return

        self._finalizing_session = session
        self._audit_paused = False
        self._audit_pause_event.set()
        self._set_audit_source_controls_enabled(False)
        self.run_button.setText("Finalizing…")
        self.run_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.progress.setRange(0, 0)
        self.status_label.setText(
            f"Finalizing audit results • {cached_count} cached • {live_count} live"
        )
        QTimer.singleShot(0, lambda: self._complete_controlled_done(payload))

    def _complete_controlled_done(self, payload: object) -> None:
        session = payload[0]  # type: ignore[index]
        if session != self._audit_session or self._finalizing_session != session:
            return
        self._finalizing_session = None
        super()._on_controlled_done(payload)
        self._restore_device_source_identity()

    # ---------- Cross-platform ADB ----------
    def _find_adb(self) -> str | None:
        return find_adb()

    def _scan_phone(self) -> None:
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Looking for ADB…")
        threading.Thread(target=self._find_adb_worker, daemon=True).start()

    def _find_adb_worker(self) -> None:
        try:
            self.signals.adb_discovery_done.emit(self._find_adb())
        except Exception as exc:
            self.signals.failed.emit(f"ADB discovery failed:\n\n{exc}")

    def _on_adb_discovery_done(self, adb: str | None) -> None:
        if adb:
            self._start_adb_scan(adb)
            return

        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("ADB not found")
        self._set_busy(False)
        if not runtime.managed_platform_tools_download_supported():
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
            return
        if choice == QMessageBox.StandardButton.No:
            QDesktopServices.openUrl(QUrl(runtime.PLATFORM_TOOLS_PAGE))
            return
        self.pending_scan_after_install = True
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Downloading Android Platform-Tools from Google…")
        threading.Thread(target=self._install_platform_tools_worker, daemon=True).start()

    def _install_platform_tools_worker(self) -> None:
        try:
            adb, version_text = install_platform_tools()
            self.signals.adb_install_done.emit(adb, version_text)
        except Exception as exc:
            self.signals.failed.emit(f"ADB installation failed:\n\n{exc}")
