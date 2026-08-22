from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import playstore_app_audit.services.app_icon_metadata as store_metadata
import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.ui.details_panel as details_ui
import playstore_app_audit.ui.results_window as results_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_details_panel_position_normalises_unknown_values() -> None:
    assert details_ui.normalise_details_panel_position("auto") == "auto"
    assert details_ui.normalise_details_panel_position("Auto") == "auto"
    assert details_ui.normalise_details_panel_position("below") == "below"
    assert details_ui.normalise_details_panel_position("Below") == "below"
    assert details_ui.normalise_details_panel_position("right") == "right"
    assert details_ui.normalise_details_panel_position("unexpected") == "right"


def test_auto_position_uses_width_hysteresis() -> None:
    assert details_ui.resolve_details_panel_position("right", 800, "below") == "right"
    assert details_ui.resolve_details_panel_position("below", 1800, "right") == "below"
    assert details_ui.resolve_details_panel_position("auto", 1500) == "right"
    assert details_ui.resolve_details_panel_position("auto", 1200) == "below"
    assert details_ui.resolve_details_panel_position("auto", 1300, "right") == "right"
    assert details_ui.resolve_details_panel_position("auto", 1300, "below") == "below"


def test_details_content_layout_uses_width_hysteresis() -> None:
    assert details_ui.details_content_layout_mode(900) == "wide"
    assert details_ui.details_content_layout_mode(500) == "narrow"
    assert details_ui.details_content_layout_mode(700, "wide") == "wide"
    assert details_ui.details_content_layout_mode(700, "narrow") == "narrow"
    assert details_ui.details_content_layout_mode(650, "wide") == "narrow"
    assert details_ui.details_content_layout_mode(800, "narrow") == "wide"


def test_results_layout_lookup_descends_through_card_widget(app: QApplication) -> None:
    root_widget = QWidget()
    root = QVBoxLayout(root_widget)
    card = QWidget()
    card_layout = QVBoxLayout(card)
    target = QWidget()
    card_layout.addWidget(target)
    root.addWidget(card)

    assert results_ui._find_layout_containing(root, target) is card_layout

    root_widget.deleteLater()
    app.processEvents()


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


def test_change_events_and_device_inventory_are_rendered_only_with_baseline() -> None:
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
        "device_change": "New on device",
        change_service.DEVICE_HISTORY_FLAG: True,
    }

    assert details_ui.change_lines(row) == [
        "Play Store version changed: 1.0 → 2.0",
        "Maintenance state changed: Current → Aging",
        "Device inventory: New on device",
    ]

    row[change_service.DEVICE_HISTORY_FLAG] = False
    assert details_ui.change_lines(row) == [
        "Play Store version changed: 1.0 → 2.0",
        "Maintenance state changed: Current → Aging",
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


def test_panel_position_control_is_compact_icon_based(app: QApplication) -> None:
    panel = details_ui.AppDetailsPanel("right")
    changes: list[str] = []
    panel.position_changed.connect(changes.append)

    assert panel.position() == "right"
    assert set(panel.position_buttons) == {"auto", "right", "below"}
    assert all(button.icon().isNull() is False for button in panel.position_buttons.values())
    assert all(button.text() == "" for button in panel.position_buttons.values())

    panel.position_buttons["auto"].click()
    assert panel.position() == "auto"
    assert panel.position_buttons["auto"].isChecked()
    assert changes == ["auto"]

    panel._update_adaptive_layout(900)
    assert panel.content_layout_mode() == "wide"
    panel._update_adaptive_layout(700)
    assert panel.content_layout_mode() == "wide"
    panel._update_adaptive_layout(650)
    assert panel.content_layout_mode() == "narrow"

    panel.deleteLater()
    app.processEvents()


def test_panel_shows_selected_row_details_and_review_action(app: QApplication) -> None:
    panel = details_ui.AppDetailsPanel("right")
    assert all(widget.isHidden() for widget in panel._section_widgets)
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
    review_requests: list[bool] = []
    panel.review_changes_requested.connect(lambda: review_requests.append(True))

    panel.set_row(row)
    panel.review_changes_button.click()

    assert all(not widget.isHidden() for widget in panel._section_widgets)
    assert panel.title_label.text() == "Example App"
    assert panel.developer_label.text() == "Example Developer"
    assert "Package: com.example.app" in panel.store_label.text()
    assert "Store market: ch" in panel.store_label.text()
    assert "Installed version: 1.9" in panel.device_label.text()
    assert panel.open_store_button.isEnabled()
    assert review_requests == [True]

    panel.deleteLater()
    app.processEvents()
