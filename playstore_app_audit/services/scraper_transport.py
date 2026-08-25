from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from importlib import metadata
from typing import Any

from playstore_app_audit.services.audit_engine import AuditConfig

SCRAPER_TIMEOUT_SECONDS = AuditConfig().timeout_seconds
SUPPORTED_SCRAPER_VERSION = "1.2.7"
_INSTALLED_MARKER = "_playstore_app_audit_timeout_installed"
_WRAPPER_MARKER = "_playstore_app_audit_timeout_wrapper"


def _with_default_timeout(urlopen: Callable[..., Any], timeout_seconds: float) -> Callable[..., Any]:
    """Return a urlopen-compatible callable with a bounded default timeout."""

    @wraps(urlopen)
    def timed_urlopen(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", timeout_seconds)
        return urlopen(*args, **kwargs)

    setattr(timed_urlopen, _WRAPPER_MARKER, True)
    return timed_urlopen


def _supported_request_structure(request_utils: Any) -> bool:
    """Validate the exact 1.2.7 call chain patched by this bounded adapter."""

    try:
        from google_play_scraper.features import app as app_feature
    except ImportError:
        return False

    urlopen = getattr(request_utils, "urlopen", None)
    internal_open = getattr(request_utils, "_urlopen", None)
    get = getattr(request_utils, "get", None)
    app = getattr(app_feature, "app", None)
    if not all(callable(value) for value in (urlopen, internal_open, get, app)):
        return False
    return bool(
        internal_open.__globals__.get("urlopen") is urlopen
        and get.__globals__.get("_urlopen") is internal_open
        and app.__globals__.get("get") is get
    )


def install_scraper_transport_timeout() -> bool:
    """Bound google-play-scraper network calls without changing result semantics.

    google-play-scraper currently calls urllib.request.urlopen without an explicit
    timeout. A stalled socket can therefore keep an audit worker occupied for an
    unbounded period. The wrapper keeps the package's existing request flow and
    exception behaviour, while applying the same 25-second default used by the
    HTML fallback. Timeout/network exceptions still flow through the existing
    transient retry policy and HTML confirmation path, so they are never treated
    as Store not-found evidence by this transport layer.
    """
    try:
        from google_play_scraper.utils import request as request_utils
        installed_version = metadata.version("google-play-scraper")
    except (ImportError, metadata.PackageNotFoundError):
        return False

    if installed_version != SUPPORTED_SCRAPER_VERSION:
        return False

    installed_wrapper = getattr(request_utils, _INSTALLED_MARKER, None)
    if installed_wrapper is not None:
        return bool(
            installed_wrapper is getattr(request_utils, "urlopen", None)
            and getattr(installed_wrapper, _WRAPPER_MARKER, False)
            and _supported_request_structure(request_utils)
        )

    if not _supported_request_structure(request_utils):
        return False

    wrapper = _with_default_timeout(
        request_utils.urlopen,
        float(SCRAPER_TIMEOUT_SECONDS),
    )
    request_utils.urlopen = wrapper
    setattr(request_utils, _INSTALLED_MARKER, wrapper)
    return _supported_request_structure(request_utils)
