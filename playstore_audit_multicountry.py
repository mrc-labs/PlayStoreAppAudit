from __future__ import annotations

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


def fetch_app_multicountry(
    app_name: str,
    package_name: str,
    config: core.AuditConfig,
) -> dict[str, Any]:
    """Run the normal audit, then verify other markets only if unavailable.

    Status policy:
    - available_in_other_country: selected market unavailable, found elsewhere
    - not_found_in_checked_countries: unavailable in every checked market
    - multi_country_check_inconclusive: no alternative market found, but at
      least one alternative check failed, so removal cannot be concluded
    """
    result = core.fetch_app(app_name, package_name, config)
    status = str(result.get("play_status") or "")
    selected = (config.country or "").lower()

    # The legacy core already checks fallback_country (normally US). If that
    # succeeds while the primary country is unavailable, normalise it to the
    # new explicit multi-country status and preserve the data it recovered.
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

        checked.append(country)
        alternative = core._fetch_locale(
            package_name,
            "en",
            country,
            config,
        )
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
) -> list[dict[str, Any]]:
    results: list[Optional[dict[str, Any]]] = [None] * len(apps)
    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        futures = {
            executor.submit(
                fetch_app_multicountry,
                app["app_name"],
                app["package_name"],
                config,
            ): index
            for index, app in enumerate(apps)
        }
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            app = apps[index]
            try:
                results[index] = future.result()
            except Exception as exc:
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
