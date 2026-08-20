from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playstore_app_audit.platform.runtime import app_data_dir

CACHE_SCHEMA_VERSION = 2
DEFAULT_STORE_WORKERS = 16
MIN_STORE_WORKERS = 4
MAX_STORE_WORKERS = 32

DEFAULT_SETTINGS: dict[str, Any] = {
    "store_language": "en",
    "store_workers": DEFAULT_STORE_WORKERS,
    "cache_enabled": True,
    "cache_ttl_hours": 72,
    "compare_previous": False,
    "exclude_system_source": True,
    "technical_columns": [],
    "qt_header_state": "",
    "ctk_column_widths": {},
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
        workers = int(value)
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


def load_settings() -> dict[str, Any]:
    data = _read_json(settings_path(), {})
    settings = deepcopy(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        settings.update(data)
    language = str(settings.get("store_language") or "en").strip().lower()
    settings["store_language"] = language or "en"
    settings["store_workers"] = normalise_store_workers(settings.get("store_workers"))
    try:
        settings["cache_ttl_hours"] = max(0, min(24 * 30, int(settings.get("cache_ttl_hours", 72))))
    except (TypeError, ValueError):
        settings["cache_ttl_hours"] = 72
    settings["cache_enabled"] = bool(settings.get("cache_enabled", True))
    settings["compare_previous"] = bool(settings.get("compare_previous", False))
    settings["exclude_system_source"] = bool(settings.get("exclude_system_source", True))
    cols = settings.get("technical_columns", [])
    settings["technical_columns"] = (
        [c for c in cols if c in TECHNICAL_COLUMNS] if isinstance(cols, list) else []
    )
    if not isinstance(settings.get("ctk_column_widths"), dict):
        settings["ctk_column_widths"] = {}
    return settings


def save_settings(settings: dict[str, Any]) -> dict[str, Any]:
    merged = load_settings()
    merged.update(settings)
    merged["store_workers"] = normalise_store_workers(merged.get("store_workers"))
    _write_json(settings_path(), merged)
    return merged


def reset_settings() -> dict[str, Any]:
    defaults = deepcopy(DEFAULT_SETTINGS)
    _write_json(settings_path(), defaults)
    return defaults


def clear_cache() -> None:
    _write_json(cache_path(), {})


def _cache_key(country: str, language: str, package_name: str) -> str:
    # Versioning the key deliberately invalidates results cached by builds that
    # could still derive an update date from datePublished.
    return f"v{CACHE_SCHEMA_VERSION}|{country.lower()}|{language.lower()}|{package_name}"


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
    data = _read_json(cache_path(), {})
    if not isinstance(data, dict):
        data = {}
    now = datetime.now(UTC).isoformat()
    for row in rows:
        if row.get("play_status") != "available" or not row.get("play_last_update"):
            continue
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
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
            }
        }
        data[_cache_key(country, language, package_name)] = {"fetched_at": now, "row": stored}

    cutoff_seconds = 45 * 24 * 3600
    current_time = datetime.now(UTC)
    for key in list(data):
        try:
            fetched = datetime.fromisoformat(str(data[key]["fetched_at"]).replace("Z", "+00:00"))
            if (current_time - fetched.astimezone(UTC)).total_seconds() > cutoff_seconds:
                data.pop(key, None)
        except Exception:
            data.pop(key, None)
    _write_json(cache_path(), data)


def load_history() -> dict[str, dict[str, Any]]:
    data = _read_json(history_path(), {})
    return data if isinstance(data, dict) else {}


def compare_with_history(row: dict[str, Any], history: dict[str, dict[str, Any]]) -> str:
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


def save_history(rows: list[dict[str, Any]]) -> None:
    now = datetime.now(UTC).isoformat()
    data: dict[str, dict[str, Any]] = {}
    for row in rows:
        package_name = str(row.get("package_name") or "").strip()
        if not package_name:
            continue
        data[package_name] = {
            "criticality_key": row.get("criticality_key", ""),
            "criticality_rank": row.get("criticality_rank", 99),
            "criticality": row.get("criticality", ""),
            "play_last_update": row.get("play_last_update", ""),
            "saved_at": now,
        }
    _write_json(history_path(), data)
