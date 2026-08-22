from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.app_icon_metadata as store_metadata
import playstore_app_audit.ui.details_panel as details_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_details_panel_position_normalises_unknown_values() -> None:
    assert details_ui.normalise_details_panel_position("below") == "below"
    assert details_ui.normalise_details_panel_position("Below") == "below"
    assert details_ui.normalise_details_panel_position("right") == "right"
    assert details_ui.normalise_details_panel_position("unexpected") == "right"


def test_country_evidence_is_rendered_without_parsing_notes() -> None:
    row = {
        "notes": "legacy free-form notes must not be parsed",
        details_ui.STORE_EVIDENCE_FIELD: [
            {
                "role": "primary",
                "language_role": "preferred",
                "country": "ch",
                "language": "it",
                "status": "available",
                "http_status": 200,
                "source": "google_play_scraper",
            },
            {
                "role": "regional_fallback",
                "language_role": "english_fallback",
                "country": "us",
                "language": "en",
                "status": "not_found_or_unavailable",
                "http_status": 404,
                "source": "html_fallback",
            },
        ],
    }

    lines = details_ui.evidence_lines(row)

    assert lines == [
        "Primary: CH/it • available • HTTP 200 • google_play_scraper",
        "Regional Fallback: US/en • not found or unavailable • English fallback • HTTP 404 • html_fallback",
    ]


def test_change_events_and_device_inventory_are_rendered() -> None:
    row = {
        details_ui.AUDIT_CHANGES_FIELD: [
            {
                "type": "store_version_changed",
                "previous": "1.0",
                "current": "2.0",
            },
            {
                "type": "maintenance_state_changed",
                "previous": "Current",
                "current": "Aging",
            },
        ],
        "device_change": "Newly installed",
    }

    assert details_ui.change_lines(row) == [
        "Play Store version changed: 1.0 → 2.0",
        "Maintenance state changed: Current → Aging",
        "Device inventory: Newly installed",
    ]


def test_normal_store_response_capture_reuses_developer_without_extra_request() -> None:
    store_metadata.clear_icon_metadata()
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
    }
    store_metadata._remember_result_metadata(
        {
            "appId": "com.example.app",
            "developer": "Example Developer",
            "icon": "https://example.invalid/icon.png",
        }
    )

    store_metadata._enrich_rows_with_icon_urls([row])

    assert row["developer"] == "Example Developer"
    assert row["play_icon_url"] == "https://example.invalid/icon.png"


def test_panel_shows_selected_row_details(app: QApplication) -> None:
    panel = details_ui.AppDetailsPanel("right")
    row = {
        "package_name": "com.example.app",
        "play_title": "Example App",
        "developer": "Example Developer",
        "play_status": "available",
        "play_version": "2.0",
        "play_last_update": "2026-08-20",
        "store_country": "ch",
        "store_language": "it",
        "store_url": "https://play.google.com/store/apps/details?id=com.example.app",
        "installed_version": "1.9",
        "installer_source": "Google Play (com.android.vending)",
    }

    panel.set_row(row)

    assert panel.title_label.text() == "Example App"
    assert panel.developer_label.text() == "Example Developer"
    assert "Package: com.example.app" in panel.store_label.text()
    assert "Store market: ch" in panel.store_label.text()
    assert "Installed version: 1.9" in panel.device_label.text()
    assert panel.open_store_button.isEnabled()

    panel.deleteLater()
    app.processEvents()
