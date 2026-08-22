from __future__ import annotations

import json

import pytest

import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state


def _history_entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "criticality_key": "green",
        "criticality_rank": 0,
        "criticality": "Current",
        "play_status": "available",
        "play_version": "1.0",
        "play_last_update": "2026-07-01",
        "installer_source": "Google Play (com.android.vending)",
        "store_country": "ch",
        "store_language": "de",
        state.STORE_EVIDENCE_FIELD: [],
    }
    entry.update(overrides)
    return entry


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "package_name": "com.example.app",
        "criticality_key": "green",
        "criticality_rank": 0,
        "criticality": "Current",
        "play_status": "available",
        "play_version": "1.0",
        "play_last_update": "2026-07-01",
        "installer_source": "Google Play (com.android.vending)",
        "store_country": "ch",
        "store_language": "de",
        state.STORE_EVIDENCE_FIELD: [],
    }
    row.update(overrides)
    return row


def _event_types(row: dict[str, object], history: dict[str, dict[str, object]]) -> list[str]:
    return [str(event["type"]) for event in state.changes_with_history(row, history)]


def test_sparse_legacy_history_does_not_invent_unavailable_or_version_events() -> None:
    history = {
        "com.example.app": {
            "criticality_key": "green",
            "criticality_rank": 0,
            "criticality": "Current",
            "play_last_update": "2026-07-01",
        }
    }

    assert state.changes_with_history(_row(), history) == []


def test_new_package_keeps_legacy_new_label_without_newly_available_event() -> None:
    row = _row()

    assert state.compare_with_history(row, {}) == "New"
    assert row[state.AUDIT_CHANGES_FIELD] == []


def test_available_to_checked_unavailable_records_country_evidence() -> None:
    previous_evidence = [
        {
            "role": "primary",
            "country": "ch",
            "language": "de",
            "status": "available",
        }
    ]
    current_evidence = [
        {
            "role": "primary",
            "country": "ch",
            "language": "de",
            "status": "not_found_or_unavailable",
        },
        {
            "role": "regional_fallback",
            "country": "de",
            "language": "de",
            "status": "not_found_or_unavailable",
        },
    ]
    history = {
        "com.example.app": _history_entry(**{state.STORE_EVIDENCE_FIELD: previous_evidence})
    }
    row = _row(
        play_status="not_found_in_checked_countries",
        criticality_key="red",
        criticality_rank=3,
        criticality="Removed",
        **{state.STORE_EVIDENCE_FIELD: current_evidence},
    )

    changes = state.changes_with_history(row, history)

    assert changes[0]["type"] == "newly_unavailable_in_checked_countries"
    assert changes[0]["previous"] == "available"
    assert changes[0]["current"] == "not_found_in_checked_countries"
    assert changes[0]["previous_store_country"] == "ch"
    assert changes[0]["current_store_country"] == "ch"
    assert changes[0]["previous_evidence"] == previous_evidence
    assert changes[0]["current_evidence"] == current_evidence


def test_checked_unavailable_to_available_is_reappeared() -> None:
    history = {
        "com.example.app": _history_entry(
            play_status="not_found_in_checked_countries",
            criticality_key="red",
            criticality_rank=3,
            criticality="Removed",
        )
    }

    assert _event_types(_row(), history)[0] == "reappeared"


def test_inconclusive_to_available_is_newly_available() -> None:
    history = {
        "com.example.app": _history_entry(
            play_status="multi_country_check_inconclusive",
            criticality_key="purple",
            criticality_rank=5,
            criticality="Other",
        )
    }

    assert _event_types(_row(), history)[0] == "newly_available"


def test_store_metadata_maintenance_and_installer_changes_are_structured() -> None:
    history = {"com.example.app": _history_entry()}
    row = _row(
        play_version="2.0",
        play_last_update="2026-08-20",
        criticality_key="yellow",
        criticality_rank=1,
        criticality="Aging",
        installer_source="Galaxy Store (com.sec.android.app.samsungapps)",
    )

    changes = state.changes_with_history(row, history)

    assert changes == [
        {"type": "store_version_changed", "previous": "1.0", "current": "2.0"},
        {
            "type": "store_latest_update_changed",
            "previous": "2026-07-01",
            "current": "2026-08-20",
        },
        {
            "type": "maintenance_state_changed",
            "previous": "Current",
            "current": "Aging",
            "previous_key": "green",
            "current_key": "yellow",
        },
        {
            "type": "installer_source_changed",
            "previous": "Google Play (com.android.vending)",
            "current": "Galaxy Store (com.sec.android.app.samsungapps)",
        },
    ]


def test_unknown_installer_does_not_create_false_change() -> None:
    history = {
        "com.example.app": _history_entry(installer_source="Unknown / preinstalled")
    }

    assert "installer_source_changed" not in _event_types(_row(), history)


def test_compare_with_history_keeps_existing_compact_label_and_attaches_events() -> None:
    history = {"com.example.app": _history_entry()}
    row = _row(
        criticality_key="yellow",
        criticality_rank=1,
        criticality="Aging",
    )

    assert state.compare_with_history(row, history) == "↓ Worse"
    assert _event_types(row, history) == ["maintenance_state_changed"]
    assert row[state.AUDIT_CHANGES_FIELD][0]["type"] == "maintenance_state_changed"


def test_save_history_persists_richer_snapshot_and_evidence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "audit_history.json"
    monkeypatch.setattr(state, "history_path", lambda: path)
    evidence = [
        {
            "role": "primary",
            "language_role": "preferred",
            "country": "ch",
            "language": "it",
            "status": "available",
            "http_status": 200,
            "source": "test",
        }
    ]
    row = _row(
        store_language="it",
        **{state.STORE_EVIDENCE_FIELD: evidence, state.AUDIT_CHANGES_FIELD: [{"type": "ignored"}]},
    )

    state.save_history([row])
    saved = state.load_history()["com.example.app"]

    assert saved["play_status"] == "available"
    assert saved["play_version"] == "1.0"
    assert saved["play_last_update"] == "2026-07-01"
    assert saved["installer_source"] == "Google Play (com.android.vending)"
    assert saved["store_country"] == "ch"
    assert saved["store_language"] == "it"
    assert saved[state.STORE_EVIDENCE_FIELD] == evidence
    assert state.AUDIT_CHANGES_FIELD not in saved
    assert saved["saved_at"]


def test_merged_history_preserves_packages_omitted_by_targeted_recheck(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "audit_history.json"
    monkeypatch.setattr(state, "history_path", lambda: path)
    path.write_text(
        json.dumps(
            {
                "com.example.untouched": {
                    "criticality_key": "green",
                    "play_status": "available",
                    "saved_at": "2026-08-01T00:00:00+00:00",
                }
            }
        ),
        encoding="utf-8",
    )

    state.save_history_merged([_row(play_version="2.0")])
    loaded = state.load_history()

    assert "com.example.untouched" in loaded
    assert loaded["com.example.app"]["play_version"] == "2.0"
    assert loaded["com.example.app"]["play_status"] == "available"


def test_device_metadata_merged_history_adapter_uses_canonical_state_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[dict[str, object]]] = []
    monkeypatch.setattr(state, "save_history_merged", lambda rows: calls.append(rows))
    rows = [_row()]

    device_metadata.save_history_merged(rows)

    assert calls == [rows]
