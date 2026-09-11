from __future__ import annotations

import json
from pathlib import Path

import pytest

from playstore_app_audit.services import state


def test_legacy_cache_default_migration_is_persisted_on_first_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"cache_ttl_hours": 72}', encoding="utf-8")
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)

    settings = state.load_settings()
    persisted = json.loads(settings_file.read_text(encoding="utf-8"))

    assert settings["cache_ttl_hours"] == state.DEFAULT_CACHE_TTL_HOURS
    assert persisted["cache_ttl_hours"] == state.DEFAULT_CACHE_TTL_HOURS
    assert persisted[state.CACHE_TTL_DEFAULT_MIGRATION_KEY] is True


@pytest.mark.parametrize("value", [12, 24, 48, 168])
def test_custom_cache_ttls_are_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: int,
) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"cache_ttl_hours": value}),
        encoding="utf-8",
    )
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)

    assert state.load_settings()["cache_ttl_hours"] == value
