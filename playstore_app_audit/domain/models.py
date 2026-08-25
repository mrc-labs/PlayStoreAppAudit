from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StatusKey(StrEnum):
    REMOVED = "red"
    STALE = "orange"
    AGING = "yellow"
    ANOMALY = "blue"
    OTHER = "purple"
    CURRENT = "green"


class AuditRunState(StrEnum):
    """Observable lifecycle states for one reusable audit session."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    FINALIZING = "finalizing"


class AuditRunOutcome(StrEnum):
    """Terminal outcomes kept distinct from transient lifecycle states."""

    SUCCESS = "success"
    STOPPED = "stopped"
    FAILED = "failed"
    ABANDONED = "abandoned"


@dataclass(slots=True)
class AuditRunResult:
    """Completed work and finalization metadata for one audit session.

    ``rows`` contains only cached rows or live package checks that reached a
    valid semantic result. Work that never completed is represented by its
    absence, never by a synthetic error row.
    """

    session: int
    outcome: AuditRunOutcome
    rows: list[dict[str, Any]] = field(default_factory=list)
    cached_count: int = 0
    live_completed_count: int = 0
    total_count: int = 0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def completed_count(self) -> int:
        return min(
            max(0, self.total_count),
            max(0, self.cached_count) + max(0, self.live_completed_count),
        )


@dataclass(slots=True)
class AppRecord:
    package_name: str
    app_name: str = ""
    play_title: str = ""
    play_status: str = ""
    play_last_update: str = ""
    age_days: int | str = ""
    notes: str = ""
    criticality_key: str = ""
    installed_version: str = ""
    play_version: str = ""
    installer_source: str = ""
    target_sdk: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, row: dict[str, Any]) -> AppRecord:
        known = {
            "package_name",
            "app_name",
            "play_title",
            "play_status",
            "play_last_update",
            "age_days",
            "notes",
            "criticality_key",
            "installed_version",
            "play_version",
            "installer_source",
            "target_sdk",
        }
        return cls(
            package_name=str(row.get("package_name") or ""),
            app_name=str(row.get("app_name") or ""),
            play_title=str(row.get("play_title") or ""),
            play_status=str(row.get("play_status") or ""),
            play_last_update=str(row.get("play_last_update") or ""),
            age_days=row.get("age_days", ""),
            notes=str(row.get("notes") or ""),
            criticality_key=str(row.get("criticality_key") or ""),
            installed_version=str(row.get("installed_version") or ""),
            play_version=str(row.get("play_version") or ""),
            installer_source=str(row.get("installer_source") or ""),
            target_sdk=str(row.get("target_sdk") or ""),
            extra={key: value for key, value in row.items() if key not in known},
        )
