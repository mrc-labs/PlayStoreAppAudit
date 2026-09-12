from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import playstore_app_audit.services.state as state

DEVICE_HISTORY_FLAG = "_device_inventory_had_previous"

GROUP_DEFINITIONS: tuple[tuple[str, str], ...] = (
    ("newly_installed", "Newly installed on device"),
    ("removed_from_device", "Removed from device"),
    ("newly_available", "Newly available"),
    ("newly_unavailable_in_checked_countries", "Newly unavailable in checked countries"),
    ("reappeared", "Reappeared"),
    ("store_version_changed", "Play Store version changed"),
    ("store_latest_update_changed", "Play Store latest-update changed"),
    ("maintenance_state_changed", "Recent Update / Aging / Stale changed"),
    ("installer_source_changed", "Installer / source changed"),
)

_EVENT_GROUPS = {
    "newly_available": "newly_available",
    "newly_unavailable_in_checked_countries": "newly_unavailable_in_checked_countries",
    "reappeared": "reappeared",
    "store_version_changed": "store_version_changed",
    "store_latest_update_changed": "store_latest_update_changed",
    "maintenance_state_changed": "maintenance_state_changed",
    "installer_source_changed": "installer_source_changed",
}


def _text(value: object) -> str:
    return str(value or "").strip()


def _event_detail(event: Mapping[str, Any]) -> str:
    previous = _text(event.get("previous"))
    current = _text(event.get("current"))
    if previous and current:
        return f"{previous} → {current}"
    return current or previous


def row_has_meaningful_change(row: Mapping[str, Any]) -> bool:
    raw = row.get(state.AUDIT_CHANGES_FIELD)
    if isinstance(raw, list) and any(
        isinstance(event, dict) and _text(event.get("type")) in _EVENT_GROUPS for event in raw
    ):
        return True
    if not bool(row.get(DEVICE_HISTORY_FLAG)):
        return False
    return _text(row.get("device_change")) in {"New on device", "Installer changed"}


def _row_item(row: Mapping[str, Any], detail: str = "") -> dict[str, str]:
    package = _text(row.get("package_name"))
    title = _text(row.get("play_title")) or package
    return {
        "package_name": package,
        "title": title,
        "detail": detail,
    }


def has_store_change_evidence(rows: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(raw := row.get(state.AUDIT_CHANGES_FIELD), list)
        and any(
            isinstance(event, dict) and _text(event.get("type")) in _EVENT_GROUPS
            for event in raw
        )
        for row in rows
    )


def build_change_groups(
    rows: list[dict[str, Any]], inventory_changes: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Build an ordered, deduplicated overview of meaningful previous-audit changes."""
    grouped: dict[str, dict[str, dict[str, str]]] = {
        key: {} for key, _label in GROUP_DEFINITIONS
    }

    for row in rows:
        package = _text(row.get("package_name"))
        if not package:
            continue
        if bool(row.get(DEVICE_HISTORY_FLAG)) and _text(row.get("device_change")) == "New on device":
            grouped["newly_installed"][package] = _row_item(row)

        raw = row.get(state.AUDIT_CHANGES_FIELD)
        if isinstance(raw, list):
            for event in raw:
                if not isinstance(event, dict):
                    continue
                group = _EVENT_GROUPS.get(_text(event.get("type")))
                if not group:
                    continue
                grouped[group][package] = _row_item(row, _event_detail(event))

        if (
            bool(row.get(DEVICE_HISTORY_FLAG))
            and _text(row.get("device_change")) == "Installer changed"
            and package not in grouped["installer_source_changed"]
        ):
            grouped["installer_source_changed"][package] = _row_item(
                row, "Installer changed on connected device"
            )

    inventory = inventory_changes if isinstance(inventory_changes, Mapping) else {}
    if bool(inventory.get("had_previous")):
        removed_apps = inventory.get("removed_apps")
        if isinstance(removed_apps, list):
            for item in removed_apps:
                if not isinstance(item, dict):
                    continue
                package = _text(item.get("package_name"))
                if not package:
                    continue
                title = _text(item.get("play_title")) or package
                grouped["removed_from_device"][package] = {
                    "package_name": package,
                    "title": title,
                    "detail": "No longer present on the connected device",
                }
        else:
            removed = inventory.get("removed")
            if isinstance(removed, list):
                for value in removed:
                    package = _text(value)
                    if package:
                        grouped["removed_from_device"][package] = {
                            "package_name": package,
                            "title": package,
                            "detail": "No longer present on the connected device",
                        }

    result: list[dict[str, Any]] = []
    for key, label in GROUP_DEFINITIONS:
        items = sorted(
            grouped[key].values(),
            key=lambda item: (item["title"].casefold(), item["package_name"].casefold()),
        )
        if items:
            result.append({"key": key, "label": label, "items": items, "count": len(items)})
    return result


def build_store_change_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the canonical overview while excluding device-inventory-only groups."""

    store_rows = [{**row, DEVICE_HISTORY_FLAG: False} for row in rows]
    return build_change_groups(store_rows)


def total_change_count(groups: list[dict[str, Any]]) -> int:
    return sum(int(group.get("count") or 0) for group in groups)
