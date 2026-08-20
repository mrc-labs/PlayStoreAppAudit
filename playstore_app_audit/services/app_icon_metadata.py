from __future__ import annotations

import threading
from typing import Any

import playstore_app_audit.services.state as state

DEFAULT_SHOW_APP_ICONS = False

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


def clear_icon_metadata() -> None:
    with _LOCK:
        _ICON_URLS.clear()


def install_app_icon_metadata_capture() -> bool:
    """Capture icon URLs from normal scraper calls without adding Store requests.

    The experimental icon UI remains opt-in. Capturing the URL itself is cheap
    and session-only, and lets users enable icons after an audit without rerunning
    Store checks. Image bytes are handled separately by the UI and are never
    persisted by this module.
    """
    global _INSTALLED
    if _INSTALLED:
        return True

    try:
        import google_play_scraper
    except ImportError:
        return False

    original_app = google_play_scraper.app

    def app_with_icon_capture(*args: Any, **kwargs: Any) -> Any:
        result = original_app(*args, **kwargs)
        package_hint = args[0] if args else kwargs.get("app_id", "")
        _remember_result_icon(result, package_hint)
        return result

    google_play_scraper.app = app_with_icon_capture
    _INSTALLED = True
    return True
