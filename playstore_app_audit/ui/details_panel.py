from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Any, Literal

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import playstore_app_audit.services.alternative_distribution as alternative_distribution
import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.presentation as presentation

AUDIT_CHANGES_FIELD = "_audit_changes"
STORE_EVIDENCE_FIELD = "_store_evidence"
display_notes = presentation.friendly_notes

DETAILS_WIDE_ENTER_WIDTH = 760
DETAILS_WIDE_EXIT_WIDTH = 680
DETAILS_EXTRA_WIDE_ENTER_WIDTH = 1180
DETAILS_EXTRA_WIDE_EXIT_WIDTH = 1080
DETAILS_COLUMN_SPACING = 18
AUTO_RIGHT_ENTER_WIDTH = 1380
AUTO_RIGHT_EXIT_WIDTH = 1280

DetailsContentMode = Literal["narrow", "wide", "extra-wide"]

_CHANGE_LABELS = {
    "reappeared": "Reappeared in checked Store markets",
    "newly_available": "Now available after a previous inconclusive/unavailable check",
    "newly_unavailable_in_checked_countries": "No longer found in the checked Store markets",
    "store_version_changed": "Play Store version changed",
    "store_latest_update_changed": "Play Store latest-update date changed",
    "maintenance_state_changed": "Maintenance state changed",
    "installer_source_changed": "Installer/source changed",
}

_DIAGNOSTIC_STATUS_LABELS = {
    "not_found_in_checked_countries": "Terminal not-found across all checked Store markets",
    "multi_country_check_inconclusive": "Transient/inconclusive Store verification",
    "available_in_other_country": "Available in a checked fallback market",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _int_value(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _unique_text(items: list[dict[str, Any]], key: str, upper: bool = False) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = _text(item.get(key))
        if not value:
            continue
        display = value.upper() if upper else value.lower()
        marker = display.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        values.append(display)
    return values


def normalise_details_panel_position(value: object) -> str:
    position = _text(value).casefold()
    if position in {"auto", "right", "below", "hidden"}:
        return position
    return "right"


def resolve_details_panel_position(
    value: object,
    available_width: int,
    current_resolved: object = "",
) -> str:
    position = normalise_details_panel_position(value)
    if position in {"right", "below", "hidden"}:
        return position

    current = _text(current_resolved).casefold()
    if current == "right":
        return "right" if available_width >= AUTO_RIGHT_EXIT_WIDTH else "below"
    if current == "below":
        return "right" if available_width >= AUTO_RIGHT_ENTER_WIDTH else "below"
    return "right" if available_width >= AUTO_RIGHT_ENTER_WIDTH else "below"


def details_content_layout_mode(
    available_width: int, current_mode: object = ""
) -> DetailsContentMode:
    current = _text(current_mode).casefold()
    if current == "extra-wide":
        if available_width >= DETAILS_EXTRA_WIDE_EXIT_WIDTH:
            return "extra-wide"
        current = "wide"
    if current == "wide":
        if available_width >= DETAILS_EXTRA_WIDE_ENTER_WIDTH:
            return "extra-wide"
        return "wide" if available_width >= DETAILS_WIDE_EXIT_WIDTH else "narrow"
    if available_width >= DETAILS_EXTRA_WIDE_ENTER_WIDTH:
        return "extra-wide"
    return "wide" if available_width >= DETAILS_WIDE_ENTER_WIDTH else "narrow"


def _evidence_entries(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = row.get(STORE_EVIDENCE_FIELD)
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _entry_locale(item: Mapping[str, Any]) -> str:
    country = _text(item.get("country")).upper() or "?"
    language = _text(item.get("language")).lower() or "?"
    return f"{country}/{language}"


def _entry_status(item: Mapping[str, Any]) -> str:
    status = _text(item.get("status"))
    labels = {
        "available": "available",
        "not_found_or_unavailable": "not found",
        "request_error": "request failed",
        "http_error": "HTTP error",
        "check_failed": "check failed",
        "unexpected_error": "unexpected error",
    }
    return labels.get(status, status.replace("_", " ") or "unknown")


def evidence_lines(row: Mapping[str, Any]) -> list[str]:
    entries = _evidence_entries(row)
    if not entries:
        return []

    primary = next(
        (item for item in entries if _text(item.get("role")) == "primary"),
        entries[0],
    )
    lines = [f"Primary market: {_entry_locale(primary)} • {_entry_status(primary)}"]

    fallback = [
        item
        for item in entries
        if _text(item.get("role")) in {"regional_fallback", "metadata_completion"}
    ]
    fallback_countries = _unique_text(fallback, "country", upper=True)
    status = _text(row.get("play_status"))

    if status == "available_in_other_country":
        found = next(
            (item for item in fallback if _text(item.get("status")) == "available"),
            None,
        )
        if found is not None:
            lines.append(f"Found in fallback market: {_entry_locale(found)}")
        checked = _unique_text(entries, "country", upper=True)
        if checked:
            lines.append("Markets checked: " + ", ".join(checked))
        lines.append("Outcome: availability is region-specific.")
        return lines

    if status == "not_found_in_checked_countries":
        if fallback_countries:
            lines.append("Fallback markets checked: " + ", ".join(fallback_countries))
        lines.append("Outcome: no listing was found in any checked market.")
        return lines

    if status == "multi_country_check_inconclusive":
        if fallback_countries:
            lines.append("Fallback markets checked: " + ", ".join(fallback_countries))
        lines.append("Outcome: Store verification was inconclusive.")
        return lines

    metadata_found = next(
        (
            item
            for item in fallback
            if _text(item.get("role")) == "metadata_completion"
            and _text(item.get("status")) == "available"
        ),
        None,
    )
    if metadata_found is not None:
        lines.append(f"Metadata completed from: {_entry_locale(metadata_found)}")
    elif fallback_countries:
        lines.append("Additional markets checked: " + ", ".join(fallback_countries))
    return lines


def store_diagnostic_lines(row: Mapping[str, Any]) -> list[str]:
    """Summarise structured transport evidence without repeating per-market noise."""
    entries = _evidence_entries(row)
    if not entries:
        return []

    status = _text(row.get("play_status"))
    retry_count = sum(_int_value(item.get("retry_count")) for item in entries)
    outcomes = {_text(item.get("outcome")) for item in entries}
    paths = {_text(item.get("request_path")) for item in entries}
    http_values = [
        _text(item.get("http_status"))
        for item in entries
        if _text(item.get("http_status"))
    ]
    interesting = (
        status in _DIAGNOSTIC_STATUS_LABELS
        or len(entries) > 1
        or retry_count > 0
        or any("html" in value.casefold() for value in paths)
        or bool(outcomes & {"terminal_not_found", "transient_inconclusive"})
    )
    if not interesting:
        return []

    lines: list[str] = [f"Requests: {len(entries)} locale checks"]
    if any("html" in value.casefold() for value in paths):
        lines.append("Transport: scraper + HTML confirmation/fallback")
    else:
        lines.append("Transport: scraper")

    unique_http = list(dict.fromkeys(http_values))
    if len(unique_http) == 1 and http_values:
        suffix = f" on all {len(http_values)} checks" if len(http_values) > 1 else ""
        lines.append(f"HTTP: {unique_http[0]}{suffix}")
    elif unique_http:
        lines.append("HTTP statuses: " + ", ".join(unique_http))
    if retry_count:
        lines.append(f"Retries: {retry_count}")

    transient_count = sum(
        1 for item in entries if _text(item.get("outcome")) == "transient_inconclusive"
    )
    if transient_count:
        lines.append(f"Inconclusive requests: {transient_count}")
        failure_reasons = _unique_text(entries, "failure_reason")
        useful = [
            reason
            for reason in failure_reasons
            if "not found(404)" not in reason.casefold()
            and reason.casefold()
            not in {"html: 404", "scraper: app not found(404). | html: 404"}
        ]
        if useful:
            lines.append("Reason: " + " | ".join(useful[:2]))
    return lines


def change_lines(row: Mapping[str, Any]) -> list[str]:
    raw = row.get(AUDIT_CHANGES_FIELD)
    lines: list[str] = []
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            event_type = _text(item.get("type"))
            label = _CHANGE_LABELS.get(
                event_type,
                event_type.replace("_", " ").title(),
            )
            previous = _text(item.get("previous"))
            current = _text(item.get("current"))
            if previous and current:
                lines.append(f"{label}: {previous} → {current}")
            else:
                lines.append(label)
    if not lines and _text(row.get("change")).casefold() == "new":
        lines.append(
            "First audit baseline for this app. Future audits can show Store changes."
        )
    return lines


def device_inventory_line(row: Mapping[str, Any]) -> str:
    device_change = _text(row.get("device_change"))
    if not device_change:
        return ""
    if not bool(row.get(change_service.DEVICE_HISTORY_FLAG)):
        return "Inventory history: First phone-scan baseline"
    labels = {
        "new on device": "Newly installed",
        "version changed": "Installed version changed",
        "installer changed": "Installer/source changed",
        "state changed": "Enabled state changed",
        "same": "No inventory change",
        "unchanged": "No inventory change",
        "none": "No inventory change",
    }
    display = labels.get(device_change.casefold(), device_change)
    return f"Since previous phone scan: {display}"


def _joined_fields(row: Mapping[str, Any], fields: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for label, key in fields:
        value = _text(row.get(key))
        if value:
            lines.append(f"{label}: {value}")
    if (
        row.get("local_apk_version_comparison") == "Outdated"
        or row.get("version_comparison") == "Outdated"
    ):
        lines.append(
            "Update note: Store version ordering does not guarantee that an update is "
            "currently offered to every device or rollout cohort."
        )
    return "\n".join(lines)


def _joined_semantic_fields(
    row: Mapping[str, Any], fields: list[tuple[str, str]]
) -> str:
    lines: list[str] = []
    for label, key in fields:
        value = _text(row.get(key))
        if value:
            lines.append(
                f"{html.escape(label)}: {presentation.semantic_html_value(key, value)}"
            )
    return "<br>".join(lines)


def _bounded_list_text(value: object, *, limit: int = 20) -> str:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return _text(value)
    items = [str(item).strip() for item in value if str(item).strip()]
    visible = items[:limit]
    suffix = f" (+{len(items) - limit} more)" if len(items) > limit else ""
    return ", ".join(visible) + suffix


def local_apk_details_lines(row: Mapping[str, Any]) -> list[str]:
    if not local_apk_audit.is_local_apk_source(_text(row.get("source_mode"))):
        return []
    fields = (
        ("Filename", "local_apk_file_name"),
        ("Location", "local_apk_location"),
        ("SHA-256", "local_apk_sha256"),
        ("Local label", "local_apk_label"),
        ("Local version", "local_apk_version_name"),
        ("Version code", "local_apk_version_code"),
        ("Long version code", "local_apk_long_version_code"),
        ("Local APK vs Store", "local_apk_version_comparison"),
        ("File size (bytes)", "local_apk_file_size"),
        ("Modified (UTC)", "local_apk_modified_at"),
        ("Min SDK", "local_apk_min_sdk"),
        ("Target SDK", "local_apk_target_sdk"),
        ("Compile SDK", "local_apk_compile_sdk"),
    )
    lines: list[str] = []
    for label, key in fields:
        value = row.get(key)
        if value is not None and str(value) != "":
            lines.append(f"{label}: {value}")
    if (
        row.get("local_apk_version_comparison") == "N/A"
        and row.get("play_status") == "not_found_in_checked_countries"
    ):
        lines.append(
            "Store evidence: No listing was found in the successfully checked Store "
            "countries, so a version comparison is not applicable. This does not "
            "prove global absence."
        )
    debuggable = row.get("local_apk_debuggable")
    if isinstance(debuggable, bool):
        lines.append(f"Debuggable: {'Yes' if debuggable else 'No'}")
    for label, key in (
        ("Permissions", "local_apk_permissions"),
        ("Features", "local_apk_features"),
        ("Parser warnings", "local_apk_warnings"),
    ):
        value = _bounded_list_text(row.get(key))
        if value:
            lines.append(f"{label}: {value}")
    return lines


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        child = item.layout()
        if child is not None:
            _clear_layout(child)
            child.deleteLater()


def _position_icon(kind: str, widget: QWidget) -> QIcon:
    pixmap = QPixmap(36, 28)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    color = widget.palette().color(QPalette.ColorRole.ButtonText)
    pen = QPen(color)
    pen.setWidth(2)
    painter.setPen(pen)

    def draw_preview(x: int, y: int, width: int, height: int, placement: str) -> None:
        painter.drawRoundedRect(x, y, width, height, 2, 2)
        if placement == "right":
            panel_width = max(5, width // 3)
            split_x = x + width - panel_width
            painter.drawLine(split_x, y, split_x, y + height)
            painter.fillRect(split_x + 2, y + 2, panel_width - 3, height - 3, color)
        else:
            panel_height = max(5, height // 3)
            split_y = y + height - panel_height
            painter.drawLine(x, split_y, x + width, split_y)
            painter.fillRect(x + 2, split_y + 2, width - 3, panel_height - 3, color)

    if kind == "auto":
        draw_preview(2, 5, 14, 18, "right")
        draw_preview(20, 5, 14, 18, "below")
    elif kind == "hidden":
        draw_preview(4, 3, 28, 22, "right")
        painter.drawLine(20, 2, 34, 25)
    else:
        draw_preview(4, 3, 28, 22, kind)
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


class DetailsPanelControl(QToolButton):
    position_changed = Signal(str)

    _LABELS = {
        "auto": "Auto",
        "right": "Right",
        "below": "Below",
        "hidden": "Hidden",
    }
    _DESCRIPTIONS = {
        "auto": "Place the Details Panel automatically based on the available width.",
        "right": "Place the Details Panel to the right of the results table.",
        "below": "Place the Details Panel below the results table.",
        "hidden": "Hide the Details Panel and return the full area to the results table.",
    }

    def __init__(self, position: str = "right", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailsControl")
        self.setText("Details")
        self.setAccessibleName("Details Panel")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setIconSize(QSize(28, 22))
        self.setMinimumHeight(32)

        self.mode_menu = QMenu("Details Panel", self)
        self.mode_menu.setAccessibleName("Details Panel")
        self.position_group = QActionGroup(self)
        self.position_group.setExclusive(True)
        self.position_actions: dict[str, QAction] = {}
        self._position = ""

        for kind, label in self._LABELS.items():
            action = QAction(_position_icon(kind, self), label, self, checkable=True)
            action.setToolTip(self._DESCRIPTIONS[kind])
            action.setStatusTip(self._DESCRIPTIONS[kind])
            action.triggered.connect(
                lambda _checked=False, selected=kind: self.set_position(selected)
            )
            self.position_group.addAction(action)
            self.mode_menu.addAction(action)
            self.position_actions[kind] = action
        self.setMenu(self.mode_menu)
        self.set_position(position, emit=False)

    def position(self) -> str:
        return self._position

    def set_position(self, position: str, *, emit: bool = True) -> None:
        selected = normalise_details_panel_position(position)
        changed = selected != self._position
        self._position = selected
        self.position_actions[selected].setChecked(True)
        self.setIcon(_position_icon(selected, self))
        description = self._DESCRIPTIONS[selected]
        self.setToolTip(description)
        self.setAccessibleDescription(description)
        if emit and changed:
            self.position_changed.emit(selected)


class AppDetailsPanel(QFrame):
    review_changes_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AppDetailsPanel")
        self.setAccessibleName("App Details")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumWidth(300)
        self.setMinimumHeight(210)
        self._row: dict[str, Any] | None = None
        self._content_mode: DetailsContentMode | Literal[""] = ""
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
        self.title_label = QLabel("App Details")
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

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 4, 0)
        self.content_layout.setSpacing(10)
        self.scroll.setWidget(self.content)
        root.addWidget(self.scroll, 1)

        self.placeholder = QLabel(
            "Select a result row to inspect Store, local artifact, device and previous-audit details."
        )
        self.placeholder.setWordWrap(True)
        self.placeholder.setObjectName("Muted")
        self.content_layout.addWidget(self.placeholder)

        self.sections_host = QWidget()
        self.sections_layout = QVBoxLayout(self.sections_host)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(10)
        self.content_layout.addWidget(self.sections_host)

        self.store_section, self.store_label = self._section("Store")
        self.local_apk_section, self.local_apk_label = self._section("Local APK artifact")
        self.device_section, self.device_label = self._section("Installed / device")
        self.evidence_section, self.evidence_label = self._section("Store market evidence")
        self.alternative_section, self.alternative_label = self._section("Alternative distribution")
        self.alternative_buttons = QWidget(self.alternative_section)
        self.alternative_buttons_layout = QVBoxLayout(self.alternative_buttons)
        self.alternative_buttons_layout.setContentsMargins(0, 3, 0, 0)
        self.alternative_buttons_layout.setSpacing(4)
        self.alternative_section.layout().addWidget(self.alternative_buttons)
        self.diagnostics_section, self.diagnostics_label = self._section("Store diagnostics")
        self.changes_section, self.changes_label = self._section("Changes since previous audit")
        self.notes_section, self.notes_label = self._section("Notes")
        self.content_layout.addStretch(1)

        self.actions_host = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_host)
        self.actions_layout.setContentsMargins(0, 0, 0, 0)
        self.actions_layout.setSpacing(7)
        self.review_changes_button = QPushButton("Review Audit Changes")
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

    def content_layout_mode(self) -> DetailsContentMode:
        return self._content_mode or "narrow"

    def _sync_extra_wide_section_heights(self, available_width: int) -> None:
        had_minimum_heights = any(
            section.minimumHeight() > 0 for section in self._section_widgets
        )
        for section in self._section_widgets:
            section.setMinimumHeight(0)
        if self._content_mode != "extra-wide" and not had_minimum_heights:
            return
        if self._content_mode == "extra-wide":
            content_margins = self.content_layout.contentsMargins()
            column_width = max(
                1,
                (
                    available_width
                    - content_margins.left()
                    - content_margins.right()
                    - (2 * DETAILS_COLUMN_SPACING)
                )
                // 3,
            )
            for section in self._section_widgets:
                section.setMinimumHeight(max(0, section.heightForWidth(column_width)))
        self.sections_layout.invalidate()
        self.content_layout.invalidate()
        self.sections_host.updateGeometry()
        self.content.updateGeometry()
        self.sections_layout.activate()
        self.content_layout.activate()

    def _update_adaptive_layout(self, available_width: int) -> None:
        mode = details_content_layout_mode(available_width, self._content_mode)
        if mode == self._content_mode:
            self._sync_extra_wide_section_heights(available_width)
            return
        self._content_mode = mode
        _clear_layout(self.sections_layout)
        _clear_layout(self.actions_layout)
        size_constraint = (
            QLayout.SizeConstraint.SetMinimumSize
            if mode == "extra-wide"
            else QLayout.SizeConstraint.SetDefaultConstraint
        )
        self.content_layout.setSizeConstraint(size_constraint)
        self.sections_layout.setSizeConstraint(size_constraint)

        if mode == "extra-wide":
            columns = QHBoxLayout()
            columns.setContentsMargins(0, 0, 0, 0)
            columns.setSpacing(DETAILS_COLUMN_SPACING)
            store_column = QVBoxLayout()
            store_column.setContentsMargins(0, 0, 0, 0)
            store_column.setSpacing(12)
            store_column.addWidget(self.store_section)
            store_column.addWidget(self.local_apk_section)
            store_column.addWidget(self.notes_section)
            store_column.addStretch(1)
            device_column = QVBoxLayout()
            device_column.setContentsMargins(0, 0, 0, 0)
            device_column.setSpacing(12)
            device_column.addWidget(self.device_section)
            device_column.addWidget(self.changes_section)
            device_column.addStretch(1)
            evidence_column = QVBoxLayout()
            evidence_column.setContentsMargins(0, 0, 0, 0)
            evidence_column.setSpacing(12)
            evidence_column.addWidget(self.evidence_section)
            evidence_column.addWidget(self.alternative_section)
            evidence_column.addWidget(self.diagnostics_section)
            evidence_column.addStretch(1)
            columns.addLayout(store_column, 1)
            columns.addLayout(device_column, 1)
            columns.addLayout(evidence_column, 1)
            self.sections_layout.addLayout(columns)

            actions = QHBoxLayout()
            actions.setContentsMargins(0, 0, 0, 0)
            actions.setSpacing(7)
            actions.addWidget(self.review_changes_button, 1)
            actions.addWidget(self.open_store_button, 1)
            self.actions_layout.addLayout(actions)
        elif mode == "wide":
            columns = QHBoxLayout()
            columns.setContentsMargins(0, 0, 0, 0)
            columns.setSpacing(DETAILS_COLUMN_SPACING)
            left = QVBoxLayout()
            left.setContentsMargins(0, 0, 0, 0)
            left.setSpacing(12)
            left.addWidget(self.store_section)
            left.addWidget(self.evidence_section)
            left.addWidget(self.alternative_section)
            left.addWidget(self.diagnostics_section)
            left.addStretch(1)
            right = QVBoxLayout()
            right.setContentsMargins(0, 0, 0, 0)
            right.setSpacing(12)
            right.addWidget(self.local_apk_section)
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
                self.local_apk_section,
                self.device_section,
                self.evidence_section,
                self.alternative_section,
                self.diagnostics_section,
                self.changes_section,
                self.notes_section,
            ):
                self.sections_layout.addWidget(section)
            self.actions_layout.addWidget(self.review_changes_button)
            self.actions_layout.addWidget(self.open_store_button)
        self._sync_extra_wide_section_heights(available_width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        viewport_width = (
            self.scroll.viewport().width() if hasattr(self, "scroll") else event.size().width()
        )
        self._update_adaptive_layout(viewport_width)

    def set_icon(self, icon: QIcon | None) -> None:
        if icon is None or icon.isNull():
            self.icon_label.clear()
            return
        self.icon_label.setPixmap(icon.pixmap(32, 32))

    def clear(self) -> None:
        self._row = None
        self.icon_label.clear()
        self.title_label.setText("App Details")
        self.developer_label.clear()
        self.placeholder.show()
        for widget in self._section_widgets:
            widget.hide()
        for label in (
            self.store_label,
            self.local_apk_label,
            self.device_label,
            self.evidence_label,
            self.alternative_label,
            self.diagnostics_label,
            self.changes_label,
            self.notes_label,
        ):
            label.clear()
        self.open_store_button.setEnabled(False)
        self._set_alternative_listing_actions([])
        self._sync_extra_wide_section_heights(self.scroll.viewport().width())

    def set_row(self, row: Mapping[str, Any], icon: QIcon | None = None) -> None:
        self._row = dict(row)
        self.placeholder.hide()
        for widget in self._section_widgets:
            widget.show()
        self.title_label.setText(
            _text(row.get("local_apk_label"))
            or _text(row.get("play_title"))
            or _text(row.get("package_name"))
            or "App"
        )
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

        local_apk_lines = local_apk_details_lines(row)
        self.local_apk_label.setText("\n".join(local_apk_lines))
        self.local_apk_section.setVisible(bool(local_apk_lines))

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
        device_text = _joined_semantic_fields(row, device_fields)
        health_score = _text(row.get("health_score"))
        if health_score:
            health_line = f"Maintenance Score: {html.escape(health_score)}/100"
            breakdown = "<br>".join(
                html.escape(line)
                for line in device_insights.health_score_breakdown_lines(dict(row))
            )
            health_text = f"{health_line}<br>Score breakdown:<br>{breakdown}"
            device_text = f"{device_text}<br>{health_text}" if device_text else health_text
        inventory_line = device_inventory_line(row)
        if inventory_line:
            escaped_inventory = html.escape(inventory_line)
            device_text = (
                f"{device_text}<br>{escaped_inventory}"
                if device_text
                else escaped_inventory
            )
        self.device_label.setText(device_text or "No connected-device metadata for this row.")
        local_apk_row = local_apk_audit.is_local_apk_source(
            _text(row.get("source_mode"))
        )
        self.device_section.setVisible(not local_apk_row)

        evidence = evidence_lines(row)
        self.evidence_label.setText("\n".join(evidence) if evidence else "No structured Store evidence recorded.")

        alternative_results = alternative_distribution.provider_results(row)
        self.alternative_label.setText(
            alternative_distribution.provider_evidence_text(row)
        )
        self.alternative_section.setVisible(bool(alternative_results))
        self._set_alternative_listing_actions(
            [result.listing_url for result in alternative_results if result.listing_url]
        )

        diagnostics = store_diagnostic_lines(row)
        self.diagnostics_label.setText("\n".join(diagnostics))
        self.diagnostics_section.setVisible(bool(diagnostics))

        changes = change_lines(row)
        if changes:
            change_text = "\n".join(changes)
        elif _text(row.get("change")).casefold() == "same":
            change_text = "No Store changes since the previous audit."
        elif _text(row.get("change")):
            change_text = "No additional structured Store change recorded for this row."
        else:
            change_text = "Previous-audit comparison was not enabled for this run."
        self.changes_label.setText(change_text)
        self.changes_section.setVisible(not local_apk_row)

        self.notes_label.setText(presentation.friendly_notes(row))
        self.open_store_button.setEnabled(bool(_text(row.get("store_url"))))
        self._sync_extra_wide_section_heights(self.scroll.viewport().width())

    def _set_alternative_listing_actions(self, urls: list[str]) -> None:
        while self.alternative_buttons_layout.count():
            item = self.alternative_buttons_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for url in urls:
            button = QPushButton("Open provider listing")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(
                lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target))
            )
            self.alternative_buttons_layout.addWidget(button)
        self.alternative_buttons.setVisible(bool(urls))

    def _open_store(self) -> None:
        if self._row is None:
            return
        url = _text(self._row.get("store_url"))
        if url:
            QDesktopServices.openUrl(QUrl(url))
