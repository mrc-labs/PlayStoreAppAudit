from __future__ import annotations

import google_play_scraper
from google_play_scraper.exceptions import NotFoundError

import playstore_app_audit.services.audit_engine as core
import playstore_app_audit.services.device_metadata as device_metadata


def test_not_found_is_terminal_scraper_error() -> None:
    assert core.is_terminal_scraper_error(NotFoundError("missing")) is True
    assert core.is_terminal_scraper_error(ConnectionError("temporary")) is False


def test_not_found_skips_scraper_retries(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def missing_app(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        raise NotFoundError("missing")

    monkeypatch.setattr(google_play_scraper, "app", missing_app)
    monkeypatch.setattr(device_metadata.time, "sleep", sleeps.append)

    result = device_metadata.core._scraper_request(
        "com.example.missing",
        "en",
        "it",
        core.AuditConfig(max_retries=2, retry_sleep_base=1.0),
    )

    assert result["ok"] is False
    assert attempts == 1
    assert sleeps == []


def test_transient_scraper_error_still_retries(monkeypatch) -> None:
    attempts = 0
    sleeps: list[float] = []

    def transient_then_success(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("temporary")
        return {
            "title": "Example",
            "updated": 1_700_000_000,
            "version": "1.2.3",
        }

    monkeypatch.setattr(google_play_scraper, "app", transient_then_success)
    monkeypatch.setattr(device_metadata.time, "sleep", sleeps.append)

    result = device_metadata.core._scraper_request(
        "com.example.available",
        "en",
        "it",
        core.AuditConfig(max_retries=2, retry_sleep_base=1.0),
    )

    assert result["ok"] is True
    assert attempts == 2
    assert sleeps == [1.0]
