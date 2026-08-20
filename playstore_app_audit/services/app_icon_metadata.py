from __future__ import annotations

import threading
from typing import Any

import playstore_app_audit.services.state as state

DEFAULT_SHOW_APP_ICONS = False
ICON_ELIGIBLE_STATUSES = {
    "available",
    "available_in_other_country",
    "available_in_fallback_locale_only",
}

# Keep the preference default available before any window loads settings.
state.DEFAULT_SETTINGS.setdefault("show_app_icons", DEFAULT_SHOW_APP_ICONS)

_LOCK = threading.Lock()
_ICON_URLS: dict[str, str] = {}
_INSTALLED = False


def _normalise_https_url(value: object) -> str:
    text = str(value or "").strip()
    return text if text.lower().startswith("https://") else ""


def _remember_result_icon(result: object, package_hint: object = "") -> None:
    if not isinstance(result, dict):
        return
    package_name = str(result.get("appId") or package_hint or "").strip()
    icon_url = _normalise_https_url(result.get("icon"))
    if not package_name or not icon_url:
        return
    with _LOCK:
        _ICON_URLS[package_name] = icon_url


def icon_url_for_package(package_name: object) -> str:
    key = str(package_name or "").strip()
    if not key:
        return ""
    with _LOCK:
        return _ICON_URLS.get(key, "")


def _enrich_rows_with_icon_urls(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach captured icon URLs to eligible rows before normal cache persistence."""
    for row in rows:
        if str(row.get("play_status") or "") not in ICON_ELIGIBLE_STATUSES:
            continue
        if _normalise_https_url(row.get("play_icon_url")):
            continue
        icon_url = icon_url_for_package(row.get("package_name"))
        if icon_url:
            row["play_icon_url"] = icon_url
    return rows


def clear_icon_metadata() -> None:
    with _LOCK:
        _ICON_URLS.clear()


def install_app_icon_metadata_capture() -> bool:
    """Capture icon URLs from normal scraper calls without adding Store requests.

    The experimental icon UI remains opt-in. The URL is captured from Store
    responses already needed by the audit. Eligible live rows receive that URL
    before the normal healthy-result cache write, so cached audits can reuse the
    metadata after restart. Image bytes remain UI-managed and session-only.
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
        _remember_result_icon(result, package_hint)
        return result

    def audit_apps_with_icon_metadata(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        rows = original_audit_apps(*args, **kwargs)
        return _enrich_rows_with_icon_urls(rows)

    google_play_scraper.app = app_with_icon_capture
    device_metadata.audit_apps_v8 = audit_apps_with_icon_metadata
    _INSTALLED = True
    return True
