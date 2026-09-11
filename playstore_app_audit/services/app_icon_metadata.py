from __future__ import annotations

import logging
import threading
from typing import Any

import playstore_app_audit.services.state as state

logger = logging.getLogger(__name__)

DEFAULT_SHOW_APP_ICONS = True
ICON_ELIGIBLE_STATUSES = {
    "available",
    "available_in_other_country",
    "available_in_fallback_locale_only",
}

# Keep the preference default available before any window loads settings.
state.DEFAULT_SETTINGS.setdefault("show_app_icons", DEFAULT_SHOW_APP_ICONS)

_LOCK = threading.Lock()
_ICON_URLS: dict[str, str] = {}
_DEVELOPERS: dict[str, str] = {}
_INSTALLED = False


def _normalise_https_url(value: object) -> str:
    text = str(value or "").strip()
    return text if text.lower().startswith("https://") else ""


def _remember_result_metadata(result: object, package_hint: object = "") -> None:
    if not isinstance(result, dict):
        return
    package_name = str(result.get("appId") or package_hint or "").strip()
    if not package_name:
        return
    icon_url = _normalise_https_url(result.get("icon"))
    developer = str(result.get("developer") or "").strip()
    with _LOCK:
        if icon_url:
            _ICON_URLS[package_name] = icon_url
        if developer:
            _DEVELOPERS[package_name] = developer


def _remember_result_icon(result: object, package_hint: object = "") -> None:
    """Backward-compatible test/helper name for Store response capture."""
    _remember_result_metadata(result, package_hint)


def icon_url_for_package(package_name: object) -> str:
    key = str(package_name or "").strip()
    if not key:
        return ""
    with _LOCK:
        return _ICON_URLS.get(key, "")


def developer_for_package(package_name: object) -> str:
    key = str(package_name or "").strip()
    if not key:
        return ""
    with _LOCK:
        return _DEVELOPERS.get(key, "")


def enrich_rows_with_store_metadata(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach Store metadata captured from normal scraper calls before cache persistence."""
    for row in rows:
        if str(row.get("play_status") or "") not in ICON_ELIGIBLE_STATUSES:
            continue
        package_name = row.get("package_name")
        if not _normalise_https_url(row.get("play_icon_url")):
            icon_url = icon_url_for_package(package_name)
            if icon_url:
                row["play_icon_url"] = icon_url
        if not str(row.get("developer") or "").strip():
            developer = developer_for_package(package_name)
            if developer:
                row["developer"] = developer
    return rows


def _enrich_rows_with_icon_urls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backward-compatible helper retained for existing callers/tests."""
    return enrich_rows_with_store_metadata(rows)


def clear_icon_metadata() -> None:
    with _LOCK:
        _ICON_URLS.clear()
        _DEVELOPERS.clear()


def fetch_store_metadata(
    package_name: str,
    country: str,
    language: str,
    *,
    cancel_event: threading.Event | None = None,
) -> dict[str, str]:
    """Complete icon/developer metadata through the canonical Store boundary."""

    package = str(package_name or "").strip()
    if not package or (cancel_event is not None and cancel_event.is_set()):
        return {}

    from playstore_app_audit.services.scraper_transport import (
        install_scraper_transport_timeout,
    )
    from playstore_app_audit.services.store_locale import resolve_store_language

    market = str(country or "us").strip().lower() or "us"
    locale = resolve_store_language(language, market)
    try:
        if not install_scraper_transport_timeout():
            raise RuntimeError("bounded Store transport unavailable")
        from google_play_scraper import app as play_app

        store_result = play_app(package, lang=locale, country=market)
    except Exception as exc:
        logger.debug(
            "Store icon metadata backfill failed: package=%s reason=%s",
            package,
            " ".join(str(exc).split())[:300] or type(exc).__name__,
        )
        return {}
    if cancel_event is not None and cancel_event.is_set():
        return {}
    icon_url = _normalise_https_url(store_result.get("icon"))
    developer = str(store_result.get("developer") or "").strip()
    if not icon_url and not developer:
        logger.debug(
            "Store icon metadata backfill failed: package=%s reason=metadata-missing", package
        )
        return {}
    logger.debug(
        "Store icon metadata backfill succeeded: package=%s icon=%s developer=%s",
        package,
        bool(icon_url),
        bool(developer),
    )
    result: dict[str, str] = {}
    if icon_url:
        result["play_icon_url"] = icon_url
    if developer:
        result["developer"] = developer
    return result


def install_app_icon_metadata_capture() -> bool:
    """Capture reusable metadata from normal scraper calls without extra Store requests.

    The optional icon UI is enabled by default. Icon URL and developer are
    captured from Store responses already needed by the audit. Eligible live rows
    receive the metadata before the normal healthy-result cache write, so cached
    audits can reuse it after restart.
    """
    global _INSTALLED
    if _INSTALLED:
        return True

    try:
        import google_play_scraper
    except ImportError:
        return False

    import playstore_app_audit.services.device_metadata as device_metadata

    original_app = google_play_scraper.app
    original_audit_apps = device_metadata.audit_apps_v8

    def app_with_icon_capture(*args: Any, **kwargs: Any) -> Any:
        result = original_app(*args, **kwargs)
        package_hint = args[0] if args else kwargs.get("app_id", "")
        _remember_result_metadata(result, package_hint)
        return result

    def audit_apps_with_icon_metadata(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = original_audit_apps(*args, **kwargs)
        return enrich_rows_with_store_metadata(rows)

    google_play_scraper.app = app_with_icon_capture
    device_metadata.audit_apps_v8 = audit_apps_with_icon_metadata
    _INSTALLED = True
    return True
