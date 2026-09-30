"""Shared Store status classification for desktop and headless results."""

from __future__ import annotations

from datetime import date
from typing import Any

from playstore_app_audit.services.presentation import parse_date_value
from playstore_app_audit.services.store_freshness import from_settings

_LABELS = {
    "red": ("Not Found", 0),
    "orange": ("Stale", 1),
    "yellow": ("Aging", 2),
    "blue": ("Anomaly", 3),
    "green": ("Recent", 4),
}


def classify_store_row(row: dict[str, Any], settings: dict[str, Any]) -> None:
    """Apply the GUI's multi-country status and freshness classification."""
    status = str(row.get("play_status") or "").strip()
    age_days: int | None = None
    if status in {"not_found_or_unavailable", "not_found_in_checked_countries"}:
        key = "red"
    elif status != "available":
        key = "blue"
    else:
        updated_date = parse_date_value(row.get("play_last_update"))
        if updated_date is None:
            key = "blue"
        else:
            age_days = (date.today() - updated_date).days
            key = "blue" if age_days < 0 else from_settings(settings).classify_age(age_days)
    label, rank = _LABELS[key]
    row["criticality_key"] = key
    row["criticality"] = label
    row["criticality_rank"] = rank
    row["age_days"] = "" if age_days is None else age_days
