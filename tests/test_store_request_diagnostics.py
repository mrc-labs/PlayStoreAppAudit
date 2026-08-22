from __future__ import annotations

from dataclasses import dataclass

import playstore_app_audit.services.audit_engine as audit_engine
import playstore_app_audit.services.play_store as play_store
import playstore_app_audit.ui.details_panel as details_ui
from playstore_app_audit.services.audit_engine import AuditConfig


@dataclass
class _Response:
    status_code: int
    text: str = ""
    url: str = "https://play.google.com/store/apps/details?id=com.example.app"


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = iter(responses)

    def get(self, *_args, **_kwargs) -> _Response:
        return next(self._responses)


def test_html_request_reports_actual_retry_count(monkeypatch) -> None:
    sleeps: list[float] = []
    session = _Session([_Response(503), _Response(404)])
    monkeypatch.setattr(audit_engine, "_get_session", lambda _language: session)
    monkeypatch.setattr(audit_engine.time, "sleep", sleeps.append)

    result = audit_engine._html_request(
        "com.example.app",
        "it",
        "ch",
        AuditConfig(max_retries=2, retry_sleep_base=0.5),
    )

    assert result["status"] == "not_found_or_unavailable"
    assert result["attempts"] == 2
    assert result["retry_count"] == 1
    assert sleeps == [0.5]


def test_transient_locale_diagnostics_combine_scraper_and_html_retries(monkeypatch) -> None:
    monkeypatch.setattr(
        play_store,
        "scraper_request",
        lambda *_args, **_kwargs: {
            "ok": False,
            "not_found": False,
            "title": "",
            "updated": "",
            "version": "",
            "error": "temporary scraper failure",
            "attempts": 3,
            "retry_count": 2,
        },
    )
    monkeypatch.setattr(
        play_store.core,
        "_html_request",
        lambda *_args, **_kwargs: {
            "ok": False,
            "status": "request_error",
            "http_status": "",
            "title": "",
            "updated": "",
            "url": "https://example.invalid",
            "error": "timeout",
            "attempts": 2,
            "retry_count": 1,
        },
    )

    result = play_store.fetch_locale(
        "com.example.app", "it", "ch", AuditConfig(country="ch", language="it")
    )

    assert result["outcome"] == "transient_inconclusive"
    assert result["request_path"] == "google_play_scraper -> html"
    assert result["retry_count"] == 3
    assert result["scraper_attempts"] == 3
    assert result["html_attempts"] == 2
    assert "temporary scraper failure" in result["failure_reason"]
    assert "timeout" in result["failure_reason"]


def test_terminal_not_found_is_structured_without_parsing_notes(monkeypatch) -> None:
    monkeypatch.setattr(
        play_store,
        "scraper_request",
        lambda *_args, **_kwargs: {
            "ok": False,
            "not_found": True,
            "title": "",
            "updated": "",
            "version": "",
            "error": "missing",
            "attempts": 1,
            "retry_count": 0,
        },
    )
    monkeypatch.setattr(
        play_store.core,
        "_html_request",
        lambda *_args, **_kwargs: {
            "ok": False,
            "status": "not_found_or_unavailable",
            "http_status": 404,
            "title": "",
            "updated": "",
            "url": "https://example.invalid",
            "error": "404",
            "attempts": 1,
            "retry_count": 0,
        },
    )

    result = play_store.fetch_locale(
        "com.example.missing", "it", "ch", AuditConfig(country="ch", language="it")
    )

    assert result["status"] == "not_found_or_unavailable"
    assert result["outcome"] == "terminal_not_found"
    assert result["scraper_result"] == "not_found"
    assert result["html_result"] == "not_found_or_unavailable"


def test_country_evidence_retains_request_diagnostics() -> None:
    def fake_fetch(_package: str, language: str, country: str, _config: AuditConfig):
        return {
            "status": "request_error",
            "http_status": "",
            "title": "",
            "updated": "",
            "version": "",
            "source": "",
            "url": "https://example.invalid",
            "notes": "display text that diagnostics must not parse",
            "language": language,
            "country": country,
            "request_path": "google_play_scraper -> html",
            "retry_count": 2,
            "scraper_attempts": 2,
            "html_attempts": 2,
            "scraper_result": "failed",
            "html_result": "request_error",
            "outcome": "transient_inconclusive",
            "failure_reason": "html: timeout",
        }

    result = play_store._fetch_country(
        "com.example.app",
        "ch",
        "en",
        AuditConfig(country="ch", language="en"),
        fake_fetch,
    )
    evidence = result[play_store._COUNTRY_LOCALE_EVIDENCE_FIELD]

    assert len(evidence) == 1
    assert evidence[0]["retry_count"] == 2
    assert evidence[0]["outcome"] == "transient_inconclusive"
    assert evidence[0]["failure_reason"] == "html: timeout"


def test_details_diagnostics_summarise_structured_evidence_only() -> None:
    row = {
        "play_status": "multi_country_check_inconclusive",
        "notes": "fake note saying retries:999 and country:ZZ must be ignored",
        details_ui.STORE_EVIDENCE_FIELD: [
            {
                "role": "primary",
                "country": "ch",
                "language": "it",
                "status": "request_error",
                "request_path": "google_play_scraper -> html",
                "retry_count": 2,
                "outcome": "transient_inconclusive",
                "failure_reason": "html: timeout",
            },
            {
                "role": "regional_fallback",
                "country": "de",
                "language": "de",
                "status": "not_found_or_unavailable",
                "request_path": "google_play_scraper -> html",
                "retry_count": 0,
                "outcome": "terminal_not_found",
                "failure_reason": "html: 404",
            },
        ],
    }

    lines = details_ui.store_diagnostic_lines(row)
    text = "\n".join(lines)

    assert "Transient/inconclusive Store verification" in text
    assert "Countries tried: CH → DE" in text
    assert "Languages tried: it, de" in text
    assert "Locale requests: 2 • total retries: 2" in text
    assert "HTML confirmation/fallback: 2" in text
    assert "html: timeout" in text
    assert "html: 404" in text
    assert "999" not in text
    assert "ZZ" not in text
