from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.performance_diagnostics as performance_diagnostics

_LOCK = threading.Lock()
_THREAD_CONTEXT = threading.local()
_INSTALLED = False
_HTML_STATS: dict[str, dict[str, Any]] = {}
_SCRAPER_STATS: dict[str, dict[str, Any]] = {}


def _empty_stats() -> dict[str, Any]:
    return {"calls": 0, "sum_s": 0.0, "max_s": 0.0, "statuses": {}}


def _empty_scraper_stats() -> dict[str, Any]:
    return {
        "locales": 0,
        "attempts": 0,
        "retries": 0,
        "successes": 0,
        "exhausted": 0,
        "sum_s": 0.0,
        "max_s": 0.0,
        "retry_sleep_s": 0.0,
        "success_attempts": {},
        "exceptions": {},
    }


def _reset_html_stats() -> None:
    global _HTML_STATS
    with _LOCK:
        _HTML_STATS = {"primary": _empty_stats(), "fallback": _empty_stats()}


def _reset_scraper_stats() -> None:
    global _SCRAPER_STATS
    with _LOCK:
        _SCRAPER_STATS = {
            "primary": _empty_scraper_stats(),
            "fallback": _empty_scraper_stats(),
        }


def _record_html_call(role: str, elapsed_s: float, status: str) -> None:
    with _LOCK:
        stats = _HTML_STATS.setdefault(role, _empty_stats())
        elapsed = max(0.0, elapsed_s)
        stats["calls"] += 1
        stats["sum_s"] += elapsed
        stats["max_s"] = max(float(stats["max_s"]), elapsed)
        statuses = stats["statuses"]
        statuses[status] = int(statuses.get(status, 0)) + 1


def _record_scraper_locale_start(role: str) -> None:
    with _LOCK:
        _SCRAPER_STATS.setdefault(role, _empty_scraper_stats())["locales"] += 1


def _record_scraper_attempt(
    role: str,
    attempt: int,
    elapsed_s: float,
    exception_name: str,
) -> None:
    with _LOCK:
        stats = _SCRAPER_STATS.setdefault(role, _empty_scraper_stats())
        elapsed = max(0.0, elapsed_s)
        stats["attempts"] += 1
        stats["sum_s"] += elapsed
        stats["max_s"] = max(float(stats["max_s"]), elapsed)
        if exception_name:
            exceptions = stats["exceptions"]
            exceptions[exception_name] = int(exceptions.get(exception_name, 0)) + 1
        else:
            stats["successes"] += 1
            success_attempts = stats["success_attempts"]
            key = str(attempt)
            success_attempts[key] = int(success_attempts.get(key, 0)) + 1


def _finish_scraper_locale(
    role: str,
    attempts: int,
    succeeded: bool,
    config: Any,
) -> None:
    if attempts <= 0:
        return
    retries = max(0, attempts - 1)
    retry_sleep_base = max(0.0, float(getattr(config, "retry_sleep_base", 0.0) or 0.0))
    retry_sleep_s = sum(retry_sleep_base * retry for retry in range(1, attempts))
    with _LOCK:
        stats = _SCRAPER_STATS.setdefault(role, _empty_scraper_stats())
        stats["retries"] += retries
        stats["retry_sleep_s"] += retry_sleep_s
        if not succeeded:
            stats["exhausted"] += 1


def _snapshot_html_stats() -> dict[str, dict[str, Any]]:
    with _LOCK:
        return {
            role: {
                "calls": int(stats["calls"]),
                "sum_s": float(stats["sum_s"]),
                "max_s": float(stats["max_s"]),
                "statuses": dict(stats["statuses"]),
            }
            for role, stats in _HTML_STATS.items()
        }


def _snapshot_scraper_stats() -> dict[str, dict[str, Any]]:
    with _LOCK:
        return {
            role: {
                "locales": int(stats["locales"]),
                "attempts": int(stats["attempts"]),
                "retries": int(stats["retries"]),
                "successes": int(stats["successes"]),
                "exhausted": int(stats["exhausted"]),
                "sum_s": float(stats["sum_s"]),
                "max_s": float(stats["max_s"]),
                "retry_sleep_s": float(stats["retry_sleep_s"]),
                "success_attempts": dict(stats["success_attempts"]),
                "exceptions": dict(stats["exceptions"]),
            }
            for role, stats in _SCRAPER_STATS.items()
        }


def _status_text(statuses: dict[str, int]) -> str:
    return ",".join(f"{key}:{value}" for key, value in sorted(statuses.items())) or "none"


def _role_fields(
    role: str,
    html_stats: dict[str, dict[str, Any]],
    locale_stats: dict[str, dict[str, Any]],
) -> str:
    html = html_stats.get(role, _empty_stats())
    locale = locale_stats.get(role, _empty_stats())
    locale_sum = max(0.0, float(locale.get("sum_s", 0.0)))
    html_sum = max(0.0, float(html.get("sum_s", 0.0)))
    approx_scraper_sum = max(0.0, locale_sum - html_sum)
    html_share = (html_sum / locale_sum * 100.0) if locale_sum else 0.0
    return (
        f"{role}_html_calls={int(html['calls'])} "
        f"{role}_html_sum_s={html_sum:.3f} "
        f"{role}_html_max_s={float(html['max_s']):.3f} "
        f"{role}_html_share_pct={html_share:.1f} "
        f"{role}_approx_scraper_sum_s={approx_scraper_sum:.3f} "
        f"{role}_html_statuses={_status_text(html['statuses'])}"
    )


def _scraper_role_fields(role: str, scraper_stats: dict[str, dict[str, Any]]) -> str:
    stats = scraper_stats.get(role, _empty_scraper_stats())
    return (
        f"{role}_scraper_locales={int(stats['locales'])} "
        f"{role}_scraper_attempts={int(stats['attempts'])} "
        f"{role}_scraper_retries={int(stats['retries'])} "
        f"{role}_scraper_successes={int(stats['successes'])} "
        f"{role}_scraper_exhausted={int(stats['exhausted'])} "
        f"{role}_scraper_sum_s={float(stats['sum_s']):.3f} "
        f"{role}_scraper_max_s={float(stats['max_s']):.3f} "
        f"{role}_retry_sleep_s={float(stats['retry_sleep_s']):.3f} "
        f"{role}_success_attempts={_status_text(stats['success_attempts'])} "
        f"{role}_scraper_exceptions={_status_text(stats['exceptions'])}"
    )


def _format_path_event(
    html_stats: dict[str, dict[str, Any]],
    locale_stats: dict[str, dict[str, Any]],
) -> str:
    return (
        "audit_store_path_performance "
        + _role_fields("primary", html_stats, locale_stats)
        + " "
        + _role_fields("fallback", html_stats, locale_stats)
    )


def _format_scraper_event(config: Any, scraper_stats: dict[str, dict[str, Any]]) -> str:
    selected = str(getattr(config, "country", "") or "").lower()
    markets = device_metadata.get_fallback_countries(selected)
    markets_text = ",".join(markets) or "none"
    return (
        "audit_store_scraper_performance "
        f"selected_country={selected or 'none'} "
        f"fallback_markets_count={len(markets)} fallback_markets={markets_text} "
        f"max_retries={int(getattr(config, 'max_retries', 0) or 0)} "
        f"retry_sleep_base={float(getattr(config, 'retry_sleep_base', 0.0) or 0.0):.3f} "
        + _scraper_role_fields("primary", scraper_stats)
        + " "
        + _scraper_role_fields("fallback", scraper_stats)
    )


def install_store_path_diagnostics() -> None:
    """Measure aggregate Store path and scraper-attempt cost without changing semantics.

    The diagnostics record no package names. Scraper attempts are observed by a
    transparent wrapper around the already-installed google_play_scraper entry
    point, while a thread-local locale context keeps primary/fallback attribution
    correct for concurrent audits.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    original_html_request = device_metadata.core._html_request
    original_fetch_locale = device_metadata.core._fetch_locale
    original_audit_apps = device_metadata.audit_apps_v8

    try:
        import google_play_scraper
    except ImportError:
        google_play_scraper = None

    original_play_app = google_play_scraper.app if google_play_scraper is not None else None

    def measured_play_app(*args: Any, **kwargs: Any) -> Any:
        if original_play_app is None:
            raise RuntimeError("google_play_scraper app entry point is unavailable")
        role = str(getattr(_THREAD_CONTEXT, "role", "") or "")
        if role not in {"primary", "fallback"}:
            return original_play_app(*args, **kwargs)

        attempt = int(getattr(_THREAD_CONTEXT, "attempt", 0) or 0) + 1
        _THREAD_CONTEXT.attempt = attempt
        started = time.perf_counter()
        try:
            result = original_play_app(*args, **kwargs)
        except Exception as exc:
            _record_scraper_attempt(
                role,
                attempt,
                time.perf_counter() - started,
                type(exc).__name__,
            )
            raise
        _THREAD_CONTEXT.succeeded = True
        _record_scraper_attempt(role, attempt, time.perf_counter() - started, "")
        return result

    def contextual_fetch_locale(
        package_name: str,
        language: str,
        country: str,
        config: Any,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        role = performance_diagnostics._locale_role(country, language, config)
        previous = dict(vars(_THREAD_CONTEXT))
        _THREAD_CONTEXT.role = role
        _THREAD_CONTEXT.attempt = 0
        _THREAD_CONTEXT.succeeded = False
        _record_scraper_locale_start(role)
        try:
            return original_fetch_locale(
                package_name,
                language,
                country,
                config,
                cancel_event=cancel_event,
            )
        finally:
            attempts = int(getattr(_THREAD_CONTEXT, "attempt", 0) or 0)
            succeeded = bool(getattr(_THREAD_CONTEXT, "succeeded", False))
            _finish_scraper_locale(role, attempts, succeeded, config)
            vars(_THREAD_CONTEXT).clear()
            vars(_THREAD_CONTEXT).update(previous)

    def measured_html_request(
        package_name: str,
        language: str,
        country: str,
        config: Any,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        role = performance_diagnostics._locale_role(country, language, config)
        started = time.perf_counter()
        status = "exception"
        try:
            result = original_html_request(
                package_name,
                language,
                country,
                config,
                cancel_event=cancel_event,
            )
            status = str(result.get("status") or ("available" if result.get("ok") else "unknown"))
            return result
        finally:
            _record_html_call(role, time.perf_counter() - started, status)

    def measured_audit_apps(
        apps: list[dict[str, str]],
        config: Any,
        progress_callback: Callable[[int, int, str], None] | None = None,
        pause_event: threading.Event | None = None,
        cancel_event: threading.Event | None = None,
        row_completed_callback: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        _reset_html_stats()
        _reset_scraper_stats()
        try:
            return original_audit_apps(
                apps,
                config,
                progress_callback,
                pause_event=pause_event,
                cancel_event=cancel_event,
                row_completed_callback=row_completed_callback,
            )
        finally:
            device_insights.log_event(
                _format_path_event(
                    _snapshot_html_stats(),
                    performance_diagnostics._snapshot_store_stats(),
                )
            )
            device_insights.log_event(_format_scraper_event(config, _snapshot_scraper_stats()))

    if google_play_scraper is not None:
        google_play_scraper.app = measured_play_app
    device_metadata.core._fetch_locale = contextual_fetch_locale
    device_metadata.core._html_request = measured_html_request
    device_metadata.audit_apps_v8 = measured_audit_apps
    _INSTALLED = True
