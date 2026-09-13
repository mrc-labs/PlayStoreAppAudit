from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

import playstore_app_audit.services.state as state
from playstore_app_audit.services import device_insights
from playstore_app_audit.services.store_freshness import (
    StoreFreshnessThresholds,
    from_settings,
)
from playstore_app_audit.ui import base_window, compact_window


@pytest.mark.parametrize(
    ("age", "expected"),
    [(0, "green"), (365, "green"), (366, "yellow"), (730, "yellow"), (731, "orange")],
)
def test_default_store_freshness_boundaries(age: int, expected: str) -> None:
    assert StoreFreshnessThresholds().classify_age(age) == expected


def test_custom_freshness_boundaries_and_invalid_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "app_data_dir", lambda: tmp_path)
    settings = state.save_settings(
        {"store_recent_max_days": 200, "store_stale_after_days": 500}
    )
    thresholds = from_settings(state.load_settings())
    assert settings["store_recent_max_days"] == 200
    assert thresholds.aging_range == "201 to 500 days"
    assert [thresholds.classify_age(age) for age in (200, 201, 500, 501)] == [
        "green", "yellow", "yellow", "orange"
    ]
    with pytest.raises(ValueError):
        state.save_settings({"store_recent_max_days": 500, "store_stale_after_days": 500})
    assert from_settings(state.load_settings()) == thresholds


def test_classification_and_score_share_custom_age_boundaries() -> None:
    row: dict[str, object] = {
        "play_status": "available",
        "play_last_update": (date.today() - timedelta(days=400)).isoformat(),
    }
    settings = {"store_recent_max_days": 200, "store_stale_after_days": 500}
    base_window.classify_criticality(row, settings)
    device_insights.apply_health_score(row, settings)
    assert row["criticality"] == "Aging"
    assert row["age_days"] == 400
    assert row["health_score"] == 85

    settings["store_recent_max_days"] = 450
    base_window.classify_criticality(row, settings)
    device_insights.apply_health_score(row, settings)
    assert row["criticality"] == "Recent"
    assert row["health_score"] == 100

    settings.update(store_recent_max_days=100, store_stale_after_days=300)
    base_window.classify_criticality(row, settings)
    device_insights.apply_health_score(row, settings)
    assert row["criticality"] == "Stale"
    assert row["health_score"] == 75


@pytest.mark.parametrize(
    ("play_status", "score"),
    [("available_in_other_country", 80), ("multi_country_check_inconclusive", 85)],
)
def test_visible_anomaly_preserves_raw_score_distinction(
    play_status: str, score: int
) -> None:
    row: dict[str, object] = {"play_status": play_status}
    compact_window._classify_criticality_multicountry(row)
    assert row["criticality"] == "Anomaly"
    assert row["criticality_key"] == "blue"
    assert row["play_status"] == play_status
    assert device_insights.calculate_health_score(row) == score
