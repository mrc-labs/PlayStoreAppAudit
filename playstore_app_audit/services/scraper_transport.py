from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from playstore_app_audit.services.audit_engine import AuditConfig

SCRAPER_TIMEOUT_SECONDS = AuditConfig().timeout_seconds
_INSTALLED_MARKER = "_playstore_app_audit_timeout_installed"


def _with_default_timeout(urlopen: Callable[..., Any], timeout_seconds: float) -> Callable[..., Any]:
    """Return a urlopen-compatible callable with a bounded default timeout."""

    @wraps(urlopen)
    def timed_urlopen(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", timeout_seconds)
        return urlopen(*args, **kwargs)

    return timed_urlopen


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
    except ImportError:
        return False

    if bool(getattr(request_utils, _INSTALLED_MARKER, False)):
        return True

    request_utils.urlopen = _with_default_timeout(
        request_utils.urlopen,
        float(SCRAPER_TIMEOUT_SECONDS),
    )
    setattr(request_utils, _INSTALLED_MARKER, True)
    return True
