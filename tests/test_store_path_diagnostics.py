from __future__ import annotations

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


def test_html_stats_reset_between_audits() -> None:
    diagnostics._reset_html_stats()
    diagnostics._record_html_call("primary", 1.5, "available")
    assert diagnostics._snapshot_html_stats()["primary"]["calls"] == 1

    diagnostics._reset_html_stats()
    snapshot = diagnostics._snapshot_html_stats()

    assert snapshot["primary"]["calls"] == 0
    assert snapshot["fallback"]["calls"] == 0
    assert snapshot["primary"]["statuses"] == {}
    assert snapshot["fallback"]["statuses"] == {}
