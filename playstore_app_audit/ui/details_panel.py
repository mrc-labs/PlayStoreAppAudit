from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.change_overview as change_service

AUDIT_CHANGES_FIELD = "_audit_changes"
STORE_EVIDENCE_FIELD = "_store_evidence"

_CHANGE_LABELS = {
    "reappeared": "Reappeared in checked Store markets",
    "newly_available": "Now available after a previous inconclusive/unavailable check",
    "newly_unavailable_in_checked_countries": "No longer found in the checked Store markets",
    "store_version_changed": "Play Store version changed",
    "store_latest_update_changed": "Play Store latest-update date changed",
    "maintenance_state_changed": "Maintenance state changed",
    "installer_source_changed": "Installer/source changed",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def normalise_details_panel_position(value: object) -> str:
    return "below" if _text(value).casefold() == "below" else "right"


def evidence_lines(row: Mapping[str, Any]) -> list[str]:
    raw = row.get(STORE_EVIDENCE_FIELD)
    if not isinstance(raw, list):
        return []
    lines: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        role = _text(item.get("role")).replace("_", " ").title() or "Store check"
        language_role = _text(item.get("language_role"))
        country = _text(item.get("country")).upper() or "?"
        language = _text(item.get("language")).lower() or "?"
        status = _text(item.get("status")).replace("_", " ") or "unknown"
        source = _text(item.get("source"))
        http_status = _text(item.get("http_status"))
        suffix = []
        if language_role == "english_fallback":
            suffix.append("English fallback")
        if http_status:
            suffix.append(f"HTTP {http_status}")
        if source:
            suffix.append(source)
        detail = f"{role}: {country}/{language} • {status}"
        if suffix:
            detail += " • " + " • ".join(suffix)
        lines.append(detail)
    return lines


def change_lines(row: Mapping[str, Any]) -> list[str]:
    raw = row.get(AUDIT_CHANGES_FIELD)
    lines: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            event_type = _text(item.get("type"))
            label = _CHANGE_LABELS.get(event_type, event_type.replace("_", " ").title())
            previous = _text(item.get("previous"))
            current = _text(item.get("current"))
            if previous and current:
                lines.append(f"{label}: {previous} → {current}")
            else:
                lines.append(label)
    device_change = _text(row.get("device_change"))
    if (
        bool(row.get(change_service.DEVICE_HISTORY_FLAG))
        and device_change
        and device_change.casefold() not in {"same", "unchanged", "none"}
    ):
        lines.append(f"Device inventory: {device_change}")
    return lines


def _joined_fields(row: Mapping[str, Any], fields: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for label, key in fields:
        value = _text(row.get(key))
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


class AppDetailsPanel(QFrame):
    position_changed = Signal(str)
    review_changes_requested = Signal()

    def __init__(self, position: str = "right", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppDetailsPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(300)
        self.setMinimumHeight(210)
        self._row: dict[str, Any] | None = None
        self._section_widgets: list[QWidget] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(9)
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(38, 38)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        self.title_label = QLabel("App details")
        title_font = QFont(self.title_label.font())
        title_font.setBold(True)
        title_font.setPointSizeF(title_font.pointSizeF() + 1)
        self.title_label.setFont(title_font)
        self.title_label.setWordWrap(True)
        title_box.addWidget(self.title_label)
        self.developer_label = QLabel()
        self.developer_label.setObjectName("Muted")
        self.developer_label.setWordWrap(True)
        title_box.addWidget(self.developer_label)
        header.addLayout(title_box, 1)
        root.addLayout(header)

        position_row = QHBoxLayout()
        position_row.addWidget(QLabel("Panel position"))
        self.position_combo = QComboBox()
        self.position_combo.addItem("Right", "right")
        self.position_combo.addItem("Below", "below")
        wanted = normalise_details_panel_position(position)
        self.position_combo.setCurrentIndex(1 if wanted == "below" else 0)
        self.position_combo.currentIndexChanged.connect(self._emit_position)
        position_row.addWidget(self.position_combo)
        position_row.addStretch(1)
        root.addLayout(position_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 4, 0)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)

        self.placeholder = QLabel("Select a result row to inspect Store, device and previous-audit details.")
        self.placeholder.setWordWrap(True)
        self.placeholder.setObjectName("Muted")
        self.content_layout.addWidget(self.placeholder)

        self.store_label = self._section("Store")
        self.device_label = self._section("Installed / device")
        self.evidence_label = self._section("Country and language evidence")
        self.changes_label = self._section("Changes since previous audit")
        self.notes_label = self._section("Notes")
        self.content_layout.addStretch(1)

        button_row = QHBoxLayout()
        self.review_changes_button = QPushButton("Review audit changes")
        self.review_changes_button.clicked.connect(self.review_changes_requested.emit)
        button_row.addWidget(self.review_changes_button)
        self.open_store_button = QPushButton("Open in Google Play")
        self.open_store_button.setEnabled(False)
        self.open_store_button.clicked.connect(self._open_store)
        button_row.addWidget(self.open_store_button)
        root.addLayout(button_row)
        self.clear()

    def _section(self, title: str) -> QLabel:
        heading = QLabel(title)
        font = QFont(heading.font())
        font.setBold(True)
        heading.setFont(font)
        self.content_layout.addWidget(heading)
        body = QLabel()
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.content_layout.addWidget(body)
        self._section_widgets.extend((heading, body))
        return body

    def _emit_position(self) -> None:
        self.position_changed.emit(str(self.position_combo.currentData() or "right"))

    def position(self) -> str:
        return normalise_details_panel_position(self.position_combo.currentData())

    def set_icon(self, icon: QIcon | None) -> None:
        if icon is None or icon.isNull():
            self.icon_label.clear()
            return
        self.icon_label.setPixmap(icon.pixmap(32, 32))

    def clear(self) -> None:
        self._row = None
        self.icon_label.clear()
        self.title_label.setText("App details")
        self.developer_label.clear()
        self.placeholder.show()
        for widget in self._section_widgets:
            widget.hide()
        for label in (
            self.store_label,
            self.device_label,
            self.evidence_label,
            self.changes_label,
            self.notes_label,
        ):
            label.clear()
        self.open_store_button.setEnabled(False)

    def set_row(self, row: Mapping[str, Any], icon: QIcon | None = None) -> None:
        self._row = dict(row)
        self.placeholder.hide()
        for widget in self._section_widgets:
            widget.show()
        self.title_label.setText(_text(row.get("play_title")) or _text(row.get("package_name")) or "App")
        self.developer_label.setText(_text(row.get("developer")))
        self.set_icon(icon)

        store_fields = [
            ("Package", "package_name"),
            ("Play status", "play_status"),
            ("Store version", "play_version"),
            ("Latest update", "play_last_update"),
            ("Store market", "store_country"),
            ("Store language", "store_language"),
            ("Update source", "updated_source"),
            ("Store URL", "store_url"),
        ]
        self.store_label.setText(_joined_fields(row, store_fields) or "No Store metadata available.")

        device_fields = [
            ("Installed version", "installed_version"),
            ("Installed version code", "installed_version_code"),
            ("Installed vs Store", "version_comparison"),
            ("Installer/source", "installer_source"),
            ("Enabled", "app_enabled"),
            ("System app", "is_system"),
            ("Target SDK", "target_sdk"),
            ("Min SDK", "min_sdk"),
            ("Android compatibility", "compatibility_status"),
        ]
        self.device_label.setText(_joined_fields(row, device_fields) or "No connected-device metadata for this row.")

        evidence = evidence_lines(row)
        self.evidence_label.setText("\n".join(evidence) if evidence else "No structured Store evidence recorded.")

        changes = change_lines(row)
        self.changes_label.setText("\n".join(changes) if changes else "No recorded change for this row.")

        self.notes_label.setText(_text(row.get("notes")) or "No notes.")
        self.open_store_button.setEnabled(bool(_text(row.get("store_url"))))

    def _open_store(self) -> None:
        if self._row is None:
            return
        url = _text(self._row.get("store_url"))
        if url:
            QDesktopServices.openUrl(QUrl(url))
