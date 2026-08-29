from __future__ import annotations

from playstore_app_audit.services.device_insights import (
    calculate_health_score,
    compatibility_label,
    row_matches_filter,
)
from playstore_app_audit.services.device_metadata import compare_versions, parse_country_list


def test_country_parser_deduplicates_and_accepts_uk_alias() -> None:
    valid, invalid = parse_country_list("CH, it; uk ch bad-code", selected_country="it")
    assert valid == ["ch", "gb"]
    assert invalid == ["bad-code"]


def test_version_comparison_is_conservative() -> None:
    assert compare_versions("v1.2.3", "1.2.3") == "Match"
    assert compare_versions("1.2.3", "1.2.4") == "Different"
    assert compare_versions("1.2.3", "Varies with device") == "Device-specific"
    assert compare_versions("", "1.2.3") == "Unknown"


def test_compatibility_buckets() -> None:
    assert compatibility_label(34, 35) == "Modern"
    assert compatibility_label(31, 35) == "Aging target"
    assert compatibility_label(28, 35) == "Legacy target"
    assert compatibility_label("", 35) == "Unknown"


def test_health_score_penalties_are_transparent() -> None:
    row = {
        "play_status": "available",
        "age_days": 731,
        "compatibility_status": "Legacy target",
        "version_comparison": "Different",
    }
    assert calculate_health_score(row) == 55


def test_builtin_filters() -> None:
    assert row_matches_filter({"criticality_key": "red"}, "Problems")
    assert row_matches_filter({"criticality_key": "yellow"}, "Old apps")
    assert row_matches_filter({"installer_source": "Sideload / package installer"}, "Sideloaded")
    assert row_matches_filter({"version_comparison": "Different"}, "Version mismatch")
    assert row_matches_filter({"app_enabled": "Disabled"}, "Disabled")
    assert row_matches_filter({"sensitive_permissions_count": "2"}, "Sensitive permissions")
