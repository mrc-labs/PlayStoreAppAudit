from __future__ import annotations

import threading
from types import SimpleNamespace
from typing import Any

import google_play_scraper
import requests

import playstore_app_audit.services.play_store as play_store
from playstore_app_audit.services.audit_engine import AuditConfig


def _row(app_name: str, package_name: str) -> dict[str, Any]:
    return {
        "app_name": app_name,
        "package_name": package_name,
        "play_status": "available",
        "play_http_status": 200,
        "play_title": app_name,
        "play_last_update": "2026-08-01",
        "play_version": "1.0",
        "updated_source": "test",
        "store_url": f"https://play.google.com/store/apps/details?id={package_name}",
        "store_country": "us",
        "store_language": "en",
        "notes": "",
        play_store.STORE_EVIDENCE_FIELD: [],
    }


def test_store_stop_drains_initial_window_without_new_submission(monkeypatch) -> None:
    apps = [
        {"app_name": f"App {index}", "package_name": f"com.example.app{index}"}
        for index in range(6)
    ]
    cancel_event = threading.Event()
    initial_window_started = threading.Event()
    release_in_flight = threading.Event()
    lock = threading.Lock()
    started: list[str] = []
    completed: list[int] = []
    returned: list[list[dict[str, Any]]] = []

    def fake_fetch(
        app_name: str,
        package_name: str,
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, Any]:
        with lock:
            started.append(package_name)
            if len(started) == 2:
                initial_window_started.set()
        assert release_in_flight.wait(2.0)
        return _row(app_name, package_name)

    monkeypatch.setattr(play_store, "_fetch_app_bounded", fake_fetch)

    worker = threading.Thread(
        target=lambda: returned.append(
            play_store.audit_apps(
                apps,
                SimpleNamespace(country="us", language="en", max_workers=2),
                cancel_event=cancel_event,
                row_completed_callback=lambda index, _row: completed.append(index),
            )
        )
    )
    worker.start()
    assert initial_window_started.wait(2.0)
    cancel_event.set()
    release_in_flight.set()
    worker.join(2.0)

    assert not worker.is_alive()
    assert set(started) == {"com.example.app0", "com.example.app1"}
    assert sorted(completed) == [0, 1]
    assert [[row["package_name"] for row in rows] for rows in returned] == [
        ["com.example.app0", "com.example.app1"]
    ]


def test_store_stop_before_initial_submission_starts_no_request(monkeypatch) -> None:
    cancel_event = threading.Event()
    cancel_event.set()
    calls: list[str] = []
    monkeypatch.setattr(
        play_store,
        "_fetch_app_bounded",
        lambda _name, package, *_args, **_kwargs: calls.append(package),
    )

    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        SimpleNamespace(country="us", language="en", max_workers=1),
        cancel_event=cancel_event,
    )

    assert rows == []
    assert calls == []


def test_store_stop_unblocks_pause_without_starting_requests(monkeypatch) -> None:
    pause_event = threading.Event()
    cancel_event = threading.Event()
    wait_entered = threading.Event()
    calls: list[str] = []
    returned: list[list[dict[str, Any]]] = []
    original_wait = play_store._wait_until_running

    def observed_wait(pause, cancel) -> bool:
        wait_entered.set()
        return original_wait(pause, cancel)

    monkeypatch.setattr(play_store, "_wait_until_running", observed_wait)
    monkeypatch.setattr(
        play_store,
        "_fetch_app_bounded",
        lambda _name, package, *_args, **_kwargs: calls.append(package),
    )

    worker = threading.Thread(
        target=lambda: returned.append(
            play_store.audit_apps(
                [{"app_name": "Example", "package_name": "com.example.app"}],
                SimpleNamespace(country="us", language="en", max_workers=1),
                pause_event=pause_event,
                cancel_event=cancel_event,
            )
        )
    )
    worker.start()
    assert wait_entered.wait(2.0)
    cancel_event.set()
    pause_event.set()
    worker.join(2.0)

    assert not worker.is_alive()
    assert calls == []
    assert returned == [[]]


def test_stop_interrupts_scraper_backoff_before_next_retry(monkeypatch) -> None:
    first_attempt = threading.Event()
    cancel_event = threading.Event()
    attempts = 0
    returned: list[dict[str, Any]] = []

    def transient_failure(*_args: object, **_kwargs: object) -> None:
        nonlocal attempts
        attempts += 1
        first_attempt.set()
        raise ConnectionError("temporary")

    monkeypatch.setattr(google_play_scraper, "app", transient_failure)
    worker = threading.Thread(
        target=lambda: returned.append(
            play_store.scraper_request(
                "com.example.app",
                "en",
                "us",
                AuditConfig(max_retries=2, retry_sleep_base=30.0),
                cancel_event=cancel_event,
            )
        )
    )
    worker.start()
    assert first_attempt.wait(2.0)
    cancel_event.set()
    worker.join(2.0)

    assert not worker.is_alive()
    assert attempts == 1
    assert returned[0]["cancelled"] is True
    assert returned[0]["retry_count"] == 0


def test_stop_interrupts_html_backoff_before_next_retry(monkeypatch) -> None:
    first_attempt = threading.Event()
    cancel_event = threading.Event()
    attempts = 0
    returned: list[dict[str, Any]] = []

    class Session:
        def get(self, *_args: object, **_kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            first_attempt.set()
            raise requests.ConnectionError("temporary")

    monkeypatch.setattr(play_store.core, "_get_session", lambda _language: Session())
    worker = threading.Thread(
        target=lambda: returned.append(
            play_store.core._html_request(
                "com.example.app",
                "en",
                "us",
                AuditConfig(max_retries=2, retry_sleep_base=30.0),
                cancel_event=cancel_event,
            )
        )
    )
    worker.start()
    assert first_attempt.wait(2.0)
    cancel_event.set()
    worker.join(2.0)

    assert not worker.is_alive()
    assert attempts == 1
    assert returned[0]["status"] == "cancelled"
    assert returned[0]["retry_count"] == 0


def test_stop_after_primary_prevents_new_regional_fallback(monkeypatch) -> None:
    cancel_event = threading.Event()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ("gb", "de"))

    def fake_fetch(
        _package: str,
        language: str,
        country: str,
        _config: object,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        calls.append((country, language))
        if country == "us":
            assert cancel_event is not None
            cancel_event.set()
        return {
            "status": "not_found_or_unavailable",
            "country": country,
            "language": language,
            "http_status": 404,
            "title": "",
            "updated": "",
            "version": "",
            "source": "",
            "url": "",
            "notes": "",
        }

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)
    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        SimpleNamespace(country="us", language="en", max_workers=1),
        cancel_event=cancel_event,
    )

    assert rows == []
    assert calls == [("us", "en")]


def test_stop_after_preferred_locale_prevents_english_fallback(monkeypatch) -> None:
    cancel_event = threading.Event()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ())

    def fake_fetch(
        _package: str,
        language: str,
        country: str,
        _config: object,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        calls.append((country, language))
        assert cancel_event is not None
        cancel_event.set()
        return {
            "status": "request_error",
            "country": country,
            "language": language,
            "http_status": "",
            "title": "",
            "updated": "",
            "version": "",
            "source": "",
            "url": "",
            "notes": "temporary",
        }

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)
    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        SimpleNamespace(country="ch", language="de", max_workers=1),
        cancel_event=cancel_event,
    )

    assert rows == []
    assert calls == [("ch", "de")]


def test_stop_during_regional_request_keeps_valid_row_and_starts_no_next_batch(
    monkeypatch,
) -> None:
    cancel_event = threading.Event()
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(play_store, "FALLBACK_BATCH_SIZE", 1)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _selected: ("gb", "de"))

    def fake_fetch(
        _package: str,
        language: str,
        country: str,
        _config: object,
        cancel_event: threading.Event | None = None,
    ) -> dict[str, Any]:
        calls.append((country, language))
        available = country == "gb"
        if available:
            assert cancel_event is not None
            cancel_event.set()
        return {
            "status": "available" if available else "not_found_or_unavailable",
            "country": country,
            "language": language,
            "http_status": 200 if available else 404,
            "title": "Fallback result" if available else "",
            "updated": "2026-08-01" if available else "",
            "version": "1.0" if available else "",
            "source": "test" if available else "",
            "url": "",
            "notes": "",
        }

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)
    rows = play_store.audit_apps(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        SimpleNamespace(country="us", language="en", max_workers=1),
        cancel_event=cancel_event,
    )

    assert len(rows) == 1
    assert rows[0]["play_status"] == "available_in_other_country"
    assert calls == [("us", "en"), ("gb", "en")]
