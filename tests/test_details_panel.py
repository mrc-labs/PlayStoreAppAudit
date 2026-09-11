from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

import playstore_app_audit.services.app_icon_metadata as store_metadata
import playstore_app_audit.services.change_overview as change_service
import playstore_app_audit.services.state as state
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
    assert details_ui.normalise_details_panel_position("hidden") == "hidden"
    assert details_ui.normalise_details_panel_position("Hidden") == "hidden"
    assert details_ui.normalise_details_panel_position("unexpected") == "right"


def test_details_position_setting_supports_hidden_and_repairs_invalid_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, object] = {"details_panel_position": "Hidden"}
    monkeypatch.setattr(state, "_read_json", lambda *_args: dict(stored))

    assert state.DEFAULT_SETTINGS["details_panel_position"] == "right"
    assert state.load_settings()["details_panel_position"] == "hidden"

    stored["details_panel_position"] = "sideways"
    assert state.load_settings()["details_panel_position"] == "right"


def test_auto_position_uses_width_hysteresis() -> None:
    assert details_ui.resolve_details_panel_position("right", 800, "below") == "right"
    assert details_ui.resolve_details_panel_position("below", 1800, "right") == "below"
    assert details_ui.resolve_details_panel_position("hidden", 1800, "right") == "hidden"
    assert details_ui.resolve_details_panel_position("auto", 1500) == "right"
    assert details_ui.resolve_details_panel_position("auto", 1200) == "below"
    assert details_ui.resolve_details_panel_position("auto", 1300, "right") == "right"
    assert details_ui.resolve_details_panel_position("auto", 1300, "below") == "below"


def test_details_content_layout_uses_width_hysteresis() -> None:
    assert details_ui.details_content_layout_mode(900) == "wide"
    assert details_ui.details_content_layout_mode(500) == "narrow"
    assert details_ui.details_content_layout_mode(1180) == "extra-wide"
    assert details_ui.details_content_layout_mode(700, "wide") == "wide"
    assert details_ui.details_content_layout_mode(700, "narrow") == "narrow"
    assert details_ui.details_content_layout_mode(650, "wide") == "narrow"
    assert details_ui.details_content_layout_mode(800, "narrow") == "wide"


def test_details_content_layout_preserves_transition_order_and_both_hysteresis_bands() -> None:
    mode = details_ui.details_content_layout_mode(500)
    assert mode == "narrow"
    mode = details_ui.details_content_layout_mode(800, mode)
    assert mode == "wide"
    mode = details_ui.details_content_layout_mode(1179, mode)
    assert mode == "wide"
    mode = details_ui.details_content_layout_mode(1180, mode)
    assert mode == "extra-wide"
    mode = details_ui.details_content_layout_mode(1080, mode)
    assert mode == "extra-wide"
    mode = details_ui.details_content_layout_mode(1079, mode)
    assert mode == "wide"
    mode = details_ui.details_content_layout_mode(680, mode)
    assert mode == "wide"
    mode = details_ui.details_content_layout_mode(679, mode)
    assert mode == "narrow"

    assert details_ui.details_content_layout_mode(1180, "narrow") == "extra-wide"
    assert details_ui.details_content_layout_mode(1079, "extra-wide") == "wide"
    assert details_ui.details_content_layout_mode(679, "extra-wide") == "narrow"


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
        "Primary market: CH/it • available",
        "Additional markets checked: US",
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
                "previous": "Recent Update",
                "current": "Aging",
            },
        ],
        "device_change": "New on device",
        change_service.DEVICE_HISTORY_FLAG: True,
    }

    assert details_ui.change_lines(row) == [
        "Play Store version changed: 1.0 → 2.0",
        "Maintenance state changed: Recent Update → Aging",
    ]
    assert details_ui.device_inventory_line(row) == "Since previous phone scan: Newly installed"

    row[change_service.DEVICE_HISTORY_FLAG] = False
    assert details_ui.change_lines(row) == [
        "Play Store version changed: 1.0 → 2.0",
        "Maintenance state changed: Recent Update → Aging",
    ]
    assert details_ui.device_inventory_line(row) == "Inventory history: First phone-scan baseline"


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


def test_details_control_is_compact_accessible_and_menu_based(app: QApplication) -> None:
    control = details_ui.DetailsPanelControl("right")
    changes: list[str] = []
    control.position_changed.connect(changes.append)

    assert control.text() == "Details"
    assert control.accessibleName() == "Details Panel"
    assert control.mode_menu.title() == "Details Panel"
    assert control.position() == "right"
    assert set(control.position_actions) == {"auto", "right", "below", "hidden"}
    assert all(not action.icon().isNull() for action in control.position_actions.values())
    assert all(action.toolTip().endswith(".") for action in control.position_actions.values())
    assert control.position_actions["right"].isChecked()

    control.position_actions["auto"].trigger()
    assert control.position() == "auto"
    assert control.position_actions["auto"].isChecked()
    assert changes == ["auto"]

    control.deleteLater()
    app.processEvents()


def test_panel_content_layout_remains_adaptive(app: QApplication) -> None:
    panel = details_ui.AppDetailsPanel()
    panel._update_adaptive_layout(900)
    assert panel.content_layout_mode() == "wide"
    panel._update_adaptive_layout(1180)
    assert panel.content_layout_mode() == "extra-wide"
    panel._update_adaptive_layout(1080)
    assert panel.content_layout_mode() == "extra-wide"
    panel._update_adaptive_layout(1079)
    assert panel.content_layout_mode() == "wide"
    panel._update_adaptive_layout(700)
    assert panel.content_layout_mode() == "wide"
    panel._update_adaptive_layout(650)
    assert panel.content_layout_mode() == "narrow"

    panel.deleteLater()
    app.processEvents()


def test_extra_wide_layout_groups_existing_sections_in_three_columns(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    panel._update_adaptive_layout(1180)

    columns = panel.sections_layout.itemAt(0).layout()
    assert columns is not None
    assert columns.count() == 3

    expected = [
        [panel.store_section, panel.local_apk_section, panel.notes_section],
        [panel.device_section, panel.changes_section],
        [panel.evidence_section, panel.alternative_section, panel.diagnostics_section],
    ]
    for index, expected_widgets in enumerate(expected):
        column = columns.itemAt(index).layout()
        assert column is not None
        widgets = [
            column.itemAt(item).widget()
            for item in range(column.count())
            if column.itemAt(item).widget() is not None
        ]
        assert widgets == expected_widgets

    actions = panel.actions_layout.itemAt(0).layout()
    assert actions is not None
    assert [actions.itemAt(index).widget() for index in range(actions.count())] == [
        panel.review_changes_button,
        panel.open_store_button,
    ]

    panel.deleteLater()
    app.processEvents()


def test_panel_resize_uses_scroll_viewport_width_for_extra_wide_mode(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    panel.resize(details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH, 520)
    panel.show()
    app.processEvents()
    panel.resize(details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH + 1, 520)
    app.processEvents()

    assert panel.width() > details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH
    assert panel.scroll.viewport().width() < details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH
    assert panel.content_layout_mode() == "wide"

    width_delta = (
        details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH + 1 - panel.scroll.viewport().width()
    )
    panel.resize(panel.width() + width_delta, 520)
    app.processEvents()

    assert panel.scroll.viewport().width() >= details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH
    assert panel.content_layout_mode() == "extra-wide"

    panel.deleteLater()
    app.processEvents()


def test_responsive_layout_changes_preserve_all_rendered_content(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    row = {
        "package_name": "com.example.complete",
        "play_title": "Complete Details Example",
        "developer": "Example Developer",
        "play_status": "not_found_in_checked_countries",
        "play_version": "4.2",
        "play_last_update": "2025-01-20",
        "store_country": "it",
        "store_language": "en",
        "updated_source": "multi-country verification",
        "store_url": "https://play.google.com/store/apps/details?id=com.example.complete",
        "installed_version": "4.1",
        "installed_version_code": "410",
        "version_comparison": "Different",
        "installer_source": "Google Play (com.android.vending)",
        "app_enabled": "Enabled",
        "target_sdk": "29",
        "min_sdk": "23",
        "compatibility_status": "Legacy target",
        "health_score": "35",
        "change": "Changed",
        "notes": "raw technical notes remain in the selected row",
        details_ui.AUDIT_CHANGES_FIELD: [
            {"type": "store_version_changed", "previous": "4.1", "current": "4.2"}
        ],
        details_ui.STORE_EVIDENCE_FIELD: [
            {
                "role": "primary",
                "country": "it",
                "language": "en",
                "status": "not_found_or_unavailable",
                "http_status": 404,
                "request_path": "scraper+html",
                "outcome": "terminal_not_found",
                "retry_count": 1,
            },
            {
                "role": "regional_fallback",
                "country": "us",
                "language": "en",
                "status": "not_found_or_unavailable",
                "http_status": 404,
                "request_path": "scraper+html",
                "outcome": "terminal_not_found",
            },
        ],
    }
    panel.set_row(row)
    expected_text = {
        "store": panel.store_label.text(),
        "device": panel.device_label.text(),
        "evidence": panel.evidence_label.text(),
        "diagnostics": panel.diagnostics_label.text(),
        "changes": panel.changes_label.text(),
        "notes": panel.notes_label.text(),
    }

    transitions = [500, 800, 1180, 1100, 1079, 700, 679, 800, 1180]
    expected_modes = [
        "narrow",
        "wide",
        "extra-wide",
        "extra-wide",
        "wide",
        "wide",
        "narrow",
        "wide",
        "extra-wide",
    ]
    for width, expected_mode in zip(transitions, expected_modes, strict=True):
        panel._update_adaptive_layout(width)
        assert panel.content_layout_mode() == expected_mode
        assert panel._row == row
        assert panel.store_label.text() == expected_text["store"]
        assert panel.device_label.text() == expected_text["device"]
        assert panel.evidence_label.text() == expected_text["evidence"]
        assert panel.diagnostics_label.text() == expected_text["diagnostics"]
        assert panel.changes_label.text() == expected_text["changes"]
        assert panel.notes_label.text() == expected_text["notes"]
        assert panel.open_store_button.isEnabled()
        assert panel.review_changes_button.isEnabled()

    panel.deleteLater()
    app.processEvents()


def test_extra_wide_content_scrolls_instead_of_clipping_at_compact_height(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    panel.resize(details_ui.DETAILS_EXTRA_WIDE_ENTER_WIDTH + 1, 260)
    panel.show()
    app.processEvents()
    panel.resize(panel.width() + 1200 - panel.scroll.viewport().width(), 260)
    app.processEvents()
    panel.set_row(
        {
            "package_name": "com.example.evidence.heavy",
            "play_title": "Evidence-heavy Example",
            "developer": "Example Developer",
            "play_status": "available",
            "play_version": "8.4.2",
            "play_last_update": "2026-07-15",
            "store_country": "it",
            "store_language": "en",
            "store_url": (
                "https://play.google.com/store/apps/details?"
                "id=com.example.evidence.heavy"
            ),
            "installed_version": "8.1.0",
            "installed_version_code": "810",
            "version_comparison": "Different",
            "installer_source": "Google Play (com.android.vending)",
            "app_enabled": "Enabled",
            "target_sdk": "28",
            "min_sdk": "23",
            "compatibility_status": "Legacy target",
            "health_score": "38",
            "notes": "fallback token: market mismatch after all checked countries",
            details_ui.AUDIT_CHANGES_FIELD: [
                {
                    "type": "store_version_changed",
                    "previous": "8.1.0",
                    "current": "8.4.2",
                },
                {
                    "type": "maintenance_state_changed",
                    "previous": "Aging",
                    "current": "Legacy",
                },
            ],
            details_ui.STORE_EVIDENCE_FIELD: [
                {
                    "role": "primary",
                    "country": "it",
                    "language": "en",
                    "status": "not_found_or_unavailable",
                    "http_status": 404,
                    "request_path": "scraper+html",
                    "outcome": "terminal_not_found",
                    "retry_count": 1,
                },
                {
                    "role": "regional_fallback",
                    "country": "us",
                    "language": "en",
                    "status": "available",
                    "http_status": 200,
                    "request_path": "scraper",
                    "outcome": "success",
                },
            ],
        }
    )
    app.processEvents()

    assert panel.content_layout_mode() == "extra-wide"
    assert panel.scroll.verticalScrollBar().maximum() > 0
    for label in (
        panel.store_label,
        panel.device_label,
        panel.evidence_label,
        panel.diagnostics_label,
        panel.changes_label,
        panel.notes_label,
    ):
        assert label.height() >= label.heightForWidth(label.width())
    assert "Maintenance state changed: Aging → Legacy" in panel.changes_label.text()
    assert "Additional markets checked: US" in panel.evidence_label.text()

    panel.deleteLater()
    app.processEvents()


def test_panel_shows_selected_row_details_and_review_action(app: QApplication) -> None:
    panel = details_ui.AppDetailsPanel()
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

    visible_sections = {
        panel.store_section,
        panel.device_section,
        panel.evidence_section,
        panel.changes_section,
        panel.notes_section,
    }
    assert all(not widget.isHidden() for widget in visible_sections)
    assert panel.diagnostics_section.isHidden()
    assert panel.title_label.text() == "Example App"
    assert panel.developer_label.text() == "Example Developer"
    assert "Package: com.example.app" in panel.store_label.text()
    assert "Store market: ch" in panel.store_label.text()
    assert "Installed version: 1.9" in panel.device_label.text()
    assert panel.open_store_button.isEnabled()
    assert review_requests == [True]

    panel.deleteLater()
    app.processEvents()
