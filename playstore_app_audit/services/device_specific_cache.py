"""Dedicated persistence for successful Device Specific resolver evidence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playstore_app_audit.domain.device_specific_resolver import (
    RESOLVER_CACHE_SCHEMA,
    ResolverCacheIdentity,
    ResolverResult,
)
from playstore_app_audit.platform.runtime import app_data_dir

DEFAULT_RESOLVER_CACHE_TTL_HOURS = 24


def resolver_cache_path() -> Path:
    return app_data_dir() / "device_specific_resolver_cache.json"


def _empty_cache() -> dict[str, Any]:
    return {"schema": RESOLVER_CACHE_SCHEMA, "entries": {}}


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _empty_cache()
    if not isinstance(payload, dict) or payload.get("schema") != RESOLVER_CACHE_SCHEMA:
        return _empty_cache()
    entries = payload.get("entries")
    if not isinstance(entries, dict):
        return _empty_cache()
    return {"schema": RESOLVER_CACHE_SCHEMA, "entries": dict(entries)}


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(path)


def _result_matches_identity(
    result: ResolverResult,
    identity: ResolverCacheIdentity,
) -> bool:
    components = identity.components()
    return (
        result.package_name == components[1]
        and result.profile_id == components[2]
        and result.profile_hash == components[3]
        and result.requested_country == components[4]
        and result.requested_language == components[5]
        and result.provider.value == components[6]
    )


def _safe_persisted_result(result: ResolverResult) -> dict[str, Any]:
    """Serialize only non-secret resolved evidence.

    Diagnostics are intentionally omitted from persistent cache. They are useful
    for live failure reporting, but are not required to reuse successful version
    evidence and must never become an accidental sink for provider/session data.
    """

    return {
        "package_name": result.package_name,
        "profile_id": result.profile_id,
        "profile_hash": result.profile_hash,
        "provider": result.provider.value,
        "status": result.status.value,
        "requested_country": result.requested_country,
        "requested_language": result.requested_language,
        "version_name": result.version_name,
        "version_code": result.version_code,
        "fetched_at": result.fetched_at,
        "diagnostics": "",
    }


def load_cached_result(
    identity: ResolverCacheIdentity,
    *,
    ttl_hours: int = DEFAULT_RESOLVER_CACHE_TTL_HOURS,
    path: Path | None = None,
    now: datetime | None = None,
) -> ResolverResult | None:
    if ttl_hours <= 0:
        return None
    cache = _read_cache(path or resolver_cache_path())
    entry = cache["entries"].get(identity.key)
    if not isinstance(entry, dict):
        return None
    if entry.get("identity") != list(identity.components()):
        return None
    raw_result = entry.get("result")
    if not isinstance(raw_result, dict):
        return None
    try:
        result = ResolverResult.from_mapping(raw_result)
        fetched_at = datetime.fromisoformat(result.fetched_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    age_hours = (current.astimezone(UTC) - fetched_at.astimezone(UTC)).total_seconds() / 3600
    if age_hours < 0 or age_hours > ttl_hours:
        return None
    if not result.resolved or not _result_matches_identity(result, identity):
        return None
    return result


def store_resolved_result(
    identity: ResolverCacheIdentity,
    result: ResolverResult,
    *,
    path: Path | None = None,
) -> bool:
    if not result.resolved or not _result_matches_identity(result, identity):
        return False
    target = path or resolver_cache_path()
    cache = _read_cache(target)
    cache["entries"][identity.key] = {
        "identity": list(identity.components()),
        "result": _safe_persisted_result(result),
    }
    _write_cache(target, cache)
    return True


def clear_resolver_cache(*, path: Path | None = None) -> None:
    _write_cache(path or resolver_cache_path(), _empty_cache())
