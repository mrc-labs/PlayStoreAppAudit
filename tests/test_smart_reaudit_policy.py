from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import playstore_app_audit.services.re_audit as re_audit
import playstore_app_audit.services.state as state
from playstore_app_audit.ui.device_window import DeviceWindow


@pytest.mark.parametrize(
    ("status", "updated", "expected"),
    [
        ("available", "2026-08-01", True),
        ("available", "", False),
        ("available_in_other_country", "2026-08-01", False),
        ("available_in_fallback_locale_only", "2026-08-01", False),
        ("not_found_in_checked_countries", "2026-08-01", False),
        ("multi_country_check_inconclusive", "2026-08-01", False),
        ("check_failed", "2026-08-01", False),
        ("http_error", "2026-08-01", False),
    ],
)
def test_cache_reuse_policy_is_conservative(status: str, updated: str, expected: bool) -> None:
    row = {"play_status": status, "play_last_update": updated}
    assert re_audit.cache_reuse_eligible(row) is expected


def test_persistent_cache_matches_smart_policy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)

    rows = [
        {
            "package_name": "com.example.healthy",
            "play_status": "available",
            "play_last_update": "2026-08-01",
            "play_title": "Healthy",
        },
        {
            "package_name": "com.example.regional",
            "play_status": "available_in_other_country",
            "play_last_update": "2026-08-01",
            "play_title": "Regional",
        },
        {
            "package_name": "com.example.partial",
            "play_status": "available",
            "play_last_update": "",
            "play_title": "Partial",
        },
        {
            "package_name": "com.example.failed",
            "play_status": "check_failed",
            "play_last_update": "2026-08-01",
            "play_title": "Failed",
        },
    ]
    apps = [{"package_name": row["package_name"], "app_name": row["play_title"]} for row in rows]

    state.update_cache(rows, "ch", "it")
    cached = state.load_fresh_cache(apps, "ch", "it", 72)

    assert set(cached) == {"com.example.healthy"}
    assert cached["com.example.healthy"]["cache_hit"] is True
    for row in rows:
        assert (row["package_name"] in cached) is re_audit.cache_reuse_eligible(row)


def test_zero_ttl_disables_reuse_even_for_healthy_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    row = {
        "package_name": "com.example.healthy",
        "play_status": "available",
        "play_last_update": "2026-08-01",
    }
    state.update_cache([row], "de", "de")

    assert state.load_fresh_cache(
        [{"package_name": "com.example.healthy", "app_name": "Healthy"}],
        "de",
        "de",
        0,
    ) == {}


def test_full_refresh_bypasses_cache_before_any_lookup() -> None:
    stub = SimpleNamespace(_force_refresh_next=True)
    assert DeviceWindow._load_fresh_cache(
        stub,  # type: ignore[arg-type]
        [{"package_name": "com.example.app", "app_name": "Example"}],
        "ch",
        "it",
        72,
    ) == {}


def test_policy_context_is_explicit_and_bounded() -> None:
    context = re_audit.policy_context(
        {"cache_enabled": True, "cache_ttl_hours": 9999}
    )
    assert context == {
        "policy_id": "conservative-smart-reaudit-v1",
        "mode": "smart",
        "cache_only_healthy_available": True,
        "require_update_date_for_cache": True,
        "uncertain_results_always_live": True,
        "explicit_full_refresh_available": True,
        "targeted_problem_recheck_available": True,
        "cache_enabled": True,
        "healthy_cache_ttl_hours": 720,
    }


def test_tooltip_explains_live_uncertain_checks_and_full_refresh() -> None:
    text = re_audit.smart_audit_tooltip({"cache_enabled": True, "cache_ttl_hours": 48})
    assert "48h" in text
    assert "regional-only" in text
    assert "failed checks run live" in text
    assert "Run with Fresh Store Results" in text
