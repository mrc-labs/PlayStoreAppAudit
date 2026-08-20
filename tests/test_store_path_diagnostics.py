from __future__ import annotations

from types import SimpleNamespace

import pytest

import playstore_app_audit.services.store_path_diagnostics as diagnostics


def test_path_event_splits_html_and_approx_scraper_time() -> None:
    html_stats = {
        "primary": {
            "calls": 2,
            "sum_s": 3.0,
            "max_s": 2.0,
            "statuses": {"available": 1, "not_found_or_unavailable": 1},
        },
        "fallback": {
            "calls": 1,
            "sum_s": 4.0,
            "max_s": 4.0,
            "statuses": {"not_found_or_unavailable": 1},
        },
    }
    locale_stats = {
        "primary": {"calls": 4, "sum_s": 10.0, "max_s": 4.0, "statuses": {}},
        "fallback": {"calls": 2, "sum_s": 6.0, "max_s": 4.0, "statuses": {}},
    }

    event = diagnostics._format_path_event(html_stats, locale_stats)

    assert event == (
        "audit_store_path_performance "
        "primary_html_calls=2 primary_html_sum_s=3.000 primary_html_max_s=2.000 "
        "primary_html_share_pct=30.0 primary_approx_scraper_sum_s=7.000 "
        "primary_html_statuses=available:1,not_found_or_unavailable:1 "
        "fallback_html_calls=1 fallback_html_sum_s=4.000 fallback_html_max_s=4.000 "
        "fallback_html_share_pct=66.7 fallback_approx_scraper_sum_s=2.000 "
        "fallback_html_statuses=not_found_or_unavailable:1"
    )
    assert "package" not in event.casefold()


def test_scraper_stats_capture_attempts_retries_and_sleep() -> None:
    diagnostics._reset_scraper_stats()
    diagnostics._record_scraper_locale_start("primary")
    diagnostics._record_scraper_attempt("primary", 1, 1.2, "AppNotFound")
    diagnostics._record_scraper_attempt("primary", 2, 0.8, "")
    diagnostics._finish_scraper_locale(
        "primary",
        attempts=2,
        succeeded=True,
        config=SimpleNamespace(retry_sleep_base=1.0),
    )

    stats = diagnostics._snapshot_scraper_stats()["primary"]

    assert stats["locales"] == 1
    assert stats["attempts"] == 2
    assert stats["retries"] == 1
    assert stats["successes"] == 1
    assert stats["exhausted"] == 0
    assert stats["sum_s"] == pytest.approx(2.0)
    assert stats["retry_sleep_s"] == pytest.approx(1.0)
    assert stats["success_attempts"] == {"2": 1}
    assert stats["exceptions"] == {"AppNotFound": 1}


def test_scraper_event_reports_effective_fallback_markets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        diagnostics.device_metadata,
        "get_fallback_countries",
        lambda _selected: ("us", "gb", "de"),
    )
    stats = {
        "primary": {
            "locales": 2,
            "attempts": 3,
            "retries": 1,
            "successes": 1,
            "exhausted": 1,
            "sum_s": 6.0,
            "max_s": 3.0,
            "retry_sleep_s": 1.0,
            "success_attempts": {"1": 1},
            "exceptions": {"AppNotFound": 2},
        },
        "fallback": diagnostics._empty_scraper_stats(),
    }
    config = SimpleNamespace(country="it", max_retries=2, retry_sleep_base=1.0)

    event = diagnostics._format_scraper_event(config, stats)

    assert "selected_country=it" in event
    assert "fallback_markets_count=3 fallback_markets=us,gb,de" in event
    assert "primary_scraper_locales=2 primary_scraper_attempts=3" in event
    assert "primary_scraper_retries=1" in event
    assert "primary_scraper_exhausted=1" in event
    assert "primary_scraper_exceptions=AppNotFound:2" in event
    assert "package" not in event.casefold()


def test_diagnostic_stats_reset_between_audits() -> None:
    diagnostics._reset_html_stats()
    diagnostics._record_html_call("primary", 1.5, "available")
    assert diagnostics._snapshot_html_stats()["primary"]["calls"] == 1

    diagnostics._reset_html_stats()
    html_snapshot = diagnostics._snapshot_html_stats()
    assert html_snapshot["primary"]["calls"] == 0
    assert html_snapshot["fallback"]["statuses"] == {}

    diagnostics._reset_scraper_stats()
    diagnostics._record_scraper_locale_start("fallback")
    assert diagnostics._snapshot_scraper_stats()["fallback"]["locales"] == 1

    diagnostics._reset_scraper_stats()
    scraper_snapshot = diagnostics._snapshot_scraper_stats()
    assert scraper_snapshot["primary"]["attempts"] == 0
    assert scraper_snapshot["fallback"]["exceptions"] == {}
