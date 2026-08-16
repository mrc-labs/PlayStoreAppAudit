from __future__ import annotations

import threading

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QStyle,
)

import playstore_audit_qt as qt_base
import playstore_audit_qt_branch as qt_branch
import playstore_audit_qt_compact as qt_compact
import playstore_audit_qt_v9_2 as v92ui
import playstore_audit_qt_v9_3 as legacy_ui
import playstore_audit_v9_2_features as v92_features
import playstore_audit_v9_3_features as v93_features
import playstore_audit_v9_features as v9_features
from playstore_app_audit import __version__
from playstore_app_audit.devices.adb import find_adb, install_platform_tools
from playstore_app_audit.help_texts import ADB_SETUP_GUIDE
from playstore_app_audit.platform import runtime
from playstore_app_audit.resources import ensure_runtime_icon
from playstore_app_audit.services import state as state_service

# Compatibility imports above are a tested transition layer while the older
# versioned Qt modules are migrated behind this canonical package entry point.
# New product code should depend on playstore_app_audit, not versioned wrappers.

# Centralise platform decisions instead of spreading Windows assumptions across
# the UI inheritance chain.
qt_base.detect_windows_country = runtime.detect_store_country
qt_branch.detect_windows_country = runtime.detect_store_country
qt_base.managed_platform_tools_dir = runtime.managed_platform_tools_dir
qt_base.PLATFORM_TOOLS_URL = runtime.platform_tools_url()
qt_compact.ensure_runtime_icon = ensure_runtime_icon
v9_features.local_data_dir = runtime.app_data_dir
v9_features.ADB_SETUP_GUIDE = ADB_SETUP_GUIDE
state_service.app_data_dir = v9_features.app_data_dir_v9

# Surface the package version everywhere the legacy dialogs/reports read it.
v92ui.v9.features.APP_VERSION = __version__
v92_features.APP_VERSION = __version__
v93_features.APP_VERSION = __version__
v9_features.APP_VERSION = __version__


def _detach_layout(layout, keep: set[object]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        widget = item.widget()
        if child is not None:
            _detach_layout(child, keep)
        if widget is not None and widget not in keep:
            widget.deleteLater()


class MainWindow(legacy_ui.PlayStoreAuditQtV93):
    """Current Qt desktop window.

    This is the stable public UI entry point. Platform-specific behaviour lives
    behind playstore_app_audit.platform / devices instead of in the window.
    """

    def __init__(self) -> None:
        super().__init__()
        self._rebuild_source_area_v10()

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
                if child.text().strip() == "App source"
            ),
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

        row.addWidget(self._source_option("CSV / TSV / TXT file", self.choose_button), 1)
        or_label = QLabel("or")
        or_label.setObjectName("Muted")
        row.addWidget(or_label)
        row.addWidget(self._source_option("Android phone (ADB)", self.scan_button), 1)
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

    # ---------- Cross-platform ADB ----------
    def _find_adb(self) -> str | None:
        return find_adb()

    def _scan_phone(self) -> None:
        adb = self._find_adb()
        if not adb:
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
            return
        self._start_adb_scan(adb)

    def _install_platform_tools_worker(self) -> None:
        try:
            adb, version_text = install_platform_tools()
            self.signals.adb_install_done.emit(adb, version_text)
        except Exception as exc:
            self.signals.failed.emit(f"ADB installation failed:\n\n{exc}")
