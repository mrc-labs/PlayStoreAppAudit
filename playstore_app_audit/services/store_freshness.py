"""The two user-controlled boundaries for Store listing freshness."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

DEFAULT_RECENT_MAX_DAYS = 365
DEFAULT_STALE_AFTER_DAYS = 730
MIN_THRESHOLD_DAYS = 0
MAX_THRESHOLD_DAYS = 3650


@dataclass(frozen=True, slots=True)
class StoreFreshnessThresholds:
    recent_max_days: int = DEFAULT_RECENT_MAX_DAYS
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS

    def __post_init__(self) -> None:
        if not (
            MIN_THRESHOLD_DAYS <= self.recent_max_days < self.stale_after_days
            <= MAX_THRESHOLD_DAYS
        ):
            raise ValueError("Recent must be lower than Stale, within the supported range")

    @property
    def aging_range(self) -> str:
        return f"{self.recent_max_days + 1} to {self.stale_after_days} days"

    def classify_age(self, age_days: int) -> str:
        if age_days <= self.recent_max_days:
            return "green"
        if age_days <= self.stale_after_days:
            return "yellow"
        return "orange"


def from_settings(settings: Mapping[str, object]) -> StoreFreshnessThresholds:
    try:
        recent = int(str(settings.get("store_recent_max_days", DEFAULT_RECENT_MAX_DAYS)))
        stale = int(str(settings.get("store_stale_after_days", DEFAULT_STALE_AFTER_DAYS)))
        return StoreFreshnessThresholds(recent, stale)
    except (TypeError, ValueError):
        return StoreFreshnessThresholds()
