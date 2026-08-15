from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

from app_icon import ensure_runtime_icon
from playstore_audit_core import AuditConfig
from playstore_audit_multicountry import audit_apps_multicountry
import playstore_audit_qt as qt_base
from playstore_audit_qt_branch import PlayStoreAuditQtBranch


FIXED_WORKERS = 16
DISPLAY_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
)
DISPLAY_WIDTHS = (145, 300, 265, 120, 92, 460)

# Keep diagnostic fields (Play status / Update source) in the underlying rows
# and CSV export, while the interactive table shows only user-facing fields.
qt_base.COLUMNS = DISPLAY_COLUMNS
qt_base.COLUMN_LABELS.update(
    {
        "criticality": "Status",
        "package_name": "Package Name",
        "play_title": "Play Store Title",
        "play_last_update": "Last update",
        "age_days": "Age (days)",
        "notes": "Notes",
    }
)

# Keep functional behaviour shared with the CustomTkinter branch.
qt_base.audit_apps = audit_apps_multicountry
_original_classify_criticality = qt_base.classify_criticality


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
    row["criticality"] = qt_base.CRITICALITY[key]["label"]
    row["criticality_rank"] = qt_base.CRITICALITY[key]["rank"]
    row["age_days"] = ""


qt_base.classify_criticality = _classify_criticality_multicountry


def _find_layout_containing(layout, target_widget):
    """Return the nested layout that directly contains target_widget."""
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
    progress = Signal(int, int, int, str)  # session, done, total, package
    done = Signal(object)  # (session, rows, error)


class PlayStoreAuditQtCompact(PlayStoreAuditQtBranch):
    """Compact Qt6 presentation with fixed concurrency and pausable audits."""

    def __init__(self) -> None:
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

        # Keep every source control on one horizontal line:
        # path | Choose file | ADB | Store country | system-app option.
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

        # User-facing table order. Technical fields remain in the row/export.
        self.model.headerDataChanged.emit(
            Qt.Orientation.Horizontal, 0, self.model.columnCount() - 1
        )
        for column, width in enumerate(DISPLAY_WIDTHS):
            self.table.setColumnWidth(column, width)

        # Slightly denser rows than the previous Qt build.
        self.table.verticalHeader().setMinimumSectionSize(22)
        self.table.verticalHeader().setDefaultSectionSize(26)

        self._compact_action_row()
        self._compact_results_area()
        self._set_run_mode("run")

    def _compact_action_row(self) -> None:
        """Run/Pause | progress+status | Export | Clear on one compact row."""
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
        """Reduce excess vertical whitespace in the Qt results card."""
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
        self.summary_label.setContentsMargins(0, 0, 0, 0)

        self.hide_system_check.setContentsMargins(0, 0, 0, 0)
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
                widget.setContentsMargins(0, 0, 0, 0)
                break

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

        country = (self.country_edit.text().strip() or qt_base.detect_windows_country()).lower()
        self.current_system_packages = system_packages
        self.criticality_filter = None
        self._sync_criticality_buttons()

        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        self.source_label.setText(
            f"{source_label} source: {len(apps)} packages • "
            f"{len(system_packages)} classified as system • {classification_method}"
        )

        self.current_rows = []
        self.model.set_rows([])
        self.proxy.invalidateFilter()
        self.export_button.setEnabled(False)
        self.progress.setRange(0, len(apps))
        self.progress.setValue(0)
        self.status_label.setText(
            f"Starting audit for {len(apps)} packages in Store country '{country}'…"
        )

        self._audit_session += 1
        session = self._audit_session
        self._audit_active = True
        self._audit_paused = False
        self._audit_pause_event = threading.Event()
        self._audit_pause_event.set()
        self._audit_cancel_event = threading.Event()
        self._last_progress = (0, len(apps), "")
        self._set_audit_source_controls_enabled(False)
        self._set_run_mode("pause")

        config = AuditConfig(country=country, language="en", max_workers=FIXED_WORKERS)
        threading.Thread(
            target=self._controlled_audit_worker,
            args=(apps, config, session, self._audit_pause_event, self._audit_cancel_event),
            daemon=True,
        ).start()

    def _controlled_audit_worker(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        session: int,
        pause_event: threading.Event,
        cancel_event: threading.Event,
    ) -> None:
        try:
            def progress(done: int, total: int, package_name: str) -> None:
                if cancel_event.is_set() or session != self._audit_session:
                    return
                self.audit_control_signals.progress.emit(session, done, total, package_name)

            rows = audit_apps_multicountry(
                apps,
                config,
                progress,
                pause_event=pause_event,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set() or session != self._audit_session:
                return
            self.audit_control_signals.done.emit((session, rows, ""))
        except Exception as exc:
            if not cancel_event.is_set() and session == self._audit_session:
                self.audit_control_signals.done.emit((session, None, str(exc)))

    def _on_controlled_progress(
        self, session: int, done: int, total: int, package_name: str
    ) -> None:
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
        session, rows, error = payload  # type: ignore[misc]
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

        qt_base.PlayStoreAuditQt._on_audit_done(self, rows)
        self._set_run_mode("run")

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
        qt_base.PlayStoreAuditQt._clear_results(self)
        self._set_run_mode("run")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(qt_base.APP_NAME)
    app.setOrganizationName("MRC")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = PlayStoreAuditQtCompact()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
