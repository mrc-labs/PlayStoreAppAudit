from __future__ import annotations

import csv
import io
import os
from pathlib import Path

import google_play_scraper
import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_mass_rename as mass_rename
import playstore_app_audit.services.play_store as play_store
import playstore_app_audit.services.result_csv as result_csv
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.details_panel as details_ui
from playstore_app_audit.domain.models import AppRecord
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.presentation import DEFAULT_DATE_FORMAT
from playstore_app_audit.ui import column_presets, schema


def _locale_result(
    status: str,
    *,
    country: str,
    language: str,
    title: str = "",
    updated: str = "",
    version: str = "",
    category: str = "",
) -> dict[str, object]:
    return {
        "status": status,
        "http_status": 200 if status == "available" else 404,
        "title": title,
        "updated": updated,
        "version": version,
        "category": category,
        "source": "test" if status == "available" else "",
        "url": f"https://example.invalid/{country}/{language}",
        "notes": "",
        "country": country,
        "language": language,
    }


def test_scraper_genre_reaches_canonical_play_category(monkeypatch: pytest.MonkeyPatch) -> None:
    def available_app(*_args, **_kwargs):
        return {
            "title": "Example",
            "updated": 1_700_000_000,
            "version": "1.2.3",
            "genre": "Tools",
        }

    monkeypatch.setattr(google_play_scraper, "app", available_app)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _country: ())

    result = play_store.PlayStoreService().fetch_one(
        "Example",
        "com.example.app",
        AuditConfig(country="it", language="it", max_retries=0),
    )

    assert result["play_status"] == "available"
    assert result["play_category"] == "Tools"


def test_missing_scraper_genre_stays_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    def available_app(*_args, **_kwargs):
        return {
            "title": "Example",
            "updated": 1_700_000_000,
            "version": "1.2.3",
        }

    monkeypatch.setattr(google_play_scraper, "app", available_app)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _country: ())

    result = play_store.PlayStoreService().fetch_one(
        "Example",
        "com.example.app",
        AuditConfig(country="it", language="it", max_retries=0),
    )

    assert result["play_category"] == ""


def test_english_metadata_completion_does_not_replace_preferred_category() -> None:
    def fake_fetch(_package: str, language: str, country: str, _config: AuditConfig):
        if language == "it":
            return _locale_result(
                "available",
                country=country,
                language=language,
                title="Titolo italiano",
                category="Strumenti",
            )
        return _locale_result(
            "available",
            country=country,
            language=language,
            title="English title",
            updated="2026-08-01",
            version="2.0",
            category="Tools",
        )

    result = play_store._fetch_country(
        "com.example.app",
        "ch",
        "it",
        AuditConfig(country="ch", language="it"),
        fake_fetch,
    )

    assert result["title"] == "Titolo italiano"
    assert result["category"] == "Strumenti"
    assert result["updated"] == "2026-08-01"
    assert result["version"] == "2.0"


def test_regional_fallback_category_becomes_canonical(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(
        _package: str,
        language: str,
        country: str,
        _config: AuditConfig,
        cancel_event=None,
    ):
        del cancel_event
        if country == "it":
            return _locale_result(
                "not_found_or_unavailable",
                country=country,
                language=language,
            )
        return _locale_result(
            "available",
            country=country,
            language=language,
            title="Example",
            updated="2026-08-01",
            version="3.0",
            category="Productivity",
        )

    monkeypatch.setattr(play_store, "fetch_locale", fake_fetch)
    monkeypatch.setattr(play_store, "_fallback_countries", lambda _country: ("us",))

    result = play_store.PlayStoreService().fetch_one(
        "Example",
        "com.example.app",
        AuditConfig(country="it", language="it", max_retries=0, max_workers=1),
    )

    assert result["play_status"] == "available_in_other_country"
    assert result["store_country"] == "it"
    assert result["play_category"] == "Productivity"


def test_play_category_survives_healthy_store_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    row = {
        "package_name": "com.example.app",
        "app_name": "Example",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_category": "Tools",
    }

    state.update_cache([row], "it", "it")
    cached = state.load_fresh_cache(
        [{"package_name": "com.example.app", "app_name": "Example"}],
        "it",
        "it",
        24,
    )

    assert cached["com.example.app"]["play_category"] == "Tools"


@pytest.mark.parametrize(
    "source",
    [
        column_presets.SOURCE_FILE,
        column_presets.SOURCE_DEVICE,
        column_presets.SOURCE_LOCAL_APK,
    ],
)
def test_category_is_detailed_and_custom_but_not_basic(source: str) -> None:
    basic = column_presets.visible_columns(
        "Basic",
        source,
        compare_previous=True,
        device_inventory_history=True,
        health_score_enabled=True,
    )
    source_details = column_presets.visible_columns(
        "Source Details",
        source,
        compare_previous=True,
        device_inventory_history=True,
        health_score_enabled=True,
    )
    technical = column_presets.visible_columns(
        "Technical",
        source,
        compare_previous=True,
        device_inventory_history=True,
        health_score_enabled=True,
    )

    assert "play_category" in schema.MODEL_COLUMNS
    assert schema.COLUMN_LABELS["play_category"] == "Play Store Category"
    assert "play_category" not in basic
    assert "play_category" in source_details
    assert "play_category" in technical
    assert "play_category" in column_presets.custom_source_user_columns(source)


def test_play_category_is_a_text_smart_query_field() -> None:
    definition = smart_queries.FIELDS_BY_ID["play_category"]
    condition = smart_queries.normalise_condition(
        {
            "field": "play_category",
            "operator": "contains",
            "value": "game",
        }
    )

    assert definition.label == "Play Store Category"
    assert definition.field_type == smart_queries.FieldType.TEXT
    assert condition is not None
    assert smart_queries.condition_matches({"play_category": "Action Games"}, condition)
    assert not smart_queries.condition_matches({"play_category": "Tools"}, condition)


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_details_panel_and_exports_surface_category(
    app: QApplication, tmp_path: Path
) -> None:
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_title": "Example",
        "play_category": "Games & puzzles",
        "play_last_update": "2026-08-01",
        "criticality_key": "green",
        "criticality": "Recent",
    }

    panel = details_ui.AppDetailsPanel()
    panel.set_row(row)
    assert "Play Store category: Games & puzzles" in panel.store_label.text()

    csv_output = io.StringIO()
    result_csv.write_csv(csv_output, [row], date_style=DEFAULT_DATE_FORMAT)
    csv_rows = list(csv.DictReader(io.StringIO(csv_output.getvalue())))
    assert csv_rows[0]["play_category"] == "Games & puzzles"

    document = result_json.build_results_document([row])
    assert document["schema_version"] == 2
    assert document["results"][0]["play_category"] == "Games & puzzles"

    html_path = device_insights.write_html_report(tmp_path / "report.html", [row])
    html_text = html_path.read_text(encoding="utf-8")
    assert "<th>Play Store category</th>" in html_text
    assert "Games &amp; puzzles" in html_text

    local_row = {
        **row,
        "source_mode": "local_apk",
        "local_apk_file_name": "example.apk",
        "local_apk_version_name": "1.0",
        "local_apk_version_code": 1,
    }
    local_html = device_insights.write_html_report(tmp_path / "local.html", [local_row])
    local_text = local_html.read_text(encoding="utf-8")
    assert "<th>Play Store category</th>" in local_text
    assert "Games &amp; puzzles" in local_text

    panel.deleteLater()
    app.processEvents()


def test_mass_rename_category_uses_only_canonical_play_category() -> None:
    parts, error = mass_rename._template_parts("{category}")
    assert error == ""

    rendered, error = mass_rename._render_template(
        parts,
        {"play_category": "Productivity"},
    )
    assert rendered == "Productivity"
    assert error == ""

    rendered, error = mass_rename._render_template(
        parts,
        {"play_genre": "Legacy alias", "store_category": "Legacy alias"},
    )
    assert rendered == ""
    assert error == "Missing metadata for {category}."


def test_app_record_models_category_as_first_class_field() -> None:
    record = AppRecord.from_mapping(
        {
            "package_name": "com.example.app",
            "play_category": "Tools",
            "custom": "keep",
        }
    )

    assert record.play_category == "Tools"
    assert "play_category" not in record.extra
    assert record.extra["custom"] == "keep"


def test_category_difference_does_not_create_store_change_event() -> None:
    history = {
        "com.example.app": {
            "play_status": "available",
            "play_version": "1.0",
            "play_last_update": "2026-08-01",
            "criticality_key": "green",
            "installer_source": "Google Play",
            "play_category": "Tools",
        }
    }
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_version": "1.0",
        "play_last_update": "2026-08-01",
        "criticality_key": "green",
        "installer_source": "Google Play",
        "play_category": "Productivity",
    }

    assert state.changes_with_history(row, history) == []
