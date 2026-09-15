from __future__ import annotations

from datetime import UTC, datetime

import pytest

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverCacheIdentity,
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)

PROFILE_HASH = "a" * 64
CONTEXT_HASH = "b" * 64


def _resolved(**overrides: object) -> ResolverResult:
    values: dict[str, object] = {
        "package_name": "com.example.app",
        "profile_id": "profile",
        "profile_hash": PROFILE_HASH,
        "provider": ResolverProvider.ANONYMOUS_DISPENSER,
        "status": ResolverStatus.RESOLVED,
        "requested_country": "ch",
        "requested_language": "EN",
        "version_name": "1.2.3",
        "version_code": 123,
        "fetched_at": datetime.now(UTC).isoformat(),
    }
    values.update(overrides)
    return ResolverResult(**values)  # type: ignore[arg-type]


def test_resolved_result_normalises_and_roundtrips() -> None:
    result = _resolved()
    assert result.requested_country == "CH"
    assert result.requested_language == "en"
    assert result.resolved
    assert ResolverResult.from_mapping(result.to_mapping()) == result


@pytest.mark.parametrize("version_code", [None, 0, -1, True, "12"])
def test_resolved_result_requires_positive_integer_version_code(
    version_code: object,
) -> None:
    with pytest.raises(ValueError):
        _resolved(version_code=version_code)


@pytest.mark.parametrize(
    "status",
    [
        ResolverStatus.UNAVAILABLE_FOR_PROFILE,
        ResolverStatus.AUTH_FAILED,
        ResolverStatus.RATE_LIMITED,
        ResolverStatus.TRANSPORT_ERROR,
        ResolverStatus.MALFORMED_RESPONSE,
        ResolverStatus.INCONCLUSIVE,
    ],
)
def test_unresolved_result_rejects_version_evidence(status: ResolverStatus) -> None:
    with pytest.raises(ValueError):
        _resolved(status=status, version_name="1", version_code=1)


def test_diagnostics_are_single_line() -> None:
    with pytest.raises(ValueError):
        _resolved(diagnostics="first\nsecret")


def test_cache_identity_is_deterministic_and_context_sensitive() -> None:
    base = ResolverCacheIdentity(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        requested_country="ch",
        requested_language="EN",
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=CONTEXT_HASH,
        protocol_revision="fdfe-details-v1",
    )
    same = ResolverCacheIdentity(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        requested_country="CH",
        requested_language="en",
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=CONTEXT_HASH,
        protocol_revision="fdfe-details-v1",
    )
    changed = ResolverCacheIdentity(
        package_name="com.example.app",
        profile_id="profile",
        profile_hash=PROFILE_HASH,
        requested_country="CH",
        requested_language="en",
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash="c" * 64,
        protocol_revision="fdfe-details-v1",
    )
    assert base.key == same.key
    assert base.key != changed.key
    assert len(base.key) == 64
