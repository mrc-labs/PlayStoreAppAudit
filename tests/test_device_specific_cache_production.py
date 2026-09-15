from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverCacheIdentity,
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services.device_specific_cache import (
    clear_resolver_cache,
    load_cached_result,
    resolver_cache_path,
    store_resolved_result,
)
from playstore_app_audit.services.state import cache_path


PROFILE_HASH = "a" * 64
CONTEXT_HASH = "b" * 64


def _identity() -> ResolverCacheIdentity:
    return ResolverCacheIdentity(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        requested_country="CH",
        requested_language="en",
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=CONTEXT_HASH,
        protocol_revision="fdfe-details-v1",
    )


def _result(*, fetched_at: str | None = None, diagnostics: str = "") -> ResolverResult:
    return ResolverResult(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.RESOLVED,
        requested_country="CH",
        requested_language="en",
        version_name="1.2.3",
        version_code=123,
        fetched_at=fetched_at or datetime.now(UTC).isoformat(),
        diagnostics=diagnostics,
    )


def test_resolver_cache_path_is_separate_from_store_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "playstore_app_audit.services.device_specific_cache.app_data_dir",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "playstore_app_audit.services.state.app_data_dir",
        lambda: tmp_path,
    )
    assert resolver_cache_path().name == "device_specific_resolver_cache.json"
    assert cache_path().name == "audit_cache.json"
    assert resolver_cache_path() != cache_path()


def test_resolved_result_roundtrips_and_expires(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    identity = _identity()
    now = datetime.now(UTC)
    result = _result(fetched_at=(now - timedelta(hours=1)).isoformat())
    assert store_resolved_result(identity, result, path=path)
    persisted = path.read_text(encoding="utf-8")
    assert "Bearer" not in persisted
    assert "resolver.example" not in persisted
    assert load_cached_result(identity, path=path, now=now) == result
    assert load_cached_result(
        identity,
        path=path,
        now=now + timedelta(hours=25),
    ) is None


def test_resolved_diagnostics_are_not_persisted(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    identity = _identity()
    sensitive = "Bearer-test-token gsfId-123 dummy@example.invalid"
    result = _result(diagnostics=sensitive)

    assert store_resolved_result(identity, result, path=path)
    persisted = path.read_text(encoding="utf-8")
    assert sensitive not in persisted
    assert "Bearer-test-token" not in persisted
    assert "dummy@example.invalid" not in persisted

    loaded = load_cached_result(identity, path=path)
    assert loaded is not None
    assert loaded.diagnostics == ""
    assert loaded.version_name == result.version_name
    assert loaded.version_code == result.version_code


def test_unresolved_result_is_never_persisted(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    identity = _identity()
    unresolved = ResolverResult(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.TRANSPORT_ERROR,
        requested_country="CH",
        requested_language="en",
        diagnostics="play_transport_error",
    )
    assert not store_resolved_result(identity, unresolved, path=path)
    assert not path.exists()


def test_corrupt_or_unknown_schema_cache_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    path.write_text("{bad-json", encoding="utf-8")
    assert load_cached_result(_identity(), path=path) is None

    path.write_text(
        json.dumps({"schema": 999, "entries": {}}),
        encoding="utf-8",
    )
    assert load_cached_result(_identity(), path=path) is None


def test_identity_mismatch_is_not_reused(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    identity = _identity()
    assert store_resolved_result(identity, _result(), path=path)
    other = ResolverCacheIdentity(
        package_name="com.example.other",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        requested_country="CH",
        requested_language="en",
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=CONTEXT_HASH,
        protocol_revision="fdfe-details-v1",
    )
    assert load_cached_result(other, path=path) is None


def test_clear_cache_writes_only_resolver_schema(tmp_path: Path) -> None:
    path = tmp_path / "resolver.json"
    clear_resolver_cache(path=path)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "schema": 1,
        "entries": {},
    }
