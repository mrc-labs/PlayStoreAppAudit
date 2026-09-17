from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.domain.local_artifacts import LocalArtifact, LocalArtifactFormat
from playstore_app_audit.services import device_specific_integration as integration
from playstore_app_audit.services import local_apk_audit
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.device_specific_profiles import load_reference_profile
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService

ENDPOINT = "https://resolver.example/api/auth"
COUNTRY = "ch"
LANGUAGE = "en"


class FakeStore:
    def __init__(self, play_version: str) -> None:
        self.play_version = play_version

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback=None,
        pause_event=None,
        cancel_event=None,
        row_completed_callback=None,
    ) -> list[dict[str, Any]]:
        del progress_callback, pause_event, cancel_event
        rows = [
            {
                "package_name": app["package_name"],
                "play_status": "available",
                "play_version": self.play_version,
                "store_country": config.country,
                "store_language": config.language,
            }
            for app in apps
        ]
        if row_completed_callback is not None:
            for index, row in enumerate(rows):
                row_completed_callback(index, dict(row))
        return rows


def _artifact(
    *,
    version_name: str = "1.0",
    version_code: int | str = 100,
    version_code_major: int | str | None = None,
) -> LocalArtifact:
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256="a" * 64,
        package_id="com.example.app",
        application_label="Example App",
        application_label_reference=None,
        version_name=version_name,
        version_name_reference=None,
        version_code=version_code,
        version_code_major=version_code_major,
        min_sdk=23,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=(),
        features=(),
        icon_reference=None,
        file_name="example.apk",
        canonical_path=Path("C:/fixtures/example.apk"),
        file_size=1234,
        modified_at=datetime(2026, 9, 17, tzinfo=UTC),
    )


def _settings() -> dict[str, object]:
    return {
        "cache_enabled": False,
        integration.SETTING_ENABLED: True,
        integration.SETTING_ENDPOINT: ENDPOINT,
        integration.SETTING_PROFILE_ID: integration.DEFAULT_PROFILE_ID,
    }


def _resolved(*, version_code: int) -> ResolverResult:
    profile = load_reference_profile(integration.DEFAULT_PROFILE_ID)
    return ResolverResult(
        package_name="com.example.app",
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.RESOLVED,
        requested_country=COUNTRY,
        requested_language=LANGUAGE,
        version_name="2.0",
        version_code=version_code,
    )


def _service(play_version: str) -> LocalArtifactStoreService:
    return LocalArtifactStoreService(
        store_service=FakeStore(play_version),
        alternative_runner=lambda _rows, _settings, **_kwargs: [],
    )


def _disable_resolver_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        integration,
        "load_cached_result",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        integration,
        "store_resolved_result",
        lambda *_args, **_kwargs: True,
    )


def test_local_apk_device_specific_resolution_preserves_raw_store_and_uses_version_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    calls: list[dict[str, object]] = []

    def resolver(**kwargs: object) -> ResolverResult:
        calls.append(dict(kwargs))
        return _resolved(version_code=101)

    monkeypatch.setattr(integration, "resolve_if_device_specific", resolver)

    result = _service("Varies with device").collect(
        [_artifact(version_code=100)],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = local_apk_audit.association_result_rows(result.associations)[0]

    assert len(calls) == 1
    assert calls[0]["package_name"] == "com.example.app"
    assert calls[0]["use_cache"] is False
    assert row["play_version"] == "Varies with device"
    assert row[integration.RESOLVED_VERSION_FIELD] == "2.0"
    assert row[integration.RESOLVED_VERSION_CODE_FIELD] == 101
    assert row[integration.STATUS_FIELD] == "resolved"
    assert row["local_apk_version_comparison"] == "Outdated"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Outdated (DS)"


def test_local_apk_device_specific_match_keeps_raw_semantics_and_marks_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **_kwargs: _resolved(version_code=100),
    )

    result = _service("Varies with device").collect(
        [_artifact(version_code=100)],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = local_apk_audit.association_result_rows(result.associations)[0]

    assert row["local_apk_version_comparison"] == "Match"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Match (DS)"


def test_ordinary_local_apk_store_row_causes_zero_resolver_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)

    def forbidden_resolver(**_kwargs: object) -> ResolverResult:
        raise AssertionError("ordinary Store rows must not invoke the resolver")

    monkeypatch.setattr(integration, "resolve_if_device_specific", forbidden_resolver)

    result = _service("2.0").collect(
        [_artifact(version_name="1.0", version_code=100)],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = local_apk_audit.association_result_rows(result.associations)[0]

    assert row["play_version"] == "2.0"
    assert row[integration.RESOLVED_VERSION_FIELD] == ""
    assert row[integration.STATUS_FIELD] == ""
    assert row["local_apk_version_comparison"] == "Outdated"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Outdated"


def test_local_apk_resolver_failure_preserves_successful_raw_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)

    def failing_resolver(**_kwargs: object) -> ResolverResult:
        raise RuntimeError("synthetic resolver failure")

    monkeypatch.setattr(integration, "resolve_if_device_specific", failing_resolver)

    result = _service("Varies by device").collect(
        [_artifact(version_code=100)],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = local_apk_audit.association_result_rows(result.associations)[0]

    assert row["play_status"] == "available"
    assert row["play_version"] == "Varies by device"
    assert row[integration.RESOLVED_VERSION_FIELD] == ""
    assert row[integration.RESOLVED_VERSION_CODE_FIELD] == ""
    assert row[integration.STATUS_FIELD] == "inconclusive"
    assert row["local_apk_version_comparison"] == "Device-specific"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Device-specific"


def test_local_apk_prefers_long_version_code_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **_kwargs: _resolved(version_code=100),
    )

    artifact = _artifact(version_code=5, version_code_major=1)
    assert artifact.long_version_code == (1 << 32) | 5

    result = _service("Varies").collect(
        [artifact],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = local_apk_audit.association_result_rows(result.associations)[0]

    assert row[integration.RESOLVED_VERSION_CODE_FIELD] == 100
    assert row["local_apk_version_comparison"] == "Newer"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Newer (DS)"
