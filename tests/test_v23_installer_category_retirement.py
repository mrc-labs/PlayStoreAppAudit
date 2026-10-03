from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.installer_source as installer_source
import playstore_app_audit.services.result_csv as result_csv
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.scan_session as scan_session
import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state
from playstore_app_audit.services.presentation import DEFAULT_DATE_FORMAT
from playstore_app_audit.ui import column_presets, schema


def test_new_installer_metadata_omits_category_but_derives_same_type() -> None:
    fields = installer_source.installer_fields("com.sec.android.app.samsungapps")

    assert fields == {
        "installer_source": "Galaxy Store (com.sec.android.app.samsungapps)",
        "installer_package": "com.sec.android.app.samsungapps",
    }
    assert installer_source.installer_category(fields) == (
        installer_source.CATEGORY_ALTERNATIVE_STORE
    )


def test_legacy_category_precedence_and_exact_fallback_semantics_are_preserved() -> None:
    legacy = {
        "installer_category": installer_source.CATEGORY_ALTERNATIVE_STORE,
        "installer_package": "com.android.vending",
        "installer_source": "Google Play (com.android.vending)",
    }
    canonical = {
        "installer_package": "com.android.vending",
        "installer_source": "Sideload / package installer",
    }
    source_only = {"installer_source": "Sideload / package installer"}

    assert installer_source.installer_category(legacy) == (
        installer_source.CATEGORY_ALTERNATIVE_STORE
    )
    assert installer_source.installer_category(canonical) == (
        installer_source.CATEGORY_GOOGLE_PLAY
    )
    assert installer_source.installer_category(source_only) == (
        installer_source.CATEGORY_SIDELOADED
    )


def test_saved_schema_v1_installer_query_loads_unchanged_and_matches_new_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_id = "4cf53e27-2d3a-4ab6-b24f-e9ba06f70bd8"
    stored: dict[str, Any] = {
        "smart_queries": {
            "schema_version": 1,
            "items": [
                {
                    "schema_version": 1,
                    "id": query_id,
                    "name": "Alternative installers",
                    "match": "all",
                    "conditions": [
                        {
                            "field": "installer_category",
                            "operator": "is",
                            "value": "alternative_store",
                        }
                    ],
                }
            ],
        }
    }

    monkeypatch.setattr(smart_queries.state, "load_settings", lambda: stored)
    loaded = smart_queries.load_queries()

    assert smart_queries.SCHEMA_VERSION == 1
    assert len(loaded) == 1
    assert smart_queries.query_to_dict(loaded[0]) == stored["smart_queries"]["items"][0]
    assert smart_queries.FIELDS_BY_ID["installer_category"].label == "Installer Type"
    assert smart_queries.query_matches(
        {
            "installer_package": "com.sec.android.app.samsungapps",
            "installer_source": "Galaxy Store (com.sec.android.app.samsungapps)",
        },
        loaded[0],
    )
    assert not smart_queries.query_matches(
        {
            "installer_package": "com.android.vending",
            "installer_source": "Google Play (com.android.vending)",
        },
        loaded[0],
    )


def test_machine_readable_exports_drop_retired_legacy_category() -> None:
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "installer_source": "Google Play (com.android.vending)",
        "installer_package": "com.android.vending",
        "installer_category": "google_play",
    }

    document = result_json.build_results_document([row])
    exported = document["results"][0]
    assert "installer_category" not in exported
    assert exported["installer_source"] == "Google Play (com.android.vending)"
    assert exported["installer_package"] == "com.android.vending"

    output = io.StringIO()
    result_csv.write_csv(output, [row], date_style=DEFAULT_DATE_FORMAT)
    reader = csv.DictReader(io.StringIO(output.getvalue()))
    csv_row = next(reader)
    assert "installer_category" not in (reader.fieldnames or [])
    assert csv_row["installer_source"] == "Google Play (com.android.vending)"
    assert csv_row["installer_package"] == "com.android.vending"


def test_legacy_store_cache_category_is_stripped_on_read_and_not_rewritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    package = "com.example.app"
    key = state._cache_key("it", "it", package)
    old_row = {
        "package_name": package,
        "app_name": "Example",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "installer_source": "Google Play (com.android.vending)",
        "installer_package": "com.android.vending",
        "installer_category": "google_play",
    }
    cache_file.write_text(
        json.dumps(
            {
                key: {
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "row": old_row,
                }
            }
        ),
        encoding="utf-8",
    )

    cached = state.load_fresh_cache(
        [{"package_name": package, "app_name": "Example"}],
        "it",
        "it",
        24,
    )[package]
    assert "installer_category" not in cached
    assert installer_source.installer_category(cached) == installer_source.CATEGORY_GOOGLE_PLAY

    state.update_cache([old_row], "it", "it")
    stored = json.loads(cache_file.read_text(encoding="utf-8"))[key]["row"]
    assert "installer_category" not in stored
    assert stored["installer_package"] == "com.android.vending"


def test_new_inventory_and_scan_session_state_omit_duplicate_category() -> None:
    row = {
        "package_name": "com.example.app",
        "installer_source": "Google Play (com.android.vending)",
        "installer_package": "com.android.vending",
        "installer_category": "google_play",
    }
    record = device_insights._inventory_record(row)

    assert "installer_category" not in record
    assert "installer_category" not in scan_session.CompactPackageMetadata.__dataclass_fields__

    legacy_inventory = dict(record, installer_category="alternative_store")
    assert not device_insights._inventory_installer_changed(legacy_inventory, record)


def test_canonical_ui_schema_needs_no_installer_category_workaround() -> None:
    assert "installer_category" not in schema.MODEL_COLUMNS
    assert "installer_category" not in schema.COLUMN_LABELS
    assert "installer_category" not in schema.COLUMN_WIDTH_POLICIES
    assert not hasattr(column_presets, "CUSTOM_HIDDEN_COLUMNS")
