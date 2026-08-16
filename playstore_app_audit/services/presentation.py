from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import playstore_app_audit.services.state as state
from playstore_app_audit import __version__

APP_VERSION = __version__

DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD.MM.YYYY": "%d.%m.%Y",
    "DD Mon YYYY": "%d %b %Y",
    "Month D, YYYY": "%B %d, %Y",
}
DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DATE_FIELDS = {"play_last_update", "first_install_time", "last_local_update"}
VIEW_PRESETS = ("Basic", "Device", "Technical", "Custom")
DEFAULT_CUSTOM_VIEW_COLUMNS = [
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
]

CSV_EXPORT_GUIDE = """Export a package list for Play Store App Audit

PC / ADB method
1. Connect the Android phone with USB debugging enabled and authorised.
2. Open PowerShell in the folder containing adb.exe.
3. For third-party apps only, run:

  "package_name" | Set-Content packages.csv
  .\\adb.exe shell pm list packages -3 | ForEach-Object { $_ -replace "^package:", "" } | Sort-Object -Unique | Add-Content packages.csv

Remove '-3' if you also want system packages. The resulting CSV can be loaded with Choose file or drag-and-drop.

Phone-only methods
Android itself does not provide a standard built-in button that exports all package IDs to CSV. You have two practical options:

A. Use an app/package-manager on the phone that can export or share the installed-app list including Android package IDs. Save one package ID per line, or use a CSV column named 'package_name'. Play Store App Audit accepts either format.

B. Advanced: use a local shell/package-manager with shell-level access, for example a Shizuku/local-ADB capable environment. From a shell that has permission to run 'pm', you can create a file in Downloads with:

  sh -c 'echo package_name > /sdcard/Download/packages.csv; pm list packages -3 | sed "s/^package://" >> /sdcard/Download/packages.csv'

Then open Files / Downloads on the phone and share packages.csv to your PC/cloud storage. Remove '-3' to include system packages.

Important: a normal terminal app may not have Android shell-level package access, so the advanced phone-only command can require Shizuku/local ADB or equivalent privileges. No root is required when using an authorised shell-level method.

Easiest option inside this app
Use 'Scan phone with ADB', then File → Export current phone package list as CSV… .
"""


def install_defaults() -> None:
    defaults = state.DEFAULT_SETTINGS
    defaults.setdefault("date_format", DEFAULT_DATE_FORMAT)
    defaults.setdefault("custom_view_columns", list(DEFAULT_CUSTOM_VIEW_COLUMNS))


def _parse_date(value: object):
    text = str(value or "").strip()
    if not text:
        return None

    iso = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso).date()
    except ValueError:
        pass

    # Common Google Play / ADB text forms.
    for pattern in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d.%m.%Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%d %b %Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass

    # Accept a leading ISO date even if the rest contains an ADB timestamp/timezone.
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError:
            pass
    return None


def format_date_value(value: object, style: str | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = _parse_date(text)
    if parsed is None:
        return text
    style = style if style in DATE_FORMATS else DEFAULT_DATE_FORMAT
    result = parsed.strftime(DATE_FORMATS[style])
    if style == "Month D, YYYY":
        # strftime zero-pads %d on Windows; remove only that day padding.
        result = re.sub(r"\b0([1-9]),", r"\1,", result)
    return result


def configured_date_format() -> str:
    style = str(state.load_settings().get("date_format") or DEFAULT_DATE_FORMAT)
    return style if style in DATE_FORMATS else DEFAULT_DATE_FORMAT


def display_value(column: str, value: object, style: str | None = None) -> str:
    if column in DATE_FIELDS:
        return format_date_value(value, style or configured_date_format())
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "" if value is None else str(value)


def rows_for_output(rows: list[dict[str, Any]], style: str | None = None) -> list[dict[str, Any]]:
    style = style or configured_date_format()
    result: list[dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        for field in DATE_FIELDS:
            if field in copy:
                copy[field] = format_date_value(copy.get(field), style)
        result.append(copy)
    return result


def concise_summary(rows: list[dict[str, Any]], visible_count: int | None = None) -> str:
    total = len(rows)
    if not total:
        return "No results yet"
    visible = total if visible_count is None else max(0, int(visible_count))
    parts = [f"{visible}/{total} shown"]
    differences = sum(1 for row in rows if str(row.get("version_comparison") or "") == "Different")
    if differences:
        parts.append(f"Version differences {differences}")
    return "  •  ".join(parts)


install_defaults()
