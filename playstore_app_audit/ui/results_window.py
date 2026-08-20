from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
)

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.summary as summary_service
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.menu_window as menu_ui
import playstore_app_audit.ui.preferences_window as preferences_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.resources import ensure_runtime_icon


def _find_layout_containing(layout, target_widget):
    for index in range(layout.count()):
        item = layout.itemAt(index)
        if item.widget() is target_widget:
            return layout
        child = item.layout()
        if child is not None:
            found = _find_layout_containing(child, target_widget)
            if found is not None:
                return found
    return None


def _clear_layout_keep_widgets(layout, keep: set[object]) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if child is not None:
            _clear_layout_keep_widgets(child, keep)
        if widget is not None and widget not in keep:
            widget.deleteLater()


class NumericAuditFilterProxy(preferences_ui.AuditFilterProxy):
    NUMERIC_SORT_COLUMNS = frozenset(
        {
            "age_days",
            "target_sdk",
            "min_sdk",
            "sensitive_permissions_count",
            "health_score",
        }
    )

    @staticmethod
    def _numeric_sort_value(value: object) -> float:
        if value is None:
            return -1.0
        text = str(value).strip()
        if not text:
            return -1.0
        try:
            return float(text)
        except (TypeError, ValueError):
            return -1.0

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if isinstance(model, table_ui.AuditTableModel) and 0 <= left.column() < len(model.columns):
            column = model.columns[left.column()]
            if column in self.NUMERIC_SORT_COLUMNS:
                left_row = model.row_dict(left.row())
                right_row = model.row_dict(right.row())
                return self._numeric_sort_value(left_row.get(column)) < self._numeric_sort_value(
                    right_row.get(column)
                )
        return super().lessThan(left, right)


class ResultsWindow(menu_ui.MenuWindow):
    def __init__(self) -> None:
        super().__init__()
        self.exclude_system_source_check.toggled.connect(self._persist_exclude_system_source)
        self._install_numeric_sort_proxy()
        self._setup_export_button_menu()
        self._rebuild_file_menu()
        self._update_summary()

    def _persist_exclude_system_source(self, checked: bool) -> None:
        self.user_settings["exclude_system_source"] = bool(checked)
        self.user_settings = state.save_settings(self.user_settings)

    def _install_numeric_sort_proxy(self) -> None:
        old_proxy = self.proxy
        proxy = NumericAuditFilterProxy()
        proxy.setSourceModel(self.model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_status_filters(self._status_filters)
        self.proxy = proxy
        self.table.setModel(proxy)
        old_proxy.deleteLater()
        self._apply_column_visibility(reset_order=False)

    # ---------- Source UX ----------
    def _choice_row(self, text: str, button) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        row.addWidget(label)
        row.addStretch(1)
        button.setFixedWidth(132)
        row.addWidget(button)
        return row

    def _rebuild_source_area(self) -> None:
        source_card = self.path_edit.parentWidget()
        source_layout = source_card.layout() if source_card is not None else None
        if source_layout is None:
            return
        source_line = _find_layout_containing(source_layout, self.path_edit)
        if source_line is None:
            return

        keep = {
            self.path_edit,
            self.choose_button,
            self.scan_button,
            self.country_edit,
            self.exclude_system_source_check,
        }
        _clear_layout_keep_widgets(source_line, keep)
        self.path_edit.hide()

        self.choose_button.setText("Choose file")
        self.scan_button.setText("Scan phone")

        choices = QVBoxLayout()
        choices.setContentsMargins(0, 0, 0, 0)
        choices.setSpacing(5)
        choices.addLayout(self._choice_row("Choose a CSV / TSV / TXT file", self.choose_button))

        or_label = QLabel("or")
        or_label.setObjectName("Muted")
        or_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        choices.addWidget(or_label)

        choices.addLayout(self._choice_row("Scan your Android phone with ADB", self.scan_button))
        source_line.addLayout(choices, 1)

        options = QHBoxLayout()
        options.setContentsMargins(0, 2, 0, 0)
        options.setSpacing(8)
        country_label = QLabel("Store country")
        country_label.setToolTip("Google Play market, detected from Windows Region.")
        options.addWidget(country_label)
        self.country_edit.setFixedWidth(58)
        options.addWidget(self.country_edit)
        options.addSpacing(8)
        options.addWidget(self.exclude_system_source_check)
        options.addStretch(1)

        # Keep the compact status/source label as the last line in the card.
        source_layout.insertLayout(max(0, source_layout.count() - 1), options)

    def _load_input_file(self, path: str) -> None:
        super()._load_input_file(path)
        if self.source_mode == "file":
            text = self.source_label.text()
            if text.startswith("File selected: "):
                text = text[len("File selected: ") :]
            self.source_label.setText(f"{Path(path).name}  •  {text}")
            self.source_label.setToolTip(path)
        self._sync_phone_package_export_actions()

    def _on_adb_scan_done(self, apps: object, system_packages: object) -> None:
        super()._on_adb_scan_done(apps, system_packages)
        self._sync_phone_package_export_actions()

    def _sync_phone_package_export_actions(self) -> None:
        available = bool(self.device_apps_all)
        for name in ("file_phone_package_export_action", "scan_phone_package_export_action"):
            action = getattr(self, name, None)
            if action is not None:
                action.setEnabled(available)

    # ---------- Export UX ----------
    def _setup_export_button_menu(self) -> None:
        try:
            self.export_button.clicked.disconnect()
        except (TypeError, RuntimeError):
            pass
        menu = QMenu(self.export_button)
        menu.addAction("Export all results as CSV…", self._export_results)
        menu.addAction("Export visible results as CSV…", self._export_visible_results)
        menu.addSeparator()
        menu.addAction("Export all results as HTML…", self._export_html_report)
        menu.addAction("Export visible results as HTML…", self._export_visible_html_report)
        self.export_button.setText("Export results")
        self.export_button.setMenu(menu)
        self._export_results_menu = menu

    def _export_visible_html_report(self) -> None:
        self._export_html_rows(
            self._visible_rows(), "playstore_audit_visible_report.html", "Export visible results as HTML"
        )

    def _export_html_rows(self, rows: list[dict[str, Any]], default_name: str, title: str) -> None:
        if not rows:
            QMessageBox.information(self, "Nothing to export", "There are no results to export.")
            return
        selected, _ = QFileDialog.getSaveFileName(self, title, default_name, "HTML (*.html)")
        if not selected:
            return
        if not selected.lower().endswith(".html"):
            selected += ".html"
        try:
            formatted = presentation.rows_for_output([dict(row) for row in rows])
            device_insights.write_html_report(selected, formatted, self._device_summary)
            QMessageBox.information(self, "Export complete", f"HTML report saved to:\n{selected}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _rebuild_file_menu(self) -> None:
        if not hasattr(self, "file_menu"):
            return
        self.file_menu.clear()
        self.file_menu.addAction("Choose app list…", self._choose_input)
        self.recent_menu = self.file_menu.addMenu("Recent sources")
        self._recent_menu = self.recent_menu
        self._populate_recent_menu()
        self.file_menu.addAction("Scan phone with ADB", self._scan_phone)
        self.file_phone_package_export_action = self.file_menu.addAction(
            "Export current phone package list as CSV…", self._export_phone_packages_csv
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction("Run Play Store audit", self._start_audit)
        self.file_menu.addAction("Clear current results", self._clear_results)
        self.file_menu.addSeparator()
        self.file_export_results_menu = self.file_menu.addMenu("Export results")
        self.file_export_results_menu.addAction("Export all results as CSV…", self._export_results)
        self.file_export_results_menu.addAction(
            "Export visible results as CSV…", self._export_visible_results
        )
        self.file_export_results_menu.addSeparator()
        self.file_export_results_menu.addAction("Export all results as HTML…", self._export_html_report)
        self.file_export_results_menu.addAction(
            "Export visible results as HTML…", self._export_visible_html_report
        )
        self.file_menu.addSeparator()
        self.file_menu.addAction("Exit", self.close)
        self._sync_phone_package_export_actions()

    def _clear_results(self) -> None:
        super()._clear_results()
        self._sync_phone_package_export_actions()

    # ---------- Concise summary ----------
    def _update_summary(self) -> None:
        super()._update_summary()
        if not hasattr(self, "summary_label"):
            return
        visible = self.proxy.rowCount() if hasattr(self, "proxy") else len(self.current_rows)
        self.summary_label.setText(
            summary_service.concise_summary(
                list(self.current_rows), visible, getattr(self, "_last_inventory_changes", None)
            )
        )


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = ResultsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
