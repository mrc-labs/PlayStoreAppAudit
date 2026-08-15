from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Optional

import playstore_audit_core as core

# Representative Play Store markets checked only when the selected market
# reports the package as unavailable. The selected country is always checked
# first by the normal audit path and is automatically skipped here.
MULTI_COUNTRY_MARKETS = (
    "us", "gb", "de", "fr", "it", "ch", "es", "ca", "au", "jp",
)


def _append_note(existing: object, note: str) -> str:
    parts = [str(existing or "").strip(), note.strip()]
    return " | ".join(part for part in parts if part)


def _wait_until_running(
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> bool:
    """Wait while paused and return False as soon as cancellation is requested.

    A set pause_event means RUNNING; a cleared pause_event means PAUSED.
    Already-running HTTP requests cannot be interrupted safely, so pause takes
    effect before the next package / fallback-country request starts.
    """
    if cancel_event is not None and cancel_event.is_set():
        return False
    if pause_event is None:
        return True

    while not pause_event.wait(0.10):
        if cancel_event is not None and cancel_event.is_set():
            return False
    return cancel_event is None or not cancel_event.is_set()


def fetch_app_multicountry(
    app_name: str,
    package_name: str,
    config: core.AuditConfig,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any] | None:
    """Run the normal audit, then verify other markets only if unavailable.

    Status policy:
    - available_in_other_country: selected market unavailable, found elsewhere
    - not_found_in_checked_countries: unavailable in every checked market
    - multi_country_check_inconclusive: no alternative market found, but at
      least one alternative check failed, so removal cannot be concluded

    Pause/cancel controls are cooperative. Requests already in flight are
    allowed to finish; no new package/alternative-country check starts while
    paused or after cancellation.
    """
    if not _wait_until_running(pause_event, cancel_event):
        return None

    result = core.fetch_app(app_name, package_name, config)
    if cancel_event is not None and cancel_event.is_set():
        return None

    status = str(result.get("play_status") or "")
    selected = (config.country or "").lower()

    if status == "available_in_fallback_locale_only":
        found_country = (config.fallback_country or "us").lower()
        result["play_status"] = "available_in_other_country"
        result["notes"] = _append_note(
            result.get("notes"),
            f"selected_country_unavailable:{selected}; available_in:{found_country}",
        )
        return result

    if status != "not_found_or_unavailable":
        return result

    checked: list[str] = []
    failed: list[str] = []

    for country in MULTI_COUNTRY_MARKETS:
        country = country.lower()
        if not country or country == selected:
            continue
        if not _wait_until_running(pause_event, cancel_event):
            return None

        checked.append(country)
        alternative = core._fetch_locale(
            package_name,
            "en",
            country,
            config,
        )
        if cancel_event is not None and cancel_event.is_set():
            return None

        alt_status = str(alternative.get("status") or "")

        if alt_status == "available":
            result["play_status"] = "available_in_other_country"
            result["play_http_status"] = alternative.get("http_status", "")
            result["play_title"] = alternative.get("title", "") or result.get("play_title", "")
            result["play_last_update"] = alternative.get("updated", "") or result.get("play_last_update", "")
            source = str(alternative.get("source") or "")
            result["updated_source"] = f"{source}_multi_country" if source else result.get("updated_source", "")
            result["store_url"] = alternative.get("url", "") or result.get("store_url", "")
            result["notes"] = _append_note(
                result.get("notes"),
                f"selected_country_unavailable:{selected}; available_in:{country}; "
                f"multi_country_checked:{','.join(checked)}",
            )
            return result

        if alt_status != "not_found_or_unavailable":
            failed.append(f"{country}:{alt_status or 'unknown'}")

    checked_text = ",".join(checked)
    if failed:
        result["play_status"] = "multi_country_check_inconclusive"
        result["notes"] = _append_note(
            result.get("notes"),
            f"selected_country_unavailable:{selected}; multi_country_checked:{checked_text}; "
            f"check_errors:{','.join(failed)}",
        )
    else:
        result["play_status"] = "not_found_in_checked_countries"
        result["notes"] = _append_note(
            result.get("notes"),
            f"selected_country_unavailable:{selected}; also_not_found_in:{checked_text}; "
            "likely_removed_or_region_restricted",
        )

    return result


def audit_apps_multicountry(
    apps: list[dict[str, str]],
    config: core.AuditConfig,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    results: list[Optional[dict[str, Any]]] = [None] * len(apps)

    def run_one(app: dict[str, str]) -> dict[str, Any] | None:
        if not _wait_until_running(pause_event, cancel_event):
            return None
        return fetch_app_multicountry(
            app["app_name"],
            app["package_name"],
            config,
            pause_event=pause_event,
            cancel_event=cancel_event,
        )

    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        futures = {
            executor.submit(run_one, app): index
            for index, app in enumerate(apps)
        }
        completed = 0
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
                    "updated_source": "",
                    "store_url": f"{core.PLAY_URL}?id={app['package_name']}",
                    "notes": str(exc)[:500],
                }

            completed += 1
            if progress_callback:
                progress_callback(completed, len(apps), app["package_name"])

    return [row for row in results if row is not None]
