from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playstore_app_audit.platform.runtime import app_data_dir
from playstore_app_audit.services.store_locale import resolve_store_language

CACHE_SCHEMA_VERSION = 2
DEFAULT_STORE_WORKERS = 16
MIN_STORE_WORKERS = 4
MAX_STORE_WORKERS = 32
DEFAULT_CACHE_TTL_HOURS = 24
CACHE_TTL_DEFAULT_MIGRATION_KEY = "cache_ttl_default_migrated_v2"
STORE_LANGUAGE_AUTO_MIGRATION_KEY = "store_language_auto_migrated"
AUDIT_CHANGES_FIELD = "_audit_changes"
STORE_EVIDENCE_FIELD = "_store_evidence"

_AVAILABLE_PLAY_STATUSES = frozenset(
    {
        "available",
        "available_in_other_country",
        "available_in_fallback_locale_only",
    }
)
_CHECKED_UNAVAILABLE_PLAY_STATUSES = frozenset({"not_found_in_checked_countries"})
_CONCLUSIVE_STORE_CACHE_STATUSES = frozenset(
    {
        "available",
        "available_in_other_country",
        "available_in_fallback_locale_only",
        "not_found_in_checked_countries",
    }
)
_MAINTENANCE_KEYS = frozenset({"green", "yellow", "orange"})
_MAINTENANCE_LABELS = {
    "green": "Recent Update",
    "yellow": "Aging",
    "orange": "Stale",
}
_UNKNOWN_HISTORY_VALUES = frozenset(
    {
        "",
        "unknown",
        "unknown / preinstalled",
        "none",
        "null",
        "n/a",
    }
)

DEFAULT_SETTINGS: dict[str, Any] = {
    "store_language": "auto",
    STORE_LANGUAGE_AUTO_MIGRATION_KEY: True,
    "store_workers": DEFAULT_STORE_WORKERS,
    "cache_enabled": True,
    "cache_ttl_hours": DEFAULT_CACHE_TTL_HOURS,
    CACHE_TTL_DEFAULT_MIGRATION_KEY: True,
    "compare_previous": False,
    "exclude_system_source": True,
    "collect_full_device_metadata_on_scan": False,
    "details_panel_position": "right",
    "view_preset": "Basic",
    "technical_columns": [],
    "custom_view_exists": False,
    "qt_header_state": "",
    "ctk_column_widths": {},
    "alternative_distribution": {
        "fdroid_main": {"enabled": True},
        "aptoide": {
            "enabled": False,
            "store_name": "",
            "api_key_protected": "",
        },
    },
}

TECHNICAL_COLUMNS = {
    "play_status": "Play status",
    "updated_source": "Update source",
    "play_http_status": "HTTP status",
    "app_name": "Input name",
    "store_url": "Store URL",
    "is_system": "System app",
}


def normalise_store_workers(value: object) -> int:
    try:
        workers = int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        workers = DEFAULT_STORE_WORKERS
    return max(MIN_STORE_WORKERS, min(MAX_STORE_WORKERS, workers))


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return deepcopy(fallback)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def cache_path() -> Path:
    return app_data_dir() / "audit_cache.json"


def history_path() -> Path:
    return app_data_dir() / "audit_history.json"


def alternative_distribution_cache_path() -> Path:
    return app_data_dir() / "alternative_distribution_cache.json"


def load_settings() -> dict[str, Any]:
    data = _read_json(settings_path(), {})
    settings = deepcopy(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        settings.update(data)

    # v1.5 stored `en` as an unconditional default. On the first v1.6 read,
    # migrate that legacy default to Auto so upgraded users receive device/
    # country-aware language selection. A later explicit manual `en` is kept
    # because saves persist the migration marker.
    migrated = bool(isinstance(data, dict) and data.get(STORE_LANGUAGE_AUTO_MIGRATION_KEY))
    raw_language = str(settings.get("store_language") or "auto").strip().lower()
    if not migrated and raw_language == "en":
        raw_language = "auto"
    settings["store_language"] = raw_language or "auto"
    settings[STORE_LANGUAGE_AUTO_MIGRATION_KEY] = True

    # Before v2, 72 hours was written indistinguishably as the application
    # default. Migrate that legacy value exactly once. The persisted marker
    # makes a later deliberate user choice of 72 hours stable.
    cache_default_migrated = bool(
        isinstance(data, dict) and data.get(CACHE_TTL_DEFAULT_MIGRATION_KEY)
    )
    migrate_legacy_cache_default = (
        isinstance(data, dict)
        and not cache_default_migrated
        and data.get("cache_ttl_hours") == 72
    )
    if migrate_legacy_cache_default:
        settings["cache_ttl_hours"] = DEFAULT_CACHE_TTL_HOURS
    settings[CACHE_TTL_DEFAULT_MIGRATION_KEY] = True

    # Device was the v1.x name for the richer source-oriented table layout.
    # Preserve Custom data verbatim while conservatively migrating only that
    # retired built-in name.
    view_preset = str(settings.get("view_preset") or "Basic").strip()
    settings["view_preset"] = "Source Details" if view_preset == "Device" else view_preset

    settings["store_workers"] = normalise_store_workers(settings.get("store_workers"))
    try:
        settings["cache_ttl_hours"] = max(
            0,
            min(
                24 * 30,
                int(settings.get("cache_ttl_hours", DEFAULT_CACHE_TTL_HOURS)),
            ),
        )
    except (TypeError, ValueError):
        settings["cache_ttl_hours"] = DEFAULT_CACHE_TTL_HOURS
    settings["cache_enabled"] = bool(settings.get("cache_enabled", True))
    settings["compare_previous"] = bool(settings.get("compare_previous", False))
    settings["exclude_system_source"] = bool(settings.get("exclude_system_source", True))
    settings["collect_full_device_metadata_on_scan"] = (
        settings.get("collect_full_device_metadata_on_scan") is True
    )
    details_position = str(settings.get("details_panel_position") or "right").strip().casefold()
    settings["details_panel_position"] = (
        details_position
        if details_position in {"auto", "right", "below", "hidden"}
        else "right"
    )
    cols = settings.get("technical_columns", [])
    settings["technical_columns"] = (
        [c for c in cols if c in TECHNICAL_COLUMNS] if isinstance(cols, list) else []
    )
    if not isinstance(settings.get("ctk_column_widths"), dict):
        settings["ctk_column_widths"] = {}
    default_alternative = deepcopy(DEFAULT_SETTINGS["alternative_distribution"])
    raw_alternative = settings.get("alternative_distribution")
    if isinstance(raw_alternative, dict):
        raw_fdroid = raw_alternative.get("fdroid_main")
        if isinstance(raw_fdroid, dict):
            default_alternative["fdroid_main"].update(raw_fdroid)
        raw_aptoide = raw_alternative.get("aptoide")
        if isinstance(raw_aptoide, dict):
            default_alternative["aptoide"].update(raw_aptoide)
    default_alternative["fdroid_main"]["enabled"] = bool(
        default_alternative["fdroid_main"].get("enabled", True)
    )
    default_alternative["aptoide"]["enabled"] = bool(
        default_alternative["aptoide"].get("enabled", False)
    )
    default_alternative["aptoide"]["store_name"] = str(
        default_alternative["aptoide"].get("store_name") or ""
    ).strip().lower()
    default_alternative["aptoide"]["api_key_protected"] = str(
        default_alternative["aptoide"].get("api_key_protected") or ""
    ).strip()
    settings["alternative_distribution"] = default_alternative
    if migrate_legacy_cache_default:
        _write_json(settings_path(), settings)
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = load_settings()
    merged.update(settings)
    language = str(merged.get("store_language") or "auto").strip().lower()
    merged["store_language"] = language or "auto"
    merged[STORE_LANGUAGE_AUTO_MIGRATION_KEY] = True
    merged[CACHE_TTL_DEFAULT_MIGRATION_KEY] = True
    merged["store_workers"] = normalise_store_workers(merged.get("store_workers"))
    merged["collect_full_device_metadata_on_scan"] = (
        merged.get("collect_full_device_metadata_on_scan") is True
    )
    _write_json(settings_path(), merged)
    return merged


def reset_settings() -> dict[str, Any]:
    defaults = deepcopy(DEFAULT_SETTINGS)
    _write_json(settings_path(), defaults)
    return defaults


def clear_cache() -> None:
    _write_json(cache_path(), {})


def clear_alternative_distribution_cache() -> None:
    _write_json(alternative_distribution_cache_path(), {})


def _cache_key(country: str, language: str, package_name: str) -> str:
    # Cache the effective Store language, never the symbolic `auto` preference.
    # This prevents e.g. CH/it device results from being reused by CH/de file
    # audits while still preserving old CH/en cache hits when English resolves.
    effective_language = resolve_store_language(language, country)
    # Versioning the key deliberately invalidates results cached by builds that
    # could still derive an update date from datePublished.
    return f"v{CACHE_SCHEMA_VERSION}|{country.lower()}|{effective_language.lower()}|{package_name}"


def load_fresh_cache(
    apps: list[dict[str, str]],
    country: str,
    language: str,
    ttl_hours: int,
) -> dict[str, dict[str, Any]]:
    if ttl_hours <= 0:
        return {}
    data = _read_json(cache_path(), {})
    if not isinstance(data, dict):
        return {}
    now = datetime.now(UTC)
    fresh: dict[str, dict[str, Any]] = {}
    for app in apps:
        package_name = app.get("package_name", "")
        entry = data.get(_cache_key(country, language, package_name))
        if not isinstance(entry, dict):
            continue
        row = entry.get("row")
        timestamp = entry.get("fetched_at")
        if not isinstance(row, dict) or not timestamp:
            continue
        if row.get("play_status") != "available" or not row.get("play_last_update"):
            continue
        try:
            fetched = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            age_hours = (now - fetched.astimezone(UTC)).total_seconds() / 3600
        except Exception:
            continue
        if age_hours < 0 or age_hours > ttl_hours:
            continue
        cached_row = dict(row)
        cached_row["app_name"] = app.get("app_name", package_name)
        cached_row["package_name"] = package_name
        cached_row["cache_hit"] = True
        fresh[package_name] = cached_row
    return fresh


def update_cache(rows: list[dict[str, Any]], country: str, language: str) -> None:
    """Reconcile completed live Store rows with the reusable healthy cache.

    Healthy available rows replace their exact entry. Conclusive live evidence
    that is not healthy-cacheable removes only its exact old entry, while
    transient or inconclusive evidence leaves any prior healthy entry intact.
    Callers pass completed live rows only, so uncompleted packages are untouched.
    """

    data = _read_json(cache_path(), {})
    if not isinstance(data, dict):
        data = {}
    now = datetime.now(UTC).isoformat()
    for row in rows:
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
            continue
        key = _cache_key(country, language, package_name)
        play_status = str(row.get("play_status") or "").strip()
        if play_status != "available" or not row.get("play_last_update"):
            if play_status in _CONCLUSIVE_STORE_CACHE_STATUSES:
                data.pop(key, None)
            continue
        stored = {
            key: value
            for key, value in row.items()
            if key
            not in {
                "criticality",
                "criticality_key",
                "criticality_rank",
                "age_days",
                "change",
                "cache_hit",
                AUDIT_CHANGES_FIELD,
            }
        }
        data[key] = {"fetched_at": now, "row": stored}

    cutoff_seconds = 45 * 24 * 3600
    current_time = datetime.now(UTC)
    for key in list(data):
        try:
            fetched = datetime.fromisoformat(
                str(data[key]["fetched_at"]).replace("Z", "+00:00")
            )
            if (current_time - fetched.astimezone(UTC)).total_seconds() > cutoff_seconds:
                data.pop(key, None)
        except Exception:
            data.pop(key, None)
    _write_json(cache_path(), data)


def update_cached_store_metadata(
    package_name: str,
    country: str,
    language: str,
    metadata: dict[str, str],
) -> bool:
    """Complete metadata in one healthy cache row without refreshing its TTL."""

    package = str(package_name or "").strip()
    if not package:
        return False
    data = _read_json(cache_path(), {})
    if not isinstance(data, dict):
        return False
    entry = data.get(_cache_key(country, language, package))
    if not isinstance(entry, dict) or not isinstance(entry.get("row"), dict):
        return False
    row = dict(entry["row"])
    if row.get("play_status") != "available" or not row.get("play_last_update"):
        return False

    changed = False
    icon_url = str(metadata.get("play_icon_url") or "").strip()
    if icon_url.lower().startswith("https://") and not str(row.get("play_icon_url") or "").strip():
        row["play_icon_url"] = icon_url
        changed = True
    developer = str(metadata.get("developer") or "").strip()
    if developer and not str(row.get("developer") or "").strip():
        row["developer"] = developer
        changed = True
    if not changed:
        return False

    entry = dict(entry)
    entry["row"] = row
    data[_cache_key(country, language, package)] = entry
    _write_json(cache_path(), data)
    return True


def load_history() -> dict[str, dict[str, Any]]:
    data = _read_json(history_path(), {})
    return data if isinstance(data, dict) else {}


def _history_evidence(value: object) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _meaningful_history_value(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in _UNKNOWN_HISTORY_VALUES else text


def _availability_event(
    event_type: str,
    previous: dict[str, Any],
    row: dict[str, Any],
    previous_status: str,
    current_status: str,
) -> dict[str, Any]:
    return {
        "type": event_type,
        "previous": previous_status,
        "current": current_status,
        "previous_store_country": str(previous.get("store_country") or "").strip().lower(),
        "current_store_country": str(row.get("store_country") or "").strip().lower(),
        "previous_evidence": _history_evidence(previous.get(STORE_EVIDENCE_FIELD)),
        "current_evidence": _history_evidence(row.get(STORE_EVIDENCE_FIELD)),
    }


def changes_with_history(
    row: dict[str, Any], history: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return structured changes against the previous saved Play Store audit.

    Sparse pre-v1.6 history remains valid: events are emitted only when both
    sides contain enough evidence to support the comparison.
    """
    package_name = str(row.get("package_name") or "")
    previous = history.get(package_name)
    if not isinstance(previous, dict):
        return []

    changes: list[dict[str, Any]] = []
    previous_status = str(previous.get("play_status") or "").strip()
    current_status = str(row.get("play_status") or "").strip()
    previous_available = previous_status in _AVAILABLE_PLAY_STATUSES
    current_available = current_status in _AVAILABLE_PLAY_STATUSES
    previous_checked_unavailable = previous_status in _CHECKED_UNAVAILABLE_PLAY_STATUSES
    current_checked_unavailable = current_status in _CHECKED_UNAVAILABLE_PLAY_STATUSES

    if previous_checked_unavailable and current_available:
        changes.append(
            _availability_event("reappeared", previous, row, previous_status, current_status)
        )
    elif previous_available and current_checked_unavailable:
        changes.append(
            _availability_event(
                "newly_unavailable_in_checked_countries",
                previous,
                row,
                previous_status,
                current_status,
            )
        )
    elif previous_status and not previous_available and not previous_checked_unavailable and current_available:
        changes.append(
            _availability_event("newly_available", previous, row, previous_status, current_status)
        )

    previous_version = _meaningful_history_value(previous.get("play_version"))
    current_version = _meaningful_history_value(row.get("play_version"))
    if previous_version and current_version and previous_version != current_version:
        changes.append(
            {
                "type": "store_version_changed",
                "previous": previous_version,
                "current": current_version,
            }
        )

    previous_update = _meaningful_history_value(previous.get("play_last_update"))
    current_update = _meaningful_history_value(row.get("play_last_update"))
    if previous_update and current_update and previous_update != current_update:
        changes.append(
            {
                "type": "store_latest_update_changed",
                "previous": previous_update,
                "current": current_update,
            }
        )

    previous_key = str(previous.get("criticality_key") or "").strip()
    current_key = str(row.get("criticality_key") or "").strip()
    if (
        previous_key in _MAINTENANCE_KEYS
        and current_key in _MAINTENANCE_KEYS
        and previous_key != current_key
    ):
        changes.append(
            {
                "type": "maintenance_state_changed",
                "previous": _MAINTENANCE_LABELS[previous_key],
                "current": _MAINTENANCE_LABELS[current_key],
                "previous_key": previous_key,
                "current_key": current_key,
            }
        )

    previous_installer = _meaningful_history_value(previous.get("installer_source"))
    current_installer = _meaningful_history_value(row.get("installer_source"))
    if previous_installer and current_installer and previous_installer != current_installer:
        changes.append(
            {
                "type": "installer_source_changed",
                "previous": previous_installer,
                "current": current_installer,
            }
        )

    return changes


def compare_with_history(row: dict[str, Any], history: dict[str, dict[str, Any]]) -> str:
    # Keep the compact legacy label stable while attaching richer v1.6 data for
    # the details panel and change-oriented views.
    row[AUDIT_CHANGES_FIELD] = changes_with_history(row, history)
    package_name = str(row.get("package_name") or "")
    previous = history.get(package_name)
    if not isinstance(previous, dict):
        return "New"
    previous_key = str(previous.get("criticality_key") or "")
    current_key = str(row.get("criticality_key") or "")
    if previous_key == current_key:
        return "Same"
    try:
        previous_rank = int(previous.get("criticality_rank", 99))
        current_rank = int(row.get("criticality_rank", 99))
    except (TypeError, ValueError):
        return "Changed"
    if current_rank < previous_rank:
        return "↓ Worse"
    if current_rank > previous_rank:
        return "↑ Better"
    return "Changed"


def _history_snapshot(row: dict[str, Any], saved_at: str) -> dict[str, Any]:
    return {
        "criticality_key": row.get("criticality_key", ""),
        "criticality_rank": row.get("criticality_rank", 99),
        "criticality": row.get("criticality", ""),
        "play_status": row.get("play_status", ""),
        "play_version": row.get("play_version", ""),
        "play_last_update": row.get("play_last_update", ""),
        "installer_source": row.get("installer_source", ""),
        "store_country": row.get("store_country", ""),
        "store_language": row.get("store_language", ""),
        STORE_EVIDENCE_FIELD: _history_evidence(row.get(STORE_EVIDENCE_FIELD)),
        "saved_at": saved_at,
    }


def save_history(rows: list[dict[str, Any]]) -> None:
    now = datetime.now(UTC).isoformat()
    data: dict[str, dict[str, Any]] = {}
    for row in rows:
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
            continue
        data[package_name] = _history_snapshot(row, now)
    _write_json(history_path(), data)


def save_history_merged(rows: list[dict[str, Any]]) -> None:
    """Update history rows without deleting packages omitted by a targeted recheck."""
    data = load_history()
    now = datetime.now(UTC).isoformat()
    for row in rows:
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
            continue
        data[package_name] = _history_snapshot(row, now)
    _write_json(history_path(), data)
