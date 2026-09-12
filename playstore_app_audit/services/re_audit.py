from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from playstore_app_audit.services import state

POLICY_ID = "conservative-smart-reaudit-v1"
CACHE_REUSABLE_STATUS = "available"


@dataclass(frozen=True, slots=True)
class ReAuditPolicy:
    policy_id: str = POLICY_ID
    mode: str = "smart"
    cache_only_healthy_available: bool = True
    require_update_date_for_cache: bool = True
    uncertain_results_always_live: bool = True
    explicit_full_refresh_available: bool = True
    targeted_problem_recheck_available: bool = True


def cache_reuse_eligible(row: dict[str, Any]) -> bool:
    """Return whether a Store row is eligible for conservative cache reuse.

    Exact `available` status plus a validly populated update-date field are
    required. Regional/fallback availability, terminal not-found, partial
    metadata, anomalies and inconclusive/error states deliberately remain live.
    Freshness/TTL is evaluated separately by the persistent cache layer.
    """
    return (
        str(row.get("play_status") or "").strip() == CACHE_REUSABLE_STATUS
        and bool(str(row.get("play_last_update") or "").strip())
    )


def policy_context(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    values = dict(settings or {})
    policy = asdict(ReAuditPolicy())
    policy.update(
        {
            "cache_enabled": bool(values.get("cache_enabled", True)),
            "healthy_cache_ttl_hours": _ttl(
                values.get("cache_ttl_hours", state.DEFAULT_CACHE_TTL_HOURS)
            ),
        }
    )
    return policy


def _ttl(value: object) -> int:
    try:
        ttl = int(str(value))
    except (TypeError, ValueError):
        ttl = state.DEFAULT_CACHE_TTL_HOURS
    return max(0, min(720, ttl))


def smart_audit_tooltip(settings: dict[str, Any] | None = None) -> str:
    context = policy_context(settings)
    if context["cache_enabled"]:
        cache = f"fresh healthy results may be reused for up to {context['healthy_cache_ttl_hours']}h"
    else:
        cache = "cache reuse is disabled"
    return (
        "Smart audit: "
        + cache
        + "; removed, regional-only, anomalous, incomplete and failed checks run live. "
        "Use Run with Fresh Store Results to ignore result caches for every app."
    )
