from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from playstore_app_audit.platform.subprocesses import install_hidden_subprocess_windows

# Install this before the UI modules start invoking adb.exe or other console tools.
install_hidden_subprocess_windows()

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
)

import playstore_app_audit.services.app_icon_metadata as app_icon_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.insights_window as insights_ui
from app_icon import ensure_runtime_icon
from playstore_app_audit import __version__
from playstore_app_audit.ui import schema
from playstore_app_audit.ui.app_icon_backfill import StoreMetadataBackfill, StoreMetadataRequest
from playstore_app_audit.ui.app_icon_loader import AppIconLoader

logger = logging.getLogger(__name__)

TABLE_SCHEMA_VERSION = "v12-schema-3"
ICON_STATUSES = {"available", "available_in_other_country", "available_in_fallback_locale_only"}
ICON_COLUMN = "play_title"
TABLE_ITEM_FOCUS_STYLE = "QTableView::item:focus { outline: none; }"
SELECTED_ROW_BACKGROUND = "#DDEBF7"
SELECTED_ROW_FOREGROUND = "#18212A"
LOCAL_APK_RELATIONSHIP_STATUS = {
    "Outdated": "orange",
    "Different": "yellow",
    "Unknown": "purple",
    "Device-specific": "blue",
    "Newer": "green",
    "Match": "green",
}


def _suppress_table_item_focus_outline(table: QTableView) -> None:
    """Hide only the native focus outline without changing logical selection."""

    current = table.styleSheet().strip()
    if TABLE_ITEM_FOCUS_STYLE in current:
        return
    table.setStyleSheet("\n".join(part for part in (current, TABLE_ITEM_FOCUS_STYLE) if part))


class SemanticSelectionDelegate(QStyledItemDelegate):
    """Paint one coherent row selection without Windows per-cell accent bars."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        super().initStyleOption(option, index)
        if not option.state & QStyle.StateFlag.State_Selected:
            return

        # Windows 11 can paint a leading accent bar for every selected table item.
        # With SelectRows that becomes one blue mark per cell. Keep the selection
        # model untouched, but paint the selected row ourselves as ordinary items.
        option.state &= ~(
            QStyle.StateFlag.State_Selected
            | QStyle.StateFlag.State_HasFocus
            | QStyle.StateFlag.State_KeyboardFocusChange
        )

        background = index.data(Qt.ItemDataRole.BackgroundRole)
        foreground = index.data(Qt.ItemDataRole.ForegroundRole)
        if isinstance(background, QColor):
            # Semantic cells keep their meaning and become only slightly darker
            # while selected, instead of being replaced by the generic blue tint.
            selected_background = background.darker(104)
        else:
            selected_background = QColor(SELECTED_ROW_BACKGROUND)
        option.backgroundBrush = QBrush(selected_background)

        if isinstance(foreground, QColor):
            option.palette.setColor(QPalette.ColorRole.Text, foreground)
        else:
            option.palette.setColor(QPalette.ColorRole.Text, QColor(SELECTED_ROW_FOREGROUND))


class AuditTableModel(base_ui.AppTableModel):
    """Qt model with an immutable column map and optional lazy app icons.

    Older builds changed the module-level COLUMNS tuple while progressively
    extending the table. A QTableView can retain header state between versions,
    while the model later observes a different global column tuple. Freezing the
    mapping inside the model prevents valid row data from appearing under an
    empty/mismatched logical column.
    """

    store_metadata_ready = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.columns = schema.MODEL_COLUMNS
        self._icons_enabled = bool(
            state.load_settings().get(
                "show_app_icons", app_icon_metadata.DEFAULT_SHOW_APP_ICONS
            )
        )
        self._icon_rows_by_package: dict[str, list[int]] = {}
        self._icon_loader = AppIconLoader(self)
        self._icon_loader.icon_ready.connect(self._on_icon_ready)
        self._metadata_backfill = StoreMetadataBackfill(self)
        self._metadata_backfill.completed.connect(self._on_metadata_backfilled)
        self._store_context_provider: Callable[[], tuple[str, str]] | None = None

    def set_store_context_provider(
        self, provider: Callable[[], tuple[str, str]] | None
    ) -> None:
        self._store_context_provider = provider
        self._schedule_missing_metadata()

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
        self._schedule_missing_metadata()

    def _schedule_missing_metadata(self) -> None:
        if not self._icons_enabled or self._store_context_provider is None:
            return
        country, language = self._store_context_provider()
        present_packages: set[str] = set()
        for row in self.rows:
            if str(row.get("play_status") or "") not in ICON_STATUSES:
                continue
            if str(row.get("play_icon_url") or "").strip():
                package_name = str(row.get("package_name") or "").strip()
                if package_name:
                    present_packages.add(package_name)
                continue
            self._metadata_backfill.schedule(row.get("package_name"), country, language)
        if present_packages:
            logger.debug(
                "Store icon metadata already present: packages=%d", len(present_packages)
            )

    def _on_metadata_backfilled(self, request: object, metadata: object) -> None:
        if not isinstance(request, StoreMetadataRequest) or not isinstance(metadata, dict):
            return
        if self._store_context_provider is None:
            return
        country, language = self._store_context_provider()
        if (request.country, request.language) != (country.lower(), language.lower()):
            return

        affected: list[int] = []
        icon_url = str(metadata.get("play_icon_url") or "").strip()
        developer = str(metadata.get("developer") or "").strip()
        for row_index, row in enumerate(self.rows):
            if str(row.get("package_name") or "").strip() != request.package_name:
                continue
            if str(row.get("play_status") or "") not in ICON_STATUSES:
                continue
            changed = False
            if icon_url and not str(row.get("play_icon_url") or "").strip():
                row["play_icon_url"] = icon_url
                self._icon_rows_by_package.setdefault(request.package_name, []).append(row_index)
                self.icon_for_row(row)
                changed = True
            if developer and not str(row.get("developer") or "").strip():
                row["developer"] = developer
                changed = True
            if changed:
                affected.append(row_index)
        if not affected:
            return

        state.update_cached_store_metadata(
            request.package_name,
            request.country,
            request.language,
            {key: str(value) for key, value in metadata.items()},
        )
        if icon_url and ICON_COLUMN in self.columns:
            column = self.columns.index(ICON_COLUMN)
            for row_index in affected:
                index = self.index(row_index, column)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])
        self.store_metadata_ready.emit(request.package_name)

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
        if enabled:
            self._schedule_missing_metadata()
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
            return schema.TABLE_HEADER_LABELS.get(column, column)
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

        local_apk_row = str(row.get("source_mode") or "").startswith("local_apk")

        if role == Qt.ItemDataRole.BackgroundRole:
            if not local_apk_row:
                return QColor(info["background"])
            if column == "criticality":
                return QColor(info["background"])
            if column == "local_apk_version_comparison":
                relation_key = LOCAL_APK_RELATIONSHIP_STATUS.get(str(row.get(column) or ""))
                if relation_key:
                    return QColor(base_ui.CRITICALITY[relation_key]["background"])
            return None

        if role == Qt.ItemDataRole.ForegroundRole:
            if column == "criticality":
                return QColor(info["accent"])
            if local_apk_row and column == "local_apk_version_comparison":
                relation_key = LOCAL_APK_RELATIONSHIP_STATUS.get(str(row.get(column) or ""))
                if relation_key:
                    return QColor(base_ui.CRITICALITY[relation_key]["foreground"])
            semantic_colour = base_ui.semantic_foreground_colour(column, row.get(column))
            if semantic_colour:
                return QColor(semantic_colour)
            return QColor("#263238")

        if role == Qt.ItemDataRole.ToolTipRole:
            if column == "notes":
                return presentation.friendly_notes(row)
            if column == "local_apk_location":
                return str(row.get(column) or "")

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
                "version_comparison",
                "local_apk_version_comparison",
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

        old_proxy = self.proxy  # type: ignore[has-type]
        stable_model = AuditTableModel()
        stable_model.set_store_context_provider(self._store_icon_context)
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
        self.table.setItemDelegate(SemanticSelectionDelegate(self.table))
        _suppress_table_item_focus_outline(self.table)
        self.table.setIconSize(QSize(22, 22))
        if hasattr(self, "_on_details_model_data_changed"):
            stable_model.store_metadata_ready.connect(self._on_details_model_data_changed)
        old_proxy.deleteLater()
        self._restore_table_layout()
        self._apply_column_visibility(reset_order=False)

    def _store_icon_context(self) -> tuple[str, str]:
        settings = state.load_settings()
        country = str(self.country_edit.text() or "us").strip().lower() or "us"
        language = str(settings.get("store_language") or "en").strip().lower() or "en"
        return country, language

    def cancel_icon_metadata_backfill(self) -> None:
        if isinstance(self.model, AuditTableModel):
            self.model._metadata_backfill.cancel()

    def closeEvent(self, event) -> None:
        self.cancel_icon_metadata_backfill()
        super().closeEvent(event)

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