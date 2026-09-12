from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from playstore_app_audit.services import local_apk_source, state


def test_healthy_cache_default_is_24_hours(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)

    assert state.load_settings()["cache_ttl_hours"] == 24


def test_legacy_72_hour_default_migrates_once_but_later_explicit_72_is_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"cache_ttl_hours": 72}), encoding="utf-8")
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)

    migrated = state.load_settings()
    assert migrated["cache_ttl_hours"] == 24

    # The migration must be distinguishable from a later deliberate user choice.
    migrated["cache_ttl_hours"] = 72
    state.save_settings(migrated)
    assert state.load_settings()["cache_ttl_hours"] == 72


def test_cache_reads_do_not_extend_the_original_fetched_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    package = "com.example.cached"
    fetched_at = datetime.now(UTC).isoformat()
    key = state._cache_key("it", "it", package)
    cache_file.write_text(
        json.dumps(
            {
                key: {
                    "fetched_at": fetched_at,
                    "row": {
                        "package_name": package,
                        "play_status": "available",
                        "play_last_update": "2026-09-01",
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    before = cache_file.read_text(encoding="utf-8")

    rows = state.load_fresh_cache(
        [{"package_name": package, "app_name": "Cached"}],
        "it",
        "it",
        24,
    )

    assert rows[package]["cache_hit"] is True
    assert cache_file.read_text(encoding="utf-8") == before
    persisted = json.loads(cache_file.read_text(encoding="utf-8"))
    assert persisted[key]["fetched_at"] == fetched_at


def test_explicit_local_package_selection_accepts_installable_archive_containers(
    tmp_path: Path,
) -> None:
    supported = [
        tmp_path / "standalone.apk",
        tmp_path / "bundle.apks",
        tmp_path / "bundle.apkm",
        tmp_path / "bundle.xapk",
    ]
    excluded = tmp_path / "publishing.aab"
    for path in [*supported, excluded]:
        path.write_bytes(b"synthetic")

    selected = local_apk_source.normalise_explicit_apks([*supported, excluded])

    assert set(selected) == {path.resolve() for path in supported}
    assert excluded.resolve() not in selected


def test_folder_discovery_finds_supported_local_package_types_but_not_aab(
    tmp_path: Path,
) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    supported = [
        tmp_path / "one.apk",
        nested / "two.apks",
        nested / "three.apkm",
        nested / "four.xapk",
    ]
    excluded = nested / "publishing.aab"
    for path in [*supported, excluded]:
        path.write_bytes(b"synthetic")

    result = local_apk_source.discover_folder_apks(tmp_path)

    assert result.cancelled is False
    assert set(result.paths) == {path.resolve() for path in supported}
    assert excluded.resolve() not in result.paths
