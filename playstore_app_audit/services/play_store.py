from __future__ import annotations

import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import playstore_app_audit.services.audit_engine as core
from playstore_app_audit.services.audit_engine import AuditConfig, load_apps
from playstore_app_audit.services.store_locale import (
    primary_language_for_country,
    resolve_store_language,
)

ProgressCallback = Callable[[int, int, str], None]
FALLBACK_BATCH_SIZE = 3
STORE_EVIDENCE_FIELD = "_store_evidence"
_COUNTRY_LOCALE_EVIDENCE_FIELD = "_country_locale_evidence"


def _append_note(existing: object, note: str) -> str:
    parts = [str(existing or "").strip(), str(note or "").strip()]
    return " | ".join(part for part in parts if part)


def _locale_evidence(result: dict[str, Any], language_role: str) -> dict[str, Any]:
    """Return one JSON-serializable record for an actual Store locale request."""
    return {
        "language_role": language_role,
        "country": str(result.get("country") or "").strip().lower(),
        "language": str(result.get("language") or "").strip().lower(),
        "status": str(result.get("status") or "unknown"),
        "http_status": result.get("http_status", ""),
        "source": str(result.get("source") or ""),
    }


def _with_country_locale_evidence(
    result: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    enriched = dict(result)
    enriched[_COUNTRY_LOCALE_EVIDENCE_FIELD] = [dict(item) for item in evidence]
    return enriched


def _store_evidence_for_country(result: dict[str, Any], role: str) -> list[dict[str, Any]]:
    raw = result.get(_COUNTRY_LOCALE_EVIDENCE_FIELD)
    if isinstance(raw, list):
        locale_entries = [dict(item) for item in raw if isinstance(item, dict)]
    else:
        locale_entries = []
    if not locale_entries:
        locale_entries = [_locale_evidence(result, "preferred")]
    return [{"role": role, **entry} for entry in locale_entries]


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


def _fallback_countries(selected_country: str) -> tuple[str, ...]:
    # Keep the existing expert-configured country order as the canonical source
    # while moving Store execution out of device/performance modules.
    from playstore_app_audit.services import device_metadata

    return device_metadata.get_fallback_countries(selected_country)


def _normalise_version(value: object) -> str:
    text = str(value or "").strip()
    if text.casefold() in {"none", "null", "n/a"}:
        return ""
    return text


def scraper_request(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
) -> dict[str, Any]:
    """Query google-play-scraper with terminal NotFound and transient retries."""
    try:
        from google_play_scraper import app as play_app
        from google_play_scraper.exceptions import NotFoundError
    except ImportError as exc:
        return {
            "ok": False,
            "not_found": False,
            "title": "",
            "updated": "",
            "version": "",
            "error": f"google_play_scraper not installed: {exc}",
        }

    last_error = ""
    for attempt in range(config.max_retries + 1):
        try:
            data = play_app(package_name, lang=language, country=country)
            return {
                "ok": True,
                "not_found": False,
                "title": str(data.get("title") or "").strip(),
                "updated": core.normalise_updated(data.get("updated")),
                "version": _normalise_version(data.get("version")),
                "error": "",
            }
        except NotFoundError as exc:
            # Validated invariant: scraper NotFound is terminal. It must not be
            # retried as though it were a timeout/network failure.
            return {
                "ok": False,
                "not_found": True,
                "title": "",
                "updated": "",
                "version": "",
                "error": str(exc)[:300] or "Not found",
            }
        except Exception as exc:
            last_error = str(exc)[:300]
            if attempt < config.max_retries:
                time.sleep(config.retry_sleep_base * (attempt + 1))

    return {
        "ok": False,
        "not_found": False,
        "title": "",
        "updated": "",
        "version": "",
        "error": last_error or "Unknown Google Play scraper error",
    }


def fetch_locale(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
) -> dict[str, Any]:
    """Fetch one Store locale while preserving validated status semantics."""
    language = resolve_store_language(language, country)
    country = str(country or "").strip().lower()
    scraper = scraper_request(package_name, language, country, config)

    if scraper["ok"] and scraper["updated"]:
        return {
            "status": "available",
            "http_status": 200,
            "title": scraper["title"],
            "updated": scraper["updated"],
            "version": scraper["version"],
            "source": "google_play_scraper",
            "url": f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "notes": "",
            "language": language,
            "country": country,
        }

    # HTML is still the confirmation/fallback path. A scraper NotFound never
    # becomes a removed classification on its own; the Store response remains
    # the regional evidence used by the existing status model.
    html = core._html_request(package_name, language, country, config)
    if scraper["ok"]:
        title = scraper["title"] or html.get("title", "")
        updated = scraper["updated"] or html.get("updated", "")
        return {
            "status": "available",
            "http_status": html.get("http_status", 200),
            "title": title,
            "updated": updated,
            "version": scraper["version"],
            "source": "google_play_scraper"
            if scraper["updated"]
            else ("html_fallback" if updated else ""),
            "url": html.get("url")
            or f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "notes": "" if updated else "update_date_not_found",
            "language": language,
            "country": country,
        }

    return {
        "status": html.get("status", "check_failed"),
        "http_status": html.get("http_status", ""),
        "title": html.get("title", ""),
        "updated": html.get("updated", ""),
        "version": "",
        "source": "html_fallback" if html.get("updated") else "",
        "url": html.get("url")
        or f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
        "notes": " | ".join(
            value
            for value in [
                f"scraper: {scraper['error']}" if scraper["error"] else "",
                f"html: {html.get('error', '')}" if html.get("error") else "",
            ]
            if value
        ),
        "language": language,
        "country": country,
    }


def _needs_english_fallback(result: dict[str, Any], language: str) -> bool:
    if language == "en":
        return False
    status = str(result.get("status") or "")
    if status == "available":
        return not result.get("updated") or not result.get("version")
    # A conclusive regional not-found does not need a second language request.
    # English is a reliability fallback for inconclusive/failed locale requests.
    return status in {"request_error", "http_error", "check_failed", "unexpected_error"}


def _merge_available_metadata(
    preferred: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(preferred)
    for key in ("updated", "version"):
        if not merged.get(key) and fallback.get(key):
            merged[key] = fallback.get(key, "")
    if not merged.get("title") and fallback.get("title"):
        merged["title"] = fallback.get("title", "")
    if fallback.get("updated") and not preferred.get("updated"):
        merged["source"] = str(fallback.get("source") or merged.get("source") or "")
    merged["notes"] = _append_note(
        merged.get("notes"),
        f"language_fallback_checked:{fallback.get('language', 'en')}",
    )
    return merged


def _fetch_country(
    package_name: str,
    country: str,
    preferred_language: str,
    config: AuditConfig,
    fetch_one: Callable[[str, str, str, AuditConfig], dict[str, Any]],
) -> dict[str, Any]:
    language = resolve_store_language(preferred_language, country)
    preferred = fetch_one(package_name, language, country, config)
    evidence = [_locale_evidence(preferred, "preferred")]
    if not _needs_english_fallback(preferred, language):
        return _with_country_locale_evidence(preferred, evidence)

    english = fetch_one(package_name, "en", country, config)
    evidence.append(_locale_evidence(english, "english_fallback"))
    if str(preferred.get("status") or "") == "available":
        if str(english.get("status") or "") == "available":
            merged = _merge_available_metadata(preferred, english)
            return _with_country_locale_evidence(merged, evidence)
        preferred["notes"] = _append_note(
            preferred.get("notes"),
            f"english_language_fallback:{english.get('status', 'unknown')}",
        )
        return _with_country_locale_evidence(preferred, evidence)

    if str(english.get("status") or "") in {"available", "not_found_or_unavailable"}:
        english["notes"] = _append_note(
            english.get("notes"),
            f"preferred_language_failed:{language}:{preferred.get('status', 'unknown')}",
        )
        return _with_country_locale_evidence(english, evidence)

    preferred["notes"] = _append_note(
        preferred.get("notes"),
        f"english_language_fallback:{english.get('status', 'unknown')}",
    )
    return _with_country_locale_evidence(preferred, evidence)


def _fetch_locale_with_slot(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
    request_slots: threading.Semaphore,
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> dict[str, Any] | None:
    while True:
        if not _wait_until_running(pause_event, cancel_event):
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
        return fetch_locale(package_name, language, country, config)
    finally:
        request_slots.release()


def _fetch_country_with_slot(
    package_name: str,
    country: str,
    preferred_language: str,
    config: AuditConfig,
    request_slots: threading.Semaphore,
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> dict[str, Any] | None:
    def fetch_one(
        package: str,
        language: str,
        market: str,
        audit_config: AuditConfig,
    ) -> dict[str, Any]:
        result = _fetch_locale_with_slot(
            package,
            language,
            market,
            audit_config,
            request_slots,
            pause_event,
            cancel_event,
        )
        if result is None:
            return {"status": "cancelled", "language": language, "country": market}
        return result

    result = _fetch_country(package_name, country, preferred_language, config, fetch_one)
    return None if str(result.get("status") or "") == "cancelled" else result


def _fetch_app_bounded(
    app_name: str,
    package_name: str,
    config: AuditConfig,
    request_slots: threading.Semaphore,
    fallback_executor: ThreadPoolExecutor,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    fallback_progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any] | None:
    if not _wait_until_running(pause_event, cancel_event):
        return None

    selected = str(config.country or "").strip().lower()
    selected_language = resolve_store_language(config.language, selected)
    primary = _fetch_country_with_slot(
        package_name,
        selected,
        selected_language,
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
        "store_url": primary.get("url", f"{core.PLAY_URL}?id={package_name}"),
        "store_country": selected,
        "store_language": primary.get("language", selected_language),
        "notes": primary.get("notes", ""),
        STORE_EVIDENCE_FIELD: _store_evidence_for_country(primary, "primary"),
    }

    primary_status = str(primary.get("status") or "")
    markets = _fallback_countries(selected)

    if primary_status == "available":
        if result["play_last_update"] and result["play_version"]:
            return result
        for country in markets:
            if not _wait_until_running(pause_event, cancel_event):
                return None
            alternative = _fetch_country_with_slot(
                package_name,
                country,
                primary_language_for_country(country),
                config,
                request_slots,
                pause_event,
                cancel_event,
            )
            if alternative is None:
                return None
            result[STORE_EVIDENCE_FIELD].extend(
                _store_evidence_for_country(alternative, "metadata_completion")
            )
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
            result["notes"] = _append_note(
                result["notes"],
                f"missing_metadata_completed_from_fallback_market:{country}/{alternative.get('language', '')}",
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
            if not _wait_until_running(pause_event, cancel_event):
                return None
            batch = markets[start : start + batch_size]
            futures = [
                (
                    country,
                    fallback_executor.submit(
                        _fetch_country_with_slot,
                        package_name,
                        country,
                        primary_language_for_country(country),
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
                result[STORE_EVIDENCE_FIELD].extend(
                    _store_evidence_for_country(alternative, "regional_fallback")
                )
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
                    result["notes"] = _append_note(
                        result["notes"],
                        f"{note}; fallback_locale:{country}/{alternative.get('language', '')}",
                    )
                    return result
                if alt_status != "not_found_or_unavailable":
                    failed.append(f"{country}:{alt_status or 'unknown'}")

        checked_text = ",".join(checked)
        if not checked:
            result["play_status"] = "multi_country_check_inconclusive"
            result["notes"] = _append_note(result["notes"], "no_fallback_countries_configured")
        elif primary_status == "not_found_or_unavailable" and not failed:
            result["play_status"] = "not_found_in_checked_countries"
            result["notes"] = _append_note(
                result["notes"],
                f"selected_country_unavailable:{selected}; also_not_found_in:{checked_text}; "
                "likely_removed_or_region_restricted",
            )
        else:
            result["play_status"] = "multi_country_check_inconclusive"
            result["notes"] = _append_note(
                result["notes"],
                f"primary_country_status:{primary_status or 'unknown'}; "
                f"multi_country_checked:{checked_text}; check_errors:{','.join(failed)}",
            )
        return result
    finally:
        if fallback_started and fallback_progress_callback is not None:
            fallback_progress_callback("finish")


def audit_apps(
    apps: list[dict[str, str]],
    config: AuditConfig,
    progress_callback: ProgressCallback | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    """Canonical bounded Store audit used by the desktop application."""
    worker_limit = max(1, int(config.max_workers))
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
            if not _wait_until_running(pause_event, cancel_event):
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
                        "store_url": f"{core.PLAY_URL}?id={app['package_name']}",
                        "store_country": str(config.country or "").lower(),
                        "store_language": resolve_store_language(config.language, config.country),
                        "notes": str(exc)[:500],
                        STORE_EVIDENCE_FIELD: [],
                    }
                app_completed(app["package_name"])

    return [row for row in results if row is not None]


class PlayStoreService:
    """Stable service boundary between UI code and Google Play retrieval."""

    def load_packages(self, path: str) -> list[dict[str, str]]:
        return load_apps(path)

    def fetch_one(self, app_name: str, package_name: str, config: AuditConfig) -> dict[str, Any]:
        rows = audit_apps([{"app_name": app_name, "package_name": package_name}], config)
        return rows[0]

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback: ProgressCallback | None = None,
        pause_event=None,
        cancel_event=None,
    ) -> list[dict[str, Any]]:
        return audit_apps(
            apps,
            config,
            progress_callback,
            pause_event=pause_event,
            cancel_event=cancel_event,
        )


def install_play_store_service() -> bool:
    """Route the legacy v8 adapter through the canonical Store service."""
    from playstore_app_audit.services import device_metadata

    if bool(getattr(device_metadata, "_canonical_play_store_service_installed", False)):
        return True
    service = PlayStoreService()
    device_metadata.audit_apps_v8 = service.audit
    device_metadata._canonical_play_store_service = service
    device_metadata._canonical_play_store_service_installed = True
    return True
