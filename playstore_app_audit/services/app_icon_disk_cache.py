from __future__ import annotations

import hashlib
import json
import threading
from contextlib import suppress
from pathlib import Path
from typing import Any

from playstore_app_audit.platform.runtime import app_data_dir

ICON_CACHE_DIRNAME = "app-icons"
ICON_INDEX_FILENAME = "index.json"
MAX_CACHED_ICON_BYTES = 1_000_000
MAX_ICON_CACHE_ENTRIES = 512
MAX_ICON_CACHE_BYTES = 64 * 1024 * 1024

_PRUNE_LOCK = threading.Lock()
_PRUNED_CACHE_DIRS: set[Path] = set()


def icon_cache_dir() -> Path:
    return app_data_dir() / ICON_CACHE_DIRNAME


def _ensure_icon_cache_dir() -> Path | None:
    path = icon_cache_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    return path


def icon_index_path() -> Path:
    return icon_cache_dir() / ICON_INDEX_FILENAME


def _read_index() -> tuple[dict[str, dict[str, Any]], bool]:
    path = icon_index_path()
    try:
        if not path.is_file():
            return {}, True
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return {}, False
    except (UnicodeError, json.JSONDecodeError):
        return {}, True
    if not isinstance(raw, dict):
        return {}, True
    result: dict[str, dict[str, Any]] = {}
    for package_name, value in raw.items():
        if not isinstance(package_name, str) or not isinstance(value, dict):
            continue
        try:
            size_bytes = max(0, int(value.get("size_bytes") or 0))
        except (TypeError, ValueError):
            size_bytes = 0
        result[package_name] = {
            "file": str(value.get("file") or ""),
            "icon_url": str(value.get("icon_url") or ""),
            "play_last_update": str(value.get("play_last_update") or ""),
            "size_bytes": size_bytes,
        }
    return result, True


def _load_index() -> dict[str, dict[str, Any]]:
    return _read_index()[0]


def _save_index(index: dict[str, dict[str, Any]]) -> bool:
    cache_dir = _ensure_icon_cache_dir()
    if cache_dir is None:
        return False
    path = cache_dir / ICON_INDEX_FILENAME
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        temp.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    except OSError:
        with suppress(OSError):
            temp.unlink(missing_ok=True)
        return False
    return True


def _filename_for_package(package_name: str) -> str:
    digest = hashlib.sha256(package_name.encode("utf-8")).hexdigest()
    return f"{digest}.img"


def _cache_file_path(package_name: str, filename: object) -> Path | None:
    name = str(filename or "").strip()
    if not name or name != _filename_for_package(package_name):
        return None
    return icon_cache_dir() / name


def _bounded_index(
    index: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[Path]]:
    bounded: dict[str, dict[str, Any]] = {}
    sizes: dict[str, int] = {}
    removed: list[Path] = []

    for package, raw_entry in index.items():
        entry = dict(raw_entry)
        path = _cache_file_path(package, entry.get("file"))
        if path is None:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size <= 0 or size > MAX_CACHED_ICON_BYTES:
            removed.append(path)
            continue
        entry["size_bytes"] = size
        bounded[package] = entry
        sizes[package] = size

    total_bytes = sum(sizes.values())
    entry_limit = max(0, int(MAX_ICON_CACHE_ENTRIES))
    byte_limit = max(0, int(MAX_ICON_CACHE_BYTES))
    while bounded and (len(bounded) > entry_limit or total_bytes > byte_limit):
        package = next(iter(bounded))
        entry = bounded.pop(package)
        total_bytes -= sizes.pop(package, 0)
        path = _cache_file_path(package, entry.get("file"))
        if path is not None:
            removed.append(path)
    return bounded, removed


def prune_icon_cache() -> int:
    """Remove invalid and oldest bounded-cache entries without touching audit data."""
    cache_dir = icon_cache_dir()
    if not cache_dir.is_dir():
        return 0
    index, index_readable = _read_index()
    bounded, removed = _bounded_index(index)
    if index_readable:
        referenced = {
            path.name
            for package, entry in bounded.items()
            if (path := _cache_file_path(package, entry.get("file"))) is not None
        }
        removed.extend(path for path in cache_dir.glob("*.img") if path.name not in referenced)
    if bounded == index and not removed:
        return 0
    if not _save_index(bounded):
        return 0
    removed_count = 0
    for path in dict.fromkeys(removed):
        try:
            path.unlink(missing_ok=True)
            removed_count += 1
        except OSError:
            pass
    return removed_count


def _prune_icon_cache_once() -> None:
    cache_dir = icon_cache_dir()
    with _PRUNE_LOCK:
        if cache_dir in _PRUNED_CACHE_DIRS:
            return
        prune_icon_cache()
        _PRUNED_CACHE_DIRS.add(cache_dir)


def load_cached_icon_bytes(
    package_name: object,
    icon_url: object,
    play_last_update: object,
) -> bytes | None:
    """Return persisted icon bytes while the Store update marker is unchanged.

    If a Store update date is available, it is the cache invalidation key. This
    intentionally allows long-lived icon retention across sessions and across
    CDN URL changes. When no update marker is available, URL equality is used as
    the conservative fallback invalidation rule. Filesystem failures degrade to
    a cache miss so callers can continue through the normal network path.
    """
    package = str(package_name or "").strip()
    url = str(icon_url or "").strip()
    update = str(play_last_update or "").strip()
    if not package or not url:
        return None

    _prune_icon_cache_once()
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

    path = _cache_file_path(package, entry.get("file"))
    if path is None:
        remove_cached_icon(package)
        return None
    try:
        if not (0 < path.stat().st_size <= MAX_CACHED_ICON_BYTES):
            remove_cached_icon(package)
            return None
        with path.open("rb") as stream:
            data = stream.read(MAX_CACHED_ICON_BYTES + 1)
    except OSError:
        remove_cached_icon(package)
        return None
    if not data or len(data) > MAX_CACHED_ICON_BYTES:
        remove_cached_icon(package)
        return None
    return data


def store_cached_icon_bytes(
    package_name: object,
    icon_url: object,
    play_last_update: object,
    data: bytes,
) -> None:
    package = str(package_name or "").strip()
    url = str(icon_url or "").strip()
    update = str(play_last_update or "").strip()
    if not package or not url or not data or len(data) > MAX_CACHED_ICON_BYTES:
        return

    cache_dir = _ensure_icon_cache_dir()
    if cache_dir is None:
        return
    filename = _filename_for_package(package)
    destination = cache_dir / filename
    temp = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temp.write_bytes(data)
        temp.replace(destination)
    except OSError:
        with suppress(OSError):
            temp.unlink(missing_ok=True)
        return

    index = _load_index()
    previous = index.pop(package, None)
    index[package] = {
        "file": filename,
        "icon_url": url,
        "play_last_update": update,
        "size_bytes": len(data),
    }
    bounded, removed = _bounded_index(index)
    if not _save_index(bounded):
        # An icon without an index entry cannot be reused and would otherwise
        # accumulate as an orphan if persistent storage keeps failing.
        if previous is None:
            with suppress(OSError):
                destination.unlink(missing_ok=True)
        return
    for path in dict.fromkeys(removed):
        with suppress(OSError):
            path.unlink(missing_ok=True)


def remove_cached_icon(package_name: object) -> None:
    package = str(package_name or "").strip()
    if not package:
        return
    index = _load_index()
    entry = index.pop(package, None)
    if not entry:
        return

    path = _cache_file_path(package, entry.get("file"))
    if path is not None:
        with suppress(OSError):
            path.unlink(missing_ok=True)
    _save_index(index)


def cached_icon_metadata(package_name: object) -> dict[str, Any]:
    """Test/support helper exposing one persisted cache record."""
    package = str(package_name or "").strip()
    return dict(_load_index().get(package, {}))
