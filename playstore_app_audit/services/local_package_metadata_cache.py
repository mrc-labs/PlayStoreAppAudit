"""Bounded, local-only cache of successfully parsed package metadata.

Tier 1 trusts exact filesystem identity (canonical path, size and nanosecond
timestamps). Tier 2 reuses already parsed intrinsic metadata by exact SHA-256
content identity when a path changed or an identical package appears elsewhere.
The second tier is only probed when the cache already contains the same
size/format, so ordinary cold unique files do not gain an extra full-file read.

This cache never stores Store responses, provider results or comparison verdicts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFormat,
    LocalArtifactParseResult,
    LocalArtifactWarning,
)
from playstore_app_audit.platform.runtime import app_data_dir
from playstore_app_audit.services.local_package_container import parse_local_package

SCHEMA_VERSION = 2
MAX_ENTRIES = 512
_LOCK = threading.RLock()
_CONTENT_CONDITION = threading.Condition(_LOCK)
_INFLIGHT_CONTENT_KEYS: set[tuple[int, str]] = set()
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
            "ctime_ns INTEGER NOT NULL, format TEXT NOT NULL, sha256 TEXT NOT NULL, "
            "metadata TEXT NOT NULL, last_used INTEGER NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS artifacts_sha256_idx "
            "ON artifacts(sha256, size, format)"
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


def _decode(
    raw: str,
    identity: tuple[Path, int, int, int, LocalArtifactFormat],
    *,
    expected_sha256: str | None = None,
) -> LocalArtifact:
    payload = json.loads(raw)
    canonical, size, mtime_ns, _, artifact_format = identity
    if not isinstance(payload, dict) or set(payload) != {field.name for field in fields(LocalArtifact)}:
        raise ValueError("Invalid cached artifact fields")
    if payload["artifact_format"] != artifact_format.value:
        raise ValueError("Cached artifact format differs")
    digest = payload["artifact_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(
        c not in "0123456789abcdef" for c in digest
    ):
        raise ValueError("Invalid cached SHA-256")
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError("Cached SHA-256 differs from content identity")
    payload["artifact_format"] = artifact_format
    payload["canonical_path"] = canonical
    payload["file_name"] = canonical.name
    payload["file_size"] = size
    payload["modified_at"] = datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=UTC)
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


def _has_content_candidate(
    identity: tuple[Path, int, int, int, LocalArtifactFormat],
) -> bool:
    _, size, _, _, artifact_format = identity
    try:
        with _LOCK, closing(_connect()) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM artifacts WHERE size=? AND format=? LIMIT 1",
                    (size, artifact_format.value),
                ).fetchone()
                is not None
            )
    except (OSError, sqlite3.Error):
        _LOGGER.warning("Local package content-cache candidate lookup failed", exc_info=True)
        return False


def _stable_sha256(
    path: Path,
    identity: tuple[Path, int, int, int, LocalArtifactFormat],
) -> str | None:
    if _identity(path) != identity:
        return None
    digest = hashlib.sha256()
    try:
        with identity[0].open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return None
    if _identity(identity[0]) != identity:
        return None
    return digest.hexdigest()


def lookup_content(
    path: str | Path,
    artifact_sha256: str,
) -> LocalArtifact | None:
    identity = _identity(Path(path))
    if identity is None:
        return None
    canonical, size, _, _, artifact_format = identity
    try:
        with _LOCK, closing(_connect()) as connection:
            stored = connection.execute(
                "SELECT path, metadata FROM artifacts WHERE sha256=? AND size=? AND format=? "
                "ORDER BY last_used DESC, path DESC LIMIT 1",
                (artifact_sha256, size, artifact_format.value),
            ).fetchone()
            if stored is None:
                return None
            artifact = _decode(
                stored[1],
                identity,
                expected_sha256=artifact_sha256,
            )
            if _identity(canonical) != identity:
                return None
            connection.execute(
                "UPDATE artifacts SET last_used=strftime('%s','now') WHERE path=?",
                (stored[0],),
            )
            connection.commit()
            return artifact
    except (OSError, sqlite3.Error, TypeError, ValueError, KeyError):
        _LOGGER.warning("Local package content-cache lookup failed", exc_info=True)
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
                "INSERT OR REPLACE INTO artifacts VALUES "
                "(?,?,?,?,?,?,?,strftime('%s','now'))",
                (
                    str(canonical),
                    size,
                    mtime_ns,
                    ctime_ns,
                    artifact_format.value,
                    artifact.artifact_sha256,
                    _encode(artifact),
                ),
            )
            connection.execute(
                "DELETE FROM artifacts WHERE path IN (SELECT path FROM artifacts "
                "ORDER BY last_used DESC, path DESC LIMIT -1 OFFSET ?)",
                (MAX_ENTRIES,),
            )
            connection.commit()
    except (OSError, sqlite3.Error, TypeError, ValueError):
        _LOGGER.warning("Local package metadata cache write failed", exc_info=True)


def _release_content_key(key: tuple[int, str]) -> None:
    with _CONTENT_CONDITION:
        _INFLIGHT_CONTENT_KEYS.discard(key)
        _CONTENT_CONDITION.notify_all()


def parse_cached_local_package(
    path: str | Path,
    *,
    cancel_event: threading.Event | None = None,
    parser: Callable[[str | Path], LocalArtifactParseResult] | None = None,
    allow_content_reuse: bool = True,
) -> tuple[LocalArtifactParseResult, bool]:
    started = perf_counter()
    initial_identity = _identity(Path(path))
    cached = lookup(path)
    if cached is not None:
        _LOGGER.debug(
            "Local package metadata profile path=%s cache=tier1 total_ms=%.2f",
            path,
            (perf_counter() - started) * 1000,
        )
        return LocalArtifactParseResult(artifact=cached), True

    # Tests or diagnostics that need to assert exact parser invocation can opt
    # out explicitly. Production parser adapters still participate in Tier 2.
    if initial_identity is None or not allow_content_reuse:
        parse_started = perf_counter()
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
        _LOGGER.debug(
            "Local package metadata profile path=%s cache=miss parse_ms=%.2f total_ms=%.2f",
            path,
            (perf_counter() - parse_started) * 1000,
            (perf_counter() - started) * 1000,
        )
        return parsed, False

    _, size, _, _, artifact_format = initial_identity
    content_key = (size, artifact_format.value)
    reserved = False
    candidate_exists = False

    with _CONTENT_CONDITION:
        while content_key in _INFLIGHT_CONTENT_KEYS:
            if cancel_event and cancel_event.is_set():
                break
            _CONTENT_CONDITION.wait(timeout=0.05)

        if not (cancel_event and cancel_event.is_set()):
            candidate_exists = _has_content_candidate(initial_identity)
            _INFLIGHT_CONTENT_KEYS.add(content_key)
            reserved = True

    try:
        if candidate_exists:
            probe_started = perf_counter()
            digest = _stable_sha256(initial_identity[0], initial_identity)
            if digest is not None:
                content_cached = lookup_content(path, digest)
                if content_cached is not None:
                    remember(path, content_cached)
                    _LOGGER.debug(
                        "Local package metadata profile path=%s cache=tier2 "
                        "sha_probe_ms=%.2f total_ms=%.2f",
                        path,
                        (perf_counter() - probe_started) * 1000,
                        (perf_counter() - started) * 1000,
                    )
                    return LocalArtifactParseResult(artifact=content_cached), True

        parse_started = perf_counter()
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
        _LOGGER.debug(
            "Local package metadata profile path=%s cache=miss parse_ms=%.2f total_ms=%.2f",
            path,
            (perf_counter() - parse_started) * 1000,
            (perf_counter() - started) * 1000,
        )
        return parsed, False
    finally:
        if reserved:
            _release_content_key(content_key)


def clear_cache() -> None:
    with _CONTENT_CONDITION:
        _INFLIGHT_CONTENT_KEYS.clear()
        path = cache_path()
        path.unlink(missing_ok=True)
        _CONTENT_CONDITION.notify_all()


def entry_count() -> int:
    if not cache_path().exists():
        return 0
    with _LOCK, closing(_connect()) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
