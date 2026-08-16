from __future__ import annotations

import sys

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

# Install this before the UI modules start invoking adb.exe or other console tools.
install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor, QFont, QIcon
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.device_window as device_ui
import playstore_app_audit.ui.insights_window as insights_ui
from app_icon import ensure_runtime_icon

TABLE_SCHEMA_VERSION = "v9-fixed-1"


class AuditTableModel(base_ui.AppTableModel):
    """Qt model with an immutable column map.

    Older builds changed the module-level COLUMNS tuple while progressively
    extending the table. A QTableView can retain header state between versions,
    while the model later observes a different global column tuple. Freezing the
    mapping inside the model prevents valid row data from appearing under an
    empty/mismatched logical column.
    """

    def __init__(self) -> None:
        super().__init__()
        self.columns = tuple(insights_ui.V9_MODEL_COLUMNS)

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

        # Keep every Qt layer on the same schema before constructing widgets.
        device_ui.V8_MODEL_COLUMNS = tuple(insights_ui.V9_MODEL_COLUMNS)
        compact_ui.MODEL_COLUMNS = tuple(insights_ui.V9_MODEL_COLUMNS)
        base_ui.COLUMNS = tuple(insights_ui.V9_MODEL_COLUMNS)

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

        info = QLabel(
            "<b>Created by MRC</b><br><br>"
            "Audit Android packages against public Google Play listings, update dates, "
            "regional availability and optional connected-device metadata.<br><br>"
            f'<a href="{compact_ui.PROJECT_URL}">MRC on GitHub</a><br><br>'
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
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(ensure_runtime_icon())))
    window = TableWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
