from __future__ import annotations

import sys

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

# Install this before the UI modules start invoking adb.exe or other console tools.
install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

import playstore_app_audit.services.app_icon_metadata as app_icon_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.insights_window as insights_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit import __version__
from playstore_app_audit.ui import schema
from playstore_app_audit.ui.app_icon_loader import AppIconLoader

TABLE_SCHEMA_VERSION = "v12-schema-1"
ICON_STATUSES = {"available", "available_in_other_country", "available_in_fallback_locale_only"}


class AuditTableModel(base_ui.AppTableModel):
    """Qt model with an immutable column map and optional lazy app icons.

    Older builds changed the module-level COLUMNS tuple while progressively
    extending the table. A QTableView can retain header state between versions,
    while the model later observes a different global column tuple. Freezing the
    mapping inside the model prevents valid row data from appearing under an
    empty/mismatched logical column.
    """

    def __init__(self) -> None:
        super().__init__()
        self.columns = schema.MODEL_COLUMNS
        self._icons_enabled = bool(state.load_settings().get("show_app_icons", False))
        self._icon_loader = AppIconLoader(self)
        self._icon_loader.icon_ready.connect(self._on_icon_ready)

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        for row in rows:
            if str(row.get("play_status") or "") not in ICON_STATUSES:
                continue
            if row.get("play_icon_url"):
                continue
            icon_url = app_icon_metadata.icon_url_for_package(row.get("package_name"))
            if icon_url:
                row["play_icon_url"] = icon_url
        super().set_rows(rows)

    def set_app_icons_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._icons_enabled:
            return
        self._icons_enabled = enabled
        if not self.rows or "package_name" not in self.columns:
            return
        column = self.columns.index("package_name")
        top_left = self.index(0, column)
        bottom_right = self.index(len(self.rows) - 1, column)
        self.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.ItemDataRole.DecorationRole],
        )

    def _on_icon_ready(self, icon_url: str) -> None:
        if not self._icons_enabled or "package_name" not in self.columns:
            return
        column = self.columns.index("package_name")
        for row_index, row in enumerate(self.rows):
            if str(row.get("play_icon_url") or "") != icon_url:
                continue
            index = self.index(row_index, column)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.columns):
            column = self.columns[section]
            return base_ui.COLUMN_LABELS.get(column, column)
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        if not (0 <= index.column() < len(self.columns)):
            return None

        row = self.rows[index.row()]
        column = self.columns[index.column()]
        key = str(row.get("criticality_key") or "purple")
        info = base_ui.CRITICALITY.get(key, base_ui.CRITICALITY["purple"])

        if role == Qt.ItemDataRole.DisplayRole:
            value = row.get(column, "")
            if isinstance(value, bool):
                return "Yes" if value else "No"
            return "" if value is None else str(value)

        if role == Qt.ItemDataRole.DecorationRole and column == "package_name":
            if not self._icons_enabled:
                return None
            if str(row.get("play_status") or "") not in ICON_STATUSES:
                return None
            return self._icon_loader.icon_for_url(row.get("play_icon_url"))

        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(info["background"])

        if role == Qt.ItemDataRole.ForegroundRole:
            if column == "criticality":
                return QColor(info["accent"])
            return QColor("#263238")

        if role == Qt.ItemDataRole.FontRole and column == "criticality":
            font = QFont()
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in {
                "play_status",
                "play_last_update",
                "age_days",
                "criticality",
                "target_sdk",
                "min_sdk",
                "health_score",
            }:
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.UserRole:
            return row
        return None


class TableWindow(insights_ui.InsightsWindow):
    def __init__(self) -> None:
        # QHeaderView state is not portable across a changed logical-column
        # schema. Invalidate it once when upgrading to this fixed model.
        settings = state.load_settings()
        if str(settings.get("qt_header_schema_version") or "") != TABLE_SCHEMA_VERSION:
            settings["qt_header_state"] = ""
            settings["qt_header_schema_version"] = TABLE_SCHEMA_VERSION
            state.save_settings(settings)

        super().__init__()

        old_proxy = self.proxy
        stable_model = AuditTableModel()
        stable_model.set_rows(list(self.current_rows))

        proxy = insights_ui.AdvancedFilterProxy()
        proxy.setSourceModel(stable_model)
        proxy.set_query(self.search_edit.text())
        proxy.set_hide_system(self.hide_system_check.isChecked())
        proxy.set_criticality_filter(self.criticality_filter)
        proxy.set_v9_preset(self._active_filter_preset)

        self.model = stable_model
        self.proxy = proxy
        self.table.setModel(proxy)
        self.table.setIconSize(QSize(22, 22))
        old_proxy.deleteLater()
        self._apply_column_visibility(reset_order=True)

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

        version = QLabel(f"Version {__version__}")
        version.setObjectName("AboutVersion")
        layout.addWidget(version)

        info = QLabel(
            "<b>Created by MRC</b><br><br>"
            "Audit Android packages against public Google Play listings, update dates, "
            "regional availability and optional connected-device metadata.<br><br>"
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


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(base_ui.APP_NAME)
    app.setOrganizationName("MRC")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = TableWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
