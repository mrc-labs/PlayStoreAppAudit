from __future__ import annotations

import copy
import os

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QLabel

import playstore_app_audit.services.alternative_distribution as alternative
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.details_panel as details_ui
from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionResult,
    AlternativeDistributionState,
)
from playstore_app_audit.ui.main_window import MainWindow


def _provider_result(
    provider_id: str,
    provider_state: AlternativeDistributionState,
    *,
    provenance: str = "live",
) -> dict[str, object]:
    return AlternativeDistributionResult(
        provider_id=provider_id,
        provider_name={"fdroid_main": "F-Droid main repository", "aptoide": "Aptoide"}.get(
            provider_id, "Future provider"
        ),
        queried_package_id="org.example.app",
        state=provider_state,
        checked_at="2026-08-29T10:00:00Z",
        provenance=provenance,
    ).to_mapping()


def _row(
    *,
    play_status: str = "available",
    providers: list[dict[str, object]] | None = None,
    age_days: object = "",
    compatibility_status: str = "Modern",
    version_comparison: str = "Match",
) -> dict[str, object]:
    row: dict[str, object] = {
        "package_name": "org.example.app",
        "play_status": play_status,
        "age_days": age_days,
        "compatibility_status": compatibility_status,
        "version_comparison": version_comparison,
    }
    if providers is not None:
        row[alternative.ROW_FIELD] = providers
    return row


def _breakdown(**kwargs) -> device_insights.HealthScoreBreakdown:
    return device_insights.calculate_health_score_breakdown(_row(**kwargs))


def test_play_availability_uses_raw_non_overlapping_components() -> None:
    available = _breakdown(play_status="available")
    absent = _breakdown(play_status="not_found_in_checked_countries")

    assert available.play_availability_penalty == 0
    assert available.score == 100
    assert absent.play_availability_penalty == -60
    assert absent.alternative_distribution_recovery == 0
    assert absent.score == 40
    assert [component.key for component in absent.components].count("play_availability") == 1


@pytest.mark.parametrize(
    "play_status",
    ["available_in_other_country", "available_in_fallback_locale_only"],
)
def test_regional_and_fallback_locale_availability_remain_store_anomalies(
    play_status: str,
) -> None:
    breakdown = _breakdown(play_status=play_status)

    assert breakdown.play_availability_penalty == -20
    assert breakdown.play_availability_penalty != -60
    assert breakdown.score == 80


@pytest.mark.parametrize(
    "play_status",
    [
        "multi_country_check_inconclusive",
        "not_found_or_unavailable",
        "check_failed",
        "request_error",
        "",
    ],
)
def test_other_or_inconclusive_play_states_receive_only_the_other_penalty(
    play_status: str,
) -> None:
    breakdown = _breakdown(play_status=play_status)

    assert breakdown.play_availability_penalty == -15
    assert breakdown.score == 85


@pytest.mark.parametrize(
    ("provider_id", "recovery", "net_store_effect", "score"),
    [
        ("fdroid_main", 10, -50, 50),
        ("aptoide", 5, -55, 45),
    ],
)
def test_each_available_provider_recovers_only_definitive_play_absence(
    provider_id: str, recovery: int, net_store_effect: int, score: int
) -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        providers=[_provider_result(provider_id, AlternativeDistributionState.AVAILABLE)],
    )

    assert breakdown.alternative_distribution_recovery == recovery
    assert breakdown.play_availability_penalty + recovery == net_store_effect
    assert breakdown.score == score


def test_fdroid_and_aptoide_recovery_is_cumulative_and_currently_capped_by_mapping() -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        providers=[
            _provider_result("aptoide", AlternativeDistributionState.AVAILABLE),
            _provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE),
        ],
    )

    assert breakdown.play_availability_penalty == -60
    assert breakdown.alternative_distribution_recovery == 15
    assert breakdown.play_availability_penalty + breakdown.alternative_distribution_recovery == -45
    assert breakdown.score == 55
    assert sum(device_insights.PROVIDER_RECOVERY_POINTS.values()) == 15


@pytest.mark.parametrize(
    "provider_state",
    [
        AlternativeDistributionState.NOT_FOUND,
        AlternativeDistributionState.INCONCLUSIVE,
        AlternativeDistributionState.UNSUPPORTED,
        AlternativeDistributionState.NOT_CHECKED,
    ],
)
@pytest.mark.parametrize("provider_id", ["fdroid_main", "aptoide"])
def test_only_available_provider_evidence_recovers_points(
    provider_id: str, provider_state: AlternativeDistributionState
) -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        providers=[_provider_result(provider_id, provider_state)],
    )

    assert breakdown.alternative_distribution_recovery == 0
    assert breakdown.score == 40


@pytest.mark.parametrize("provenance", ["live", "cache"])
def test_live_and_cached_available_evidence_have_identical_scoring(provenance: str) -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        providers=[
            _provider_result(
                "fdroid_main", AlternativeDistributionState.AVAILABLE, provenance=provenance
            )
        ],
    )

    assert breakdown.alternative_distribution_recovery == 10
    assert breakdown.score == 50


def test_duplicate_and_future_provider_evidence_cannot_add_points() -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        providers=[
            _provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE),
            _provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE),
            _provider_result("future_provider", AlternativeDistributionState.AVAILABLE),
        ],
    )

    assert breakdown.alternative_distribution_recovery == 10
    assert breakdown.score == 50


@pytest.mark.parametrize("provider_ids", [("fdroid_main",), ("aptoide",), ("fdroid_main", "aptoide")])
def test_provider_presence_is_never_an_unconditional_bonus_when_play_is_available(
    provider_ids: tuple[str, ...],
) -> None:
    providers = [
        _provider_result(provider_id, AlternativeDistributionState.AVAILABLE)
        for provider_id in provider_ids
    ]
    breakdown = _breakdown(play_status="available", providers=providers)

    assert breakdown.play_availability_penalty == 0
    assert breakdown.alternative_distribution_recovery == 0
    assert breakdown.score == 100


@pytest.mark.parametrize(
    ("age_days", "penalty"),
    [(365, 0), (366, -15), (730, -15), (731, -25)],
)
def test_listing_age_ranges_are_explicit_and_non_overlapping(
    age_days: int, penalty: int
) -> None:
    breakdown = _breakdown(age_days=age_days)

    assert breakdown.listing_age_penalty == penalty
    assert breakdown.score == 100 + penalty


@pytest.mark.parametrize("age_days", [None, "", "unknown", -1])
def test_unknown_or_unusable_listing_age_does_not_manufacture_a_penalty(age_days: object) -> None:
    breakdown = _breakdown(age_days=age_days)

    assert breakdown.listing_age_penalty == 0
    assert breakdown.score == 100


@pytest.mark.parametrize(
    ("compatibility_status", "penalty"),
    [("Modern", 0), ("Unknown", 0), ("Aging target", -10), ("Legacy target", -15)],
)
def test_android_compatibility_penalties_use_canonical_labels(
    compatibility_status: str, penalty: int
) -> None:
    breakdown = _breakdown(compatibility_status=compatibility_status)

    assert breakdown.compatibility_penalty == penalty
    assert breakdown.score == 100 + penalty


@pytest.mark.parametrize(
    ("version_comparison", "penalty"),
    [
        ("Outdated", -10),
        ("Different", -5),
        ("Newer", 0),
        ("Match", 0),
        ("Unknown", 0),
        ("Device-specific", 0),
        ("", 0),
    ],
)
def test_installed_version_penalty_is_relationship_aware(
    version_comparison: str, penalty: int
) -> None:
    breakdown = _breakdown(version_comparison=version_comparison)

    assert breakdown.version_comparison_penalty == penalty
    assert breakdown.score == 100 + penalty


@pytest.mark.parametrize(
    ("relationship", "penalty"),
    [
        ("Outdated", -10),
        ("Different", -5),
        ("Unknown", -15),
        ("Device-specific", 0),
        ("Newer", 0),
        ("Match", 0),
    ],
)
def test_local_apk_version_penalty_is_source_aware(
    relationship: str, penalty: int
) -> None:
    row = _row(version_comparison="Outdated")
    row.update(
        source_mode="local_apk",
        local_apk_version_comparison=relationship,
        local_apk_version_name="" if relationship == "Unknown" else "1.0",
        play_version="2.0",
    )
    breakdown = device_insights.calculate_health_score_breakdown(row)
    assert breakdown.version_comparison_penalty == penalty
    assert [component.key for component in breakdown.components].count("local_store_version") <= 1


def test_outdated_and_aging_store_penalties_remain_independent() -> None:
    row = _row(age_days=500)
    row.update(
        source_mode="local_apk",
        local_apk_version_comparison="Outdated",
        local_apk_version_name="1.0",
        play_version="2.0",
    )

    breakdown = device_insights.calculate_health_score_breakdown(row)

    assert breakdown.version_comparison_penalty == -10
    assert breakdown.listing_age_penalty == -15
    assert breakdown.score == 75


@pytest.mark.parametrize(
    "play_status",
    [
        "not_found_in_checked_countries",
        "multi_country_check_inconclusive",
        "check_failed",
    ],
)
def test_local_unknown_from_missing_store_counterpart_has_no_version_penalty(
    play_status: str,
) -> None:
    row = _row(play_status=play_status)
    row.update(
        source_mode="local_apk",
        local_apk_version_comparison="Unknown",
        local_apk_version_name="1.0",
        play_version="",
    )

    breakdown = device_insights.calculate_health_score_breakdown(row)

    assert breakdown.version_comparison_penalty == 0
    assert all(component.key != "local_store_version" for component in breakdown.components)


def test_local_na_relationship_does_not_double_count_store_absence() -> None:
    row = _row(play_status="not_found_in_checked_countries")
    row.update(
        source_mode="local_apk",
        local_apk_version_comparison="N/A",
        local_apk_version_name="1.0",
        play_version="",
    )

    breakdown = device_insights.calculate_health_score_breakdown(row)

    assert breakdown.play_availability_penalty == -60
    assert breakdown.version_comparison_penalty == 0
    assert breakdown.score == 40
    assert all(component.key != "local_store_version" for component in breakdown.components)


def test_independent_penalties_compose_and_score_is_clamped_to_zero() -> None:
    breakdown = _breakdown(
        play_status="not_found_in_checked_countries",
        age_days=731,
        compatibility_status="Legacy target",
        version_comparison="Different",
    )

    assert breakdown.unclamped_score == -5
    assert breakdown.score == 0


def test_calculation_preserves_raw_play_installer_provider_and_cache_evidence() -> None:
    row = _row(
        play_status="not_found_in_checked_countries",
        providers=[
            _provider_result(
                "fdroid_main", AlternativeDistributionState.AVAILABLE, provenance="cache"
            )
        ],
    )
    row["installer_source"] = "Google Play"
    original = copy.deepcopy(row)

    assert device_insights.calculate_health_score(row) == 50
    assert row == original


def test_breakdown_is_visible_in_details_panel_and_html_report(tmp_path) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    row = _row(
        play_status="not_found_in_checked_countries",
        providers=[
            _provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE),
            _provider_result("aptoide", AlternativeDistributionState.AVAILABLE),
        ],
    )
    row["health_score"] = device_insights.calculate_health_score(row)
    row["criticality_key"] = "red"

    panel = details_ui.AppDetailsPanel()
    panel.set_row(row)
    target = device_insights.write_html_report(tmp_path / "report.html", [row])
    rendered = target.read_text(encoding="utf-8")

    assert "Maintenance Score: 55/100" in panel.device_label.text()
    assert "Google Play availability (not found in checked markets): -60" in panel.device_label.text()
    assert "F-Droid availability recovery: +10" in panel.device_label.text()
    assert "Aptoide availability recovery: +5" in panel.device_label.text()
    assert "55/100" in rendered
    assert "Google Play availability (not found in checked markets): -60" in rendered
    assert "F-Droid availability recovery: +10" in rendered
    assert "Aptoide availability recovery: +5" in rendered
    panel.deleteLater()
    app.processEvents()


def test_breakdown_is_visible_in_app_details_dialog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    row = _row(
        play_status="not_found_in_checked_countries",
        providers=[_provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE)],
    )
    row["health_score"] = device_insights.calculate_health_score(row)
    captured: dict[str, str] = {}

    def inspect_dialog(dialog: QDialog) -> QDialog.DialogCode:
        score = dialog.findChild(QLabel, "DetailsValue_health_score")
        breakdown = dialog.findChild(QLabel, "DetailsValue_health_score_breakdown")
        captured["score"] = score.text() if score is not None else ""
        captured["breakdown"] = breakdown.text() if breakdown is not None else ""
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", inspect_dialog)
    window = MainWindow()
    try:
        window._show_details(row)
    finally:
        window.close()
        app.processEvents()

    assert captured["score"] == "50/100"
    assert "Google Play availability (not found in checked markets): -60" in captured[
        "breakdown"
    ]
    assert "F-Droid availability recovery: +10" in captured["breakdown"]


def test_history_contract_stays_score_and_provider_independent() -> None:
    row = _row(
        play_status="not_found_in_checked_countries",
        providers=[_provider_result("fdroid_main", AlternativeDistributionState.AVAILABLE)],
    )
    row.update(
        {
            "health_score": 50,
            "criticality_key": "red",
            "criticality_rank": 0,
            "criticality": "Removed",
        }
    )

    snapshot = state._history_snapshot(row, "2026-08-29T10:00:00Z")
    document = result_json.build_results_document([{**row, "health_score": 37}])

    assert "health_score" not in snapshot
    assert alternative.ROW_FIELD not in snapshot
    assert document["results"][0]["health_score"] == 37


def test_stored_score_from_another_calculation_is_not_given_a_recomputed_breakdown() -> None:
    row = _row(play_status="available_in_other_country")
    row["health_score"] = 85

    assert device_insights.health_score_breakdown_lines(row) == [
        "Stored audit score uses a different calculation; a current-method breakdown is not shown."
    ]
