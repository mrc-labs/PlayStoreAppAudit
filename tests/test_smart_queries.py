from __future__ import annotations

from datetime import date
from time import perf_counter
from typing import Any

import pytest

import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state


def _condition(
    field: str,
    operator: smart_queries.Operator | str,
    value: object = None,
) -> smart_queries.SmartCondition:
    condition = smart_queries.normalise_condition(
        {"field": field, "operator": str(operator), "value": value}
    )
    assert condition is not None
    return condition


def _query(
    *conditions: smart_queries.SmartCondition,
    match: smart_queries.MatchMode = smart_queries.MatchMode.ALL,
    name: str = "Maintenance review",
) -> smart_queries.SmartQuery:
    query = smart_queries.create_query(name, match, conditions)
    assert query is not None
    return query


def test_curated_fields_exclude_technical_internals() -> None:
    assert [field.field_id for field in smart_queries.FIELD_DEFINITIONS] == [
        "package_name",
        "play_title",
        "notes",
        "criticality_key",
        "play_status",
        "version_comparison",
        "local_apk_version_comparison",
        "installer_category",
        "compatibility_status",
        "app_enabled",
        "device_change",
        "age_days",
        "target_sdk",
        "min_sdk",
        "sensitive_permissions_count",
        "health_score",
        "play_last_update",
        "first_install_time",
        "last_local_update",
        "is_system",
    ]
    assert not {"play_http_status", "store_url", "_store_evidence"}.intersection(
        smart_queries.FIELDS_BY_ID
    )


@pytest.mark.parametrize(
    ("field", "operator", "value", "row_value", "expected"),
    [
        ("package_name", "contains", "EXAMPLE", "com.example.app", True),
        ("package_name", "does_not_contain", "other", "com.example.app", True),
        ("package_name", "is", " COM.EXAMPLE.APP ", "com.example.app", True),
        ("package_name", "is_not", "com.other", "com.example.app", True),
        ("package_name", "starts_with", "COM.EX", "com.example.app", True),
        ("criticality_key", "is", "orange", "orange", True),
        ("criticality_key", "is_not", "red", "orange", True),
        ("age_days", "equals", 730, "730", True),
        ("age_days", "does_not_equal", 365, 730, True),
        ("age_days", "greater_than", 729, 730, True),
        ("age_days", "greater_or_equal", 730, 730, True),
        ("age_days", "less_than", 731, 730, True),
        ("age_days", "less_or_equal", 730, 730, True),
        ("play_last_update", "is_on", "2026-01-20", "2026-01-20", True),
        ("play_last_update", "is_before", "2026-01-21", "2026-01-20", True),
        ("play_last_update", "is_after", "2026-01-19", "2026-01-20", True),
        ("is_system", "is_yes", None, True, True),
        ("is_system", "is_no", None, False, True),
    ],
)
def test_condition_operator_evaluation(
    field: str,
    operator: str,
    value: object,
    row_value: object,
    expected: bool,
) -> None:
    condition = _condition(field, operator, value)
    assert smart_queries.condition_matches({field: row_value}, condition) is expected


@pytest.mark.parametrize(
    "operator",
    ["does_not_contain", "is_not", "does_not_equal"],
)
def test_negative_comparisons_do_not_match_missing_values(operator: str) -> None:
    field = "age_days" if operator == "does_not_equal" else "package_name"
    value: object = 10 if field == "age_days" else "example"
    assert not smart_queries.condition_matches({}, _condition(field, operator, value))


@pytest.mark.parametrize("missing", [None, "", "not-a-number"])
def test_numeric_missing_semantics(missing: object) -> None:
    assert smart_queries.condition_matches(
        {"age_days": missing}, _condition("age_days", "is_empty")
    )
    assert not smart_queries.condition_matches(
        {"age_days": missing}, _condition("age_days", "is_not_empty")
    )


def test_date_within_last_days_uses_calendar_dates() -> None:
    condition = _condition("play_last_update", "within_last_days", 30)
    current = date(2026, 8, 24)
    assert smart_queries.condition_matches(
        {"play_last_update": "2026-07-25T23:30:00+00:00"}, condition, today=current
    )
    assert not smart_queries.condition_matches(
        {"play_last_update": "2026-07-24"}, condition, today=current
    )
    assert not smart_queries.condition_matches(
        {"play_last_update": "2026-08-25"}, condition, today=current
    )


def test_all_and_any_are_one_level_and_keep_missing_values_explicit() -> None:
    stale = _condition("criticality_key", "is", "orange")
    alternative = _condition("installer_category", "is", "alternative_store")
    row = {"criticality_key": "orange", "installer_category": "google_play"}

    assert not smart_queries.query_matches(row, _query(stale, alternative))
    assert smart_queries.query_matches(
        row, _query(stale, alternative, match=smart_queries.MatchMode.ANY)
    )


def test_normalisation_rejects_unknown_schema_fields_operators_and_nested_groups() -> None:
    valid = {
        "schema_version": 1,
        "id": "4cf53e27-2d3a-4ab6-b24f-e9ba06f70bd8",
        "name": "Review",
        "match": "all",
        "conditions": [{"field": "age_days", "operator": "greater_than", "value": 365}],
    }
    assert smart_queries.normalise_query(valid) is not None

    for mutation in (
        {"schema_version": 2},
        {"match": "nested"},
        {"conditions": [{"field": "store_url", "operator": "contains", "value": "x"}]},
        {"conditions": [{"field": "age_days", "operator": "regex", "value": "x"}]},
        {"conditions": [{"all": []}]},
        {"conditions": []},
        {"conditions": valid["conditions"] * 21},
    ):
        candidate = dict(valid)
        candidate.update(mutation)
        assert smart_queries.normalise_query(candidate) is None


def test_choice_values_are_canonical_and_unknown_values_are_rejected() -> None:
    assert _condition("installer_category", "is", "ALTERNATIVE_STORE").value == (
        "alternative_store"
    )
    assert (
        smart_queries.normalise_condition(
            {"field": "installer_category", "operator": "is", "value": "internal_value"}
        )
        is None
    )


def test_versioned_store_round_trip_replace_rename_delete_and_legacy_separation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored: dict[str, Any] = {
        "saved_filters": {"Legacy": {"query": "old"}},
        "audit_profiles": {"Phone": {"schema_version": 1}},
    }

    def load() -> dict[str, Any]:
        return dict(stored)

    def save(values: dict[str, Any]) -> dict[str, Any]:
        stored.clear()
        stored.update(values)
        return dict(stored)

    monkeypatch.setattr(state, "load_settings", load)
    monkeypatch.setattr(state, "save_settings", save)

    first = _query(_condition("age_days", "greater_than", 365), name="Needs review")
    smart_queries.save_query(first)
    loaded = smart_queries.load_queries()
    assert loaded == [first]
    assert stored["smart_queries"]["schema_version"] == 1
    assert stored["saved_filters"] == {"Legacy": {"query": "old"}}
    assert stored["audit_profiles"] == {"Phone": {"schema_version": 1}}

    renamed = smart_queries.renamed_query(first, "Later review")
    assert renamed is not None
    smart_queries.save_query(renamed)
    assert smart_queries.load_queries()[0].query_id == first.query_id
    assert smart_queries.load_queries()[0].name == "Later review"

    conflict = _query(_condition("is_system", "is_no"), name="later REVIEW")
    with pytest.raises(smart_queries.DuplicateQueryNameError):
        smart_queries.save_query(conflict)
    smart_queries.save_query(conflict, replace_name=True)
    assert smart_queries.load_queries() == [conflict]

    assert smart_queries.delete_query(conflict.query_id)
    assert not smart_queries.delete_query(conflict.query_id)
    assert smart_queries.load_queries() == []


def test_loader_ignores_malformed_items_and_unknown_storage_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    valid = _query(_condition("app_enabled", "is", "Enabled"))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "items": [
            smart_queries.query_to_dict(valid),
            {"schema_version": 1, "id": "not-a-uuid", "name": "Broken"},
        ],
    }
    monkeypatch.setattr(state, "load_settings", lambda: {"smart_queries": payload})
    assert smart_queries.load_queries() == [valid]

    payload["schema_version"] = 99
    assert smart_queries.load_queries() == []


def test_ten_thousand_rows_and_twenty_conditions_remain_in_memory_fast() -> None:
    conditions = tuple(
        _condition("package_name", "contains", "com.example") for _index in range(20)
    )
    query = _query(*conditions)
    rows = [{"package_name": f"com.example.app{index}"} for index in range(10_000)]

    started = perf_counter()
    count = sum(smart_queries.query_matches(row, query) for row in rows)
    elapsed = perf_counter() - started

    assert count == 10_000
    assert elapsed < 2.0
