from __future__ import annotations

import hashlib
import html
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.services.state as state
from playstore_app_audit import __version__
from playstore_app_audit.help_texts import ADB_SETUP_GUIDE as ADB_SETUP_GUIDE
from playstore_app_audit.platform import runtime

APP_VERSION = __version__
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

Current penalties:
- Removed from checked Play markets: -60
- Store anomaly: -20
- Other/inconclusive Store state: -15
- Stale (>730 days since update): -25
- Aging (>365 days): -10
- Legacy target SDK relative to the connected device: -15
- Aging target SDK relative to the connected device: -7
- Installed version differs from Store version: -5

Installer source and requested permissions do not reduce the score. The score is optional and disabled by default.
"""


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
    device_hash = (
        hashlib.sha256(serial.encode("utf-8", errors="ignore")).hexdigest()[:16] if serial else "unknown"
    )
    masked = ("••••" + serial[-4:]) if len(serial) >= 4 else (serial or "Unknown")
    manufacturer = props.get("ro.product.manufacturer", "")
    model = props.get("ro.product.model", "")
    release = props.get("ro.build.version.release", "")
    sdk = props.get("ro.build.version.sdk", "")
    patch = props.get("ro.build.version.security_patch", "")
    return {
        "device_id": device_hash,
        "serial_masked": masked,
        "manufacturer": manufacturer,
        "model": model,
        "android_version": release,
        "android_api": sdk,
        "security_patch": patch,
        "total_packages": int(total_packages),
        "system_packages": int(system_packages),
        "third_party_packages": max(0, int(total_packages) - int(system_packages)),
        "captured_at": datetime.now(UTC).isoformat(),
    }


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


def collect_device_metadata_v9(
    adb: str,
    packages: list[str],
    cancel_event=None,
    max_workers: int = 6,
) -> dict[str, dict[str, str]]:
    from concurrent.futures import FIRST_COMPLETED, CancelledError, Future, ThreadPoolExecutor, wait

    settings = state.load_settings()
    include_permissions = bool(settings.get("permissions_audit_enabled", False))
    packages = list(dict.fromkeys(str(p).strip() for p in packages if str(p).strip()))
    if not adb or not packages:
        return {}

    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        props = _parse_getprop(_run(adb, ["shell", "getprop"], 25))
        device_sdk = int(props.get("ro.build.version.sdk", "0") or 0)
    except Exception:
        device_sdk = 0

    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        disabled_output = _run(adb, ["shell", "pm", "list", "packages", "-d"], 45)
        disabled = {
            line.replace("package:", "", 1).strip()
            for line in disabled_output.splitlines()
            if line.strip().startswith("package:")
        }
    except Exception:
        disabled = set()

    installer_map: dict[str, str] = {}
    try:
        if cancel_event is not None and cancel_event.is_set():
            return {}
        output = _run(adb, ["shell", "pm", "list", "packages", "-i"], 60)
        installer_map = device_metadata._parse_installer_map(output)
    except Exception:
        pass

    metadata: dict[str, dict[str, str]] = {}

    # Fast path: one PackageManager dump for the entire inventory. This avoids
    # starting hundreds of separate adb/dumpsys processes on larger phones.
    # Any package whose block is missing or does not contain usable metadata is
    # handled by the proven per-package fallback below.
    try:
        cancelled = cancel_event is not None and cancel_event.is_set()
        if not cancelled:
            bulk_dump = _run(adb, ["shell", "dumpsys", "package"], 60)
            blocks = _extract_bulk_package_blocks(bulk_dump, set(packages))
            for package, dump in blocks.items():
                info = _parse_package_dump(dump, package in disabled, device_sdk, include_permissions)
                if not _metadata_is_usable(info):
                    continue
                info["installer_source"] = device_metadata._friendly_installer(installer_map.get(package, ""))
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
            dump = _run(adb, ["shell", "dumpsys", "package", package], 30)
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
        info["installer_source"] = device_metadata._friendly_installer(installer_map.get(package, ""))
        return package, info

    if not remaining:
        return metadata

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
    return metadata


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


def calculate_health_score(row: dict[str, Any]) -> int:
    score = 100
    key = str(row.get("criticality_key") or "")
    score -= {"red": 60, "blue": 20, "purple": 15, "orange": 25, "yellow": 10}.get(key, 0)
    compatibility = str(row.get("compatibility_status") or "")
    if compatibility == "Legacy target":
        score -= 15
    elif compatibility == "Aging target":
        score -= 7
    if str(row.get("version_comparison") or "") == "Different":
        score -= 5
    return max(0, min(100, score))


def apply_health_score(row: dict[str, Any]) -> None:
    row["health_score"] = calculate_health_score(row)


def snapshots_dir() -> Path:
    path = app_data_dir_v9() / "device_snapshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_device_snapshot(rows: list[dict[str, Any]], device_summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "format": "PlayStoreAppAudit-device-snapshot-v1",
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


def annotate_inventory_changes_and_save(
    rows: list[dict[str, Any]], device_summary: dict[str, Any]
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
    current: dict[str, dict[str, Any]] = {}
    counts = {"new": 0, "version": 0, "installer": 0, "state": 0, "same": 0, "removed": 0}
    for row in rows:
        package = str(row.get("package_name") or "")
        old = old_apps.get(package)
        if not isinstance(old, dict):
            change = "New on device"
            counts["new"] += 1
        elif str(old.get("installed_version") or "") != str(row.get("installed_version") or ""):
            change = "Version changed"
            counts["version"] += 1
        elif str(old.get("installer_source") or "") != str(row.get("installer_source") or ""):
            change = "Installer changed"
            counts["installer"] += 1
        elif str(old.get("app_enabled") or "") != str(row.get("app_enabled") or ""):
            change = "State changed"
            counts["state"] += 1
        else:
            change = "Same"
            counts["same"] += 1
        row["device_change"] = change
        current[package] = {
            "installed_version": row.get("installed_version", ""),
            "installer_source": row.get("installer_source", ""),
            "app_enabled": row.get("app_enabled", ""),
            "play_title": row.get("play_title", ""),
        }
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
    for row in rows:
        table_rows.append(
            f'<tr class="{_status_class(row)}">'
            f"<td>{html.escape(str(row.get('criticality') or ''))}</td>"
            f"<td>{html.escape(str(row.get('package_name') or ''))}</td>"
            f"<td>{html.escape(str(row.get('play_title') or ''))}</td>"
            f"<td>{html.escape(str(row.get('play_last_update') or ''))}</td>"
            f"<td>{html.escape(str(row.get('age_days') or ''))}</td>"
            f"<td>{html.escape(str(row.get('compatibility_status') or ''))}</td>"
            f"<td>{html.escape(str(row.get('health_score') or ''))}</td>"
            f"<td>{html.escape(presentation.friendly_notes(row))}</td>"
            "</tr>"
        )
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %Z")
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><title>Play Store App Audit report</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:28px;background:#f5f7fa;color:#20252b}}.wrap{{max-width:1500px;margin:auto}}h1{{margin-bottom:4px}}.muted{{color:#6f7c87}}.cards{{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0}}.card{{background:white;border:1px solid #dde3e8;border-radius:10px;padding:10px 15px;min-width:100px;display:flex;justify-content:space-between;gap:18px}}.card span{{font-size:20px;font-weight:700}}table{{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden}}th,td{{padding:8px 10px;border-bottom:1px solid #e6ebef;text-align:left;vertical-align:top}}th{{background:#eef2f5;position:sticky;top:0}}tr.green{{background:#f2f9f3}}tr.yellow{{background:#fffcef}}tr.orange{{background:#fff7ee}}tr.red{{background:#fdf3f3}}tr.blue{{background:#f0f7fc}}tr.purple{{background:#f8f2fa}}code{{font-family:Consolas,monospace}}
</style></head><body><div class="wrap"><h1>Play Store App Audit</h1><p class="muted">Generated {html.escape(generated)} · App version {APP_VERSION}</p>{device_html}<div class="cards">{cards}</div><table><thead><tr><th>Status</th><th>Package</th><th>Play Store title</th><th>Last update</th><th>Age</th><th>Android compatibility</th><th>Maintenance Score</th><th>Notes</th></tr></thead><tbody>{"".join(table_rows)}</tbody></table></div></body></html>"""
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
