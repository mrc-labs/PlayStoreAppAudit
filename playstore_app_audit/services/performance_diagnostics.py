from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata

FALLBACK_BATCH_SIZE = 3

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
    selected_language = str(getattr(config, "language", "") or "").lower()
    return (
        "primary"
        if str(country or "").lower() == selected_country
        and str(language or "").lower() == selected_language
        else "fallback"
    )


def _fetch_locale_with_slot(
    package_name: str,
    language: str,
    country: str,
    config: Any,
    request_slots: threading.Semaphore,
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> dict[str, Any] | None:
    """Run one Store locale request without exceeding the normal worker ceiling."""
    while True:
        if not device_metadata._wait_until_running(pause_event, cancel_event):
            return None
        if not request_slots.acquire(timeout=0.10):
            continue
        if cancel_event is not None and cancel_event.is_set():
            request_slots.release()
            return None
        if pause_event is not None and not pause_event.is_set():
            request_slots.release()
            continue
        break

    try:
        return device_metadata.core._fetch_locale(package_name, language, country, config)
    finally:
        request_slots.release()


def _fetch_app_bounded(
    app_name: str,
    package_name: str,
    config: Any,
    request_slots: threading.Semaphore,
    fallback_executor: ThreadPoolExecutor,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    fallback_progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    """Fetch one app while parallelising only negative multi-country verification.

    Alternative markets are evaluated in small ordered batches. The batch calls
    may run concurrently, but the first available market is still chosen by the
    configured market order. A shared semaphore keeps total in-flight Store
    locale requests at or below the existing audit worker ceiling.
    """
    if not device_metadata._wait_until_running(pause_event, cancel_event):
        return None

    selected = str(getattr(config, "country", "") or "").lower()
    primary = _fetch_locale_with_slot(
        package_name,
        str(getattr(config, "language", "") or ""),
        selected,
        config,
        request_slots,
        pause_event,
        cancel_event,
    )
    if primary is None or (cancel_event is not None and cancel_event.is_set()):
        return None

    result: dict[str, Any] = {
        "app_name": app_name,
        "package_name": package_name,
        "play_status": primary.get("status", "check_failed"),
        "play_http_status": primary.get("http_status", ""),
        "play_title": primary.get("title", ""),
        "play_last_update": primary.get("updated", ""),
        "play_version": primary.get("version", ""),
        "updated_source": primary.get("source", ""),
        "store_url": primary.get(
            "url", f"{device_metadata.core.PLAY_URL}?id={package_name}"
        ),
        "notes": primary.get("notes", ""),
    }

    primary_status = str(primary.get("status") or "")
    markets = device_metadata.get_fallback_countries(selected)

    # Healthy listings keep the proven sequential metadata-completion path.
    # The measured slow tail is the negative multi-country verification path.
    if primary_status == "available":
        if result["play_last_update"] and result["play_version"]:
            return result
        for country in markets:
            alternative = _fetch_locale_with_slot(
                package_name,
                "en",
                country,
                config,
                request_slots,
                pause_event,
                cancel_event,
            )
            if alternative is None:
                return None
            if str(alternative.get("status") or "") != "available":
                continue
            if not result["play_last_update"] and alternative.get("updated"):
                result["play_last_update"] = alternative.get("updated", "")
                result["updated_source"] = (
                    f"{alternative.get('source', '')}_fallback_locale".strip("_")
                )
            if not result["play_version"] and alternative.get("version"):
                result["play_version"] = alternative.get("version", "")
            if not result["play_title"] and alternative.get("title"):
                result["play_title"] = alternative.get("title", "")
            result["notes"] = device_metadata._append_note(
                result["notes"], "missing_metadata_completed_from_fallback_market"
            )
            break
        return result

    checked: list[str] = []
    failed: list[str] = []
    batch_size = max(1, min(FALLBACK_BATCH_SIZE, len(markets) or 1))
    fallback_started = bool(markets and fallback_progress_callback)
    if fallback_started and fallback_progress_callback is not None:
        fallback_progress_callback("start")

    try:
        for start in range(0, len(markets), batch_size):
            if not device_metadata._wait_until_running(pause_event, cancel_event):
                return None
            batch = markets[start : start + batch_size]
            futures = [
                (
                    country,
                    fallback_executor.submit(
                        _fetch_locale_with_slot,
                        package_name,
                        "en",
                        country,
                        config,
                        request_slots,
                        pause_event,
                        cancel_event,
                    ),
                )
                for country in batch
            ]

            for index, (country, future) in enumerate(futures):
                alternative = future.result()
                if alternative is None:
                    for _later_country, later_future in futures[index + 1 :]:
                        later_future.cancel()
                    return None

                checked.append(country)
                if fallback_progress_callback is not None:
                    fallback_progress_callback("check")
                alt_status = str(alternative.get("status") or "")
                if alt_status == "available":
                    for _later_country, later_future in futures[index + 1 :]:
                        later_future.cancel()
                    if primary_status == "not_found_or_unavailable":
                        result["play_status"] = "available_in_other_country"
                        note = (
                            f"selected_country_unavailable:{selected}; available_in:{country}; "
                            f"multi_country_checked:{','.join(checked)}"
                        )
                    else:
                        result["play_status"] = "available"
                        note = (
                            f"primary_country_check_failed:{selected}; fallback_available:{country}; "
                            f"multi_country_checked:{','.join(checked)}"
                        )
                    result["play_http_status"] = alternative.get("http_status", "")
                    result["play_title"] = alternative.get("title", "") or result["play_title"]
                    result["play_last_update"] = (
                        alternative.get("updated", "") or result["play_last_update"]
                    )
                    result["play_version"] = alternative.get("version", "") or result["play_version"]
                    source = str(alternative.get("source") or "")
                    result["updated_source"] = (
                        f"{source}_multi_country" if source else result["updated_source"]
                    )
                    result["store_url"] = alternative.get("url", "") or result["store_url"]
                    result["notes"] = device_metadata._append_note(result["notes"], note)
                    return result
                if alt_status != "not_found_or_unavailable":
                    failed.append(f"{country}:{alt_status or 'unknown'}")

        checked_text = ",".join(checked)
        if not checked:
            result["play_status"] = "multi_country_check_inconclusive"
            result["notes"] = device_metadata._append_note(
                result["notes"], "no_fallback_countries_configured"
            )
        elif primary_status == "not_found_or_unavailable" and not failed:
            result["play_status"] = "not_found_in_checked_countries"
            result["notes"] = device_metadata._append_note(
                result["notes"],
                f"selected_country_unavailable:{selected}; also_not_found_in:{checked_text}; "
                "likely_removed_or_region_restricted",
            )
        else:
            result["play_status"] = "multi_country_check_inconclusive"
            result["notes"] = device_metadata._append_note(
                result["notes"],
                f"primary_country_status:{primary_status or 'unknown'}; "
                f"multi_country_checked:{checked_text}; check_errors:{','.join(failed)}",
            )
        return result
    finally:
        if fallback_started and fallback_progress_callback is not None:
            fallback_progress_callback("finish")


def _audit_apps_bounded(
    apps: list[dict[str, str]],
    config: Any,
    progress_callback: Callable[[int, int, str], None] | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    """Run the normal audit with bounded parallel fallback-country batches."""
    device_metadata.install_core_version_support()
    worker_limit = max(1, int(getattr(config, "max_workers", 1)))
    request_slots = threading.Semaphore(worker_limit)
    results: list[dict[str, Any] | None] = [None] * len(apps)
    progress_lock = threading.Lock()
    completed = 0
    active_fallback_apps = 0
    fallback_checks_completed = 0

    def fallback_progress(event: str) -> None:
        nonlocal active_fallback_apps, fallback_checks_completed
        if progress_callback is None:
            return
        with progress_lock:
            if event == "start":
                active_fallback_apps += 1
            elif event == "check":
                fallback_checks_completed += 1
            elif event == "finish":
                active_fallback_apps = max(0, active_fallback_apps - 1)
                return
            else:
                return

            app_word = "app" if active_fallback_apps == 1 else "apps"
            check_word = "check" if fallback_checks_completed == 1 else "checks"
            progress_callback(
                completed,
                len(apps),
                "Verifying regional availability • "
                f"{fallback_checks_completed} country {check_word} completed • "
                f"{active_fallback_apps} {app_word} still checking",
            )

    def app_completed(package_name: str) -> None:
        nonlocal completed
        with progress_lock:
            completed += 1
            if progress_callback is not None:
                progress_callback(completed, len(apps), package_name)

    with ThreadPoolExecutor(
        max_workers=worker_limit, thread_name_prefix="playstore-fallback"
    ) as fallback_executor:

        def run_one(app: dict[str, str]) -> dict[str, Any] | None:
            if not device_metadata._wait_until_running(pause_event, cancel_event):
                return None
            return _fetch_app_bounded(
                app["app_name"],
                app["package_name"],
                config,
                request_slots,
                fallback_executor,
                pause_event=pause_event,
                cancel_event=cancel_event,
                fallback_progress_callback=fallback_progress,
            )

        with ThreadPoolExecutor(
            max_workers=worker_limit, thread_name_prefix="playstore-app"
        ) as executor:
            futures = {executor.submit(run_one, app): index for index, app in enumerate(apps)}
            for future in as_completed(futures):
                index = futures[future]
                app = apps[index]
                if cancel_event is not None and cancel_event.is_set():
                    for pending in futures:
                        pending.cancel()
                try:
                    row = future.result()
                    if row is None:
                        continue
                    results[index] = row
                except Exception as exc:
                    if cancel_event is not None and cancel_event.is_set():
                        continue
                    results[index] = {
                        "app_name": app["app_name"],
                        "package_name": app["package_name"],
                        "play_status": "unexpected_error",
                        "play_http_status": "",
                        "play_title": "",
                        "play_last_update": "",
                        "play_version": "",
                        "updated_source": "",
                        "store_url": f"{device_metadata.core.PLAY_URL}?id={app['package_name']}",
                        "notes": str(exc)[:500],
                    }
                app_completed(app["package_name"])

    return [row for row in results if row is not None]


def install_performance_diagnostics() -> None:
    """Install aggregate timings plus the bounded negative-fallback scheduler."""
    global _INSTALLED
    if _INSTALLED:
        return

    original_fetch_locale = device_metadata.core._fetch_locale
    original_collect_metadata = device_insights.collect_device_metadata_v9

    def measured_fetch_locale(
        package_name: str,
        language: str,
        country: str,
        config: Any,
    ) -> dict[str, Any]:
        role = _locale_role(country, language, config)
        started = time.perf_counter()
        status = "exception"
        try:
            result = original_fetch_locale(package_name, language, country, config)
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
    ) -> list[dict[str, Any]]:
        _reset_store_stats()
        started = time.perf_counter()
        result = "success"
        try:
            return _audit_apps_bounded(
                apps,
                config,
                progress_callback,
                pause_event=pause_event,
                cancel_event=cancel_event,
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

    device_metadata.core._fetch_locale = measured_fetch_locale
    device_metadata.audit_apps_v8 = measured_audit_apps
    device_insights.collect_device_metadata_v9 = measured_collect_metadata
    _INSTALLED = True
