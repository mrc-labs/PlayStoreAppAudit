from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

import playstore_app_audit.services.play_store as play_store


def _locale_result(status: str, country: str) -> dict[str, object]:
    return {
        "status": status,
        "http_status": 200 if status == "available" else 404,
        "title": f"Title {country}" if status == "available" else "",
        "updated": "2026-08-01" if status == "available" else "",
        "version": "1.0" if status == "available" else "",
        "source": "test" if status == "available" else "",
        "url": f"https://example.invalid/{country}",
        "notes": "",
        "language": "en",
        "country": country,
    }


def test_negative_fallback_batches_preserve_configured_market_priority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(country="ch", language="de", max_workers=4)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ("us", "gb", "de"))
    de_started = threading.Event()

    def fake_fetch(_package: str, _language: str, country: str, _config: object):
        if country == "ch":
            return _locale_result("not_found_or_unavailable", country)
        if country == "us":
            return _locale_result("not_found_or_unavailable", country)
        if country == "de":
            de_started.set()
            return _locale_result("available", country)
        if country == "gb":
            assert de_started.wait(1.0)
            return _locale_result("available", country)
        raise AssertionError(country)

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)

    with ThreadPoolExecutor(max_workers=4) as fallback_executor:
        row = play_store._fetch_app_bounded(
            "Example",
            "com.example.app",
            config,
            threading.Semaphore(4),
            fallback_executor,
        )

    assert row is not None
    assert row["play_status"] == "available_in_other_country"
    assert row["play_title"] == "Title gb"
    assert "available_in:gb" in str(row["notes"])
    assert "multi_country_checked:us,gb" in str(row["notes"])


def test_negative_fallback_parallelism_stays_within_existing_worker_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(country="ch", language="de", max_workers=4)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ("us", "gb", "de"))

    lock = threading.Lock()
    active = 0
    max_active = 0
    fallback_active = 0
    max_fallback_active = 0
    calls: list[tuple[str, str]] = []

    def fake_fetch(package: str, _language: str, country: str, _config: object):
        nonlocal active, max_active, fallback_active, max_fallback_active
        is_fallback = country != "ch"
        with lock:
            active += 1
            max_active = max(max_active, active)
            if is_fallback:
                fallback_active += 1
                max_fallback_active = max(max_fallback_active, fallback_active)
            calls.append((package, country))
        time.sleep(0.02)
        with lock:
            active -= 1
            if is_fallback:
                fallback_active -= 1
        return _locale_result("not_found_or_unavailable", country)

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)

    apps = [
        {"app_name": f"App {index}", "package_name": f"com.example.app{index}"}
        for index in range(4)
    ]
    rows = play_store.audit_apps(apps, config)

    assert [row["package_name"] for row in rows] == [app["package_name"] for app in apps]
    assert all(row["play_status"] == "not_found_in_checked_countries" for row in rows)
    assert len(calls) == 16
    assert max_active <= config.max_workers
    assert max_fallback_active > 1
    assert max_fallback_active <= config.max_workers


def test_regional_verification_emits_live_progress_without_regressing_app_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(country="ch", language="de", max_workers=2)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ("us", "gb"))

    def fake_fetch(_package: str, _language: str, country: str, _config: object):
        return _locale_result("not_found_or_unavailable", country)

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)
    progress: list[tuple[int, int, str]] = []

    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        config,
        lambda done, total, text: progress.append((done, total, text)),
    )

    assert rows[0]["play_status"] == "not_found_in_checked_countries"
    regional = [item for item in progress if item[2].startswith("Verifying regional availability")]
    assert regional
    assert any("2 country checks completed" in text for _done, _total, text in regional)
    assert progress[-1] == (1, 1, "com.example.app")
    assert [done for done, _total, _text in progress] == sorted(
        done for done, _total, _text in progress
    )


def test_healthy_complete_listing_does_not_schedule_fallbacks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = SimpleNamespace(country="ch", language="de", max_workers=4)
    calls: list[str] = []

    def fake_fetch(_package: str, _language: str, country: str, _config: object):
        calls.append(country)
        return _locale_result("available", country)

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)

    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}], config
    )

    assert rows[0]["play_status"] == "available"
    assert calls == ["ch"]
