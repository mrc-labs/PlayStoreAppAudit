"""Qt-independent orchestration of the product's existing audit services."""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playstore_app_audit.devices.adb import find_adb
from playstore_app_audit.platform.runtime import detect_store_country
from playstore_app_audit.services import (
    alternative_distribution,
    app_list_system,
    device_insights,
    device_metadata,
    device_specific_integration,
    device_specific_settings,
    local_apk_audit,
    local_apk_source,
    local_package_metadata_cache,
    personal_device_library,
    result_classification,
    scan_session,
    state,
    store_locale,
)
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.device_specific_profiles import load_reference_profile
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService
from playstore_app_audit.services.play_store import PlayStoreService

Progress = Callable[[int, int, str], None]


class InvalidAuditInput(ValueError):
    """A source or command-local configuration cannot be used safely."""


@dataclass(frozen=True, slots=True)
class AuditSource:
    kind: str
    path: Path | None = None
    files: tuple[Path, ...] = ()
    include_system: bool = False


def _enrich_device_specific(
    rows: list[dict[str, Any]], settings: dict[str, Any], config: AuditConfig,
    running: threading.Event, cancelled: threading.Event, *,
    connected_profile: Any = None,
) -> None:
    try:
        device_specific_integration.enrich_rows_with_device_specific_resolution(
            rows, settings=settings, country=config.country, language=config.language,
            pause_event=running, cancel_event=cancelled,
            connected_profile=connected_profile,
        )
    except Exception:
        # This metadata is additive; public Store evidence remains authoritative.
        for row in rows:
            for field in device_specific_integration.ROW_FIELDS:
                row[field] = ""
            row["version_comparison"] = device_metadata.compare_versions(
                row.get("installed_version"), row.get("play_version")
            )


def validate_device_specific(settings: dict[str, Any], source: AuditSource) -> None:
    provider = device_specific_settings.provider_from_settings(settings)
    if provider is device_specific_settings.DeviceSpecificProvider.DISABLED:
        return
    profile_id = str(settings.get(device_specific_settings.SETTING_PROFILE_ID) or "").strip()
    if profile_id == device_specific_settings.CONNECTED_DEVICE_PROFILE_ID:
        if source.kind != "phone":
            raise InvalidAuditInput("Connected Device profile requires the phone source.")
    elif personal_device_library.is_personal_profile_id(profile_id):
        try:
            personal_device_library.get_profile(profile_id)
        except (KeyError, personal_device_library.PersonalDeviceLibraryError) as exc:
            raise InvalidAuditInput("The saved Personal Device profile is unavailable.") from exc
    else:
        try:
            load_reference_profile(profile_id or device_specific_integration.DEFAULT_PROFILE_ID)
        except (KeyError, ValueError, TypeError) as exc:
            raise InvalidAuditInput("The Device Specific profile is invalid.") from exc
    if provider is device_specific_settings.DeviceSpecificProvider.CUSTOM_DISPENSER:
        try:
            device_specific_integration.validate_resolver_endpoint(
                settings.get(device_specific_settings.SETTING_ENDPOINT)
            )
        except (ValueError, TypeError) as exc:
            raise InvalidAuditInput("The Device Specific endpoint is invalid.") from exc
    else:
        from playstore_app_audit.services.device_specific_personal_session import personal_session_status

        if not personal_session_status().signed_in:
            raise InvalidAuditInput("An existing Personal Google Session is required.")


def _store_rows(
    apps: list[dict[str, str]], config: AuditConfig, settings: dict[str, Any],
    cancel_event: threading.Event, progress: Progress | None, *, fresh: bool,
    enrich: bool = True,
) -> list[dict[str, Any]]:
    cached = (
        state.load_fresh_cache(
            apps, config.country, config.language,
            int(settings.get("cache_ttl_hours", state.DEFAULT_CACHE_TTL_HOURS)),
        )
        if settings.get("cache_enabled", True) and not fresh else {}
    )
    pending = [app for app in apps if app["package_name"] not in cached]
    running = threading.Event()
    running.set()
    live = (
        PlayStoreService().audit(
            pending, config, progress_callback=progress,
            pause_event=running, cancel_event=cancel_event,
        )
        if pending and not cancel_event.is_set() else []
    )
    if settings.get("cache_enabled", True) and live:
        state.update_cache(live, config.country, config.language)
    by_package = {key: dict(row) for key, row in cached.items()}
    by_package.update({str(row.get("package_name") or ""): row for row in live})
    rows = [by_package[app["package_name"]] for app in apps if app["package_name"] in by_package]
    if enrich and not cancel_event.is_set():
        _enrich_device_specific(rows, settings, config, running, cancel_event)
    if enrich and not cancel_event.is_set():
        alternative_distribution.run_alternative_distribution_phase(
            rows, settings, pause_event=running, cancel_event=cancel_event,
            force_refresh=fresh,
        )
    return rows


def run_audit(
    source: AuditSource, settings: dict[str, Any], cancel_event: threading.Event,
    *, country: str | None = None, language: str | None = None,
    workers: int | None = None, fresh: bool = False,
    progress: Progress | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one audit without writing GUI settings, history, or result files."""
    if source.kind not in {"app_list", "local_files", "local_folder", "phone"}:
        raise InvalidAuditInput("Unknown audit source.")
    validate_device_specific(settings, source)
    session: scan_session.ScanSession | None = None
    adb: str | None = None
    if source.kind == "phone":
        adb = find_adb()
        if not adb:
            raise InvalidAuditInput("ADB is unavailable. Install Android Platform-Tools first.")
        session = scan_session.collect_scan_session(
            adb, exclude_system=not source.include_system,
            collect_full_metadata=settings.get("collect_full_device_metadata_on_scan") is True,
            cancel_event=cancel_event,
        )
        if cancel_event.is_set():
            return [], {}
        store_locale.set_active_device_store_locale(session.locale)

    selected_country = (country or detect_store_country()).lower()
    selected_language = (language or str(settings.get("store_language") or "auto")).lower()
    device_metadata.set_fallback_countries(
        settings.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),
        selected_country,
    )
    config = AuditConfig(
        country=selected_country, language=selected_language,
        max_workers=workers or state.normalise_store_workers(settings.get("store_workers")),
    )
    context: dict[str, Any] = {
        "source_mode": {"app_list": "file", "local_files": "local_apk", "local_folder": "local_apk", "phone": "device"}[source.kind],
        "store_country": selected_country,
        "store_language": store_locale.resolve_store_language(selected_language, selected_country),
    }
    try:
        if source.kind == "app_list":
            if source.path is None:
                raise InvalidAuditInput("An App List file is required.")
            apps = PlayStoreService().load_packages(str(source.path))
            system_metadata = app_list_system.read_system_metadata(source.path, apps)
            system_packages = app_list_system.classify_packages(apps, system_metadata)
            rows = _store_rows(apps, config, settings, cancel_event, progress, fresh=fresh)
            for row in rows:
                row["source_mode"] = "file"
                row["is_system"] = row["package_name"] in system_packages
        elif source.kind == "phone":
            assert session is not None and adb is not None
            apps = [{"app_name": package, "package_name": package} for package in session.packages]
            rows = _store_rows(apps, config, settings, cancel_event, progress, fresh=fresh, enrich=False)
            if not cancel_event.is_set():
                if session.full_metadata_status is scan_session.FullMetadataStatus.COMPLETE:
                    metadata = session.full_metadata_by_package()
                elif settings.get("collect_device_metadata", True) and scan_session.authorised_device_matches(adb, session.device_id):
                    metadata = device_insights.collect_device_metadata_v9(
                        adb, list(session.packages), cancel_event
                    )
                else:
                    metadata = {}
                device_insights.enrich_rows_with_device_metadata_v9(rows, metadata)
                scan_session.enrich_rows_with_compact_metadata(rows, session)
                for row in rows:
                    row["source_mode"] = "device"
                    row["version_comparison"] = device_metadata.compare_versions(
                        row.get("installed_version"), row.get("play_version")
                    )
                running = threading.Event()
                running.set()
                connected_profile = None
                if (
                    device_specific_settings.provider_from_settings(settings)
                    is not device_specific_settings.DeviceSpecificProvider.DISABLED
                    and settings.get(device_specific_settings.SETTING_PROFILE_ID)
                    == device_specific_settings.CONNECTED_DEVICE_PROFILE_ID
                ):
                    try:
                        connected_profile = scan_session.collect_connected_device_profile_for_session(
                            adb, session
                        )
                    except Exception:
                        connected_profile = None
                _enrich_device_specific(
                    rows, settings, config, running, cancel_event,
                    connected_profile=connected_profile,
                )
                if not cancel_event.is_set():
                    alternative_distribution.run_alternative_distribution_phase(
                        rows, settings, pause_event=running, cancel_event=cancel_event,
                        force_refresh=fresh,
                    )
                context["device"] = {
                    "manufacturer": session.manufacturer, "model": session.model,
                    "android_version": session.android_version,
                    "android_api": session.android_api,
                    "total_packages": session.package_count,
                    "system_packages": session.system_package_count,
                }
        elif source.kind in {"local_files", "local_folder"}:
            if source.kind == "local_files":
                paths = local_apk_source.normalise_explicit_apks(source.files)
            else:
                if source.path is None:
                    raise InvalidAuditInput("A Local APK folder is required.")
                discovered = local_apk_source.discover_folder_apks(source.path, cancel_event=cancel_event)
                paths = discovered.paths
            if not paths:
                raise InvalidAuditInput("No supported local package files were found.")
            artifacts = []
            for index, path in enumerate(paths, 1):
                if cancel_event.is_set():
                    return [], context
                parsed, _hit = local_package_metadata_cache.parse_cached_local_package(
                    path, cancel_event=cancel_event
                )
                if parsed.artifact is not None:
                    artifacts.append(parsed.artifact)
                if progress:
                    progress(index, len(paths), path.name)
            if not artifacts:
                raise InvalidAuditInput("No selected package file could be parsed.")
            running = threading.Event()
            running.set()
            result = LocalArtifactStoreService().collect(
                artifacts, config, settings, force_refresh=fresh,
                pause_event=running, cancel_event=cancel_event,
                progress_callback=progress,
            )
            rows = local_apk_audit.association_result_rows(result.associations)
            context["physical_files"] = len(paths)
            context["parsed_files"] = len(artifacts)
            context["packages"] = len(result.packages)
        if cancel_event.is_set():
            return [], context
        for row in rows:
            result_classification.classify_store_row(row, settings)
            device_insights.apply_health_score(row, settings)
            row["change"] = ""
        return rows, context
    finally:
        if session is not None:
            store_locale.set_active_device_store_locale(None)
