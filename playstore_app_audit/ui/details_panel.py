from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QIcon, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.change_overview as change_service

AUDIT_CHANGES_FIELD = "_audit_changes"
STORE_EVIDENCE_FIELD = "_store_evidence"

DETAILS_WIDE_ENTER_WIDTH = 760
DETAILS_WIDE_EXIT_WIDTH = 680
AUTO_RIGHT_ENTER_WIDTH = 1380
AUTO_RIGHT_EXIT_WIDTH = 1280

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
    position = _text(value).casefold()
    if position in {"auto", "below"}:
        return position
    return "right"


def resolve_details_panel_position(
    value: object,
    available_width: int,
    current_resolved: object = "",
) -> str:
    position = normalise_details_panel_position(value)
    if position != "auto":
        return position

    current = _text(current_resolved).casefold()
    if current == "right":
        return "right" if available_width >= AUTO_RIGHT_EXIT_WIDTH else "below"
    if current == "below":
        return "right" if available_width >= AUTO_RIGHT_ENTER_WIDTH else "below"
    return "right" if available_width >= AUTO_RIGHT_ENTER_WIDTH else "below"


def details_content_layout_mode(available_width: int, current_mode: object = "") -> str:
    current = _text(current_mode).casefold()
    if current == "wide":
        return "wide" if available_width >= DETAILS_WIDE_EXIT_WIDTH else "narrow"
    return "wide" if available_width >= DETAILS_WIDE_ENTER_WIDTH else "narrow"


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


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        if child is not None:
            _clear_layout(child)
            child.deleteLater()


def _position_icon(kind: str, widget: QWidget) -> QIcon:
    pixmap = QPixmap(28, 22)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = widget.palette().color(QPalette.ColorRole.ButtonText)
    pen = QPen(color)
    pen.setWidth(2)
    painter.setPen(pen)

    if kind == "auto":
        painter.drawLine(5, 11, 23, 11)
        painter.drawLine(5, 11, 9, 7)
        painter.drawLine(5, 11, 9, 15)
        painter.drawLine(23, 11, 19, 7)
        painter.drawLine(23, 11, 19, 15)
    else:
        outer_x, outer_y, outer_w, outer_h = 3, 3, 22, 16
        painter.drawRect(outer_x, outer_y, outer_w, outer_h)
        if kind == "right":
            split_x = 17
            painter.drawLine(split_x, outer_y, split_x, outer_y + outer_h)
            painter.fillRect(split_x + 2, outer_y + 2, 5, outer_h - 3, color)
        else:
            split_y = 13
            painter.drawLine(outer_x, split_y, outer_x + outer_w, split_y)
            painter.fillRect(outer_x + 2, split_y + 2, outer_w - 3, 4, color)
    painter.end()
    return QIcon(pixmap)


class _DetailSection(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        heading = QLabel(title)
        font = QFont(heading.font())
        font.setBold(True)
        heading.setFont(font)
        layout.addWidget(heading)

        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.body)


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
        self._position = normalise_details_panel_position(position)
        self._content_mode = ""
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

        self.position_group = QButtonGroup(self)
        self.position_group.setExclusive(True)
        self.position_buttons: dict[str, QToolButton] = {}
        tooltips = {
            "auto": "Panel position: Auto. Uses Right on wide windows and Below when space is tighter.",
            "right": "Panel position: Right",
            "below": "Panel position: Below",
        }
        for kind in ("auto", "right", "below"):
            button = QToolButton(self)
            button.setAutoRaise(True)
            button.setCheckable(True)
            button.setIcon(_position_icon(kind, button))
            button.setIconSize(QSize(24, 19))
            button.setFixedSize(32, 30)
            button.setToolTip(tooltips[kind])
            button.setAccessibleName(tooltips[kind].split(".", 1)[0])
            button.clicked.connect(lambda _checked=False, selected=kind: self._select_position(selected))
            self.position_group.addButton(button)
            self.position_buttons[kind] = button
            header.addWidget(button)
        self.position_buttons[self._position].setChecked(True)
        root.addLayout(header)

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

        self.sections_host = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_host)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(10)
        self.content_layout.addWidget(self.sections_host)

        self.store_section, self.store_label = self._section("Store")
        self.device_section, self.device_label = self._section("Installed / device")
        self.evidence_section, self.evidence_label = self._section("Country and language evidence")
        self.changes_section, self.changes_label = self._section("Changes since previous audit")
        self.notes_section, self.notes_label = self._section("Notes")
        self.content_layout.addStretch(1)

        self.actions_host = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(7)
        self.review_changes_button = QPushButton("Review audit changes")
        self.review_changes_button.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.review_changes_button.clicked.connect(self.review_changes_requested.emit)
        self.open_store_button = QPushButton("Open in Google Play")
        self.open_store_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_store_button.setEnabled(False)
        self.open_store_button.clicked.connect(self._open_store)
        root.addWidget(self.actions_host)

        self._update_adaptive_layout(self.minimumWidth())
        self.clear()

    def _section(self, title: str) -> tuple[_DetailSection, QLabel]:
        section = _DetailSection(title, self.sections_host)
        self._section_widgets.append(section)
        return section, section.body

    def _select_position(self, position: str) -> None:
        selected = normalise_details_panel_position(position)
        if selected == self._position:
            return
        self._position = selected
        self.position_buttons[selected].setChecked(True)
        self.position_changed.emit(selected)

    def position(self) -> str:
        return self._position

    def content_layout_mode(self) -> str:
        return self._content_mode or "narrow"

    def _update_adaptive_layout(self, available_width: int) -> None:
        mode = details_content_layout_mode(available_width, self._content_mode)
        if mode == self._content_mode:
            return
        self._content_mode = mode
        _clear_layout(self.sections_layout)
        _clear_layout(self.actions_layout)

        if mode == "wide":
            columns = QHBoxLayout()
            columns.setContentsMargins(0, 0, 0, 0)
            columns.setSpacing(18)
            left = QVBoxLayout()
            left.setContentsMargins(0, 0, 0, 0)
            left.setSpacing(12)
            left.addWidget(self.store_section)
            left.addWidget(self.evidence_section)
            left.addStretch(1)
            right = QVBoxLayout()
            right.setContentsMargins(0, 0, 0, 0)
            right.setSpacing(12)
            right.addWidget(self.device_section)
            right.addWidget(self.changes_section)
            right.addStretch(1)
            columns.addLayout(left, 1)
            columns.addLayout(right, 1)
            self.sections_layout.addLayout(columns)
            self.sections_layout.addWidget(self.notes_section)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(7)
            actions.addWidget(self.review_changes_button, 1)
            actions.addWidget(self.open_store_button, 1)
            self.actions_layout.addLayout(actions)
        else:
            for section in (
                self.store_section,
                self.device_section,
                self.evidence_section,
                self.changes_section,
                self.notes_section,
            ):
                self.sections_layout.addWidget(section)
            self.actions_layout.addWidget(self.review_changes_button)
            self.actions_layout.addWidget(self.open_store_button)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        viewport_width = self.scroll.viewport().width() if hasattr(self, "scroll") else event.size().width()
        self._update_adaptive_layout(viewport_width)

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
