from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import playstore_app_audit.services.local_artifact_store as local_store_module
from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionResult,
    AlternativeDistributionState,
)
from playstore_app_audit.domain.local_artifacts import LocalArtifact, LocalArtifactFormat
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService


def _artifact(package_id: str, sha256: str, index: int) -> LocalArtifact:
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256=sha256,
        package_id=package_id,
        application_label=f"Artifact {index}",
        application_label_reference=None,
        version_name="1.0",
        version_name_reference=None,
        version_code=index,
        version_code_major=None,
        min_sdk=23,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=(),
        features=(),
        icon_reference=None,
        file_name=f"artifact-{index}.apk",
        canonical_path=Path(f"C:/fixtures/artifact-{index}.apk"),
        file_size=100 + index,
        modified_at=datetime(2026, 9, 1, tzinfo=UTC),
    )


@dataclass
class FakeStoreService:
    statuses: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, dict[str, str]] = field(default_factory=dict)
    calls: list[tuple[list[str], AuditConfig]] = field(default_factory=list)

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback=None,
        pause_event=None,
        cancel_event=None,
        row_completed_callback=None,
    ) -> list[dict[str, Any]]:
        del progress_callback, pause_event, cancel_event, row_completed_callback
        packages = [app["package_name"] for app in apps]
        self.calls.append((packages, config))
        return [
            {
                "app_name": package,
                "package_name": package,
                "play_status": self.statuses.get(package, "available"),
                "store_country": config.country,
                "store_language": config.language,
                "details": {"source": "fake"},
                **self.metadata.get(package, {}),
            }
            for package in packages
        ]


def _no_alternatives(rows, settings, **kwargs) -> list[str]:
    del rows, settings, kwargs
    return []


def test_duplicate_packages_are_looked_up_once_and_fanned_out_by_identity() -> None:
    first = _artifact("com.example.same", "a" * 64, 1)
    second = _artifact("com.example.same", "b" * 64, 2)
    other = _artifact("com.example.other", "c" * 64, 3)
    store = FakeStoreService()
    service = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    )

    result = service.collect(
        [first, second, other],
        AuditConfig(country="us", language="en"),
        {"cache_enabled": False},
    )

    assert store.calls[0][0] == ["com.example.same", "com.example.other"]
    assert [item.artifact.artifact_sha256 for item in result.associations] == [
        "a" * 64,
        "b" * 64,
        "c" * 64,
    ]
    assert [item.package_lookup_key for item in result.packages] == [
        "com.example.same",
        "com.example.other",
    ]
    assert result.associations[0].package_evidence is result.associations[1].package_evidence
    assert result.associations[2].package_evidence is result.packages[1]


def test_progress_callback_exposes_store_rows_without_sending_local_evidence() -> None:
    artifact = _artifact("com.example.private", "9" * 64, 1)

    class CallbackStore:
        def __init__(self) -> None:
            self.apps: list[dict[str, str]] = []

        def audit(self, apps, config, _progress=None, *, row_completed_callback, **_kwargs):
            self.apps = [dict(app) for app in apps]
            row = {
                "package_name": apps[0]["package_name"],
                "play_status": "available",
                "play_version": "2.0",
                "store_country": config.country,
            }
            row_completed_callback(0, row)
            return [row]

    store = CallbackStore()
    completed: list[tuple[str, dict[str, Any]]] = []
    LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    ).collect(
        [artifact],
        AuditConfig(),
        {"cache_enabled": False},
        row_completed_callback=lambda package, row: completed.append((package, row)),
    )

    assert store.apps == [
        {"app_name": "com.example.private", "package_name": "com.example.private"}
    ]
    assert completed[0][0] == "com.example.private"
    remote_payload = repr(store.apps)
    assert str(artifact.canonical_path) not in remote_payload
    assert artifact.artifact_sha256 not in remote_payload


def test_store_failure_row_is_isolated_and_store_evidence_is_immutable() -> None:
    store = FakeStoreService(
        statuses={
            "com.example.good": "available",
            "com.example.failed": "request_error",
        }
    )
    service = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    )

    result = service.collect(
        [
            _artifact("com.example.good", "d" * 64, 1),
            _artifact("com.example.failed", "e" * 64, 2),
        ],
        AuditConfig(),
        {"cache_enabled": False},
    )

    assert [package.play_status for package in result.packages] == ["available", "request_error"]
    assert result.associations[0].package_evidence is result.packages[0]
    assert result.associations[1].package_evidence is result.packages[1]
    with pytest.raises(TypeError):
        result.packages[0].store_result["play_status"] = "changed"  # type: ignore[index]
    with pytest.raises(TypeError):
        result.packages[0].store_result["details"]["source"] = "changed"  # type: ignore[index]


def test_cache_is_applied_once_per_unique_package_and_only_live_rows_are_updated() -> None:
    artifacts = [
        _artifact("com.example.cached", "f" * 64, 1),
        _artifact("com.example.cached", "0" * 64, 2),
        _artifact("com.example.live", "1" * 64, 3),
    ]
    cache_calls: list[tuple[list[str], str, str, int]] = []
    update_calls: list[tuple[list[str], str, str]] = []

    def load_cache(apps, country, language, ttl):
        cache_calls.append(([item["package_name"] for item in apps], country, language, ttl))
        return {
            "com.example.cached": {
                "package_name": "com.example.cached",
                "play_status": "available",
                "cache_hit": True,
            }
        }

    def update_cache(rows, country, language):
        update_calls.append(([str(row["package_name"]) for row in rows], country, language))

    store = FakeStoreService()
    result = LocalArtifactStoreService(
        store_service=store,
        cache_loader=load_cache,
        cache_updater=update_cache,
        alternative_runner=_no_alternatives,
    ).collect(
        artifacts,
        AuditConfig(country="ch", language="it"),
        {"cache_enabled": True, "cache_ttl_hours": 12},
    )

    assert cache_calls == [
        (["com.example.cached", "com.example.live"], "ch", "it", 12)
    ]
    assert store.calls[0][0] == ["com.example.live"]
    assert update_calls == [(["com.example.live"], "ch", "it")]
    assert result.associations[0].package_evidence is result.associations[1].package_evidence


def test_live_local_apk_rows_retain_canonical_icon_metadata_before_cache_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached_rows: list[dict[str, Any]] = []
    monkeypatch.setattr(
        local_store_module.app_icon_metadata,
        "enrich_rows_with_store_metadata",
        lambda rows: rows,
    )
    service = LocalArtifactStoreService(
        store_service=FakeStoreService(
            metadata={
                "com.example.live": {
                    "play_icon_url": "https://example.invalid/icon.png",
                    "developer": "Example Developer",
                }
            }
        ),
        cache_updater=lambda rows, _country, _language: cached_rows.extend(rows),
        alternative_runner=_no_alternatives,
    )

    result = service.collect(
        [_artifact("com.example.live", "2" * 64, 1)],
        AuditConfig(country="it", language="en"),
        {"cache_enabled": True},
    )

    assert cached_rows[0]["play_icon_url"] == "https://example.invalid/icon.png"
    assert result.packages[0].store_result["play_icon_url"] == (
        "https://example.invalid/icon.png"
    )
    assert result.packages[0].store_result["developer"] == "Example Developer"


def test_different_lookup_contexts_are_not_coalesced() -> None:
    artifact = _artifact("com.example.context", "2" * 64, 1)
    store = FakeStoreService()
    service = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    )

    us = service.collect(
        [artifact],
        AuditConfig(country="us", language="en"),
        {"cache_enabled": False},
    )
    italy = service.collect(
        [artifact],
        AuditConfig(country="it", language="it"),
        {"cache_enabled": False},
    )

    assert [(call[1].country, call[1].language) for call in store.calls] == [
        ("us", "en"),
        ("it", "it"),
    ]
    assert us.packages[0].store_result["store_country"] == "us"
    assert italy.packages[0].store_result["store_country"] == "it"


@dataclass
class FakeProvider:
    provider_id: str = "fdroid_main"
    provider_name: str = "F-Droid"
    cache_namespace: str = "fake-fdroid"
    calls: list[str] = field(default_factory=list)

    def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
        del timeout
        self.calls.append(package_id)
        return AlternativeDistributionResult(
            provider_id=self.provider_id,
            provider_name=self.provider_name,
            queried_package_id=package_id,
            state=AlternativeDistributionState.AVAILABLE,
            provenance="live",
        )


def test_alternative_provider_runs_once_only_for_definitive_play_absence(tmp_path) -> None:
    missing_one = _artifact("com.example.missing", "3" * 64, 1)
    missing_two = _artifact("com.example.missing", "4" * 64, 2)
    inconclusive = _artifact("com.example.unknown", "5" * 64, 3)
    provider = FakeProvider()
    store = FakeStoreService(
        statuses={
            "com.example.missing": "not_found_in_checked_countries",
            "com.example.unknown": "multi_country_check_inconclusive",
        }
    )

    result = LocalArtifactStoreService(store_service=store).collect(
        [missing_one, missing_two, inconclusive],
        AuditConfig(),
        {"cache_enabled": False},
        providers=[provider],
        provider_cache_file=tmp_path / "alternative.json",
    )

    assert provider.calls == ["com.example.missing"]
    assert result.packages[0].alternative_distribution[0].state is AlternativeDistributionState.AVAILABLE
    assert result.packages[1].alternative_distribution == ()
    assert result.associations[0].package_evidence is result.associations[1].package_evidence


def test_cancelled_missing_store_rows_keep_artifact_associations() -> None:
    class EmptyStore(FakeStoreService):
        def audit(self, apps, config, *args, **kwargs):
            self.calls.append(([app["package_name"] for app in apps], config))
            return []

    artifact = _artifact("com.example.cancelled", "6" * 64, 1)
    result = LocalArtifactStoreService(
        store_service=EmptyStore(),
        alternative_runner=_no_alternatives,
    ).collect(
        [artifact],
        AuditConfig(),
        {"cache_enabled": False},
    )

    assert result.packages == ()
    assert result.associations[0].artifact is artifact
    assert result.associations[0].package_evidence is None
