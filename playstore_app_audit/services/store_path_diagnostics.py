from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.performance_diagnostics as performance_diagnostics

_LOCK = threading.Lock()
_INSTALLED = False
_HTML_STATS: dict[str, dict[str, Any]] = {}


def _empty_stats() -> dict[str, Any]:
    return {"calls": 0, "sum_s": 0.0, "max_s": 0.0, "statuses": {}}


def _reset_html_stats() -> None:
    global _HTML_STATS
    with _LOCK:
        _HTML_STATS = {"primary": _empty_stats(), "fallback": _empty_stats()}


def _record_html_call(role: str, elapsed_s: float, status: str) -> None:
    with _LOCK:
        stats = _HTML_STATS.setdefault(role, _empty_stats())
        elapsed = max(0.0, elapsed_s)
        stats["calls"] += 1
        stats["sum_s"] += elapsed
        stats["max_s"] = max(float(stats["max_s"]), elapsed)
        statuses = stats["statuses"]
        statuses[status] = int(statuses.get(status, 0)) + 1


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


def install_store_path_diagnostics() -> None:
    """Measure aggregate HTML-fallback cost without changing Store semantics.

    Locale timing already includes the scraper path. Subtracting measured HTML
    time from locale aggregate time gives an approximate scraper-side aggregate
    cost, with only tiny locale bookkeeping included in that approximation.
    No package names are logged.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    original_html_request = device_metadata.core._html_request
    original_audit_apps = device_metadata.audit_apps_v8

    def measured_html_request(
        package_name: str,
        language: str,
        country: str,
        config: Any,
    ) -> dict[str, Any]:
        role = performance_diagnostics._locale_role(country, language, config)
        started = time.perf_counter()
        status = "exception"
        try:
            result = original_html_request(package_name, language, country, config)
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
    ) -> list[dict[str, Any]]:
        _reset_html_stats()
        try:
            return original_audit_apps(
                apps,
                config,
                progress_callback,
                pause_event=pause_event,
                cancel_event=cancel_event,
            )
        finally:
            device_insights.log_event(
                _format_path_event(
                    _snapshot_html_stats(),
                    performance_diagnostics._snapshot_store_stats(),
                )
            )

    device_metadata.core._html_request = measured_html_request
    device_metadata.audit_apps_v8 = measured_audit_apps
    _INSTALLED = True
