"""Audit-pipeline integration for optional Device Specific Play evidence."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ThreadPoolExecutor,
    wait,
)
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverCacheIdentity,
    ResolverResult,
)
from playstore_app_audit.services.device_specific_cache import (
    DEFAULT_RESOLVER_CACHE_TTL_HOURS,
    load_cached_result,
    store_resolved_result,
)
from playstore_app_audit.services.device_specific_profiles import (
    PRODUCTION_PROFILE_IDS,
    list_reference_profiles,
    load_reference_profile,
)
from playstore_app_audit.services.device_specific_protocol import provider_context_hash
from playstore_app_audit.services.device_specific_resolver import (
    build_cache_identity,
    resolve_if_device_specific,
    should_attempt_device_specific_resolver,
)

SETTING_ENABLED = "device_specific_resolver_enabled"
SETTING_ENDPOINT = "device_specific_resolver_endpoint"
SETTING_PROFILE_ID = "device_specific_resolver_profile"
DEFAULT_PROFILE_ID = PRODUCTION_PROFILE_IDS[-1]
DEFAULT_MAX_WORKERS = 4

RESOLVED_VERSION_FIELD = "resolved_play_version"
RESOLVED_VERSION_CODE_FIELD = "resolved_play_version_code"
PROFILE_FIELD = "device_specific_profile"
PROFILE_ID_FIELD = "device_specific_profile_id"
STATUS_FIELD = "device_specific_resolver_status"
ROW_FIELDS = (
    RESOLVED_VERSION_FIELD,
    RESOLVED_VERSION_CODE_FIELD,
    PROFILE_FIELD,
    PROFILE_ID_FIELD,
    STATUS_FIELD,
)

ResolverCallable = Callable[..., ResolverResult | None]


@dataclass(frozen=True, slots=True)
class ResolverIntegrationSummary:
    eligible: int = 0
    attempted: int = 0
    cache_hits: int = 0
    resolved: int = 0
    unresolved: int = 0
    cancelled: bool = False
    configuration_error: str = ""


def profile_choices() -> tuple[tuple[str, str], ...]:
    """Return production profile IDs with user-facing coherent-device labels."""

    return tuple(
        (
            profile.profile_id,
            f"{profile.display_name} — Android {profile.android_release} / API {profile.api_level}",
        )
        for profile in list_reference_profiles()
    )


def validate_resolver_endpoint(value: object) -> str:
    """Validate a non-secret explicit dispenser endpoint and return it trimmed."""

    endpoint = str(value or "").strip()
    if not endpoint:
        raise ValueError("A dispenser endpoint is required when the resolver is enabled.")
    provider_context_hash(endpoint)
    return endpoint


def _positive_version_code(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value or "").strip()
    if not text.isdecimal():
        return None
    number = int(text)
    return number if number > 0 else None


def relationship_from_version_codes(
    installed_version_code: object,
    resolved_play_version_code: object,
) -> str | None:
    """Return the strict installed-vs-deliverable relationship from versionCode."""

    installed = _positive_version_code(installed_version_code)
    available = _positive_version_code(resolved_play_version_code)
    if installed is None or available is None:
        return None
    if installed < available:
        return "Outdated"
    if installed > available:
        return "Newer"
    return "Match"


def _clear_resolver_evidence(row: dict[str, Any]) -> None:
    for field in ROW_FIELDS:
        row[field] = ""


def _apply_result(
    row: dict[str, Any],
    result: ResolverResult,
    *,
    profile_label: str,
) -> bool:
    row[PROFILE_FIELD] = profile_label
    row[PROFILE_ID_FIELD] = result.profile_id
    row[STATUS_FIELD] = result.status.value
    if not result.resolved:
        return False

    row[RESOLVED_VERSION_FIELD] = result.version_name or ""
    row[RESOLVED_VERSION_CODE_FIELD] = result.version_code or ""
    relationship = relationship_from_version_codes(
        row.get("installed_version_code"),
        result.version_code,
    )
    if relationship is not None:
        row["version_comparison"] = relationship
    return True


def _apply_inconclusive(
    row: dict[str, Any],
    *,
    profile_id: str,
    profile_label: str,
) -> None:
    row[PROFILE_FIELD] = profile_label
    row[PROFILE_ID_FIELD] = profile_id
    row[STATUS_FIELD] = "inconclusive"


def _wait_until_running(
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> bool:
    if cancel_event is not None and cancel_event.is_set():
        return False
    if pause_event is None:
        return True
    while not pause_event.wait(0.10):
        if cancel_event is not None and cancel_event.is_set():
            return False
    return cancel_event is None or not cancel_event.is_set()


def enrich_rows_with_device_specific_resolution(
    rows: list[dict[str, Any]],
    *,
    settings: Mapping[str, Any],
    country: str,
    language: str,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    cache_ttl_hours: int = DEFAULT_RESOLVER_CACHE_TTL_HOURS,
    use_cache: bool = True,
    timeout: float = 30.0,
    resolver: ResolverCallable | None = None,
) -> ResolverIntegrationSummary:
    """Add resolved evidence without replacing raw Store facts.

    Cache access is deliberately serialized in this coordinator. Only cache
    misses perform concurrent network work, and the C1 resolver is called with
    its own cache disabled so worker threads never write the same cache file.
    """

    for row in rows:
        _clear_resolver_evidence(row)

    if settings.get(SETTING_ENABLED) is not True:
        return ResolverIntegrationSummary()

    eligible_indices = [
        index
        for index, row in enumerate(rows)
        if should_attempt_device_specific_resolver(row.get("play_version"))
    ]
    if not eligible_indices:
        return ResolverIntegrationSummary()

    endpoint = str(settings.get(SETTING_ENDPOINT) or "").strip()
    profile_id = str(settings.get(SETTING_PROFILE_ID) or DEFAULT_PROFILE_ID).strip()
    try:
        endpoint = validate_resolver_endpoint(endpoint)
        profile = load_reference_profile(profile_id)
    except (KeyError, TypeError, ValueError):
        return ResolverIntegrationSummary(
            eligible=len(eligible_indices),
            configuration_error="invalid_resolver_configuration",
        )

    if not _wait_until_running(pause_event, cancel_event):
        return ResolverIntegrationSummary(
            eligible=len(eligible_indices),
            cancelled=True,
        )

    profile_label = (
        f"{profile.display_name} — Android {profile.android_release} / API {profile.api_level}"
    )
    misses: list[tuple[int, ResolverCacheIdentity]] = []
    cache_hits = 0
    resolved = 0

    for index in eligible_indices:
        try:
            identity = build_cache_identity(
                package_name=str(rows[index].get("package_name") or ""),
                profile_id=profile.profile_id,
                dispenser_url=endpoint,
                country=country,
                language=language,
            )
        except (KeyError, TypeError, ValueError):
            _apply_inconclusive(
                rows[index],
                profile_id=profile.profile_id,
                profile_label=profile_label,
            )
            continue

        cached = None
        if use_cache:
            try:
                cached = load_cached_result(
                    identity,
                    ttl_hours=cache_ttl_hours,
                )
            except Exception:
                # Resolver cache is optional enrichment. A locked, corrupt
                # or otherwise unreadable cache must never fail an audit.
                cached = None
        if cached is not None:
            cache_hits += 1
            resolved += int(
                _apply_result(rows[index], cached, profile_label=profile_label)
            )
        else:
            misses.append((index, identity))

    if not misses:
        return ResolverIntegrationSummary(
            eligible=len(eligible_indices),
            cache_hits=cache_hits,
            resolved=resolved,
            unresolved=len(eligible_indices) - resolved,
        )

    try:
        requested_workers = int(max_workers)
    except (TypeError, ValueError):
        requested_workers = DEFAULT_MAX_WORKERS
    worker_limit = max(1, min(DEFAULT_MAX_WORKERS, requested_workers, len(misses)))
    resolver_fn = resolver or resolve_if_device_specific
    executor = ThreadPoolExecutor(max_workers=worker_limit)
    pending: dict[Future[ResolverResult | None], tuple[int, ResolverCacheIdentity]] = {}
    next_miss = 0
    attempted = 0
    cancelled = False

    def run_one(index: int) -> ResolverResult | None:
        if not _wait_until_running(pause_event, cancel_event):
            return None
        return resolver_fn(
            public_store_version=rows[index].get("play_version"),
            package_name=str(rows[index].get("package_name") or ""),
            profile_id=profile.profile_id,
            dispenser_url=endpoint,
            country=country,
            language=language,
            use_cache=False,
            timeout=timeout,
        )

    def fill_submission_window() -> None:
        nonlocal next_miss
        while (
            next_miss < len(misses)
            and len(pending) < worker_limit
            and (cancel_event is None or not cancel_event.is_set())
        ):
            index, identity = misses[next_miss]
            next_miss += 1
            pending[executor.submit(run_one, index)] = (index, identity)

    try:
        fill_submission_window()
        while pending:
            completed, _not_done = wait(tuple(pending), return_when=FIRST_COMPLETED)
            for future in completed:
                index, identity = pending.pop(future)
                attempted += 1
                try:
                    result = future.result()
                except Exception:
                    result = None

                if result is None:
                    _apply_inconclusive(
                        rows[index],
                        profile_id=profile.profile_id,
                        profile_label=profile_label,
                    )
                    continue

                is_resolved = _apply_result(
                    rows[index],
                    result,
                    profile_label=profile_label,
                )
                if is_resolved:
                    resolved += 1
                    if use_cache:
                        with suppress(Exception):
                            store_resolved_result(identity, result)

            if cancel_event is not None and cancel_event.is_set():
                cancelled = True
                for future in pending:
                    future.cancel()
                break
            fill_submission_window()
    finally:
        executor.shutdown(wait=not cancelled, cancel_futures=True)

    unresolved = max(0, len(eligible_indices) - resolved)
    return ResolverIntegrationSummary(
        eligible=len(eligible_indices),
        attempted=attempted,
        cache_hits=cache_hits,
        resolved=resolved,
        unresolved=unresolved,
        cancelled=cancelled,
    )
