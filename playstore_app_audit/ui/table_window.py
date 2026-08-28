from __future__ import annotations

import sys

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

# Install this before the UI modules start invoking adb.exe or other console tools.
install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

import playstore_app_audit.services.app_icon_metadata as app_icon_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.insights_window as insights_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit import __version__
from playstore_app_audit.ui import schema
from playstore_app_audit.ui.app_icon_loader import AppIconLoader

TABLE_SCHEMA_VERSION = "v12-schema-1"
ICON_STATUSES = {"available", "available_in_other_country", "available_in_fallback_locale_only"}
ICON_COLUMN = "play_title"


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
        self._icon_rows_by_package: dict[str, list[int]] = {}
        self._icon_loader = AppIconLoader(self)
        self._icon_loader.icon_ready.connect(self._on_icon_ready)

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        icon_rows_by_package: dict[str, list[int]] = {}
        for row_index, row in enumerate(rows):
            if str(row.get("play_status") or "") not in ICON_STATUSES:
                continue
            if row.get("play_icon_url"):
                icon_url = str(row.get("play_icon_url") or "").strip()
            else:
                icon_url = app_icon_metadata.icon_url_for_package(row.get("package_name"))
                if icon_url:
                    row["play_icon_url"] = icon_url
            package_name = str(row.get("package_name") or "").strip()
            if package_name and icon_url:
                icon_rows_by_package.setdefault(package_name, []).append(row_index)
        self._icon_rows_by_package = icon_rows_by_package
        super().set_rows(rows)

    def icon_for_row(self, row: dict[str, object]) -> QIcon | None:
        if not self._icons_enabled:
            return None
        if str(row.get("play_status") or "") not in ICON_STATUSES:
            return None
        return self._icon_loader.icon_for_row(
            row.get("package_name"),
            row.get("play_icon_url"),
            row.get("play_last_update"),
        )

    def set_app_icons_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._icons_enabled:
            return
        self._icons_enabled = enabled
        if not self.rows or ICON_COLUMN not in self.columns:
            return
        column = self.columns.index(ICON_COLUMN)
        top_left = self.index(0, column)
        bottom_right = self.index(len(self.rows) - 1, column)
        self.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.ItemDataRole.DecorationRole],
        )

    def _on_icon_ready(self, package_name: str) -> None:
        if not self._icons_enabled or ICON_COLUMN not in self.columns:
            return
        column = self.columns.index(ICON_COLUMN)
        for row_index in self._icon_rows_by_package.get(package_name, []):
            if not 0 <= row_index < len(self.rows):
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
            if column == "notes":
                return presentation.friendly_notes(row)
            value = row.get(column, "")
            if isinstance(value, bool):
                return "Yes" if value else "No"
            return "" if value is None else str(value)

        if role == Qt.ItemDataRole.DecorationRole and column == ICON_COLUMN:
            return self.icon_for_row(row)

        if role == Qt.ItemDataRole.BackgroundRole:
            return QColor(info["background"])

        if role == Qt.ItemDataRole.ForegroundRole:
            if column == "criticality":
                return QColor(info["accent"])
            semantic_colour = base_ui.semantic_foreground_colour(column, row.get(column))
            if semantic_colour:
                return QColor(semantic_colour)
            return QColor("#263238")

        if role == Qt.ItemDataRole.ToolTipRole and column == "notes":
            return presentation.friendly_notes(row)

        if role == Qt.ItemDataRole.FontRole:
            if column == "criticality":
                font = QFont()
                font.setBold(True)
                return font
            return base_ui.semantic_value_font(column, row.get(column))

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
        title.setObjectName("AboutTitle")
        font = QFont(title.font())
        font.setPointSizeF(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        tagline = QLabel("Android App Inventory, Store Analysis & Maintenance Toolkit")
        tagline.setObjectName("AboutTagline")
        tagline.setWordWrap(True)
        tagline_font = QFont(tagline.font())
        tagline_font.setPointSizeF(tagline_font.pointSizeF() + 1)
        tagline.setFont(tagline_font)
        layout.addWidget(tagline)

        version = QLabel(f"Version {__version__}")
        version.setObjectName("AboutVersion")
        version.setForegroundRole(QPalette.ColorRole.PlaceholderText)
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
