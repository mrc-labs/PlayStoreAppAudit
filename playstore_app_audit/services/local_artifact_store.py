from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, Protocol

from playstore_app_audit.domain.alternative_distribution import AlternativeDistributionProvider
from playstore_app_audit.domain.local_artifact_store import (
    LocalArtifactStoreAssociation,
    LocalArtifactStoreFanoutResult,
    PackageStoreEvidence,
)
from playstore_app_audit.domain.local_artifacts import LocalArtifact
from playstore_app_audit.services import alternative_distribution, state
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.play_store import PlayStoreService


class StoreAuditService(Protocol):
    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback: Callable[[int, int, str], None] | None = None,
        pause_event: threading.Event | None = None,
        cancel_event: threading.Event | None = None,
        row_completed_callback: Callable[[int, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]: ...


CacheLoader = Callable[
    [list[dict[str, str]], str, str, int],
    dict[str, dict[str, Any]],
]
CacheUpdater = Callable[[list[dict[str, Any]], str, str], None]


class AlternativeDistributionRunner(Protocol):
    def __call__(
        self,
        rows: list[dict[str, Any]],
        settings: Mapping[str, Any],
        *,
        pause_event: threading.Event,
        cancel_event: threading.Event,
        force_refresh: bool = False,
        providers: list[AlternativeDistributionProvider] | None = None,
        cache_file: Path | None = None,
    ) -> list[str]: ...


def _cache_ttl(settings: Mapping[str, Any]) -> int:
    try:
        return max(0, min(24 * 30, int(settings.get("cache_ttl_hours", 72))))
    except (TypeError, ValueError):
        return 72


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


class LocalArtifactStoreService:
    """Resolve package evidence once and fan it out to immutable APK artifacts.

    A call represents one homogeneous Store/provider lookup context. Country,
    language, provider configuration, and refresh policy therefore apply to the
    entire call; callers use separate calls for different contexts.
    """

    def __init__(
        self,
        *,
        store_service: StoreAuditService | None = None,
        cache_loader: CacheLoader | None = None,
        cache_updater: CacheUpdater | None = None,
        alternative_runner: AlternativeDistributionRunner | None = None,
    ) -> None:
        self._store_service = store_service or PlayStoreService()
        self._cache_loader = cache_loader or state.load_fresh_cache
        self._cache_updater = cache_updater or state.update_cache
        self._alternative_runner = (
            alternative_runner or alternative_distribution.run_alternative_distribution_phase
        )

    def collect(
        self,
        artifacts: Iterable[LocalArtifact],
        config: AuditConfig,
        settings: Mapping[str, Any],
        *,
        force_refresh: bool = False,
        pause_event: threading.Event | None = None,
        cancel_event: threading.Event | None = None,
        providers: list[AlternativeDistributionProvider] | None = None,
        provider_cache_file: Path | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> LocalArtifactStoreFanoutResult:
        ordered_artifacts = tuple(artifacts)
        unique_apps: list[dict[str, str]] = []
        seen_packages: set[str] = set()
        for artifact in ordered_artifacts:
            package_id = artifact.package_lookup_key
            if package_id in seen_packages:
                continue
            seen_packages.add(package_id)
            unique_apps.append({"app_name": package_id, "package_name": package_id})

        if not unique_apps:
            return LocalArtifactStoreFanoutResult((), ())

        running = pause_event or threading.Event()
        if pause_event is None:
            running.set()
        cancelled = cancel_event or threading.Event()
        cache_enabled = bool(settings.get("cache_enabled", True))
        cached = (
            self._cache_loader(
                unique_apps,
                config.country,
                config.language,
                _cache_ttl(settings),
            )
            if cache_enabled and not force_refresh
            else {}
        )
        live_apps = [app for app in unique_apps if app["package_name"] not in cached]
        live_rows = (
            self._store_service.audit(
                live_apps,
                config,
                progress_callback,
                pause_event=running,
                cancel_event=cancelled,
            )
            if live_apps
            else []
        )
        if cache_enabled and live_rows:
            self._cache_updater(live_rows, config.country, config.language)

        rows_by_package: dict[str, dict[str, Any]] = {
            package_id: dict(row) for package_id, row in cached.items()
        }
        for row in live_rows:
            row_package = row.get("package_name")
            if isinstance(row_package, str) and row_package in seen_packages:
                rows_by_package[row_package] = row

        ordered_rows = [
            rows_by_package[app["package_name"]]
            for app in unique_apps
            if app["package_name"] in rows_by_package
        ]
        issues: list[str] = []
        if not cancelled.is_set():
            issues = self._alternative_runner(
                ordered_rows,
                settings,
                pause_event=running,
                cancel_event=cancelled,
                force_refresh=force_refresh,
                providers=providers,
                cache_file=provider_cache_file,
            )

        evidence_by_package: dict[str, PackageStoreEvidence] = {}
        for row in ordered_rows:
            package_id = str(row["package_name"])
            provider_evidence = tuple(alternative_distribution.provider_results(row))
            store_row = {
                key: value
                for key, value in row.items()
                if key != alternative_distribution.ROW_FIELD
            }
            evidence_by_package[package_id] = PackageStoreEvidence(
                package_lookup_key=package_id,
                store_result=_freeze(store_row),
                alternative_distribution=provider_evidence,
            )

        package_evidence = tuple(
            evidence_by_package[app["package_name"]]
            for app in unique_apps
            if app["package_name"] in evidence_by_package
        )
        associations = tuple(
            LocalArtifactStoreAssociation(
                artifact=artifact,
                package_evidence=evidence_by_package.get(artifact.package_lookup_key),
            )
            for artifact in ordered_artifacts
        )
        return LocalArtifactStoreFanoutResult(
            associations=associations,
            packages=package_evidence,
            issues=tuple(issues),
        )
