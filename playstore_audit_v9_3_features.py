from __future__ import annotations

from typing import Any

import playstore_audit_v9_2_features as v92


APP_VERSION = "0.9.3"


def device_change_count(inventory_changes: object) -> int:
    if not isinstance(inventory_changes, dict) or not inventory_changes.get("had_previous"):
        return 0
    counts = inventory_changes.get("counts", {})
    if not isinstance(counts, dict):
        return 0
    total = 0
    for key in ("new", "removed", "version", "installer", "state"):
        try:
            total += int(counts.get(key, 0) or 0)
        except (TypeError, ValueError):
            pass
    return total


def concise_summary(
    rows: list[dict[str, Any]],
    visible_count: int | None = None,
    inventory_changes: object = None,
) -> str:
    summary = v92.concise_summary(rows, visible_count)
    changes = device_change_count(inventory_changes)
    if rows and changes:
        summary += f"  •  Device changes {changes}"
    return summary
