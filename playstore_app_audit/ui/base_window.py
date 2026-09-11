from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit import __version__
from playstore_app_audit.platform import runtime
from playstore_app_audit.services import presentation
from playstore_app_audit.services.audit_engine import OUTPUT_FIELDS, AuditConfig, audit_apps, load_apps
from playstore_app_audit.ui import schema
from playstore_app_audit.ui.action_icons import main_action_icon

APP_NAME = "PlayStoreAppAudit"
PLATFORM_TOOLS_URL = runtime.platform_tools_url()
PLATFORM_TOOLS_PAGE = runtime.PLATFORM_TOOLS_PAGE
SDK_LICENSE_PAGE = "https://developer.android.com/studio/terms"


SYSTEM_COLUMN_NAMES = {
    "is_system",
    "issystem",
    "system",
    "system_app",
    "systemapp",
    "is_system_app",
    "issystemapp",
    "app_type",
    "apptype",
    "type",
}
PACKAGE_COLUMN_NAMES = {
    "package",
    "packageid",
    "packagename",
    "package_name",
    "appid",
    "app_id",
    "id",
}
TRUE_SYSTEM_VALUES = {
    "1",
    "true",
    "yes",
    "y",
    "system",
    "system_app",
    "systemapp",
    "preinstalled",
    "pre-installed",
}
FALSE_SYSTEM_VALUES = {
    "0",
    "false",
    "no",
    "n",
    "user",
    "user_app",
    "userapp",
    "third-party",
    "third_party",
    "thirdparty",
}

DEFINITE_SYSTEM_PREFIXES = (
    "com.android.",
    "com.google.android.overlay.",
    "com.google.android.providers.",
    "com.google.android.permissioncontroller",
    "com.google.android.modulemetadata",
    "com.google.android.ext.",
    "com.google.android.networkstack",
    "com.google.android.adservices.api",
    "com.google.android.ondevicepersonalization.services",
)
DEFINITE_SYSTEM_PACKAGES = {
    "android",
    "com.google.android.packageinstaller",
    "com.google.android.documentsui",
    "com.google.android.settings.intelligence",
    "com.google.android.cellbroadcastreceiver",
    "com.google.android.cellbroadcastservice",
    "com.google.android.connectivity.resources",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "gen": 1,
    "gennaio": 1,
    "feb": 2,
    "february": 2,
    "febbraio": 2,
    "mar": 3,
    "march": 3,
    "marzo": 3,
    "apr": 4,
    "april": 4,
    "aprile": 4,
    "may": 5,
    "maggio": 5,
    "mag": 5,
    "jun": 6,
    "june": 6,
    "giu": 6,
    "giugno": 6,
    "jul": 7,
    "july": 7,
    "lug": 7,
    "luglio": 7,
    "aug": 8,
    "august": 8,
    "ago": 8,
    "agosto": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "set": 9,
    "settembre": 9,
    "oct": 10,
    "october": 10,
    "ott": 10,
    "ottobre": 10,
    "nov": 11,
    "november": 11,
    "novembre": 11,
    "dec": 12,
    "december": 12,
    "dic": 12,
    "dicembre": 12,
}

CRITICALITY = {
    "red": {
        "label": "●  Not Found",
        "button": "● Not Found",
        "rank": 0,
        "background": "#FDF3F3",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["red"],
        "accent": "#C94B4B",
        "tooltip": "Show apps with no conclusive Google Play listing.",
    },
    "orange": {
        "label": "●  Stale",
        "button": "● Stale",
        "rank": 1,
        "background": "#FFF7EE",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["orange"],
        "accent": "#D77A23",
        "tooltip": "Show apps last updated more than 730 days ago.",
    },
    "yellow": {
        "label": "●  Aging",
        "button": "● Aging",
        "rank": 2,
        "background": "#FFFCEF",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["yellow"],
        "accent": "#C6A919",
        "tooltip": "Show apps last updated 366 to 730 days ago.",
    },
    "blue": {
        "label": "●  Store anomaly",
        "button": "● Anomaly",
        "rank": 3,
        "background": "#F0F7FC",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["blue"],
        "accent": "#3A84B8",
        "tooltip": "Show apps with unusual or inconclusive Store availability.",
    },
    "purple": {
        "label": "●  Other",
        "button": "● Other",
        "rank": 4,
        "background": "#F8F2FA",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["purple"],
        "accent": "#8E5BA6",
        "tooltip": "Show apps with unknown results or audit errors.",
    },
    "green": {
        "label": "●  Current",
        "button": "● Current",
        "rank": 5,
        "background": "#F2F9F3",
        "foreground": presentation.STATUS_FOREGROUND_COLOURS["green"],
        "accent": "#4D9560",
        "tooltip": "Show apps updated within the last 365 days.",
    },
}

def semantic_foreground_colour(column: str, value: object) -> str | None:
    return presentation.semantic_foreground_colour(column, value)


def semantic_value_font(
    column: str, value: object, base_font: QFont | None = None
) -> QFont | None:
    value_presentation = presentation.semantic_value_presentation(column, value)
    if value_presentation is None:
        return None
    font = QFont(base_font) if base_font is not None else QFont()
    font.setWeight(QFont.Weight(value_presentation.font_weight))
    return font


def apply_semantic_label_presentation(
    label: QLabel, column: str, value: object
) -> bool:
    colour = semantic_foreground_colour(column, value)
    font = semantic_value_font(column, value, label.font())
    if colour is None or font is None:
        return False

    palette = label.palette()
    semantic_colour = QColor(colour)
    palette.setColor(
        QPalette.ColorGroup.Active,
        QPalette.ColorRole.WindowText,
        semantic_colour,
    )
    palette.setColor(
        QPalette.ColorGroup.Inactive,
        QPalette.ColorRole.WindowText,
        semantic_colour,
    )
    # Keep the platform's Disabled-role colour so disabled/unavailable labels
    # continue to follow native contrast behavior.
    label.setPalette(palette)
    label.setFont(font)
    return True

COLUMNS = schema.MODEL_COLUMNS
COLUMN_LABELS = dict(schema.COLUMN_LABELS)
EXPORT_FIELDS = list(dict.fromkeys(list(OUTPUT_FIELDS) + list(schema.EXPORT_EXTRA_FIELDS)))


def normalise_header(value: str) -> str:
    return "".join(
        character
        for character in value.strip().lower().replace(" ", "_").replace("-", "_")
        if character.isalnum() or character == "_"
    )


def parse_bool(value: str) -> bool | None:
    normalised = value.strip().lower()
    if normalised in TRUE_SYSTEM_VALUES:
        return True
    if normalised in FALSE_SYSTEM_VALUES:
        return False
    return None


def parse_update_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None

    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ.]+)\s+(\d{4})", text)
    if match:
        day, month_name, year = match.groups()
        month = MONTHS.get(month_name.lower().rstrip("."))
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None

    match = re.fullmatch(r"([A-Za-zÀ-ÿ.]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if match:
        month_name, day, year = match.groups()
        month = MONTHS.get(month_name.lower().rstrip("."))
        if month:
            try:
                return date(int(year), month, int(day))
            except ValueError:
                return None
    return None


def classify_criticality(row: dict[str, object]) -> None:
    status = str(row.get("play_status") or "").strip()
    update_date = parse_update_date(row.get("play_last_update"))
    age_days: int | None = None

    if status == "not_found_or_unavailable":
        key = "red"
    elif status == "available_in_fallback_locale_only":
        key = "blue"
    elif status != "available" or update_date is None:
        key = "purple"
    else:
        age_days = (date.today() - update_date).days
        if age_days < 0:
            key = "purple"
        elif age_days <= 365:
            key = "green"
        elif age_days <= 730:
            key = "yellow"
        else:
            key = "orange"

    row["criticality_key"] = key
    row["criticality"] = CRITICALITY[key]["label"]
    row["criticality_rank"] = CRITICALITY[key]["rank"]
    row["age_days"] = "" if age_days is None else age_days


def detect_windows_country() -> str:
    """Compatibility name for the canonical cross-platform Store-country detector."""
    return runtime.detect_store_country()


def managed_platform_tools_dir() -> Path:
    return runtime.managed_platform_tools_dir()


def parse_adb_packages(output: str) -> set[str]:
    return {
        line.replace("package:", "", 1).strip()
        for line in output.splitlines()
        if line.strip().startswith("package:")
    }


def is_definite_system_package(package_name: str) -> bool:
    return package_name in DEFINITE_SYSTEM_PACKAGES or any(
        package_name.startswith(prefix) for prefix in DEFINITE_SYSTEM_PREFIXES
    )


class AppTableModel(QAbstractTableModel):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[dict[str, object]] = []

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(COLUMNS):
            return schema.TABLE_HEADER_LABELS[COLUMNS[section]]
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None

        row = self.rows[index.row()]
        column = COLUMNS[index.column()]
        key = str(row.get("criticality_key") or "purple")
        info = CRITICALITY.get(key, CRITICALITY["purple"])

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
            semantic_colour = semantic_foreground_colour(column, row.get(column))
            if semantic_colour:
                return QColor(semantic_colour)
            return QColor("#263238")

        if role == Qt.ItemDataRole.FontRole:
            if column == "criticality":
                font = QFont()
                font.setBold(True)
                return font
            return semantic_value_font(column, row.get(column))

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in {"play_status", "play_last_update", "age_days", "criticality"}:
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        if role == Qt.ItemDataRole.UserRole:
            return row

        return None

    def row_dict(self, source_row: int) -> dict[str, object]:
        return self.rows[source_row]


class AppFilterProxy(QSortFilterProxyModel):
    def __init__(self) -> None:
        super().__init__()
        self.query = ""
        self.hide_system = True
        self.criticality_filter: str | None = None
        self.setDynamicSortFilter(True)

    def set_query(self, query: str) -> None:
        self.beginFilterChange()
        self.query = query.strip().casefold()
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_hide_system(self, hide: bool) -> None:
        self.beginFilterChange()
        self.hide_system = hide
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def set_criticality_filter(self, key: str | None) -> None:
        self.beginFilterChange()
        self.criticality_filter = key
        self.endFilterChange(QSortFilterProxyModel.Direction.Rows)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, AppTableModel):
            return True
        row = model.row_dict(source_row)

        if self.hide_system and bool(row.get("is_system")):
            return False

        if self.criticality_filter and row.get("criticality_key") != self.criticality_filter:
            return False

        if self.query:
            search_fields = list(OUTPUT_FIELDS) + ["criticality", "is_system", "age_days", "criticality_key"]
            haystack = " ".join(str(row.get(field, "") or "") for field in search_fields).casefold()
            if self.query not in haystack:
                return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, AppTableModel):
            return super().lessThan(left, right)

        column = COLUMNS[left.column()]
        left_row = model.row_dict(left.row())
        right_row = model.row_dict(right.row())

        def sort_value(row: dict[str, object]):
            if column == "criticality":
                return int(row.get("criticality_rank", 99))
            if column == "age_days":
                try:
                    return int(row.get("age_days", ""))
                except (TypeError, ValueError):
                    return -1
            if column == "play_last_update":
                parsed = parse_update_date(row.get(column))
                return parsed.toordinal() if parsed else -1
            return str(row.get(column, "") or "").strip().casefold()

        return sort_value(left_row) < sort_value(right_row)


class WorkerSignals(QObject):
    progress = Signal(int, int, str)
    audit_done = Signal(object)
    failed = Signal(str)
    adb_discovery_done = Signal(object, int)
    adb_scan_done = Signal(object, object)
    adb_scan_failed = Signal(int, str)
    adb_install_done = Signal(str, str)


class BaseWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Play Store App Audit")
        self.resize(1500, 900)
        self.setMinimumSize(1100, 700)

        self.signals = WorkerSignals()
        self.signals.progress.connect(self._on_progress)
        self.signals.audit_done.connect(self._on_audit_done)
        self.signals.failed.connect(self._on_worker_failed)
        self.signals.adb_scan_done.connect(self._on_adb_scan_done)
        self.signals.adb_scan_failed.connect(self._on_adb_scan_failed)
        self.signals.adb_install_done.connect(self._on_adb_install_done)

        self.source_mode: str | None = None
        self.file_apps: list[dict[str, str]] = []
        self.file_system_metadata: dict[str, bool] = {}
        self.device_apps_all: list[dict[str, str]] = []
        self.device_system_packages: set[str] = set()
        self.current_system_packages: set[str] = set()
        self.current_rows: list[dict[str, object]] = []
        self.criticality_filter: str | None = None
        self.advanced_visible = False
        self.pending_scan_after_install = False

        self.model = AppTableModel()
        self.proxy = AppFilterProxy()
        self.proxy.setSourceModel(self.model)

        self._build_ui()
        self._apply_style()
        self._update_summary()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget#Central {
                background: #F5F7FA;
                color: #20252B;
            }
            QFrame#Card {
                background: #FFFFFF;
                border: 1px solid #E2E7EC;
                border-radius: 12px;
            }
            QLabel#Title {
                font-size: 22pt;
                font-weight: 700;
                color: #18212A;
            }
            QLabel#Subtitle {
                color: #64717D;
                font-size: 10pt;
            }
            QLabel#SectionTitle {
                font-size: 11pt;
                font-weight: 650;
                color: #26323D;
            }
            QLabel#Muted {
                color: #6F7C87;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #FFFFFF;
                border: 1px solid #CCD4DC;
                border-radius: 7px;
                min-height: 31px;
                padding: 2px 8px;
                selection-background-color: #2F75B5;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #4A8BC2;
            }
            QPushButton, QToolButton {
                background: #FFFFFF;
                border: 1px solid #CCD4DC;
                border-radius: 7px;
                min-height: 32px;
                padding: 2px 12px;
            }
            QPushButton:hover, QToolButton:hover {
                background: #F2F6FA;
                border-color: #AEBBC6;
            }
            QPushButton#Primary {
                background: #236EA8;
                color: white;
                border: 1px solid #236EA8;
                font-weight: 650;
                min-height: 38px;
            }
            QPushButton#Primary:hover {
                background: #1D6398;
            }
            QPushButton#CriticalityButton {
                min-height: 29px;
                padding: 1px 9px;
            }
            QPushButton#CriticalityButton:checked {
                border: 2px solid #657786;
                font-weight: 650;
            }
            QCheckBox {
                spacing: 7px;
            }
            QProgressBar {
                background: #E9EEF3;
                border: none;
                border-radius: 5px;
                height: 10px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: #4A8BC2;
                border-radius: 5px;
            }
            QTableView {
                background: #FFFFFF;
                alternate-background-color: #FAFBFC;
                border: 1px solid #DFE5EA;
                border-radius: 8px;
                gridline-color: #E7EBEF;
                selection-background-color: #DDEBF7;
                selection-color: #18212A;
            }
            QHeaderView::section {
                background: #F1F4F7;
                color: #35424E;
                border: none;
                border-right: 1px solid #DDE3E8;
                border-bottom: 1px solid #D7DEE5;
                padding: 3px 7px;
                font-weight: 650;
            }
            """
        )

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        return frame, layout

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
        self.choose_button.setIcon(main_action_icon("choose_file", self.palette()))
        self.choose_button.clicked.connect(self._choose_input)
        self.scan_button = QPushButton("Scan Phone with ADB")
        self.scan_button.setIcon(main_action_icon("scan_phone", self.palette()))
        self.scan_button.clicked.connect(self._scan_phone)
        source_line.addWidget(self.path_edit, 1)
        source_line.addWidget(self.choose_button)
        source_line.addWidget(self.scan_button)
        source_layout.addLayout(source_line)

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

        self.advanced_button = QToolButton()
        self.advanced_button.setText("Advanced")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setArrowType(Qt.ArrowType.RightArrow)
        self.advanced_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.advanced_button.toggled.connect(self._toggle_advanced)
        settings_grid.addWidget(self.advanced_button, 0, 4)

        hint = QLabel("Country affects Store availability; language normally does not.")
        hint.setObjectName("Muted")
        settings_grid.addWidget(hint, 1, 0, 1, 5)
        settings_layout.addLayout(settings_grid)

        self.advanced_panel = QFrame()
        self.advanced_panel.setVisible(False)
        advanced_layout = QHBoxLayout(self.advanced_panel)
        advanced_layout.setContentsMargins(0, 4, 0, 0)

        advanced_layout.addWidget(QLabel("Store language"))
        self.language_edit = QLineEdit("en")
        self.language_edit.setMaxLength(8)
        self.language_edit.setFixedWidth(75)
        advanced_layout.addWidget(self.language_edit)

        self.skip_system_check = QCheckBox("Skip system apps during audit")
        self.skip_system_check.setToolTip(
            "Faster, but skipped system apps are not queried and cannot appear in results."
        )
        advanced_layout.addSpacing(12)
        advanced_layout.addWidget(self.skip_system_check)
        advanced_layout.addStretch(1)
        settings_layout.addWidget(self.advanced_panel)

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
        self.export_button.setIcon(main_action_icon("export_results", self.palette()))
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
        self.store_status_filter_label = QLabel("Store Status:")
        self.store_status_filter_label.setObjectName("StoreStatusFilterLabel")
        self.store_status_filter_label.setToolTip(
            "These filters use Store Status only; version relationships remain independent."
        )
        chip_row.addWidget(self.store_status_filter_label)
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
                f"""
                QPushButton {{
                    background: {info["background"]};
                    color: {info["foreground"]};
                    border: 1px solid {info["background"]};
                }}
                QPushButton:hover {{
                    border: 1px solid {info["accent"]};
                }}
                QPushButton:checked {{
                    border: 2px solid {info["accent"]};
                    font-weight: 650;
                }}
                """
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
        self.table.setToolTip(
            "Double-click to open Google Play when available. Right-click for more options."
        )
        self.table.doubleClicked.connect(self._open_selected_store_url)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        results_layout.addWidget(self.table, 1)

        for column, key in enumerate(COLUMNS):
            self.table.setColumnWidth(column, schema.DEFAULT_WIDTHS.get(key, 140))

    def _toggle_advanced(self, visible: bool) -> None:
        self.advanced_panel.setVisible(visible)
        self.advanced_button.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)

    def _set_busy(self, busy: bool) -> None:
        self.run_button.setEnabled(not busy)
        self.choose_button.setEnabled(not busy)
        self.scan_button.setEnabled(not busy)
        self.export_button.setEnabled((not busy) and bool(self.current_rows))

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

        self.file_apps = apps
        self.file_system_metadata = metadata
        self.device_apps_all = []
        self.device_system_packages = set()
        self.source_mode = "file"
        self.path_edit.setText(selected)
        meta_text = f" • system flag available for {len(metadata)} packages" if metadata else ""
        self.source_label.setText(f"File selected: {len(apps)} unique Android packages{meta_text}")
        self.status_label.setText("File ready. Run the Play Store audit.")

    def _read_system_metadata_from_file(
        self, path: str | Path, apps: list[dict[str, str]]
    ) -> dict[str, bool]:
        file_path = Path(path)
        if file_path.suffix.lower() not in {".csv", ".tsv"}:
            return {}
        raw = file_path.read_text(encoding="utf-8-sig", errors="replace")
        if not raw.strip():
            return {}
        try:
            delimiter = csv.Sniffer().sniff(raw[:5000], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","

        reader = csv.DictReader(raw.splitlines(), delimiter=delimiter)
        fieldnames = reader.fieldnames or []
        normalised = {normalise_header(name): name for name in fieldnames if name is not None}
        package_column = next(
            (original for name, original in normalised.items() if name in PACKAGE_COLUMN_NAMES),
            None,
        )
        system_column = next(
            (original for name, original in normalised.items() if name in SYSTEM_COLUMN_NAMES),
            None,
        )
        if not package_column or not system_column:
            return {}

        valid_packages = {app["package_name"] for app in apps}
        metadata: dict[str, bool] = {}
        for row in reader:
            package_name = (row.get(package_column) or "").strip()
            if package_name not in valid_packages:
                continue
            value = parse_bool(row.get(system_column) or "")
            if value is not None:
                metadata[package_name] = value
        return metadata

    def _find_adb(self) -> str | None:
        candidates: list[str | None] = [
            shutil.which("adb"),
            str(Path.cwd() / "adb.exe"),
            str(Path.cwd() / "platform-tools" / "adb.exe"),
            str(managed_platform_tools_dir() / "adb.exe"),
        ]

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            candidates.append(str(Path(local_app_data) / "Android" / "Sdk" / "platform-tools" / "adb.exe"))

        for variable in ("ANDROID_SDK_ROOT", "ANDROID_HOME"):
            value = os.environ.get(variable)
            if value:
                candidates.append(str(Path(value) / "platform-tools" / "adb.exe"))

        seen: set[str] = set()
        for candidate in candidates:
            if not candidate:
                continue
            normalised = str(Path(candidate))
            if normalised in seen:
                continue
            seen.add(normalised)
            if Path(normalised).is_file():
                return normalised
        return None

    def _get_system_packages_from_adb(self, adb: str) -> set[str]:
        result = subprocess.run(
            [adb, "shell", "pm", "list", "packages", "-s"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        return parse_adb_packages(result.stdout)

    def _get_authorised_adb(self) -> str | None:
        adb = self._find_adb()
        if not adb:
            return None
        try:
            devices = subprocess.run(
                [adb, "devices"], check=True, capture_output=True, text=True, timeout=20
            ).stdout.splitlines()
        except Exception:
            return None
        return (
            adb
            if any(len(line.split()) >= 2 and line.split()[1] == "device" for line in devices[1:])
            else None
        )

    def _scan_phone(self) -> None:
        adb = self._find_adb()
        if not adb:
            choice = QMessageBox.question(
                self,
                "Install Android Platform-Tools?",
                "ADB is not installed on this PC.\n\n"
                "PlayStoreAppAudit can download the latest Windows Platform-Tools directly "
                "from Google's official fixed download endpoint and install them only for this app.\n\n"
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
                QDesktopServices.openUrl(QUrl(PLATFORM_TOOLS_PAGE))
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
            target = managed_platform_tools_dir()
            with tempfile.TemporaryDirectory(prefix="playstore_audit_adb_") as temp_dir:
                temp_root = Path(temp_dir)
                archive_path = temp_root / "platform-tools.zip"
                request = urllib.request.Request(
                    PLATFORM_TOOLS_URL, headers={"User-Agent": f"{APP_NAME}/{__version__}"}
                )
                with (
                    urllib.request.urlopen(request, timeout=90) as response,
                    archive_path.open("wb") as output,
                ):
                    shutil.copyfileobj(response, output)

                extract_root = temp_root / "extract"
                extract_root.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive_path, "r") as archive:
                    root_resolved = extract_root.resolve()
                    for member in archive.infolist():
                        destination = (extract_root / member.filename).resolve()
                        if root_resolved not in destination.parents and destination != root_resolved:
                            raise RuntimeError("Unsafe path in Platform-Tools archive.")
                    archive.extractall(extract_root)

                extracted_tools = extract_root / "platform-tools"
                extracted_adb = extracted_tools / "adb.exe"
                if not extracted_adb.is_file():
                    raise RuntimeError("Google Platform-Tools archive did not contain adb.exe.")

                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(extracted_tools, target)

            adb = target / "adb.exe"
            version = (
                subprocess.run(
                    [str(adb), "version"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                .stdout.strip()
                .splitlines()
            )
            version_text = version[0] if version else "ADB installed"
            self.signals.adb_install_done.emit(str(adb), version_text)
        except Exception as exc:
            self.signals.failed.emit(f"ADB installation failed:\n\n{exc}")

    def _on_adb_install_done(self, adb: str, version_text: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_busy(False)
        QMessageBox.information(
            self,
            "ADB installed",
            f"{version_text}\n\nInstalled in:\n{managed_platform_tools_dir()}\n\n"
            "Keep the phone unlocked and accept the USB debugging RSA prompt if it appears.",
        )
        if self.pending_scan_after_install:
            self.pending_scan_after_install = False
            self._start_adb_scan(adb)

    def _start_adb_scan(self, adb: str) -> None:
        self._set_busy(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("Checking ADB device connection…")
        threading.Thread(target=self._scan_phone_worker, args=(adb,), daemon=True).start()

    def _scan_phone_worker(self, adb: str) -> None:
        try:
            devices_output = subprocess.run(
                [adb, "devices"],
                check=True,
                capture_output=True,
                text=True,
                timeout=20,
            ).stdout.splitlines()

            device_rows: list[tuple[str, str]] = []
            for line in devices_output[1:]:
                parts = line.split()
                if len(parts) >= 2:
                    device_rows.append((parts[0], parts[1]))

            authorised = [serial for serial, state in device_rows if state == "device"]
            unauthorised = [serial for serial, state in device_rows if state == "unauthorized"]
            offline = [serial for serial, state in device_rows if state == "offline"]

            if not authorised:
                if unauthorised:
                    raise RuntimeError(
                        "The phone is visible to ADB but is not authorised.\n\n"
                        "Unlock the phone and accept the 'Allow USB debugging?' RSA prompt, then scan again."
                    )
                if offline:
                    raise RuntimeError(
                        "The phone is visible to ADB but is offline.\n\n"
                        "Disconnect/reconnect the USB cable, unlock the phone and try again."
                    )
                raise RuntimeError(
                    "ADB is installed, but no Android phone is visible.\n\n"
                    "Check USB debugging, use a data-capable USB cable, select a USB data/file-transfer "
                    "mode if needed, and install the phone manufacturer's USB driver if Windows requires it."
                )

            all_result = subprocess.run(
                [adb, "shell", "pm", "list", "packages"],
                check=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
            system_packages = self._get_system_packages_from_adb(adb)
            all_packages = sorted(parse_adb_packages(all_result.stdout))
            if not all_packages:
                raise RuntimeError("ADB returned no Android packages.")

            apps = [{"app_name": package, "package_name": package} for package in all_packages]
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

        user_count = sum(1 for app in typed_apps if app["package_name"] not in typed_system)
        self.source_label.setText(
            f"Phone scan: {len(typed_apps)} total packages • "
            f"{user_count} third-party • {len(typed_system)} system"
        )
        self.status_label.setText("Phone scan ready. Run the Play Store audit.")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._set_busy(False)

    def _on_adb_scan_failed(self, _request_id: int, message: str) -> None:
        self._on_worker_failed(message)

    def _classify_file_system_packages(self, apps: list[dict[str, str]]) -> tuple[set[str], str]:
        system_packages = {
            package_name for package_name, is_system in self.file_system_metadata.items() if is_system
        }
        known_user_packages = {
            package_name for package_name, is_system in self.file_system_metadata.items() if not is_system
        }
        method_parts: list[str] = []
        if self.file_system_metadata:
            method_parts.append("CSV system flag")

        adb = self._get_authorised_adb()
        if adb:
            try:
                system_packages.update(self._get_system_packages_from_adb(adb))
                method_parts.append("ADB exact match")
            except Exception:
                adb = None

        heuristic_count = 0
        if not adb:
            for app in apps:
                package_name = app["package_name"]
                if package_name in system_packages or package_name in known_user_packages:
                    continue
                if is_definite_system_package(package_name):
                    system_packages.add(package_name)
                    heuristic_count += 1
            if heuristic_count:
                method_parts.append("conservative package-name fallback")

        method = (
            " + ".join(method_parts)
            if method_parts
            else "no exact classifier available; connect the source phone via ADB or add an is_system column"
        )
        valid_packages = {app["package_name"] for app in apps}
        return system_packages.intersection(valid_packages), method

    def _get_apps_to_audit(self) -> tuple[list[dict[str, str]], set[str], str]:
        if self.source_mode == "device" and self.device_apps_all:
            return (
                list(self.device_apps_all),
                set(self.device_system_packages),
                "ADB exact system classification",
            )
        if self.source_mode == "file" and self.file_apps:
            system_packages, method = self._classify_file_system_packages(self.file_apps)
            return list(self.file_apps), system_packages, method
        raise ValueError("Choose a CSV/TXT file or scan a connected Android phone first.")

    def _start_audit(self) -> None:
        try:
            all_apps, system_packages, classification_method = self._get_apps_to_audit()
        except Exception as exc:
            QMessageBox.warning(self, "No app list", str(exc))
            return

        country = (self.country_edit.text().strip() or detect_windows_country()).lower()
        language = (self.language_edit.text().strip() or "en").lower()
        workers = self.workers_spin.value()

        apps = list(all_apps)
        skipped_system = 0
        if self.skip_system_check.isChecked():
            apps = [app for app in all_apps if app["package_name"] not in system_packages]
            skipped_system = len(all_apps) - len(apps)
            if not apps:
                QMessageBox.warning(
                    self,
                    "Nothing to audit",
                    "All packages were classified as system apps and skipped by Advanced settings.",
                )
                return

        self.current_system_packages = system_packages
        self.criticality_filter = None
        self._sync_criticality_buttons()
        source_label = "Phone" if self.source_mode == "device" else "CSV/TXT"
        extra = f" • {skipped_system} system skipped" if skipped_system else ""
        self.source_label.setText(
            f"{source_label} source: {len(all_apps)} packages • "
            f"{len(system_packages)} classified as system • {classification_method}{extra}"
        )

        self.current_rows = []
        self.model.set_rows([])
        self._set_busy(True)
        self.progress.setRange(0, len(apps))
        self.progress.setValue(0)
        self.status_label.setText(
            f"Starting audit for {len(apps)} packages in Store country '{country}'"
            + (f" ({skipped_system} system apps skipped)…" if skipped_system else "…")
        )

        config = AuditConfig(
            country=country,
            language=language,
            max_workers=workers,
        )
        threading.Thread(target=self._audit_worker, args=(apps, config), daemon=True).start()

    def _audit_worker(self, apps: list[dict[str, str]], config: AuditConfig) -> None:
        try:

            def progress(done: int, total: int, package_name: str) -> None:
                self.signals.progress.emit(done, total, package_name)

            rows = audit_apps(apps, config, progress)
            self.signals.audit_done.emit(rows)
        except Exception as exc:
            self.signals.failed.emit(f"Audit failed:\n\n{exc}")

    def _on_progress(self, done: int, total: int, package_name: str) -> None:
        self.progress.setRange(0, total)
        self.progress.setValue(done)
        self.status_label.setText(f"Completed {done}/{total}: {package_name}")

    def _on_audit_done(self, rows: object) -> None:
        typed_rows = list(rows)  # type: ignore[arg-type]
        for row in typed_rows:
            row["is_system"] = str(row.get("package_name") or "") in self.current_system_packages
            classify_criticality(row)

        self.current_rows = typed_rows
        self.model.set_rows(typed_rows)
        self.progress.setRange(0, max(len(typed_rows), 1))
        self.progress.setValue(len(typed_rows))
        self.status_label.setText("Audit completed")
        self._set_busy(False)
        self.export_button.setEnabled(True)
        self._update_summary()

    def _on_worker_failed(self, message: str) -> None:
        self.pending_scan_after_install = False
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("Operation failed")
        self._set_busy(False)
        QMessageBox.critical(self, "Operation failed", message)

    def _on_search_changed(self, text: str) -> None:
        self.proxy.set_query(text)
        self._update_summary()

    def _on_hide_system_changed(self, checked: bool) -> None:
        self.proxy.set_hide_system(checked)
        self._update_summary()

    def _set_criticality_filter(self, key: str | None) -> None:
        if key is not None and self.criticality_filter == key:
            key = None
        self.criticality_filter = key
        self.proxy.set_criticality_filter(key)
        self._sync_criticality_buttons()
        self._update_summary()

    def _sync_criticality_buttons(self) -> None:
        self.all_chip.setChecked(self.criticality_filter is None)
        for key, button in self.criticality_buttons.items():
            button.setChecked(self.criticality_filter == key)

    def _rows_before_criticality_filter(self) -> list[dict[str, object]]:
        rows = self.current_rows
        if self.hide_system_check.isChecked():
            rows = [row for row in rows if not row.get("is_system")]

        query = self.search_edit.text().strip().casefold()
        if query:
            search_fields = list(OUTPUT_FIELDS) + ["criticality", "is_system", "age_days", "criticality_key"]
            rows = [
                row
                for row in rows
                if query in " ".join(str(row.get(field, "") or "") for field in search_fields).casefold()
            ]
        return rows

    def _update_summary(self) -> None:
        base_rows = self._rows_before_criticality_filter()
        counts = {
            key: sum(1 for row in base_rows if row.get("criticality_key") == key) for key in CRITICALITY
        }
        for key, button in self.criticality_buttons.items():
            button.setText(f"{CRITICALITY[key]['button']} {counts[key]}")

        visible = self.proxy.rowCount()
        total = len(self.current_rows)
        if not total:
            self.summary_label.setText("No Results Yet")
            return

        parts = [f"Showing {visible}/{total}"]
        if self.hide_system_check.isChecked():
            hidden_system = sum(1 for row in self.current_rows if row.get("is_system"))
            if hidden_system:
                parts.append(f"{hidden_system} system hidden")
        if self.criticality_filter:
            parts.append(str(CRITICALITY[self.criticality_filter]["label"]).replace("●  ", ""))
        self.summary_label.setText("  •  ".join(parts))

    def _open_selected_store_url(self, proxy_index: QModelIndex) -> None:
        if not proxy_index.isValid():
            return
        source_index = self.proxy.mapToSource(proxy_index)
        row = self.model.row_dict(source_index.row())
        store_url = str(row.get("store_url") or "").strip()
        if store_url:
            QDesktopServices.openUrl(QUrl(store_url))

    def _export_results(self) -> None:
        if not self.current_rows:
            return
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Export audit results",
            "playstore_audit_results.csv",
            "CSV (*.csv)",
        )
        if not selected:
            return
        if not selected.lower().endswith(".csv"):
            selected += ".csv"

        try:
            with open(selected, "w", newline="", encoding="utf-8-sig") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=EXPORT_FIELDS,
                    extrasaction="ignore",
                )
                writer.writeheader()
                writer.writerows(self.current_rows)
            QMessageBox.information(self, "Export complete", f"Results saved to:\n{selected}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _clear_results(self) -> None:
        self.current_rows = []
        self.current_system_packages = set()
        self.criticality_filter = None
        self.search_edit.clear()
        self.model.set_rows([])
        self.proxy.set_criticality_filter(None)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.status_label.setText("Ready")
        self.export_button.setEnabled(False)
        self._sync_criticality_buttons()
        self._update_summary()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("MRC")
    window = BaseWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
