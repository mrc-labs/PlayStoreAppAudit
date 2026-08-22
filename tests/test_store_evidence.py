from __future__ import annotations

import pytest

import playstore_app_audit.services.play_store as play_store
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.base_window as base_ui


def test_structured_store_evidence_survives_healthy_cache_roundtrip(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    evidence = [
        {
            "role": "primary",
            "language_role": "preferred",
            "country": "ch",
            "language": "de",
            "status": "available",
            "http_status": 200,
            "source": "test",
        }
    ]
    row = {
        "app_name": "Example",
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_version": "1.0",
        play_store.STORE_EVIDENCE_FIELD: evidence,
    }

    state.update_cache([row], "ch", "de")
    loaded = state.load_fresh_cache(
        [{"app_name": "Example", "package_name": "com.example.app"}],
        "ch",
        "de",
        72,
    )

    assert loaded["com.example.app"][play_store.STORE_EVIDENCE_FIELD] == evidence


def test_internal_store_evidence_is_not_a_csv_export_column() -> None:
    assert play_store.STORE_EVIDENCE_FIELD not in base_ui.EXPORT_FIELDS
