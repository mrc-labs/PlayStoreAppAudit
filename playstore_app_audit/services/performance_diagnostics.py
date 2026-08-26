from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.play_store as play_store
from playstore_app_audit.services.store_locale import resolve_store_language

_STORE_LOCK = threading.Lock()
_INSTALLED = False
_STORE_STATS: dict[str, dict[str, Any]] = {}


def _empty_role_stats() -> dict[str, Any]:
    return {"calls": 0, "sum_s": 0.0, "max_s": 0.0, "statuses": {}}


def _reset_store_stats() -> None:
    global _STORE_STATS
    with _STORE_LOCK:
        _STORE_STATS = {
            "primary": _empty_role_stats(),
            "fallback": _empty_role_stats(),
        }


def _record_locale_call(role: str, elapsed_s: float, status: str) -> None:
    with _STORE_LOCK:
        stats = _STORE_STATS.setdefault(role, _empty_role_stats())
        stats["calls"] += 1
        stats["sum_s"] += max(0.0, elapsed_s)
        stats["max_s"] = max(float(stats["max_s"]), max(0.0, elapsed_s))
        statuses = stats["statuses"]
        statuses[status] = int(statuses.get(status, 0)) + 1


def _snapshot_store_stats() -> dict[str, dict[str, Any]]:
    with _STORE_LOCK:
        return {
            role: {
                "calls": int(stats["calls"]),
                "sum_s": float(stats["sum_s"]),
                "max_s": float(stats["max_s"]),
                "statuses": dict(stats["statuses"]),
            }
            for role, stats in _STORE_STATS.items()
        }


def _status_text(statuses: dict[str, int]) -> str:
    return ",".join(f"{key}:{value}" for key, value in sorted(statuses.items())) or "none"


def _format_store_event(result: str, wall_s: float, stats: dict[str, dict[str, Any]]) -> str:
    primary = stats.get("primary", _empty_role_stats())
    fallback = stats.get("fallback", _empty_role_stats())
    return (
        "audit_store_performance "
        f"result={result} store_wall_s={wall_s:.3f} "
        f"primary_calls={int(primary['calls'])} primary_sum_s={float(primary['sum_s']):.3f} "
        f"primary_max_s={float(primary['max_s']):.3f} "
        f"fallback_calls={int(fallback['calls'])} fallback_sum_s={float(fallback['sum_s']):.3f} "
        f"fallback_max_s={float(fallback['max_s']):.3f} "
        f"primary_statuses={_status_text(primary['statuses'])} "
        f"fallback_statuses={_status_text(fallback['statuses'])}"
    )


def _locale_role(country: str, language: str, config: Any) -> str:
    selected_country = str(getattr(config, "country", "") or "").lower()
    selected_language = resolve_store_language(
        getattr(config, "language", ""),
        selected_country,
    )
    return (
        "primary"
        if str(country or "").lower() == selected_country
        and str(language or "").lower() == selected_language
        else "fallback"
    )


def install_performance_diagnostics() -> None:
    """Add aggregate timings without owning or replacing Store scheduling."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_fetch_locale = play_store.fetch_locale
    original_audit_apps = device_metadata.audit_apps_v8
    original_collect_metadata = device_insights.collect_device_metadata_v9

    def measured_fetch_locale(
        package_name: str,
        language: str,
        country: str,
        config: Any,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        role = _locale_role(country, language, config)
        started = time.perf_counter()
        status = "exception"
        try:
            result = original_fetch_locale(
                package_name,
                language,
                country,
                config,
                cancel_event=cancel_event,
            )
            status = str(result.get("status") or "unknown")
            return result
        finally:
            _record_locale_call(role, time.perf_counter() - started, status)

    def measured_audit_apps(
        apps: list[dict[str, str]],
        config: Any,
        progress_callback: Callable[[int, int, str], None] | None = None,
        pause_event: threading.Event | None = None,
        cancel_event: threading.Event | None = None,
        row_completed_callback: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        _reset_store_stats()
        started = time.perf_counter()
        result = "success"
        try:
            return original_audit_apps(
                apps,
                config,
                progress_callback,
                pause_event=pause_event,
                cancel_event=cancel_event,
                row_completed_callback=row_completed_callback,
            )
        except Exception:
            result = "error"
            raise
        finally:
            wall_s = max(0.0, time.perf_counter() - started)
            device_insights.log_event(_format_store_event(result, wall_s, _snapshot_store_stats()))

    def measured_collect_metadata(
        adb: str,
        packages: list[str],
        cancel_event: threading.Event | None = None,
        max_workers: int = 6,
    ) -> dict[str, dict[str, str]]:
        started = time.perf_counter()
        result = "success"
        try:
            return original_collect_metadata(adb, packages, cancel_event, max_workers=max_workers)
        except Exception:
            result = "error"
            raise
        finally:
            elapsed_s = max(0.0, time.perf_counter() - started)
            device_insights.log_event(
                "audit_device_performance "
                f"result={result} metadata_s={elapsed_s:.3f} packages={len(packages)} "
                f"metadata_workers={max_workers}"
            )

    # The canonical scheduler remains in play_store. Diagnostics only wrap its
    # stable entry points and therefore cannot silently change result semantics.
    play_store.fetch_locale = measured_fetch_locale
    device_metadata.audit_apps_v8 = measured_audit_apps
    device_insights.collect_device_metadata_v9 = measured_collect_metadata
    _INSTALLED = True
