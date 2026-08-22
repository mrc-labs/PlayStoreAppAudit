from __future__ import annotations

from dataclasses import dataclass
from typing import Any

COMPATIBILITY_VALUES = ("", "Modern", "Aging target", "Legacy target", "Unknown")


@dataclass(frozen=True, slots=True)
class SdkMaintenanceFilter:
    """Session-only filters for observed Android SDK metadata.

    These fields describe compatibility and maintenance context only. They must
    not be interpreted as a security, malware or trust score.
    """

    target_sdk_max: int | None = None
    min_sdk_max: int | None = None
    compatibility: str = ""

    def active(self) -> bool:
        return (
            self.target_sdk_max is not None
            or self.min_sdk_max is not None
            or self.compatibility in COMPATIBILITY_VALUES[1:]
        )


def _sdk_number(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        return None
    return number if number >= 1 else None


def normalise_sdk_filter(value: SdkMaintenanceFilter | None) -> SdkMaintenanceFilter:
    if value is None:
        return SdkMaintenanceFilter()
    target = value.target_sdk_max
    minimum = value.min_sdk_max
    compatibility = str(value.compatibility or "").strip()
    if target is not None:
        target = max(1, int(target))
    if minimum is not None:
        minimum = max(1, int(minimum))
    if compatibility not in COMPATIBILITY_VALUES:
        compatibility = ""
    return SdkMaintenanceFilter(target, minimum, compatibility)


def row_matches_sdk_filter(
    row: dict[str, Any],
    value: SdkMaintenanceFilter | None,
) -> bool:
    current = normalise_sdk_filter(value)
    if not current.active():
        return True

    if current.target_sdk_max is not None:
        target = _sdk_number(row.get("target_sdk"))
        if target is None or target > current.target_sdk_max:
            return False

    if current.min_sdk_max is not None:
        minimum = _sdk_number(row.get("min_sdk"))
        if minimum is None or minimum > current.min_sdk_max:
            return False

    if current.compatibility:
        compatibility = str(row.get("compatibility_status") or "Unknown").strip() or "Unknown"
        if compatibility != current.compatibility:
            return False

    return True


def describe_sdk_filter(value: SdkMaintenanceFilter | None) -> str:
    current = normalise_sdk_filter(value)
    if not current.active():
        return "SDK filter: All"
    parts: list[str] = []
    if current.target_sdk_max is not None:
        parts.append(f"targetSdk ≤ {current.target_sdk_max}")
    if current.min_sdk_max is not None:
        parts.append(f"minSdk ≤ {current.min_sdk_max}")
    if current.compatibility:
        parts.append(current.compatibility)
    return "SDK filter: " + " · ".join(parts)
