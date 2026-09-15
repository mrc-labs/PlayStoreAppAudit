from __future__ import annotations

from typing import Any

import pytest

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services import device_specific_integration as integration
from playstore_app_audit.services.device_specific_profiles import (
    PRODUCTION_PROFILE_IDS,
    load_reference_profile,
)


ENDPOINT = "https://resolver.example/api/auth"
COUNTRY = "CH"
LANGUAGE = "en"


def _settings(
    *,
    enabled: bool = True,
    endpoint: str = ENDPOINT,
    profile_id: str = integration.DEFAULT_PROFILE_ID,
) -> dict[str, Any]:
    return {
        integration.SETTING_ENABLED: enabled,
        integration.SETTING_ENDPOINT: endpoint,
        integration.SETTING_PROFILE_ID: profile_id,
    }


def _resolved(
    *,
    version_name: str = "5.0",
    version_code: int = 101,
) -> ResolverResult:
    profile = load_reference_profile(integration.DEFAULT_PROFILE_ID)
    return ResolverResult(
        package_name="com.example.app",
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.RESOLVED,
        requested_country=COUNTRY,
        requested_language=LANGUAGE,
        version_name=version_name,
        version_code=version_code,
    )


def _unresolved(status: ResolverStatus) -> ResolverResult:
    profile = load_reference_profile(integration.DEFAULT_PROFILE_ID)
    return ResolverResult(
        package_name="com.example.app",
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=status,
        requested_country=COUNTRY,
        requested_language=LANGUAGE,
    )


@pytest.mark.parametrize(
    ("installed", "available", "expected"),
    [
        (100, 101, "Outdated"),
        (101, 101, "Match"),
        (102, 101, "Newer"),
        ("100", "101", "Outdated"),
        ("", 101, None),
        (None, 101, None),
        (True, 101, None),
        (100, 0, None),
    ],
)
def test_relationship_from_version_codes(
    installed: object,
    available: object,
    expected: str | None,
) -> None:
    assert integration.relationship_from_version_codes(installed, available) == expected


def test_disabled_resolver_makes_zero_calls_and_clears_stale_evidence() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies with device",
            "version_comparison": "Device-specific",
            integration.RESOLVED_VERSION_FIELD: "stale",
            integration.STATUS_FIELD: "resolved",
        }
    ]

    def forbidden_resolver(**_kwargs: object) -> ResolverResult | None:
        raise AssertionError("resolver must not be called")

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(enabled=False),
        country=COUNTRY,
        language=LANGUAGE,
        resolver=forbidden_resolver,
    )

    assert summary.attempted == 0
    assert rows[0]["play_version"] == "Varies with device"
    assert rows[0]["version_comparison"] == "Device-specific"
    assert rows[0][integration.RESOLVED_VERSION_FIELD] == ""
    assert rows[0][integration.STATUS_FIELD] == ""


def test_missing_endpoint_is_fail_closed_without_network() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies with device",
            "version_comparison": "Device-specific",
        }
    ]

    def forbidden_resolver(**_kwargs: object) -> ResolverResult | None:
        raise AssertionError("resolver must not be called")

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(endpoint=""),
        country=COUNTRY,
        language=LANGUAGE,
        resolver=forbidden_resolver,
    )

    assert summary.eligible == 1
    assert summary.attempted == 0
    assert summary.configuration_error == "invalid_resolver_configuration"
    assert rows[0][integration.STATUS_FIELD] == ""


def test_ordinary_store_version_never_invokes_resolver() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "5.0",
            "version_comparison": "Match",
        }
    ]

    def forbidden_resolver(**_kwargs: object) -> ResolverResult | None:
        raise AssertionError("resolver must not be called")

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        resolver=forbidden_resolver,
    )

    assert summary.eligible == 0
    assert summary.attempted == 0
    assert rows[0]["version_comparison"] == "Match"


def test_resolved_version_code_is_authoritative_and_raw_store_fact_is_preserved() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies with device",
            "installed_version": "5.0",
            "installed_version_code": "100",
            "version_comparison": "Device-specific",
        }
    ]

    calls: list[dict[str, object]] = []

    def resolver(**kwargs: object) -> ResolverResult:
        calls.append(dict(kwargs))
        return _resolved(version_name="5.0", version_code=101)

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        use_cache=False,
        max_workers=1,
        resolver=resolver,
    )

    assert summary == integration.ResolverIntegrationSummary(
        eligible=1,
        attempted=1,
        resolved=1,
    )
    assert len(calls) == 1
    assert calls[0]["use_cache"] is False
    assert rows[0]["play_version"] == "Varies with device"
    assert rows[0][integration.RESOLVED_VERSION_FIELD] == "5.0"
    assert rows[0][integration.RESOLVED_VERSION_CODE_FIELD] == 101
    assert rows[0][integration.STATUS_FIELD] == "resolved"
    assert rows[0][integration.PROFILE_ID_FIELD] == integration.DEFAULT_PROFILE_ID
    assert "Android 13 / API 33" in rows[0][integration.PROFILE_FIELD]
    assert rows[0]["version_comparison"] == "Outdated"


def test_unresolved_result_preserves_conservative_relationship() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies with device",
            "installed_version_code": "100",
            "version_comparison": "Device-specific",
        }
    ]

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        use_cache=False,
        max_workers=1,
        resolver=lambda **_kwargs: _unresolved(ResolverStatus.AUTH_FAILED),
    )

    assert summary.resolved == 0
    assert summary.unresolved == 1
    assert rows[0][integration.STATUS_FIELD] == "auth_failed"
    assert rows[0][integration.RESOLVED_VERSION_FIELD] == ""
    assert rows[0][integration.RESOLVED_VERSION_CODE_FIELD] == ""
    assert rows[0]["version_comparison"] == "Device-specific"


def test_missing_installed_version_code_does_not_fabricate_comparison() -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies",
            "installed_version": "5.0",
            "installed_version_code": "",
            "version_comparison": "Device-specific",
        }
    ]

    integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        use_cache=False,
        max_workers=1,
        resolver=lambda **_kwargs: _resolved(version_name="5.0", version_code=101),
    )

    assert rows[0][integration.RESOLVED_VERSION_FIELD] == "5.0"
    assert rows[0]["version_comparison"] == "Device-specific"


def test_cache_hit_is_equivalent_to_live_result_without_resolver_call(monkeypatch) -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies by device",
            "installed_version_code": "101",
            "version_comparison": "Device-specific",
        }
    ]
    cached = _resolved(version_code=101)
    monkeypatch.setattr(integration, "load_cached_result", lambda *_args, **_kwargs: cached)

    def forbidden_resolver(**_kwargs: object) -> ResolverResult | None:
        raise AssertionError("cache hit must avoid live resolver")

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        resolver=forbidden_resolver,
    )

    assert summary.cache_hits == 1
    assert summary.attempted == 0
    assert summary.resolved == 1
    assert rows[0]["version_comparison"] == "Match"
    assert rows[0][integration.STATUS_FIELD] == "resolved"


def test_live_result_is_persisted_only_after_worker_returns(monkeypatch) -> None:
    rows = [
        {
            "package_name": "com.example.app",
            "play_version": "Varies with device",
            "installed_version_code": "100",
            "version_comparison": "Device-specific",
        }
    ]
    stored: list[tuple[object, ResolverResult]] = []
    monkeypatch.setattr(integration, "load_cached_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        integration,
        "store_resolved_result",
        lambda identity, result: stored.append((identity, result)) or True,
    )

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings=_settings(),
        country=COUNTRY,
        language=LANGUAGE,
        max_workers=4,
        resolver=lambda **_kwargs: _resolved(version_code=101),
    )

    assert summary.attempted == 1
    assert summary.resolved == 1
    assert len(stored) == 1
    assert stored[0][1].version_code == 101


def test_profile_choices_are_restricted_to_production_profiles() -> None:
    choices = integration.profile_choices()
    assert tuple(profile_id for profile_id, _label in choices) == PRODUCTION_PROFILE_IDS
    assert any(
        "OnePlus 8 Pro" in label and "API 29" in label
        for _profile_id, label in choices
    )
    assert any(
        "Galaxy S20+" in label and "API 33" in label
        for _profile_id, label in choices
    )
