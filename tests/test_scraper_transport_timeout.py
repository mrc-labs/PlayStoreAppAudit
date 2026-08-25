from __future__ import annotations

from typing import Any

import google_play_scraper

import playstore_app_audit.services.audit_engine as audit_engine
import playstore_app_audit.services.play_store as play_store
from playstore_app_audit.services import scraper_transport
from playstore_app_audit.services.audit_engine import AuditConfig


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


def test_real_google_play_scraper_127_structure_is_supported() -> None:
    from google_play_scraper.utils import request as request_utils

    assert scraper_transport.SUPPORTED_SCRAPER_VERSION == "1.2.7"
    assert scraper_transport._supported_request_structure(request_utils)


def test_incompatible_scraper_structure_fails_closed_to_html(monkeypatch) -> None:
    from google_play_scraper.utils import request as request_utils

    scraper_calls: list[str] = []
    html_calls: list[str] = []
    marker = scraper_transport._INSTALLED_MARKER
    monkeypatch.delattr(request_utils, marker, raising=False)
    monkeypatch.setattr(request_utils, "_urlopen", None)
    monkeypatch.setattr(
        google_play_scraper,
        "app",
        lambda package, **_kwargs: scraper_calls.append(package),
    )

    def html_request(
        package_name: str,
        _language: str,
        _country: str,
        _config: AuditConfig,
        cancel_event=None,
    ) -> dict[str, Any]:
        assert cancel_event is None
        html_calls.append(package_name)
        return {
            "ok": True,
            "status": "available",
            "http_status": 200,
            "title": "HTML result",
            "updated": "2026-08-01",
            "url": "https://play.google.com/store/apps/details?id=com.example.app",
            "error": "",
            "attempts": 1,
            "retry_count": 0,
        }

    monkeypatch.setattr(play_store.core, "_html_request", html_request)

    result = play_store.fetch_locale("com.example.app", "en", "us", AuditConfig())

    assert scraper_calls == []
    assert html_calls == ["com.example.app"]
    assert result["status"] == "available"
    assert result["source"] == "html_fallback"


def test_direct_core_scraper_path_also_fails_closed(monkeypatch) -> None:
    scraper_calls: list[str] = []
    monkeypatch.setattr(
        scraper_transport,
        "install_scraper_transport_timeout",
        lambda: False,
    )
    monkeypatch.setattr(
        google_play_scraper,
        "app",
        lambda package, **_kwargs: scraper_calls.append(package),
    )

    result = audit_engine._scraper_request(
        "com.example.app",
        "en",
        "us",
        AuditConfig(),
    )

    assert scraper_calls == []
    assert result["ok"] is False
    assert result["error"] == "bounded google-play-scraper transport unavailable"


def test_dependency_surfaces_pin_supported_scraper_version() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert '"google-play-scraper==1.2.7"' in (root / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert "google-play-scraper==1.2.7" in (root / "requirements.txt").read_text(
        encoding="utf-8"
    ).splitlines()
