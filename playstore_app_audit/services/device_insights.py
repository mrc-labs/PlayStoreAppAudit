from __future__ import annotations

import html
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Event
from typing import TYPE_CHECKING, Any

import requests

import playstore_app_audit.services.alternative_distribution as alternative_distribution
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
from playstore_app_audit import __version__
from playstore_app_audit.domain.alternative_distribution import AlternativeDistributionState
from playstore_app_audit.help_texts import ADB_SETUP_GUIDE as ADB_SETUP_GUIDE
from playstore_app_audit.platform import runtime

if TYPE_CHECKING:
    from playstore_app_audit.services.scan_session import ScanSession

APP_VERSION = __version__
DEVICE_SNAPSHOT_FORMAT = "PlayStoreAppAudit-device-snapshot-v1"
GITHUB_REPOSITORY = "mrc-labs/PlayStoreAppAudit"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
LATEST_RELEASE_PAGE = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"

SENSITIVE_PERMISSIONS = {
    "android.permission.CAMERA": "Camera",
    "android.permission.RECORD_AUDIO": "Microphone",
    "android.permission.ACCESS_FINE_LOCATION": "Precise location",
    "android.permission.ACCESS_COARSE_LOCATION": "Approx. location",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "Background location",
    "android.permission.READ_CONTACTS": "Read contacts",
    "android.permission.WRITE_CONTACTS": "Write contacts",
    "android.permission.READ_CALENDAR": "Read calendar",
    "android.permission.WRITE_CALENDAR": "Write calendar",
    "android.permission.READ_SMS": "Read SMS",
    "android.permission.SEND_SMS": "Send SMS",
    "android.permission.RECEIVE_SMS": "Receive SMS",
    "android.permission.READ_CALL_LOG": "Read call log",
    "android.permission.WRITE_CALL_LOG": "Write call log",
    "android.permission.CALL_PHONE": "Phone calls",
    "android.permission.READ_PHONE_STATE": "Phone state",
    "android.permission.BODY_SENSORS": "Body sensors",
    "android.permission.ACTIVITY_RECOGNITION": "Activity recognition",
    "android.permission.READ_MEDIA_IMAGES": "Photos/images",
    "android.permission.READ_MEDIA_VIDEO": "Videos",
    "android.permission.READ_MEDIA_AUDIO": "Audio/media",
    "android.permission.MANAGE_EXTERNAL_STORAGE": "All files access",
    "android.permission.SYSTEM_ALERT_WINDOW": "Display over other apps",
    "android.permission.QUERY_ALL_PACKAGES": "Query installed apps",
}

V9_TECHNICAL_COLUMNS = {
    "compatibility_status": "Android compatibility",
    "target_sdk": "Target SDK",
    "min_sdk": "Min SDK",
    "first_install_time": "First installed",
    "last_local_update": "Last local update",
    "app_enabled": "Enabled state",
    "sensitive_permissions_count": "Sensitive permissions count",
    "sensitive_permissions": "Sensitive permissions",
    "device_change": "Device inventory change",
    "health_score": "Maintenance Score",
}

VIEW_PRESETS = ("Basic", "Device", "Technical")
BUILTIN_FILTERS = (
    "All",
    "Problems",
    "Old apps",
    "Sideloaded",
    "Version mismatch",
    "Disabled",
    "Sensitive permissions",
)

CSV_EXPORT_GUIDE = """Export a package CSV directly from an Android phone

The easiest method is simply to use 'Scan phone with ADB' inside Play Store App Audit. If you want a reusable CSV instead, open PowerShell in the folder containing adb.exe and run:

  "package_name" | Set-Content packages.csv
  .\\adb.exe shell pm list packages -3 | ForEach-Object { $_ -replace "^package:", "" } | Sort-Object -Unique | Add-Content packages.csv

'-3' means third-party packages only. Remove '-3' if you want system packages too.

The resulting packages.csv can be loaded later with Choose file or dragged into the app.
"""

HEALTH_SCORE_GUIDE = """Maintenance Score

The score is a transparent maintenance heuristic from 0 to 100. It is NOT a malware/security rating and it does not judge whether requested permissions are appropriate.

Current components:
- Not found in the configured/checked Google Play markets: -60
- F-Droid main availability recovery while that -60 penalty is active: +10
- Aptoide availability recovery while that -60 penalty is active: +5
- Store anomaly: -20
- Other/inconclusive Store state: -15
- Stale (>730 days since update): -25
- Aging (366-730 days): -15
- Legacy target SDK relative to the connected device: -15
- Aging target SDK relative to the connected device: -10
- Installed version differs from Store version: -5

Alternative-provider recovery is cumulative up to +15, but it is never a bonus when Google Play is available and never changes the underlying Play or provider states. Installer source and requested permissions do not reduce the score. The score is optional and disabled by default.
"""

HEALTH_SCORE_BASE = 100
DEFINITIVE_PLAY_ABSENCE_STATUS = "not_found_in_checked_countries"
STORE_ANOMALY_PLAY_STATUSES = frozenset(
    {"available_in_other_country", "available_in_fallback_locale_only"}
)
PROVIDER_RECOVERY_POINTS = {"fdroid_main": 10, "aptoide": 5}


@dataclass(frozen=True, slots=True)
class HealthScoreComponent:
    key: str
    label: str
    points: int


@dataclass(frozen=True, slots=True)
class HealthScoreBreakdown:
    score: int
    unclamped_score: int
    play_availability_penalty: int
    alternative_distribution_recovery: int
    listing_age_penalty: int
    compatibility_penalty: int
    version_comparison_penalty: int
    components: tuple[HealthScoreComponent, ...]


def portable_marker() -> Path:
    return runtime.portable_marker()


def portable_data_dir() -> Path:
    return runtime.portable_data_dir()


def local_data_dir() -> Path:
    return runtime.default_app_data_dir()


def app_data_dir_v9() -> Path:
    return runtime.app_data_dir()


def portable_mode_active() -> bool:
    return runtime.portable_mode_active()


def migrate_portable_mode(enable: bool) -> tuple[bool, str]:
    return runtime.migrate_portable_mode(enable)


def install_v9_state_extensions() -> None:
    defaults = state.DEFAULT_SETTINGS
    defaults.setdefault("permissions_audit_enabled", False)
    defaults.setdefault("health_score_enabled", False)
    defaults.setdefault("inventory_history_enabled", True)
    defaults.setdefault("view_preset", "Basic")
    defaults.setdefault("recent_sources", [])
    defaults.setdefault("saved_filters", {})
    defaults.setdefault("active_filter_preset", "All")
    state.TECHNICAL_COLUMNS.update(V9_TECHNICAL_COLUMNS)


def add_recent_source(path: str, limit: int = 8) -> None:
    settings = state.load_settings()
    existing = settings.get("recent_sources", [])
    items = [str(Path(path))]
    if isinstance(existing, list):
        items.extend(str(x) for x in existing if str(x) != str(path))
    settings["recent_sources"] = items[:limit]
    state.save_settings(settings)


def get_recent_sources() -> list[str]:
    settings = state.load_settings()
    items = settings.get("recent_sources", [])
    return (
        [str(x) for x in items if isinstance(x, str) and Path(x).is_file()][:8]
        if isinstance(items, list)
        else []
    )


def save_filter(name: str, query: str, criticality: str | None, hide_system: bool, preset: str) -> None:
    settings = state.load_settings()
    saved = settings.get("saved_filters", {})
    if not isinstance(saved, dict):
        saved = {}
    saved[name] = {
        "query": query,
        "criticality": criticality or "",
        "hide_system": bool(hide_system),
        "preset": preset if preset in BUILTIN_FILTERS else "All",
    }
    settings["saved_filters"] = saved
    state.save_settings(settings)


def delete_filter(name: str) -> None:
    settings = state.load_settings()
    saved = settings.get("saved_filters", {})
    if isinstance(saved, dict):
        saved.pop(name, None)
        settings["saved_filters"] = saved
        state.save_settings(settings)


def get_saved_filters() -> dict[str, dict[str, Any]]:
    saved = state.load_settings().get("saved_filters", {})
    return saved if isinstance(saved, dict) else {}


def row_matches_filter(row: dict[str, Any], preset: str) -> bool:
    preset = preset or "All"
    if preset == "All":
        return True
    key = str(row.get("criticality_key") or "")
    if preset == "Problems":
        return key in {"red", "blue", "purple"}
    if preset == "Old apps":
        return key in {"yellow", "orange"}
    if preset == "Sideloaded":
        return "sideload" in str(row.get("installer_source") or "").casefold()
    if preset == "Version mismatch":
        return str(row.get("version_comparison") or "") == "Different"
    if preset == "Disabled":
        return str(row.get("app_enabled") or "").casefold() == "disabled"
    if preset == "Sensitive permissions":
        try:
            return int(row.get("sensitive_permissions_count") or 0) > 0
        except (TypeError, ValueError):
            return False
    return True


def _run(adb: str, args: list[str], timeout: int = 30) -> str:
    result = subprocess.run([adb, *args], check=True, capture_output=True, text=True, timeout=timeout)
    return result.stdout


def _parse_getprop(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\[([^]]+)\]: \[([^]]*)\]", line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def collect_device_summary(adb: str, total_packages: int = 0, system_packages: int = 0) -> dict[str, Any]:
    try:
        props = _parse_getprop(_run(adb, ["shell", "getprop"], 25))
    except Exception:
        props = {}
    try:
        serial = _run(adb, ["get-serialno"], 10).strip()
    except Exception:
        serial = ""
    from playstore_app_audit.services.scan_session import device_summary_from_properties

    return device_summary_from_properties(props, serial, total_packages, system_packages)


def _permission_labels(text: str) -> list[str]:
    found: list[str] = []
    for permission, label in SENSITIVE_PERMISSIONS.items():
        if re.search(rf"(?m)^\s*{re.escape(permission)}(?::|\s|$)", text):
            found.append(label)
    return found


def _parse_package_dump(
    text: str, disabled: bool, device_sdk: int, include_permissions: bool
) -> dict[str, str]:
    def first(pattern: str) -> str:
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1).strip() if match else ""

    version_name = first(r"\bversionName=([^\r\n]+)")
    version_code = first(r"\bversionCode=(\d+)")
    target_sdk = first(r"\btargetSdk(?:Version)?[=:](\d+)")
    min_sdk = first(r"\bminSdk(?:Version)?[=:](\d+)")
    first_install = first(r"\bfirstInstallTime=([^\r\n]+)")
    last_update = first(r"\blastUpdateTime=([^\r\n]+)")
    permissions = _permission_labels(text) if include_permissions else []
    compatibility = compatibility_label(target_sdk, device_sdk)
    return {
        "installed_version": version_name,
        "installed_version_code": version_code,
        "target_sdk": target_sdk,
        "min_sdk": min_sdk,
        "first_install_time": first_install,
        "last_local_update": last_update,
        "app_enabled": "Disabled" if disabled else "Enabled",
        "compatibility_status": compatibility,
        "sensitive_permissions_count": str(len(permissions)) if include_permissions else "",
        "sensitive_permissions": ", ".join(permissions),
    }


def _extract_bulk_package_blocks(text: str, wanted: set[str] | None = None) -> dict[str, str]:
    """Extract package sections from one ``dumpsys package`` response.

    Android's own CTS utilities parse the Packages section from the same bulk
    command. Keep this deliberately defensive: if the section shape is not
    recognised the caller simply falls back to per-package dumpsys calls.
    """
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    section_match = re.search(r"(?m)^[ \t]*Packages:[ \t]*$", normalized)
    if not section_match:
        return {}
    tail = normalized[section_match.end() :].lstrip("\n")
    section = re.split(r"\n[ \t]*\n", tail, maxsplit=1)[0]
    header = re.compile(r"(?m)^[ \t]{2}Package \[([^\]]+)\][^\n]*$")
    matches = list(header.finditer(section))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        package = match.group(1).strip()
        if wanted is not None and package not in wanted:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        blocks[package] = section[match.start() : end].rstrip()
    return blocks


def _metadata_is_usable(info: dict[str, str]) -> bool:
    return any(
        str(info.get(key) or "").strip()
        for key in (
            "installed_version_code",
            "installed_version",
            "target_sdk",
            "first_install_time",
            "last_local_update",
        )
    )


def compatibility_label(target_sdk: object, device_sdk: object) -> str:
    try:
        target = int(str(target_sdk))
        device = int(str(device_sdk))
    except (TypeError, ValueError):
        return "Unknown"
    gap = device - target
    if gap <= 2:
        return "Modern"
    if gap <= 5:
        return "Aging target"
    return "Legacy target"


@dataclass(slots=True)
class FullCollectionReceipt:
    """Opt-in completion evidence, separate from the compatibility metadata dict."""

    complete: bool = False
    includes_permissions: bool = False


def _metadata_has_full_inputs(info: dict[str, str]) -> bool:
    # Optional versionName/timestamps may legitimately be absent. A usable
    # version alone does not certify a full SDK/device snapshot.
    return all(
        str(info.get(key) or "").isdigit()
        for key in ("installed_version_code", "target_sdk", "min_sdk")
    )


def collect_device_metadata_v9(
    adb: str,
    packages: list[str],
    cancel_event: Event | None = None,
    max_workers: int = 6,
    *,
    scan_context: ScanSession | None = None,
    receipt: FullCollectionReceipt | None = None,
) -> dict[str, dict[str, str]]:
    """Collect read-only ADB evidence with cooperative command boundaries.

    Stop prevents the next command or per-package submission but does not kill
    a running adb process. Existing command timeouts bound that drain: 25s for
    getprop, 45s for disabled packages, 60s for installer/bulk package queries,
    and 30s for a per-package dumpsys query.
    """
    from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait

    from playstore_app_audit.services import installer_source

    settings = state.load_settings()
    include_permissions = bool(settings.get("permissions_audit_enabled", False))
    if receipt is not None:
        receipt.complete = False
        receipt.includes_permissions = include_permissions
    packages = list(dict.fromkeys(str(p).strip() for p in packages if str(p).strip()))
    if not adb or not packages:
        return {}

    command_prefix: list[str] = []
    compact = {}
    if scan_context is not None:
        from playstore_app_audit.services.scan_session import authorised_session_serial

        if cancel_event is not None and cancel_event.is_set():
            return {}
        if set(packages) != set(scan_context.packages):
            return {}
        # Recheck authorization/identity after compact capture, then pin every
        # full command so a disconnect/replacement cannot collect another phone.
        command_prefix = ["-s", authorised_session_serial(adb, scan_context.device_id)]
        compact = scan_context.metadata_by_package()

    def run(args: list[str], timeout: int) -> str:
        return _run(adb, command_prefix + args, timeout)

    context_complete = True
    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        if scan_context is not None and scan_context.android_api.isdigit():
            device_sdk = int(scan_context.android_api)
        else:
            props = _parse_getprop(run(["shell", "getprop"], 25))
            device_sdk = int(props.get("ro.build.version.sdk", "0") or 0)
        context_complete = device_sdk > 0
    except Exception:
        device_sdk = 0
        context_complete = False

    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        if compact and all(item.is_enabled is not None for item in compact.values()):
            disabled = {package for package, item in compact.items() if not item.is_enabled}
        else:
            disabled_output = run(["shell", "pm", "list", "packages", "-d"], 45)
            disabled = {
                line.replace("package:", "", 1).strip()
                for line in disabled_output.splitlines()
                if line.strip().startswith("package:")
            }
    except Exception:
        disabled = set()
        context_complete = False

    installer_map: dict[str, str] = {}
    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        if compact and all(item.installer_package is not None for item in compact.values()):
            installer_map = {package: item.installer_package or "" for package, item in compact.items()}
        else:
            output = run(["shell", "pm", "list", "packages", "-i"], 60)
            installer_map = device_metadata._parse_installer_map(output)
            if not set(packages).issubset(installer_map):
                context_complete = False
    except Exception:
        context_complete = False

    metadata: dict[str, dict[str, str]] = {}

    def finish() -> dict[str, dict[str, str]]:
        if receipt is not None:
            receipt.complete = (
                context_complete
                and not (cancel_event is not None and cancel_event.is_set())
                and set(metadata) == set(packages)
                and all(_metadata_has_full_inputs(info) for info in metadata.values())
            )
        return metadata

    # Fast path: one PackageManager dump for the entire inventory. This avoids
    # starting hundreds of separate adb/dumpsys processes on larger phones.
    # Any package whose block is missing or does not contain usable metadata is
    # handled by the proven per-package fallback below.
    try:
        cancelled = cancel_event is not None and cancel_event.is_set()
        if not cancelled:
            bulk_dump = run(["shell", "dumpsys", "package"], 60)
            blocks = _extract_bulk_package_blocks(bulk_dump, set(packages))
            for package, dump in blocks.items():
                info = _parse_package_dump(dump, package in disabled, device_sdk, include_permissions)
                if not _metadata_is_usable(info):
                    continue
                if receipt is not None and not _metadata_has_full_inputs(info):
                    continue
                info.update(installer_source.installer_fields(installer_map.get(package, "")))
                metadata[package] = info
    except Exception:
        # Bulk dumps differ across Android/OEM versions. Falling back is a
        # correctness feature, not an error condition.
        pass

    remaining = [package for package in packages if package not in metadata]
    if cancel_event is not None and cancel_event.is_set():
        return metadata

    def read_one(package: str) -> tuple[str, dict[str, str]]:
        if cancel_event is not None and cancel_event.is_set():
            return package, {}
        try:
            dump = run(["shell", "dumpsys", "package", package], 30)
            info = _parse_package_dump(dump, package in disabled, device_sdk, include_permissions)
        except Exception:
            info = {
                "installed_version": "",
                "installed_version_code": "",
                "target_sdk": "",
                "min_sdk": "",
                "first_install_time": "",
                "last_local_update": "",
                "app_enabled": "Unknown",
                "compatibility_status": "Unknown",
                "sensitive_permissions_count": "" if not include_permissions else "0",
                "sensitive_permissions": "",
            }
        info.update(installer_source.installer_fields(installer_map.get(package, "")))
        return package, info

    if not remaining:
        return finish()

    worker_limit = max(1, min(max_workers, 8))
    with ThreadPoolExecutor(max_workers=worker_limit) as executor:
        pending: dict[Future[tuple[str, dict[str, str]]], int] = {}
        next_index = 0

        def fill_submission_window() -> None:
            nonlocal next_index
            while (
                next_index < len(remaining)
                and len(pending) < worker_limit
                and (cancel_event is None or not cancel_event.is_set())
            ):
                index = next_index
                next_index += 1
                pending[executor.submit(read_one, remaining[index])] = index

        fill_submission_window()
        while pending:
            completed_futures, _not_done = wait(
                tuple(pending), return_when=FIRST_COMPLETED
            )
            for future in completed_futures:
                pending.pop(future)
                try:
                    package, info = future.result()
                except CancelledError:
                    continue
                if info:
                    metadata[package] = info
            if cancel_event is not None and cancel_event.is_set():
                for future in pending:
                    future.cancel()
            else:
                fill_submission_window()
    return finish()


def enrich_rows_with_device_metadata_v9(
    rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]
) -> None:
    for row in rows:
        package = str(row.get("package_name") or "")
        info = metadata.get(package, {})
        for key in (
            "installed_version",
            "installed_version_code",
            "installer_source",
            "target_sdk",
            "min_sdk",
            "first_install_time",
            "last_local_update",
            "app_enabled",
            "compatibility_status",
            "sensitive_permissions_count",
            "sensitive_permissions",
        ):
            row[key] = info.get(key, "")
        row["version_comparison"] = device_metadata.compare_versions(
            row.get("installed_version"), row.get("play_version")
        )


def _play_availability_score_component(play_status: str) -> HealthScoreComponent | None:
    if play_status == DEFINITIVE_PLAY_ABSENCE_STATUS:
        return HealthScoreComponent(
            "play_availability",
            "Google Play availability (not found in checked markets)",
            -60,
        )
    if play_status in STORE_ANOMALY_PLAY_STATUSES:
        return HealthScoreComponent("play_availability", "Store anomaly", -20)
    if play_status == "available":
        return None
    return HealthScoreComponent(
        "play_availability", "Other/inconclusive Google Play state", -15
    )


def _listing_age_score_component(value: object) -> HealthScoreComponent | None:
    try:
        age_days = int(str(value))
    except (TypeError, ValueError):
        return None
    if age_days > 730:
        return HealthScoreComponent("listing_age", "Listing age (>730 days)", -25)
    if age_days >= 366:
        return HealthScoreComponent("listing_age", "Listing age (366-730 days)", -15)
    return None


def calculate_health_score_breakdown(row: dict[str, Any]) -> HealthScoreBreakdown:
    """Calculate one non-overlapping, raw-state Maintenance Score breakdown."""

    components: list[HealthScoreComponent] = []
    play_status = str(row.get("play_status") or "").strip()
    play_component = _play_availability_score_component(play_status)
    play_penalty = play_component.points if play_component is not None else 0
    if play_component is not None:
        components.append(play_component)

    recovery = 0
    if play_status == DEFINITIVE_PLAY_ABSENCE_STATUS:
        available_provider_ids = {
            result.provider_id
            for result in alternative_distribution.provider_results(row)
            if result.state is AlternativeDistributionState.AVAILABLE
        }
        for provider_id, points in PROVIDER_RECOVERY_POINTS.items():
            if provider_id not in available_provider_ids:
                continue
            label = (
                "F-Droid availability recovery"
                if provider_id == "fdroid_main"
                else "Aptoide availability recovery"
            )
            components.append(
                HealthScoreComponent(f"provider_recovery_{provider_id}", label, points)
            )
            recovery += points

    age_component = _listing_age_score_component(row.get("age_days"))
    age_penalty = age_component.points if age_component is not None else 0
    if age_component is not None:
        components.append(age_component)

    compatibility = str(row.get("compatibility_status") or "")
    compatibility_component = None
    if compatibility == "Legacy target":
        compatibility_component = HealthScoreComponent(
            "android_compatibility", "Legacy target SDK", -15
        )
    elif compatibility == "Aging target":
        compatibility_component = HealthScoreComponent(
            "android_compatibility", "Aging target SDK", -10
        )
    compatibility_penalty = (
        compatibility_component.points if compatibility_component is not None else 0
    )
    if compatibility_component is not None:
        components.append(compatibility_component)

    version_component = None
    if str(row.get("version_comparison") or "") == "Different":
        version_component = HealthScoreComponent(
            "installed_store_version", "Installed vs Store is Different", -5
        )
    version_penalty = version_component.points if version_component is not None else 0
    if version_component is not None:
        components.append(version_component)

    unclamped_score = HEALTH_SCORE_BASE + sum(component.points for component in components)
    score = max(0, min(100, unclamped_score))
    return HealthScoreBreakdown(
        score=score,
        unclamped_score=unclamped_score,
        play_availability_penalty=play_penalty,
        alternative_distribution_recovery=recovery,
        listing_age_penalty=age_penalty,
        compatibility_penalty=compatibility_penalty,
        version_comparison_penalty=version_penalty,
        components=tuple(components),
    )


def health_score_breakdown_lines(row: dict[str, Any]) -> list[str]:
    breakdown = calculate_health_score_breakdown(row)
    stored_score = row.get("health_score")
    if stored_score not in (None, ""):
        try:
            if int(str(stored_score)) != breakdown.score:
                return [
                    "Stored audit score uses a different calculation; "
                    "a current-method breakdown is not shown."
                ]
        except (TypeError, ValueError):
            return ["Score breakdown is unavailable for this stored value."]
    if not breakdown.components:
        return ["No applicable deductions or recovery."]
    return [f"{component.label}: {component.points:+d}" for component in breakdown.components]


def calculate_health_score(row: dict[str, Any]) -> int:
    return calculate_health_score_breakdown(row).score


def apply_health_score(row: dict[str, Any]) -> None:
    row["health_score"] = calculate_health_score(row)


def snapshots_dir() -> Path:
    path = app_data_dir_v9() / "device_snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_device_snapshot(rows: list[dict[str, Any]], device_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": DEVICE_SNAPSHOT_FORMAT,
        "created_at": datetime.now(UTC).isoformat(),
        "device": dict(device_summary or {}),
        "apps": [
            {
                key: row.get(key, "")
                for key in (
                    "package_name",
                    "play_title",
                    "installed_version",
                    "installed_version_code",
                    "installer_source",
                    "app_enabled",
                    "target_sdk",
                    "min_sdk",
                    "compatibility_status",
                )
            }
            for row in rows
        ],
    }


def save_snapshot(path: str | Path, rows: list[dict[str, Any]], device_summary: dict[str, Any]) -> Path:
    target = Path(path)
    target.write_text(
        json.dumps(make_device_snapshot(rows, device_summary), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return target


def load_snapshot(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("apps"), list):
        raise ValueError("Not a valid Play Store App Audit device snapshot.")
    return data


def compare_snapshots(
    current_rows: list[dict[str, Any]], current_device: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    old_apps = {
        str(row.get("package_name") or ""): row for row in snapshot.get("apps", []) if isinstance(row, dict)
    }
    new_apps = {str(row.get("package_name") or ""): row for row in current_rows}
    only_old = sorted(set(old_apps) - set(new_apps))
    only_new = sorted(set(new_apps) - set(old_apps))
    version_diff = []
    installer_diff = []
    state_diff = []
    for package in sorted(set(old_apps) & set(new_apps)):
        old = old_apps[package]
        new = new_apps[package]
        if str(old.get("installed_version") or "") != str(new.get("installed_version") or ""):
            version_diff.append(package)
        if str(old.get("installer_source") or "") != str(new.get("installer_source") or ""):
            installer_diff.append(package)
        if str(old.get("app_enabled") or "") != str(new.get("app_enabled") or ""):
            state_diff.append(package)
    return {
        "snapshot_device": snapshot.get("device", {}),
        "current_device": current_device,
        "only_snapshot": only_old,
        "only_current": only_new,
        "version_differences": version_diff,
        "installer_differences": installer_diff,
        "state_differences": state_diff,
    }


def inventory_path(device_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", device_id or "unknown")
    return app_data_dir_v9() / f"inventory_{safe}.json"


def clear_device_inventory_history() -> int:
    """Delete only per-device baselines used by Device Inventory Change."""

    deleted = 0
    for path in app_data_dir_v9().glob("inventory_*.json"):
        if not path.is_file():
            continue
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stored = None
        if isinstance(stored, dict) and stored.get("format") == DEVICE_SNAPSHOT_FORMAT:
            continue
        path.unlink()
        deleted += 1
    return deleted


def _meaningful_inventory_value(value: object) -> str:
    text = str(value or "").strip()
    if text.casefold() in {
        "",
        "unknown",
        "unknown / preinstalled",
        "none",
        "null",
        "n/a",
    }:
        return ""
    return text


def _inventory_version_changed(old: dict[str, Any], current: dict[str, Any]) -> bool:
    old_code = _meaningful_inventory_value(old.get("installed_version_code"))
    current_code = _meaningful_inventory_value(current.get("installed_version_code"))
    if old_code and current_code:
        return old_code != current_code
    old_name = _meaningful_inventory_value(old.get("installed_version"))
    current_name = _meaningful_inventory_value(current.get("installed_version"))
    return bool(old_name and current_name and old_name != current_name)


def _inventory_installer_changed(old: dict[str, Any], current: dict[str, Any]) -> bool:
    old_package = _meaningful_inventory_value(old.get("installer_package"))
    current_package = _meaningful_inventory_value(current.get("installer_package"))
    if old_package and current_package:
        return old_package != current_package
    old_source = _meaningful_inventory_value(old.get("installer_source"))
    current_source = _meaningful_inventory_value(current.get("installer_source"))
    return bool(old_source and current_source and old_source != current_source)


def _inventory_enabled_changed(old: dict[str, Any], current: dict[str, Any]) -> bool:
    old_state = str(old.get("app_enabled") or "").strip().casefold()
    current_state = str(current.get("app_enabled") or "").strip().casefold()
    known = {"enabled", "disabled"}
    return old_state in known and current_state in known and old_state != current_state


def _inventory_record(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "installed_version": row.get("installed_version", ""),
        "installed_version_code": row.get("installed_version_code", ""),
        "installer_package": row.get("installer_package", ""),
        "installer_source": row.get("installer_source", ""),
        "installer_category": row.get("installer_category", ""),
        "app_enabled": row.get("app_enabled", ""),
        "is_system": bool(row.get("is_system")),
        "play_title": row.get("play_title", ""),
    }


def annotate_inventory_changes_and_save(
    rows: list[dict[str, Any]],
    device_summary: dict[str, Any],
    inventory_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    device_id = str(device_summary.get("device_id") or "unknown")
    path = inventory_path(device_id)
    try:
        previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except Exception:
        previous = {}
    old_apps = previous.get("apps", {}) if isinstance(previous, dict) else {}
    if not isinstance(old_apps, dict):
        old_apps = {}
    current_source = rows if inventory_rows is None else inventory_rows
    current = {
        str(row.get("package_name") or ""): _inventory_record(row)
        for row in current_source
        if str(row.get("package_name") or "")
    }
    counts = {"new": 0, "version": 0, "installer": 0, "state": 0, "same": 0, "removed": 0}
    changes: dict[str, str] = {}
    for package, current_row in current.items():
        old = old_apps.get(package)
        if not isinstance(old, dict):
            change = "New on device"
            counts["new"] += 1
        elif _inventory_version_changed(old, current_row):
            change = "Version changed"
            counts["version"] += 1
        elif _inventory_installer_changed(old, current_row):
            change = "Installer changed"
            counts["installer"] += 1
        elif _inventory_enabled_changed(old, current_row):
            change = "State changed"
            counts["state"] += 1
        else:
            change = "Same"
            counts["same"] += 1
        changes[package] = change
    for row in rows:
        package = str(row.get("package_name") or "")
        if package in changes:
            row["device_change"] = changes[package]
    removed = sorted(set(old_apps) - set(current))
    counts["removed"] = len(removed)
    payload = {
        "device": device_summary,
        "saved_at": datetime.now(UTC).isoformat(),
        "apps": current,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"counts": counts, "removed": removed, "had_previous": bool(old_apps)}


def _status_class(row: dict[str, Any]) -> str:
    return str(row.get("criticality_key") or "purple")


def write_html_report(
    path: str | Path, rows: list[dict[str, Any]], device_summary: dict[str, Any] | None = None
) -> Path:
    target = Path(path)
    local_apk_report = any(
        local_apk_audit.is_local_apk_source(row.get("source_mode")) for row in rows
    )
    counts = {
        key: sum(1 for row in rows if _status_class(row) == key)
        for key in ("green", "yellow", "orange", "red", "blue", "purple")
    }
    cards = "".join(
        f'<div class="card {key}"><b>{label}</b><span>{counts[key]}</span></div>'
        for key, label in (
            ("green", "Current"),
            ("yellow", "Aging"),
            ("orange", "Stale"),
            ("red", "Removed"),
            ("blue", "Anomaly"),
            ("purple", "Other"),
        )
    )
    device_html = ""
    if device_summary:
        name = " ".join(
            filter(
                None, [str(device_summary.get("manufacturer") or ""), str(device_summary.get("model") or "")]
            )
        ).strip()
        device_html = f'<p class="muted">Device: {html.escape(name or "Android device")} · Android {html.escape(str(device_summary.get("android_version") or "?"))} (API {html.escape(str(device_summary.get("android_api") or "?"))}) · Security patch {html.escape(str(device_summary.get("security_patch") or "?"))}</p>'
    table_rows = []
    alternative_rows: list[str] = []
    for row in rows:
        version_comparison = presentation.semantic_html_value(
            "version_comparison", row.get("version_comparison")
        )
        compatibility = presentation.semantic_html_value(
            "compatibility_status", row.get("compatibility_status")
        )
        device_change = html.escape(str(row.get("device_change") or ""))
        health_score = str(row.get("health_score") or "").strip()
        health_score_html = html.escape(health_score)
        if health_score:
            escaped_health_score = html.escape(health_score)
            breakdown_html = "<br>".join(
                html.escape(line) for line in health_score_breakdown_lines(row)
            )
            health_score_html = (
                f"<b>{escaped_health_score}/100</b>"
                f'<div class="score-breakdown">{breakdown_html}</div>'
            )
        if local_apk_report:
            table_rows.append(
                f'<tr class="{_status_class(row)}">'
                f"<td>{html.escape(str(row.get('criticality') or ''))}</td>"
                f"<td>{html.escape(str(row.get('local_apk_file_name') or ''))}</td>"
                f"<td>{html.escape(str(row.get('package_name') or ''))}</td>"
                f"<td>{html.escape(str(row.get('local_apk_version_name') or ''))}</td>"
                f"<td>{html.escape('' if row.get('local_apk_version_code') is None else str(row.get('local_apk_version_code')))}</td>"
                f"<td>{html.escape(str(row.get('play_version') or ''))}</td>"
                f"<td>{html.escape(str(row.get('local_apk_version_comparison') or ''))}</td>"
                f"<td>{html.escape(str(row.get('play_title') or ''))}</td>"
                f"<td>{html.escape(str(row.get('play_last_update') or ''))}</td>"
                f"<td>{html.escape(str(row.get('local_apk_sha256') or ''))}</td>"
                f"<td>{html.escape(presentation.friendly_notes(row))}</td>"
                "</tr>"
            )
        else:
            table_rows.append(
                f'<tr class="{_status_class(row)}">'
                f"<td>{html.escape(str(row.get('criticality') or ''))}</td>"
                f"<td>{html.escape(str(row.get('package_name') or ''))}</td>"
                f"<td>{html.escape(str(row.get('play_title') or ''))}</td>"
                f"<td>{html.escape(str(row.get('play_last_update') or ''))}</td>"
                f"<td>{html.escape(str(row.get('age_days') or ''))}</td>"
                f"<td>{version_comparison}</td>"
                f"<td>{compatibility}</td>"
                f"<td>{device_change}</td>"
                f"<td>{health_score_html}</td>"
                f"<td>{html.escape(presentation.friendly_notes(row))}</td>"
                "</tr>"
            )
        provider_results = alternative_distribution.provider_results(row)
        if provider_results:
            provider_items: list[str] = []
            for result in provider_results:
                details = [
                    f"Status: {alternative_distribution.STATE_LABELS[result.state]}",
                    f"Checked: {result.checked_at}" if result.checked_at else "",
                    f"Source: {result.provenance.title()}" if result.provenance else "",
                    f"Version: {result.version_name}" if result.version_name else "",
                    f"Version code: {result.version_code}" if result.version_code != "" else "",
                    f"Reason: {result.reason}" if result.reason else "",
                ]
                detail_text = " · ".join(html.escape(item) for item in details if item)
                link = (
                    f' · <a href="{html.escape(result.listing_url, quote=True)}">Open provider listing</a>'
                    if result.listing_url
                    else ""
                )
                provider_items.append(
                    f"<li><b>{html.escape(result.provider_name)}</b> — {detail_text}{link}</li>"
                )
            package = html.escape(str(row.get("package_name") or ""))
            alternative_rows.append(
                f"<section><h3>{package}</h3><ul>{''.join(provider_items)}</ul></section>"
            )
    alternative_html = ""
    if alternative_rows:
        alternative_html = (
            "<h2>Alternative distribution checks</h2>"
            "<p class=\"muted\">Availability means only that a provider returned an active "
            "listing for the exact package identifier; it does not establish publisher identity "
            "or binary equivalence.</p>"
            + "".join(alternative_rows)
        )
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    table_header = (
        "<th>Status</th><th>APK filename</th><th>Package</th><th>Local version</th>"
        "<th>Local version code</th><th>Play Store version</th>"
        "<th>Local APK vs Store</th><th>Play Store title</th><th>Last update</th>"
        "<th>APK SHA-256</th><th>Notes</th>"
        if local_apk_report
        else "<th>Status</th><th>Package</th><th>Play Store title</th><th>Last update</th>"
        "<th>Age</th><th>Installed vs Store</th><th>Android compatibility</th>"
        "<th>Device Inventory Change</th><th>Maintenance Score</th><th>Notes</th>"
    )
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Play Store App Audit report</title>
<style>
.score-breakdown {{ margin-top: 0.3rem; font-size: 0.82em; line-height: 1.35; }}
</style></head><body><div class="wrap"><h1>Play Store App Audit</h1><p class="muted">Generated {html.escape(generated)} · App version {APP_VERSION}</p>{device_html}<div class="cards">{cards}</div><table><thead><tr>{table_header}</tr></thead><tbody>{"".join(table_rows)}</tbody></table>{alternative_html}</div></body></html>"""
    target.write_text(doc, encoding="utf-8")
    return target


def _parse_version_tuple(value: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", value or "")
    return tuple(int(x) for x in nums[:4]) or (0,)


def check_for_updates() -> dict[str, Any]:
    try:
        response = requests.get(
            LATEST_RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": f"PlayStoreAppAudit/{APP_VERSION}",
            },
            timeout=8,
        )
        if response.status_code == 404:
            return {
                "status": "unavailable",
                "message": "No public release feed is available. The GitHub repository may still be private or may not have a published release.",
            }
        response.raise_for_status()
        data = response.json()
        tag = str(data.get("tag_name") or "")
        url = str(data.get("html_url") or LATEST_RELEASE_PAGE)
        newer = _parse_version_tuple(tag) > _parse_version_tuple(APP_VERSION)
        return {"status": "ok", "tag": tag, "url": url, "newer": newer}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def log_event(message: str) -> None:
    try:
        path = app_data_dir_v9() / "activity.log"
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")
        if path.stat().st_size > 2_000_000:
            text = path.read_text(encoding="utf-8", errors="replace")[-1_000_000:]
            path.write_text(text, encoding="utf-8")
    except Exception:
        pass


def create_diagnostic_bundle(
    path: str | Path, rows: list[dict[str, Any]], device_summary: dict[str, Any] | None = None
) -> Path:
    target = Path(path)
    settings = state.load_settings()
    sanitized = dict(settings)
    sanitized.pop("recent_sources", None)
    sanitized.pop("saved_filters", None)
    sanitized.pop("smart_queries", None)
    alternative_settings = sanitized.get("alternative_distribution")
    if isinstance(alternative_settings, dict):
        alternative_settings = dict(alternative_settings)
        aptoide_settings = alternative_settings.get("aptoide")
        if isinstance(aptoide_settings, dict):
            aptoide_settings = dict(aptoide_settings)
            aptoide_settings.pop("api_key_protected", None)
            alternative_settings["aptoide"] = aptoide_settings
        sanitized["alternative_distribution"] = alternative_settings
    summary = {
        "app_version": APP_VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "portable_mode": portable_mode_active(),
        "result_count": len(rows),
        "status_counts": {
            key: sum(1 for row in rows if str(row.get("criticality_key") or "") == key)
            for key in ("green", "yellow", "orange", "red", "blue", "purple")
        },
        "device": {k: v for k, v in (device_summary or {}).items() if k not in {"device_id"}},
    }
    with tempfile.TemporaryDirectory(prefix="psaa_diag_") as tmp:
        root = Path(tmp)
        (root / "system.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (root / "settings_sanitized.json").write_text(
            json.dumps(sanitized, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log = app_data_dir_v9() / "activity.log"
        if log.is_file():
            shutil.copy2(log, root / "activity.log")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for item in root.iterdir():
                archive.write(item, item.name)
    return target


def open_app_info_on_device(adb: str, package_name: str) -> None:
    subprocess.run(
        [
            adb,
            "shell",
            "am",
            "start",
            "-a",
            "android.settings.APPLICATION_DETAILS_SETTINGS",
            "-d",
            f"package:{package_name}",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )


install_v9_state_extensions()
# Make the v8 worker transparently collect the richer v9 metadata.
device_metadata.collect_device_metadata = collect_device_metadata_v9
device_metadata.enrich_rows_with_device_metadata = enrich_rows_with_device_metadata_v9
