"""Bounded, local-only cache of successfully parsed package metadata.

Fast hits trust filesystem identity (path, size and nanosecond timestamps).
Cold parsing still performs the parser's full content recheck before an entry
is admitted; this cache never stores Store responses or comparison verdicts.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import fields
from datetime import datetime
from pathlib import Path

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFormat,
    LocalArtifactParseResult,
    LocalArtifactWarning,
)
from playstore_app_audit.platform.runtime import app_data_dir
from playstore_app_audit.services.local_package_container import parse_local_package

SCHEMA_VERSION = 1
MAX_ENTRIES = 512
_LOCK = threading.RLock()
_LOGGER = logging.getLogger(__name__)


def cache_path() -> Path:
    return app_data_dir() / "local_package_metadata.sqlite3"


def _connect() -> sqlite3.Connection:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    try:
        if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
            connection.execute("DROP TABLE IF EXISTS artifacts")
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS artifacts ("
            "path TEXT PRIMARY KEY, size INTEGER NOT NULL, mtime_ns INTEGER NOT NULL, "
            "ctime_ns INTEGER NOT NULL, format TEXT NOT NULL, metadata TEXT NOT NULL, "
            "last_used INTEGER NOT NULL)"
        )
        connection.commit()
        return connection
    except Exception:
        connection.close()
        raise


def _identity(path: Path) -> tuple[Path, int, int, int, LocalArtifactFormat] | None:
    try:
        canonical = path.expanduser().resolve(strict=True)
        if not canonical.is_file():
            return None
        stat = canonical.stat()
        artifact_format = LocalArtifactFormat(canonical.suffix.casefold().lstrip("."))
        return canonical, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, artifact_format
    except (OSError, ValueError):
        return None


def _encode(artifact: LocalArtifact) -> str:
    payload = {field.name: getattr(artifact, field.name) for field in fields(artifact)}
    payload["artifact_format"] = artifact.artifact_format.value
    payload["canonical_path"] = str(artifact.canonical_path)
    payload["modified_at"] = artifact.modified_at.isoformat()
    payload["warnings"] = [warning.value for warning in artifact.warnings]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _decode(raw: str, identity: tuple[Path, int, int, int, LocalArtifactFormat]) -> LocalArtifact:
    payload = json.loads(raw)
    canonical, size, _, _, artifact_format = identity
    if not isinstance(payload, dict) or set(payload) != {field.name for field in fields(LocalArtifact)}:
        raise ValueError("Invalid cached artifact fields")
    if payload["artifact_format"] != artifact_format.value:
        raise ValueError("Cached artifact format differs")
    digest = payload["artifact_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid cached SHA-256")
    payload["artifact_format"] = artifact_format
    payload["canonical_path"] = canonical
    payload["file_name"] = canonical.name
    payload["file_size"] = size
    payload["modified_at"] = datetime.fromisoformat(payload["modified_at"])
    payload["warnings"] = tuple(LocalArtifactWarning(value) for value in payload["warnings"])
    payload["permissions"] = tuple(payload["permissions"])
    payload["features"] = tuple(payload["features"])
    return LocalArtifact(**payload)


def lookup(path: str | Path) -> LocalArtifact | None:
    identity = _identity(Path(path))
    if identity is None:
        return None
    canonical, size, mtime_ns, ctime_ns, artifact_format = identity
    try:
        with _LOCK, closing(_connect()) as connection:
            stored = connection.execute(
                "SELECT metadata FROM artifacts WHERE path=? AND size=? AND mtime_ns=? "
                "AND ctime_ns=? AND format=?",
                (str(canonical), size, mtime_ns, ctime_ns, artifact_format.value),
            ).fetchone()
            if stored is None:
                return None
            artifact = _decode(stored[0], identity)
            if _identity(canonical) != identity:
                return None
            connection.execute(
                "UPDATE artifacts SET last_used=strftime('%s','now') WHERE path=?",
                (str(canonical),),
            )
            connection.commit()
            return artifact
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError):
        _LOGGER.warning("Local package metadata cache read failed; reparsing", exc_info=True)
        return None


def remember(path: str | Path, artifact: LocalArtifact) -> None:
    identity = _identity(Path(path))
    if identity is None:
        return
    canonical, size, mtime_ns, ctime_ns, artifact_format = identity
    if (
        canonical != artifact.canonical_path
        or size != artifact.file_size
        or artifact_format != artifact.artifact_format
    ):
        return
    try:
        with _LOCK, closing(_connect()) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO artifacts VALUES (?,?,?,?,?,?,strftime('%s','now'))",
                (str(canonical), size, mtime_ns, ctime_ns, artifact_format.value, _encode(artifact)),
            )
            connection.execute(
                "DELETE FROM artifacts WHERE path IN (SELECT path FROM artifacts "
                "ORDER BY last_used DESC, path DESC LIMIT -1 OFFSET ?)",
                (MAX_ENTRIES,),
            )
            connection.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        _LOGGER.warning("Local package metadata cache write failed", exc_info=True)


def parse_cached_local_package(
    path: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    parser: Callable[[str | Path], LocalArtifactParseResult] | None = None,
) -> tuple[LocalArtifactParseResult, bool]:
    initial_identity = _identity(Path(path))
    cached = lookup(path)
    if cached is not None:
        return LocalArtifactParseResult(artifact=cached), True
    parsed = (
        parser(path)
        if parser is not None
        else parse_local_package(path, cancel_event=cancel_event)
    )
    if (
        parsed.artifact is not None
        and initial_identity == _identity(Path(path))
        and not (cancel_event and cancel_event.is_set())
    ):
        remember(path, parsed.artifact)
    return parsed, False


def clear_cache() -> None:
    with _LOCK:
        path = cache_path()
        path.unlink(missing_ok=True)


def entry_count() -> int:
    if not cache_path().exists():
        return 0
    with _LOCK, closing(_connect()) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
