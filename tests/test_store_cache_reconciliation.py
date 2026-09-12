from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from playstore_app_audit.services import state


class _FixedDateTime(datetime):
    current = datetime(2026, 9, 12, 10, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):  # noqa: ANN001, ANN206 - mirrors datetime.now
        value = cls.current
        return value if tz is None else value.astimezone(tz)


@pytest.fixture
def cache_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: path)
    monkeypatch.setattr(state, "datetime", _FixedDateTime)
    return path


def _row(
    package: str,
    *,
    status: str = "available",
    update: str = "2026-09-01",
    title: str = "Current",
) -> dict[str, object]:
    return {
        "package_name": package,
        "play_status": status,
        "play_last_update": update,
        "play_title": title,
    }


def _seed(cache_file: Path, rows: list[dict[str, object]], fetched_at: str) -> None:
    payload = {
        state._cache_key("us", "en", str(row["package_name"])): {
            "fetched_at": fetched_at,
            "row": row,
        }
        for row in rows
    }
    cache_file.write_text(json.dumps(payload), encoding="utf-8")


def _payload(cache_file: Path) -> dict[str, object]:
    return json.loads(cache_file.read_text(encoding="utf-8"))


def test_update_cache_restores_45_day_storage_hygiene_without_touching_recent_entry(
    cache_file: Path,
) -> None:
    old_package = "com.example.old"
    recent_package = "com.example.recent"
    malformed_package = "com.example.malformed"
    live_package = "com.example.live"
    recent_fetched_at = "2026-09-01T10:00:00+00:00"
    payload = {
        state._cache_key("us", "en", old_package): {
            "fetched_at": "2026-07-28T09:59:59+00:00",
            "row": _row(old_package),
        },
        state._cache_key("us", "en", recent_package): {
            "fetched_at": recent_fetched_at,
            "row": _row(recent_package, title="Recent untouched"),
        },
        state._cache_key("us", "en", malformed_package): {
            "fetched_at": "not-a-timestamp",
            "row": _row(malformed_package),
        },
    }
    cache_file.write_text(json.dumps(payload), encoding="utf-8")

    state.update_cache([_row(live_package)], "us", "en")

    stored = _payload(cache_file)
    assert state._cache_key("us", "en", old_package) not in stored
    assert state._cache_key("us", "en", malformed_package) not in stored
    recent = stored[state._cache_key("us", "en", recent_package)]
    assert recent["fetched_at"] == recent_fetched_at
    assert recent["row"]["play_title"] == "Recent untouched"
    assert state._cache_key("us", "en", live_package) in stored


def test_live_healthy_available_replaces_exact_row_with_new_fetched_at(
    cache_file: Path,
) -> None:
    package = "com.example.available"
    old_fetched_at = "2026-09-12T09:00:00+00:00"
    _seed(cache_file, [_row(package, title="Old")], old_fetched_at)

    state.update_cache([_row(package, title="New")], "us", "en")

    entry = _payload(cache_file)[state._cache_key("us", "en", package)]
    assert entry["row"]["play_title"] == "New"
    assert entry["fetched_at"] == _FixedDateTime.current.isoformat()
    assert entry["fetched_at"] != old_fetched_at


@pytest.mark.parametrize(
    ("status", "update"),
    [
        ("not_found_in_checked_countries", ""),
        ("available_in_other_country", "2026-09-01"),
        ("available_in_fallback_locale_only", "2026-09-01"),
        ("available", ""),
    ],
)
def test_conclusive_non_cacheable_live_result_removes_exact_stale_available(
    cache_file: Path, status: str, update: str
) -> None:
    package = "com.example.superseded"
    _seed(
        cache_file,
        [_row(package), _row("com.example.unrelated")],
        "2026-09-12T09:00:00+00:00",
    )

    state.update_cache([_row(package, status=status, update=update)], "us", "en")

    payload = _payload(cache_file)
    assert state._cache_key("us", "en", package) not in payload
    assert state._cache_key("us", "en", "com.example.unrelated") in payload
    assert state.load_fresh_cache(
        [{"package_name": package, "app_name": "Superseded"}], "us", "en", 24
    ) == {}


@pytest.mark.parametrize(
    "status",
    [
        "multi_country_check_inconclusive",
        "request_error",
        "http_error",
        "check_failed",
        "unexpected_error",
    ],
)
def test_transient_live_result_preserves_old_row_and_fetched_at(
    cache_file: Path, status: str
) -> None:
    package = "com.example.transient"
    old_fetched_at = "2026-09-12T09:00:00+00:00"
    _seed(cache_file, [_row(package, title="Old")], old_fetched_at)

    state.update_cache([_row(package, status=status, update="")], "us", "en")

    entry = _payload(cache_file)[state._cache_key("us", "en", package)]
    assert entry["row"]["play_title"] == "Old"
    assert entry["fetched_at"] == old_fetched_at


def test_partial_stop_or_failure_reconciles_only_completed_packages(
    cache_file: Path,
) -> None:
    old_fetched_at = "2026-09-12T09:00:00+00:00"
    packages = ["com.example.a", "com.example.b", "com.example.c"]
    _seed(cache_file, [_row(package, title="Old") for package in packages], old_fetched_at)

    state.update_cache(
        [
            _row(packages[0], title="New"),
            _row(packages[1], status="not_found_in_checked_countries", update=""),
        ],
        "us",
        "en",
    )

    payload = _payload(cache_file)
    first = payload[state._cache_key("us", "en", packages[0])]
    assert first["row"]["play_title"] == "New"
    assert first["fetched_at"] == _FixedDateTime.current.isoformat()
    assert state._cache_key("us", "en", packages[1]) not in payload
    untouched = payload[state._cache_key("us", "en", packages[2])]
    assert untouched["row"]["play_title"] == "Old"
    assert untouched["fetched_at"] == old_fetched_at
