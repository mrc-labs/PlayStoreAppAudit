from __future__ import annotations

import google_play_scraper
from google_play_scraper.exceptions import NotFoundError

import playstore_app_audit.services.play_store as play_store
from playstore_app_audit.services.audit_engine import AuditConfig


def _result(
    status: str,
    *,
    language: str,
    country: str = "ch",
    title: str = "",
    updated: str = "",
    version: str = "",
) -> dict[str, object]:
    return {
        "status": status,
        "http_status": 200 if status == "available" else 404,
        "title": title,
        "updated": updated,
        "version": version,
        "source": "test" if status == "available" else "",
        "url": f"https://example.invalid/{country}/{language}",
        "notes": "",
        "language": language,
        "country": country,
    }


def test_not_found_is_terminal_in_canonical_scraper_policy(monkeypatch) -> None:
    attempts = 0
    waits: list[float] = []

    class RetryWait:
        def wait(self, timeout: float) -> bool:
            waits.append(timeout)
            return False

    def missing_app(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise NotFoundError("missing")

    monkeypatch.setattr(google_play_scraper, "app", missing_app)
    monkeypatch.setattr(play_store.threading, "Event", RetryWait)

    result = play_store.scraper_request(
        "com.example.missing",
        "it",
        "it",
        AuditConfig(max_retries=2, retry_sleep_base=1.0),
    )

    assert result["ok"] is False
    assert result["not_found"] is True
    assert attempts == 1
    assert waits == []


def test_transient_scraper_failure_retries_in_canonical_policy(monkeypatch) -> None:
    attempts = 0
    waits: list[float] = []

    class RetryWait:
        def wait(self, timeout: float) -> bool:
            waits.append(timeout)
            return False

    def transient_then_success(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary")
        return {"title": "Example", "updated": 1_700_000_000, "version": "1.2.3"}

    monkeypatch.setattr(google_play_scraper, "app", transient_then_success)
    monkeypatch.setattr(play_store.threading, "Event", RetryWait)

    result = play_store.scraper_request(
        "com.example.available",
        "it",
        "it",
        AuditConfig(max_retries=2, retry_sleep_base=1.0),
    )

    assert result["ok"] is True
    assert result["version"] == "1.2.3"
    assert attempts == 2
    assert waits == [1.0]


def test_english_fallback_completes_metadata_without_replacing_localised_title() -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetch(_package: str, language: str, country: str, _config: AuditConfig):
        calls.append((country, language))
        if language == "it":
            return _result(
                "available",
                language="it",
                country=country,
                title="Titolo italiano",
            )
        return _result(
            "available",
            language="en",
            country=country,
            title="English title",
            updated="2026-08-01",
            version="2.0",
        )

    result = play_store._fetch_country(
        "com.example.app",
        "ch",
        "it",
        AuditConfig(country="ch", language="it"),
        fake_fetch,
    )

    assert calls == [("ch", "it"), ("ch", "en")]
    assert result["title"] == "Titolo italiano"
    assert result["updated"] == "2026-08-01"
    assert result["version"] == "2.0"
    assert "language_fallback_checked:en" in str(result["notes"])


def test_conclusive_not_found_does_not_repeat_same_country_in_english() -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetch(_package: str, language: str, country: str, _config: AuditConfig):
        calls.append((country, language))
        return _result("not_found_or_unavailable", language=language, country=country)

    result = play_store._fetch_country(
        "com.example.missing",
        "it",
        "it",
        AuditConfig(country="it", language="it"),
        fake_fetch,
    )

    assert result["status"] == "not_found_or_unavailable"
    assert calls == [("it", "it")]


def test_inconclusive_localised_request_can_be_confirmed_in_english() -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetch(_package: str, language: str, country: str, _config: AuditConfig):
        calls.append((country, language))
        if language == "de":
            return _result("request_error", language=language, country=country)
        return _result(
            "available",
            language="en",
            country=country,
            title="Example",
            updated="2026-08-01",
            version="1.0",
        )

    result = play_store._fetch_country(
        "com.example.app",
        "ch",
        "de",
        AuditConfig(country="ch", language="de"),
        fake_fetch,
    )

    assert result["status"] == "available"
    assert calls == [("ch", "de"), ("ch", "en")]
    assert "preferred_language_failed:de:request_error" in str(result["notes"])
