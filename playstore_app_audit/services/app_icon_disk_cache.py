from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from playstore_app_audit.platform.runtime import app_data_dir

ICON_CACHE_DIRNAME = "app-icons"
ICON_INDEX_FILENAME = "index.json"


def icon_cache_dir() -> Path:
    path = app_data_dir() / ICON_CACHE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def icon_index_path() -> Path:
    return icon_cache_dir() / ICON_INDEX_FILENAME


def _load_index() -> dict[str, dict[str, str]]:
    path = icon_index_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, str]] = {}
    for package_name, value in raw.items():
        if not isinstance(package_name, str) or not isinstance(value, dict):
            continue
        result[package_name] = {
            "file": str(value.get("file") or ""),
            "icon_url": str(value.get("icon_url") or ""),
            "play_last_update": str(value.get("play_last_update") or ""),
        }
    return result


def _save_index(index: dict[str, dict[str, str]]) -> None:
    path = icon_index_path()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def _filename_for_package(package_name: str) -> str:
    digest = hashlib.sha256(package_name.encode("utf-8")).hexdigest()
    return f"{digest}.img"


def load_cached_icon_bytes(
    package_name: object,
    icon_url: object,
    play_last_update: object,
) -> bytes | None:
    """Return persisted icon bytes while the Store update marker is unchanged.

    If a Store update date is available, it is the cache invalidation key. This
    intentionally allows long-lived icon retention across sessions and across
    CDN URL changes. When no update marker is available, URL equality is used as
    the conservative fallback invalidation rule.
    """
    package = str(package_name or "").strip()
    url = str(icon_url or "").strip()
    update = str(play_last_update or "").strip()
    if not package or not url:
        return None

    index = _load_index()
    entry = index.get(package)
    if not entry:
        return None

    cached_update = str(entry.get("play_last_update") or "").strip()
    cached_url = str(entry.get("icon_url") or "").strip()
    valid = cached_update == update if update else cached_url == url
    if not valid:
        remove_cached_icon(package)
        return None

    filename = str(entry.get("file") or "").strip()
    if not filename:
        return None
    path = icon_cache_dir() / filename
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return data or None


def store_cached_icon_bytes(
    package_name: object,
    icon_url: object,
    play_last_update: object,
    data: bytes,
) -> None:
    package = str(package_name or "").strip()
    url = str(icon_url or "").strip()
    update = str(play_last_update or "").strip()
    if not package or not url or not data:
        return

    cache_dir = icon_cache_dir()
    filename = _filename_for_package(package)
    destination = cache_dir / filename
    temp = destination.with_suffix(destination.suffix + ".tmp")
    temp.write_bytes(data)
    temp.replace(destination)

    index = _load_index()
    index[package] = {
        "file": filename,
        "icon_url": url,
        "play_last_update": update,
    }
    _save_index(index)


def remove_cached_icon(package_name: object) -> None:
    package = str(package_name or "").strip()
    if not package:
        return
    index = _load_index()
    entry = index.pop(package, None)
    if entry:
        filename = str(entry.get("file") or "").strip()
        if filename:
            try:
                (icon_cache_dir() / filename).unlink(missing_ok=True)
            except OSError:
                pass
        _save_index(index)


def cached_icon_metadata(package_name: object) -> dict[str, Any]:
    """Test/support helper exposing one persisted cache record."""
    package = str(package_name or "").strip()
    return dict(_load_index().get(package, {}))
