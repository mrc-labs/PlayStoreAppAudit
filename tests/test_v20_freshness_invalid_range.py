from __future__ import annotations

from playstore_app_audit.services.store_freshness import aging_range_presentation


def test_aging_range_presentation_is_clear_for_valid_thresholds() -> None:
    text, valid = aging_range_presentation(365, 730)

    assert valid is True
    assert text == "366 to 730 days (automatic)"


def test_aging_range_presentation_marks_impossible_edit_without_mutating_values() -> None:
    text, valid = aging_range_presentation(751, 730)

    assert valid is False
    assert text == "Invalid range: Recent must be lower than Stale."
