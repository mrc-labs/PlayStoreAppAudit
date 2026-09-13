from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

import playstore_app_audit.services.smart_queries as smart_queries
import playstore_app_audit.services.state as state


def test_legacy_purple_condition_normalises_to_anomaly_blue() -> None:
    condition = smart_queries.normalise_condition(
        {"field": "criticality_key", "operator": "is", "value": "purple"}
    )

    assert condition is not None
    assert condition.value == "blue"
    assert all(
        choice.value != "purple"
        for choice in smart_queries.FIELDS_BY_ID["criticality_key"].choices
    )


def test_legacy_purple_rows_follow_blue_is_and_is_not_semantics() -> None:
    is_anomaly = smart_queries.normalise_condition(
        {"field": "criticality_key", "operator": "is", "value": "blue"}
    )
    is_not_anomaly = smart_queries.normalise_condition(
        {"field": "criticality_key", "operator": "is_not", "value": "blue"}
    )

    assert is_anomaly is not None
    assert is_not_anomaly is not None
    assert smart_queries.condition_matches({"criticality_key": "purple"}, is_anomaly)
    assert not smart_queries.condition_matches(
        {"criticality_key": "purple"}, is_not_anomaly
    )
    assert smart_queries.condition_matches({"criticality_key": "red"}, is_not_anomaly)


def test_load_queries_migrates_schema_v1_purple_storage_in_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query_id = "4cf53e27-2d3a-4ab6-b24f-e9ba06f70bd8"
    stored: dict[str, Any] = {
        "unrelated_setting": "keep-me",
        "smart_queries": {
            "schema_version": 1,
            "items": [
                {
                    "schema_version": 1,
                    "id": query_id,
                    "name": "Legacy anomaly",
                    "match": "all",
                    "conditions": [
                        {
                            "field": "criticality_key",
                            "operator": "is_not",
                            "value": "purple",
                        }
                    ],
                }
            ],
        },
    }
    save_calls: list[dict[str, Any]] = []

    def load() -> dict[str, Any]:
        return stored

    def save(values: dict[str, Any]) -> dict[str, Any]:
        snapshot = deepcopy(values)
        save_calls.append(snapshot)
        stored.clear()
        stored.update(snapshot)
        return stored

    monkeypatch.setattr(state, "load_settings", load)
    monkeypatch.setattr(state, "save_settings", save)

    queries = smart_queries.load_queries()

    assert len(queries) == 1
    assert queries[0].conditions[0].value == "blue"
    assert save_calls
    assert stored["unrelated_setting"] == "keep-me"
    migrated = stored["smart_queries"]["items"][0]["conditions"][0]
    assert migrated["value"] == "blue"
    assert migrated["operator"] == "is_not"
