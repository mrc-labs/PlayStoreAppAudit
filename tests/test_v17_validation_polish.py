from __future__ import annotations

import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.ui.details_panel as details_ui


def _not_found_row() -> dict[str, object]:
    return {
        "play_status": "not_found_in_checked_countries",
        "store_country": "it",
        details_ui.STORE_EVIDENCE_FIELD: [
            {
                "role": "primary",
                "country": "it",
                "language": "en",
                "status": "not_found_or_unavailable",
                "http_status": 404,
                "request_path": "google_play_scraper -> html",
                "outcome": "terminal_not_found",
                "failure_reason": "scraper: App not found(404). | html: 404",
            },
            *[
                {
                    "role": "regional_fallback",
                    "country": country,
                    "language": language,
                    "status": "not_found_or_unavailable",
                    "http_status": 404,
                    "request_path": "google_play_scraper -> html",
                    "outcome": "terminal_not_found",
                    "failure_reason": "scraper: App not found(404). | html: 404",
                }
                for country, language in (
                    ("us", "en"),
                    ("gb", "en"),
                    ("de", "de"),
                    ("fr", "fr"),
                )
            ],
        ],
        "notes": "raw technical notes stay available to exports",
    }


def test_removed_evidence_is_concise_and_does_not_repeat_transport_details() -> None:
    row = _not_found_row()
    lines = details_ui.evidence_lines(row)

    assert lines == [
        "Primary market: IT/en • not found",
        "Fallback markets checked: US, GB, DE, FR",
        "Outcome: no listing was found in any checked market.",
    ]
    joined = " ".join(lines)
    assert "HTTP" not in joined
    assert "google_play_scraper" not in joined
    assert "terminal" not in joined


def test_removed_diagnostics_collapse_repeated_404_transport_noise() -> None:
    assert details_ui.store_diagnostic_lines(_not_found_row()) == [
        "Requests: 5 locale checks",
        "Transport: scraper + HTML confirmation/fallback",
        "HTTP: 404 on all 5 checks",
    ]


def test_friendly_notes_hide_raw_machine_tokens() -> None:
    note = details_ui.display_notes(_not_found_row())
    assert "No Google Play listing was found" in note
    assert "selected_country_unavailable" not in note
    assert "scraper:" not in note


def test_fallback_availability_summary_names_selected_and_found_markets() -> None:
    row = {
        "play_status": "available_in_other_country",
        "store_country": "it",
        details_ui.STORE_EVIDENCE_FIELD: [
            {
                "role": "primary",
                "country": "it",
                "language": "it",
                "status": "not_found_or_unavailable",
            },
            {
                "role": "regional_fallback",
                "country": "de",
                "language": "de",
                "status": "available",
            },
        ],
    }

    assert details_ui.evidence_lines(row) == [
        "Primary market: IT/it • not found",
        "Found in fallback market: DE/de",
        "Markets checked: IT, DE",
        "Outcome: availability is region-specific.",
    ]
    assert details_ui.display_notes(row) == (
        "Not available in IT, but found in DE. Google Play availability is region-specific."
    )


def test_first_audit_and_first_phone_inventory_are_distinct() -> None:
    row = {
        "change": "New",
        "device_change": "New on device",
        change_service.DEVICE_HISTORY_FLAG: False,
    }
    assert details_ui.change_lines(row) == [
        "First audit baseline for this app. Future audits can show Store changes."
    ]
    assert details_ui.device_inventory_line(row) == "Inventory history: First phone-scan baseline"


def test_previous_phone_scan_change_is_not_added_to_audit_change_lines() -> None:
    row = {
        "change": "Same",
        "device_change": "Version changed",
        change_service.DEVICE_HISTORY_FLAG: True,
    }
    assert details_ui.change_lines(row) == []
    assert details_ui.device_inventory_line(row) == (
        "Since previous phone scan: Installed version changed"
    )
