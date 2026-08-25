from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait
from typing import Any

import playstore_app_audit.services.audit_engine as core
from playstore_app_audit.services.audit_engine import AuditConfig, load_apps
from playstore_app_audit.services.scraper_transport import install_scraper_transport_timeout
from playstore_app_audit.services.store_locale import (
    primary_language_for_country,
    resolve_store_language,
)

ProgressCallback = Callable[[int, int, str], None]
RowCompletedCallback = Callable[[int, dict[str, Any]], None]
FALLBACK_BATCH_SIZE = 3
STORE_EVIDENCE_FIELD = "_store_evidence"
_COUNTRY_LOCALE_EVIDENCE_FIELD = "_country_locale_evidence"

_DIAGNOSTIC_FIELDS = (
    "request_path",
    "retry_count",
    "scraper_attempts",
    "html_attempts",
    "scraper_result",
    "html_result",
    "outcome",
    "failure_reason",
)


def _wait_for_retry(cancel_event: threading.Event | None, delay_seconds: float) -> bool:
    if cancel_event is None:
        threading.Event().wait(max(0.0, float(delay_seconds)))
        return True
    return not cancel_event.wait(max(0.0, float(delay_seconds)))


def _append_note(existing: object, note: str) -> str:
    parts = [str(existing or "").strip(), str(note or "").strip()]
    return " | ".join(part for part in parts if part)


def _as_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _request_outcome(status: object, updated: object, version: object) -> str:
    value = str(status or "").strip()
    if value == "not_found_or_unavailable":
        return "terminal_not_found"
    if value in {"request_error", "http_error", "check_failed", "unexpected_error"}:
        return "transient_inconclusive"
    if value == "available" and (not updated or not version):
        return "available_metadata_partial"
    if value == "available":
        return "available"
    return "inconclusive"


def _request_diagnostics(
    scraper: dict[str, Any],
    html: dict[str, Any] | None,
    status: object,
    updated: object,
    version: object,
) -> dict[str, Any]:
    scraper_attempts = _as_non_negative_int(scraper.get("attempts"))
    scraper_retries = _as_non_negative_int(scraper.get("retry_count"))
    html_attempts = _as_non_negative_int(html.get("attempts")) if html is not None else 0
    html_retries = _as_non_negative_int(html.get("retry_count")) if html is not None else 0

    if scraper.get("ok"):
        scraper_result = "available"
    elif scraper.get("not_found"):
        scraper_result = "not_found"
    else:
        scraper_result = "failed"

    html_result = "not_used"
    if html is not None:
        html_result = str(html.get("status") or ("available" if html.get("ok") else "unknown"))

    failures: list[str] = []
    scraper_error = str(scraper.get("error") or "").strip()
    html_error = str(html.get("error") or "").strip() if html is not None else ""
    if scraper_error and not scraper.get("ok"):
        failures.append(f"scraper: {scraper_error}")
    if html_error and html_result != "available":
        failures.append(f"html: {html_error}")

    return {
        "request_path": "google_play_scraper -> html" if html is not None else "google_play_scraper",
        "retry_count": scraper_retries + html_retries,
        "scraper_attempts": scraper_attempts,
        "html_attempts": html_attempts,
        "scraper_result": scraper_result,
        "html_result": html_result,
        "outcome": _request_outcome(status, updated, version),
        "failure_reason": " | ".join(failures),
    }


def _locale_evidence(result: dict[str, Any], language_role: str) -> dict[str, Any]:
    """Return one JSON-serializable record for an actual Store locale request."""
    evidence = {
        "language_role": language_role,
        "country": str(result.get("country") or "").strip().lower(),
        "language": str(result.get("language") or "").strip().lower(),
        "status": str(result.get("status") or "unknown"),
        "http_status": result.get("http_status", ""),
        "source": str(result.get("source") or ""),
    }
    for field in _DIAGNOSTIC_FIELDS:
        value = result.get(field)
        if value not in (None, ""):
            evidence[field] = value
    return evidence


def _with_country_locale_evidence(
    result: dict[str, Any], evidence: list[dict[str, Any]]
) -> dict[str, Any]:
    enriched = dict(result)
    enriched[_COUNTRY_LOCALE_EVIDENCE_FIELD] = [dict(item) for item in evidence]
    return enriched


def _store_evidence_for_country(result: dict[str, Any], role: str) -> list[dict[str, Any]]:
    raw = result.get(_COUNTRY_LOCALE_EVIDENCE_FIELD)
    locale_entries = (
        [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    )
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
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Query google-play-scraper with terminal NotFound and transient retries."""
    if not install_scraper_transport_timeout():
        return {
            "ok": False,
            "not_found": False,
            "title": "",
            "updated": "",
            "version": "",
            "error": "bounded google-play-scraper transport unavailable",
            "attempts": 0,
            "retry_count": 0,
        }
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
            "attempts": 0,
            "retry_count": 0,
        }

    last_error = ""
    attempts = 0
    for attempt in range(config.max_retries + 1):
        if cancel_event is not None and cancel_event.is_set():
            break
        attempts = attempt + 1
        try:
            data = play_app(package_name, lang=language, country=country)
            return {
                "ok": True,
                "not_found": False,
                "title": str(data.get("title") or "").strip(),
                "updated": core.normalise_updated(data.get("updated")),
                "version": _normalise_version(data.get("version")),
                "error": "",
                "attempts": attempts,
                "retry_count": max(0, attempts - 1),
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
                "attempts": attempts,
                "retry_count": max(0, attempts - 1),
            }
        except Exception as exc:
            last_error = str(exc)[:300]
            if attempt < config.max_retries and not _wait_for_retry(
                cancel_event, config.retry_sleep_base * (attempt + 1)
            ):
                break

    return {
        "ok": False,
        "not_found": False,
        "title": "",
        "updated": "",
        "version": "",
        "error": (
            "cancelled"
            if cancel_event is not None and cancel_event.is_set()
            else (last_error or "Unknown Google Play scraper error")
        ),
        "attempts": attempts,
        "retry_count": max(0, attempts - 1),
        "cancelled": cancel_event is not None and cancel_event.is_set(),
    }


def fetch_locale(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any]:
    """Fetch one Store locale while preserving validated status semantics."""
    language = resolve_store_language(language, country)
    country = str(country or "").strip().lower()
    scraper = scraper_request(
        package_name,
        language,
        country,
        config,
        cancel_event=cancel_event,
    )

    if scraper.get("cancelled"):
        return {"status": "cancelled", "language": language, "country": country}

    if scraper["ok"] and scraper["updated"]:
        result = {
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
        result.update(
            _request_diagnostics(
                scraper,
                None,
                result["status"],
                result["updated"],
                result["version"],
            )
        )
        return result

    # HTML is still the confirmation/fallback path. A scraper NotFound never
    # becomes a removed classification on its own; the Store response remains
    # the regional evidence used by the existing status model.
    html = core._html_request(
        package_name,
        language,
        country,
        config,
        cancel_event=cancel_event,
    )
    if str(html.get("status") or "") == "cancelled":
        if scraper["ok"]:
            result = {
                "status": "available",
                "http_status": 200,
                "title": scraper["title"],
                "updated": scraper["updated"],
                "version": scraper["version"],
                "source": "google_play_scraper",
                "url": f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
                "notes": "html_fallback_cancelled",
                "language": language,
                "country": country,
            }
            result.update(
                _request_diagnostics(
                    scraper,
                    None,
                    result["status"],
                    result["updated"],
                    result["version"],
                )
            )
            return result
        return {"status": "cancelled", "language": language, "country": country}
    if scraper["ok"]:
        title = scraper["title"] or html.get("title", "")
        updated = scraper["updated"] or html.get("updated", "")
        result = {
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
        result.update(
            _request_diagnostics(
                scraper,
                html,
                result["status"],
                result["updated"],
                result["version"],
            )
        )
        return result

    result = {
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
    result.update(
        _request_diagnostics(
            scraper,
            html,
            result["status"],
            result["updated"],
            result["version"],
        )
    )
    return result


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
    if str(preferred.get("status") or "") == "cancelled":
        return preferred
    evidence = [_locale_evidence(preferred, "preferred")]
    if not _needs_english_fallback(preferred, language):
        return _with_country_locale_evidence(preferred, evidence)

    english = fetch_one(package_name, "en", country, config)
    if str(english.get("status") or "") == "cancelled":
        if str(preferred.get("status") or "") == "available":
            return _with_country_locale_evidence(preferred, evidence)
        return english
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
        if cancel_event is None:
            return fetch_locale(package_name, language, country, config)
        return fetch_locale(package_name, language, country, config, cancel_event=cancel_event)
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
    if primary is None:
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

    if cancel_event is not None and cancel_event.is_set():
        return result if primary_status == "available" else None

    if primary_status == "available":
        if result["play_last_update"] and result["play_version"]:
            return result
        for country in markets:
            if not _wait_until_running(pause_event, cancel_event):
                return result
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
            futures: list[tuple[str, Future[dict[str, Any] | None]]] = [
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

            for country, future in futures:
                try:
                    alternative = future.result()
                except CancelledError:
                    alternative = None
                if alternative is None:
                    continue

                checked.append(country)
                result[STORE_EVIDENCE_FIELD].extend(
                    _store_evidence_for_country(alternative, "regional_fallback")
                )
                if fallback_progress_callback is not None:
                    fallback_progress_callback("check")
                alt_status = str(alternative.get("status") or "")
                if alt_status == "available":
                    for later_country, later_future in futures:
                        if later_country == country:
                            continue
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

            if cancel_event is not None and cancel_event.is_set():
                return None

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
    row_completed_callback: RowCompletedCallback | None = None,
) -> list[dict[str, Any]]:
    """Run the canonical Store audit with cooperative Stop boundaries.

    Submission is limited to ``max_workers`` applications. Once cancellation is
    observed, no package, retry, country, or language request is started. A
    request that was already inside urllib/requests may still run until its
    configured per-request timeout (25 seconds by default); its conclusive row
    is retained when it remains valid independently of unfinished fallbacks.
    """
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

        with ThreadPoolExecutor(max_workers=worker_limit, thread_name_prefix="playstore-app") as executor:
            pending: dict[Future[dict[str, Any] | None], int] = {}
            next_index = 0

            def fill_submission_window() -> None:
                nonlocal next_index
                while (
                    next_index < len(apps)
                    and len(pending) < worker_limit
                    and (cancel_event is None or not cancel_event.is_set())
                ):
                    index = next_index
                    next_index += 1
                    pending[executor.submit(run_one, apps[index])] = index

            fill_submission_window()
            while pending:
                completed_futures, _not_done = wait(
                    tuple(pending), return_when=FIRST_COMPLETED
                )
                for future in sorted(completed_futures, key=lambda item: pending[item]):
                    index = pending.pop(future)
                    app = apps[index]
                    try:
                        row = future.result()
                    except CancelledError:
                        row = None
                    except Exception as exc:
                        if cancel_event is not None and cancel_event.is_set():
                            row = None
                        else:
                            row = {
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
                                "store_language": resolve_store_language(
                                    config.language, config.country
                                ),
                                "notes": str(exc)[:500],
                                STORE_EVIDENCE_FIELD: [],
                            }
                    if row is None:
                        continue
                    results[index] = row
                    if row_completed_callback is not None:
                        row_completed_callback(index, row)
                    app_completed(app["package_name"])

                if cancel_event is not None and cancel_event.is_set():
                    for future in pending:
                        future.cancel()
                else:
                    fill_submission_window()

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
        row_completed_callback: RowCompletedCallback | None = None,
    ) -> list[dict[str, Any]]:
        return audit_apps(
            apps,
            config,
            progress_callback,
            pause_event=pause_event,
            cancel_event=cancel_event,
            row_completed_callback=row_completed_callback,
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
