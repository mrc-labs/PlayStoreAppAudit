from __future__ import annotations

from types import SimpleNamespace

import playstore_app_audit.services.performance_diagnostics as diagnostics


def test_locale_role_distinguishes_selected_market_from_fallback() -> None:
    config = SimpleNamespace(country="ch", language="de")

    assert diagnostics._locale_role("CH", "DE", config) == "primary"
    assert diagnostics._locale_role("us", "en", config) == "fallback"
    assert diagnostics._locale_role("ch", "en", config) == "fallback"


def test_store_event_reports_aggregate_timings_without_package_names() -> None:
    diagnostics._reset_store_stats()
    diagnostics._record_locale_call("primary", 1.25, "available")
    diagnostics._record_locale_call("primary", 0.75, "not_found_or_unavailable")
    diagnostics._record_locale_call("fallback", 2.5, "available")
    diagnostics._record_locale_call("fallback", 3.0, "not_found_or_unavailable")

    event = diagnostics._format_store_event(
        "success", 4.25, diagnostics._snapshot_store_stats()
    )

    assert event == (
        "audit_store_performance result=success store_wall_s=4.250 "
        "primary_calls=2 primary_sum_s=2.000 primary_max_s=1.250 "
        "fallback_calls=2 fallback_sum_s=5.500 fallback_max_s=3.000 "
        "primary_statuses=available:1,not_found_or_unavailable:1 "
        "fallback_statuses=available:1,not_found_or_unavailable:1"
    )
    assert "package" not in event.casefold()


def test_store_stats_reset_between_audits() -> None:
    diagnostics._reset_store_stats()
    diagnostics._record_locale_call("fallback", 7.0, "available")
    assert diagnostics._snapshot_store_stats()["fallback"]["calls"] == 1

    diagnostics._reset_store_stats()
    snapshot = diagnostics._snapshot_store_stats()

    assert snapshot["primary"]["calls"] == 0
    assert snapshot["fallback"]["calls"] == 0
    assert snapshot["primary"]["statuses"] == {}
    assert snapshot["fallback"]["statuses"] == {}
