from __future__ import annotations

import copy
import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.details_panel as details_ui
import playstore_app_audit.ui.table_window as table_ui

RAW_NOTES = "selected_country_unavailable | available_in:de | scraper:error(404)"


def _regional_row() -> dict[str, object]:
    return {
        "package_name": "com.example.app",
        "play_status": "available_in_other_country",
        "store_country": "it",
        "health_score": 85,
        "notes": RAW_NOTES,
        "_store_evidence": [
            {
                "role": "primary",
                "country": "it",
                "status": "not_found_or_unavailable",
            },
            {
                "role": "regional_fallback",
                "country": "de",
                "status": "available",
            },
        ],
    }


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_friendly_notes_are_one_pure_shared_presentation() -> None:
    row = _regional_row()
    original = copy.deepcopy(row)

    assert details_ui.display_notes is presentation.friendly_notes
    assert presentation.friendly_notes(row) == (
        "Not available in IT, but found in DE. Google Play availability is region-specific."
    )
    assert row == original


def test_notes_table_display_and_tooltip_share_complete_friendly_text(
    app: QApplication,
) -> None:
    row = _regional_row()
    model = table_ui.AuditTableModel()
    model.set_rows([row])
    notes_index = model.index(0, model.columns.index("notes"))
    expected = presentation.friendly_notes(row)

    assert model.data(notes_index, Qt.ItemDataRole.DisplayRole) == expected
    assert model.data(notes_index, Qt.ItemDataRole.ToolTipRole) == expected
    assert model.data(notes_index, Qt.ItemDataRole.UserRole) is row

    model.deleteLater()
    app.processEvents()


@pytest.mark.parametrize(
    ("column", "value", "status_colour"),
    [
        ("version_comparison", "Different", "yellow"),
        ("compatibility_status", "Aging target", "yellow"),
        ("compatibility_status", "Legacy target", "orange"),
    ],
)
def test_semantic_table_foregrounds_reuse_status_palette(
    app: QApplication,
    column: str,
    value: str,
    status_colour: str,
) -> None:
    model = table_ui.AuditTableModel()
    model.set_rows([{"package_name": "com.example.app", column: value}])
    index = model.index(0, model.columns.index(column))
    colour = model.data(index, Qt.ItemDataRole.ForegroundRole)

    assert colour.name().casefold() == base_ui.CRITICALITY[status_colour]["foreground"].casefold()

    model.deleteLater()
    app.processEvents()


def test_html_uses_friendly_notes_and_maintenance_score_label(tmp_path) -> None:
    row = _regional_row()
    target = device_insights.write_html_report(tmp_path / "report.html", [row])
    report = target.read_text(encoding="utf-8")

    assert presentation.friendly_notes(row) in report
    assert RAW_NOTES not in report
    assert "<th>Maintenance Score</th>" in report
    assert row["notes"] == RAW_NOTES


def test_raw_outputs_and_v18_smart_query_notes_semantics_are_unchanged() -> None:
    row = _regional_row()
    output_row = presentation.rows_for_output([row])[0]
    document = result_json.build_results_document([row], scope="all")
    persisted_condition = {
        "field": "notes",
        "operator": "contains",
        "value": "scraper:error",
    }
    condition = smart_queries.normalise_condition(persisted_condition)

    assert output_row["notes"] == RAW_NOTES
    assert document["results"][0]["notes"] == RAW_NOTES
    assert condition is not None
    assert smart_queries.condition_matches(row, condition)
    assert smart_queries.FIELDS_BY_ID["notes"].field_id == "notes"
    assert smart_queries.FIELDS_BY_ID["health_score"].label == "Maintenance Score"
