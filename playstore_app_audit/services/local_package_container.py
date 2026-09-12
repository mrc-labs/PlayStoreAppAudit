from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import tempfile
import threading
import zipfile
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import IO, Any

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseResult,
)
from playstore_app_audit.services.local_apk import parse_local_apk

_CONTAINER_SUFFIXES = {
    ".apks": LocalArtifactFormat.APKS,
    ".apkm": LocalArtifactFormat.APKM,
    ".xapk": LocalArtifactFormat.XAPK,
}
_EOCD_SIGNATURE = b"PK\x05\x06"
_EOCD = struct.Struct("<4s4H2LH")
_ZIP64_SENTINEL_16 = 0xFFFF
_ZIP64_SENTINEL_32 = 0xFFFFFFFF
_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_PACKAGE_APK_STEM = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)
_SPLIT_NAME_PREFIXES = (
    "config.",
    "config_",
    "split.",
    "split_",
    "split-config.",
    "split-config_",
    "split_config.",
    "split_config_",
    "feature.",
    "feature_",
)


@dataclass(frozen=True, slots=True)
class ContainerInspectionLimits:
    max_container_bytes: int = 2 * 1024**3
    max_central_directory_bytes: int = 32 * 1024**2
    max_entries: int = 4_096
    max_total_uncompressed_bytes: int = 4 * 1024**3
    max_entry_uncompressed_bytes: int = 2 * 1024**3
    max_compression_ratio: int = 1_000
    max_metadata_bytes: int = 1024**2


DEFAULT_CONTAINER_LIMITS = ContainerInspectionLimits()


class _ContainerFailure(Exception):
    def __init__(self, kind: LocalArtifactFailureKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def parse_local_package(
    path: str | Path,
    *,
    limits: ContainerInspectionLimits = DEFAULT_CONTAINER_LIMITS,
    cancel_event: threading.Event | None = None,
) -> LocalArtifactParseResult:
    """Parse an APK or bounded installable container as one physical artifact."""

    supplied = Path(path)
    suffix = supplied.suffix.casefold()
    if suffix == ".apk":
        return parse_local_apk(supplied)
    artifact_format = _CONTAINER_SUFFIXES.get(suffix)
    if artifact_format is None:
        return _result_failure(
            supplied.absolute(),
            LocalArtifactFailureKind.UNSUPPORTED_FORMAT,
            "Supported local package formats are .apk, .apks, .apkm, and .xapk.",
        )

    try:
        canonical = supplied.expanduser().resolve(strict=True)
    except FileNotFoundError:
        return _result_failure(
            supplied.absolute(),
            LocalArtifactFailureKind.NOT_FOUND,
            "The local package does not exist.",
        )
    except OSError:
        return _result_failure(
            supplied.absolute(),
            LocalArtifactFailureKind.IO_ERROR,
            "The local package path could not be resolved.",
        )
    if not canonical.is_file():
        return _result_failure(
            canonical,
            LocalArtifactFailureKind.NOT_A_FILE,
            "The local package path is not a regular file.",
        )

    cancelled = cancel_event or threading.Event()
    container_sha256: str | None = None
    try:
        with canonical.open("rb") as source:
            initial_stat = os.fstat(source.fileno())
            if initial_stat.st_size <= 0:
                raise _ContainerFailure(
                    LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                    "The package container is empty or is not valid ZIP data.",
                )
            if initial_stat.st_size > limits.max_container_bytes:
                raise _ContainerFailure(
                    LocalArtifactFailureKind.FILE_TOO_LARGE,
                    "The package container exceeds the configured file-size limit.",
                )
            container_sha256 = _hash_stream(
                source,
                limits.max_container_bytes,
                cancelled,
            )
            _check_cancelled(cancelled)
            _preflight_zip(source, initial_stat.st_size, limits)
            source.seek(0)
            with zipfile.ZipFile(source, mode="r", allowZip64=False) as archive:
                infos = _inspect_entries(archive, limits)
                base_info = _select_base_apk(archive, infos, artifact_format, limits)
                with tempfile.TemporaryDirectory(prefix="playstore_audit_package_") as temp_dir:
                    extracted = Path(temp_dir) / "base.apk"
                    _extract_member(archive, base_info, extracted, limits, cancelled)
                    _check_cancelled(cancelled)
                    parsed = parse_local_apk(
                        extracted,
                        allow_split_dependencies=True,
                    )
                    _check_cancelled(cancelled)

            final_sha256 = _hash_stream(
                source,
                limits.max_container_bytes,
                cancelled,
            )
            final_stat = os.fstat(source.fileno())
            if (
                final_sha256 != container_sha256
                or final_stat.st_size != initial_stat.st_size
                or final_stat.st_mtime_ns != initial_stat.st_mtime_ns
            ):
                raise _ContainerFailure(
                    LocalArtifactFailureKind.IO_ERROR,
                    "The package container changed while it was being parsed.",
                )

        if parsed.failure is not None:
            return _result_failure(
                canonical,
                parsed.failure.kind,
                parsed.failure.message,
                container_sha256,
            )
        artifact = parsed.artifact
        if artifact is None:  # Defensive: LocalArtifactParseResult enforces this invariant.
            raise _ContainerFailure(
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "The selected base APK produced no parse result.",
            )
        return LocalArtifactParseResult(
            artifact=replace(
                artifact,
                artifact_format=artifact_format,
                artifact_sha256=container_sha256,
                file_name=canonical.name,
                canonical_path=canonical,
                file_size=initial_stat.st_size,
                modified_at=datetime.fromtimestamp(
                    initial_stat.st_mtime,
                    tz=UTC,
                ),
            )
        )
    except _ContainerFailure as exc:
        return _result_failure(canonical, exc.kind, exc.message, container_sha256)
    except OSError:
        return _result_failure(
            canonical,
            LocalArtifactFailureKind.IO_ERROR,
            "The package container could not be read from the filesystem.",
            container_sha256,
        )
    except (EOFError, NotImplementedError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return _result_failure(
            canonical,
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package container is not readable, supported ZIP data.",
            container_sha256,
        )


def _result_failure(
    path: Path,
    kind: LocalArtifactFailureKind,
    message: str,
    artifact_sha256: str | None = None,
) -> LocalArtifactParseResult:
    from playstore_app_audit.domain.local_artifacts import LocalArtifactParseFailure

    return LocalArtifactParseResult(
        failure=LocalArtifactParseFailure(path, kind, message, artifact_sha256)
    )


def _check_cancelled(cancel_event: threading.Event) -> None:
    if cancel_event.is_set():
        raise _ContainerFailure(
            LocalArtifactFailureKind.CANCELLED,
            "Package-container inspection was cancelled.",
        )


def _hash_stream(
    stream: IO[bytes],
    max_bytes: int,
    cancel_event: threading.Event,
) -> str:
    digest = hashlib.sha256()
    total = 0
    stream.seek(0)
    while block := stream.read(1024 * 1024):
        _check_cancelled(cancel_event)
        total += len(block)
        if total > max_bytes:
            raise _ContainerFailure(
                LocalArtifactFailureKind.FILE_TOO_LARGE,
                "The package container exceeds the configured file-size limit.",
            )
        digest.update(block)
    return digest.hexdigest()


def _preflight_zip(
    stream: IO[bytes],
    file_size: int,
    limits: ContainerInspectionLimits,
) -> None:
    tail_size = min(file_size, _EOCD.size + 0xFFFF)
    stream.seek(file_size - tail_size)
    tail = stream.read(tail_size)
    offset = tail.rfind(_EOCD_SIGNATURE)
    record: tuple[bytes, int, int, int, int, int, int, int] | None = None
    while offset >= 0:
        if len(tail) - offset >= _EOCD.size:
            candidate = _EOCD.unpack_from(tail, offset)
            if offset + _EOCD.size + candidate[-1] == len(tail):
                record = candidate
                break
        offset = tail.rfind(_EOCD_SIGNATURE, 0, offset)
    if record is None:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package container has no valid ZIP directory.",
        )
    _, disk, directory_disk, disk_entries, entries, directory_size, directory_offset, _ = record
    if disk != 0 or directory_disk != 0 or disk_entries != entries:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "Multi-disk package containers are not supported.",
        )
    if (
        entries == _ZIP64_SENTINEL_16
        or directory_size == _ZIP64_SENTINEL_32
        or directory_offset == _ZIP64_SENTINEL_32
    ):
        raise _ContainerFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "ZIP64 package containers are outside the supported resource limits.",
        )
    if entries > limits.max_entries or directory_size > limits.max_central_directory_bytes:
        raise _ContainerFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "The package-container directory exceeds the configured limits.",
        )
    eocd_offset = file_size - tail_size + offset
    if directory_offset + directory_size != eocd_offset:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package-container ZIP offsets are inconsistent.",
        )


def _safe_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not name or "\x00" in name or "\\" in name:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package container contains an unsafe archive path.",
        )
    posix = PurePosixPath(name)
    windows = PureWindowsPath(name)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or bool(_DRIVE_PREFIX.match(name))
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package container contains an unsafe archive path.",
        )
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The package container contains a symbolic-link entry.",
        )
    return posix.as_posix()


def _inspect_entries(
    archive: zipfile.ZipFile,
    limits: ContainerInspectionLimits,
) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > limits.max_entries:
        raise _ContainerFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "The package container contains too many entries.",
        )
    total = 0
    by_name: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        name = _safe_member_name(info)
        key = name.casefold()
        if key in by_name:
            raise _ContainerFailure(
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "The package container contains ambiguous duplicate paths.",
            )
        by_name[key] = info
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            raise _ContainerFailure(
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "Encrypted package-container entries are not supported.",
            )
        if info.file_size > limits.max_entry_uncompressed_bytes:
            raise _ContainerFailure(
                LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                "A package-container entry exceeds the configured size limit.",
            )
        total += info.file_size
        if total > limits.max_total_uncompressed_bytes:
            raise _ContainerFailure(
                LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                "The package container declares too much uncompressed data.",
            )
        if info.file_size and (
            info.compress_size <= 0
            or info.file_size / info.compress_size > limits.max_compression_ratio
        ):
            raise _ContainerFailure(
                LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                "A package-container entry has a suspicious compression ratio.",
            )
    return by_name


def _read_json_metadata(
    archive: zipfile.ZipFile,
    by_name: dict[str, zipfile.ZipInfo],
    names: tuple[str, ...],
    limits: ContainerInspectionLimits,
) -> dict[str, Any]:
    for name in names:
        info = by_name.get(name.casefold())
        if info is None or info.file_size > limits.max_metadata_bytes:
            continue
        try:
            with archive.open(info) as member:
                data = member.read(limits.max_metadata_bytes + 1)
            if len(data) > limits.max_metadata_bytes:
                continue
            value = json.loads(data.decode("utf-8"))
        except (OSError, UnicodeError, ValueError, zipfile.BadZipFile):
            continue
        if isinstance(value, dict):
            return value
    return {}


def _metadata_base_paths(metadata: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    for key in ("base_apk", "baseApk", "base"):
        value = metadata.get(key)
        if isinstance(value, str):
            candidates.append(value)
    splits = metadata.get("split_apks")
    if isinstance(splits, list):
        for item in splits:
            if not isinstance(item, dict):
                continue
            split_id = str(item.get("id") or item.get("type") or "").casefold()
            if split_id not in {"base", "master", "base-master"}:
                continue
            for key in ("file", "apk", "name", "path"):
                value = item.get(key)
                if isinstance(value, str):
                    candidates.append(value)
                    break
    package_name = metadata.get("package_name") or metadata.get("packageName")
    if isinstance(package_name, str) and package_name:
        candidates.append(f"{package_name}.apk")
    return candidates


def _select_unique(
    candidates: list[zipfile.ZipInfo],
) -> zipfile.ZipInfo | None:
    if len(candidates) > 1:
        raise _ContainerFailure(
            LocalArtifactFailureKind.AMBIGUOUS_BASE_APK,
            "The package container identifies more than one possible base APK.",
        )
    return candidates[0] if candidates else None


def _select_base_apk(
    archive: zipfile.ZipFile,
    by_name: dict[str, zipfile.ZipInfo],
    artifact_format: LocalArtifactFormat,
    limits: ContainerInspectionLimits,
) -> zipfile.ZipInfo:
    apk_infos = [
        info
        for info in by_name.values()
        if not info.is_dir() and PurePosixPath(info.filename).suffix.casefold() == ".apk"
    ]
    if not apk_infos:
        raise _ContainerFailure(
            LocalArtifactFailureKind.NO_BASE_APK,
            "The package container contains no APK entry.",
        )
    if len(apk_infos) == 1 and artifact_format is not LocalArtifactFormat.XAPK:
        return apk_infos[0]

    metadata_names = (
        ("manifest.json",)
        if artifact_format is LocalArtifactFormat.XAPK
        else ("info.json", "manifest.json")
    )
    metadata = _read_json_metadata(archive, by_name, metadata_names, limits)
    for raw_path in _metadata_base_paths(metadata):
        try:
            normalized = PurePosixPath(raw_path).as_posix().casefold()
        except (TypeError, ValueError):
            continue
        selected = by_name.get(normalized)
        if selected is not None and PurePosixPath(selected.filename).suffix.casefold() == ".apk":
            return selected

    preferred_names = (
        ("base-master.apk", "base.apk")
        if artifact_format is LocalArtifactFormat.APKS
        else ("base.apk", "base-master.apk")
    )
    for preferred in preferred_names:
        selected = _select_unique(
            [
                info
                for info in apk_infos
                if PurePosixPath(info.filename).name.casefold() == preferred
            ]
        )
        if selected is not None:
            return selected

    if artifact_format is LocalArtifactFormat.XAPK:
        package_named = [
            info
            for info in apk_infos
            if _is_package_named_base_candidate(PurePosixPath(info.filename).stem)
        ]
        selected = _select_unique(package_named)
        if selected is not None:
            return selected
        if not package_named:
            raise _ContainerFailure(
                LocalArtifactFailureKind.NO_BASE_APK,
                "No credible base APK could be identified in the package container.",
            )
    raise _ContainerFailure(
        LocalArtifactFailureKind.AMBIGUOUS_BASE_APK,
        "No single credible base APK could be identified in the package container.",
    )


def _is_package_named_base_candidate(stem: str) -> bool:
    normalized = stem.casefold()
    return not normalized.startswith(_SPLIT_NAME_PREFIXES) and bool(
        _PACKAGE_APK_STEM.fullmatch(stem)
    )


def _extract_member(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    destination: Path,
    limits: ContainerInspectionLimits,
    cancel_event: threading.Event,
) -> None:
    total = 0
    with archive.open(info) as source, destination.open("xb") as output:
        while block := source.read(1024 * 1024):
            _check_cancelled(cancel_event)
            total += len(block)
            if total > limits.max_entry_uncompressed_bytes or total > info.file_size:
                raise _ContainerFailure(
                    LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                    "The selected base APK expanded beyond its declared safe size.",
                )
            output.write(block)
    if total != info.file_size:
        raise _ContainerFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The selected base APK has an inconsistent uncompressed size.",
        )
