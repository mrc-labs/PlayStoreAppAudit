from __future__ import annotations

from typing import Any

from playstore_app_audit.services import scraper_transport


def test_default_timeout_is_added() -> None:
    seen: list[dict[str, Any]] = []

    def fake_urlopen(*_args: Any, **kwargs: Any) -> str:
        seen.append(dict(kwargs))
        return "ok"

    wrapped = scraper_transport._with_default_timeout(fake_urlopen, 25.0)

    assert wrapped("https://example.invalid") == "ok"
    assert seen == [{"timeout": 25.0}]


def test_explicit_timeout_is_preserved() -> None:
    seen: list[dict[str, Any]] = []

    def fake_urlopen(*_args: Any, **kwargs: Any) -> str:
        seen.append(dict(kwargs))
        return "ok"

    wrapped = scraper_transport._with_default_timeout(fake_urlopen, 25.0)

    assert wrapped("https://example.invalid", timeout=3.0) == "ok"
    assert seen == [{"timeout": 3.0}]


def test_install_patches_google_play_scraper_transport_once(monkeypatch) -> None:
    from google_play_scraper.utils import request as request_utils

    calls: list[dict[str, Any]] = []

    class Response:
        def read(self) -> bytes:
            return b"ok"

    def fake_urlopen(*_args: Any, **kwargs: Any) -> Response:
        calls.append(dict(kwargs))
        return Response()

    marker = scraper_transport._INSTALLED_MARKER
    monkeypatch.delattr(request_utils, marker, raising=False)
    monkeypatch.setattr(request_utils, "urlopen", fake_urlopen)

    try:
        assert scraper_transport.install_scraper_transport_timeout() is True
        first_wrapper = request_utils.urlopen
        assert scraper_transport.install_scraper_transport_timeout() is True
        assert request_utils.urlopen is first_wrapper
        assert request_utils._urlopen("https://example.invalid") == "ok"
        assert calls == [{"timeout": float(scraper_transport.SCRAPER_TIMEOUT_SECONDS)}]
    finally:
        if hasattr(request_utils, marker):
            delattr(request_utils, marker)
