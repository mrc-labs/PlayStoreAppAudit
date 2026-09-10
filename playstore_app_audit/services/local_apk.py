from __future__ import annotations

import hashlib
import os
import re
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from pyaxmlparser.arscparser import ARSCParser as _ARSCParser
from pyaxmlparser.arscutil import ARSCResTableConfig as _ARSCResTableConfig
from pyaxmlparser.axmlprinter import AXMLPrinter as _AXMLPrinter

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseFailure,
    LocalArtifactParseResult,
    LocalArtifactWarning,
    ManifestScalar,
)

_APK_SUFFIX = ".apk"
_MANIFEST_NAME = "AndroidManifest.xml"
_RESOURCES_NAME = "resources.arsc"
_ANDROID_NAMESPACE = "{http://schemas.android.com/apk/res/android}"
_ZIP_EOCD_SIGNATURE = b"PK\x05\x06"
_ZIP_EOCD = struct.Struct("<4s4H2LH")
_ZIP64_SENTINEL_16 = 0xFFFF
_ZIP64_SENTINEL_32 = 0xFFFFFFFF
_PACKAGE_ID_RE = re.compile(
    r"^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+$"
)


@dataclass(frozen=True, slots=True)
class ApkParseLimits:
    max_apk_bytes: int = 2 * 1024**3
    max_in_memory_snapshot_bytes: int = 8 * 1024**2
    max_central_directory_bytes: int = 64 * 1024**2
    max_archive_entries: int = 50_000
    max_total_uncompressed_bytes: int = 8 * 1024**3
    max_manifest_bytes: int = 4 * 1024**2
    max_resources_bytes: int = 64 * 1024**2
    max_selected_member_compression_ratio: int = 1_000
    max_manifest_items: int = 4_096
    max_metadata_text_chars: int = 4_096


DEFAULT_APK_PARSE_LIMITS = ApkParseLimits()


class _ParseFailure(Exception):
    def __init__(self, kind: LocalArtifactFailureKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message


def parse_local_apk(
    path: str | Path,
    *,
    limits: ApkParseLimits = DEFAULT_APK_PARSE_LIMITS,
) -> LocalArtifactParseResult:
    """Parse one standalone APK through a bounded untrusted-input boundary."""

    supplied_path = Path(path)
    try:
        canonical_path = supplied_path.expanduser().resolve(strict=True)
    except FileNotFoundError:
        return _failure(
            supplied_path.absolute(),
            LocalArtifactFailureKind.NOT_FOUND,
            "The local artifact does not exist.",
        )
    except OSError:
        return _failure(
            supplied_path.absolute(),
            LocalArtifactFailureKind.IO_ERROR,
            "The local artifact path could not be resolved.",
        )

    if not canonical_path.is_file():
        return _failure(
            canonical_path,
            LocalArtifactFailureKind.NOT_A_FILE,
            "The local artifact path is not a regular file.",
        )
    if canonical_path.suffix.casefold() != _APK_SUFFIX:
        return _failure(
            canonical_path,
            LocalArtifactFailureKind.UNSUPPORTED_FORMAT,
            "Only standalone .apk files are supported; .apks and .aab are not supported.",
        )

    artifact_sha256: str | None = None
    try:
        with (
            canonical_path.open("rb") as source,
            tempfile.SpooledTemporaryFile(
                max_size=max(1, limits.max_in_memory_snapshot_bytes),
                mode="w+b",
            ) as snapshot,
        ):
            initial_stat = os.fstat(source.fileno())
            if initial_stat.st_size > limits.max_apk_bytes:
                raise _ParseFailure(
                    LocalArtifactFailureKind.FILE_TOO_LARGE,
                    "The APK exceeds the configured file-size limit.",
                )
            if initial_stat.st_size <= 0:
                raise _ParseFailure(
                    LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                    "The APK is empty or is not a valid ZIP archive.",
                )

            artifact_sha256, snapshot_size = _capture_snapshot(
                source,
                snapshot,
                max_bytes=limits.max_apk_bytes,
            )
            if snapshot_size != initial_stat.st_size:
                raise _ParseFailure(
                    LocalArtifactFailureKind.IO_ERROR,
                    "The APK changed while its parsing snapshot was captured.",
                )
            _preflight_zip_structure(snapshot, snapshot_size, limits)
            artifact = _parse_open_apk(
                snapshot,
                canonical_path=canonical_path,
                initial_stat=initial_stat,
                artifact_sha256=artifact_sha256,
                limits=limits,
            )
            final_sha256, final_size = _sha256_stream(
                source,
                max_bytes=limits.max_apk_bytes,
            )
            final_stat = os.fstat(source.fileno())
            if (
                final_sha256 != artifact_sha256
                or final_size != snapshot_size
                or final_stat.st_size != initial_stat.st_size
                or final_stat.st_mtime_ns != initial_stat.st_mtime_ns
            ):
                raise _ParseFailure(
                    LocalArtifactFailureKind.IO_ERROR,
                    "The APK changed while it was being parsed.",
                )
            return LocalArtifactParseResult(artifact=artifact)
    except _ParseFailure as exc:
        return _failure(canonical_path, exc.kind, exc.message, artifact_sha256)
    except OSError:
        return _failure(
            canonical_path,
            LocalArtifactFailureKind.IO_ERROR,
            "The APK could not be read from the filesystem.",
            artifact_sha256,
        )
    except (
        EOFError,
        NotImplementedError,
        RuntimeError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
    ):
        return _failure(
            canonical_path,
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The APK is not a readable, supported ZIP archive.",
            artifact_sha256,
        )


def _failure(
    path: Path,
    kind: LocalArtifactFailureKind,
    message: str,
    artifact_sha256: str | None = None,
) -> LocalArtifactParseResult:
    return LocalArtifactParseResult(
        failure=LocalArtifactParseFailure(
            path=path,
            kind=kind,
            message=message,
            artifact_sha256=artifact_sha256,
        )
    )


def _capture_snapshot(
    source: IO[bytes],
    snapshot: IO[bytes],
    *,
    max_bytes: int,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    source.seek(0)
    snapshot.seek(0)
    while True:
        block = source.read(max(1, min(1024 * 1024, max_bytes - total + 1)))
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise _ParseFailure(
                LocalArtifactFailureKind.FILE_TOO_LARGE,
                "The APK exceeds the configured file-size limit.",
            )
        digest.update(block)
        snapshot.write(block)
    snapshot.flush()
    snapshot.seek(0)
    return digest.hexdigest(), total


def _sha256_stream(
    stream: IO[bytes],
    *,
    max_bytes: int,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    stream.seek(0)
    while True:
        block = stream.read(max(1, min(1024 * 1024, max_bytes - total + 1)))
        if not block:
            break
        total += len(block)
        if total > max_bytes:
            raise _ParseFailure(
                LocalArtifactFailureKind.IO_ERROR,
                "The APK changed while it was being parsed.",
            )
        digest.update(block)
    return digest.hexdigest(), total


def _preflight_zip_structure(
    stream: IO[bytes],
    file_size: int,
    limits: ApkParseLimits,
) -> None:
    """Bound central-directory allocation before ``zipfile`` reads it."""

    tail_size = min(file_size, _ZIP_EOCD.size + 0xFFFF)
    stream.seek(file_size - tail_size)
    tail = stream.read(tail_size)
    offset = tail.rfind(_ZIP_EOCD_SIGNATURE)
    record: tuple[bytes, int, int, int, int, int, int, int] | None = None
    while offset >= 0:
        if len(tail) - offset >= _ZIP_EOCD.size:
            candidate = _ZIP_EOCD.unpack_from(tail, offset)
            if offset + _ZIP_EOCD.size + candidate[-1] == len(tail):
                record = candidate
                break
        offset = tail.rfind(_ZIP_EOCD_SIGNATURE, 0, offset)
    if record is None:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The APK has no valid ZIP end-of-central-directory record.",
        )

    (
        _signature,
        disk_number,
        central_directory_disk,
        entries_on_disk,
        total_entries,
        central_directory_size,
        central_directory_offset,
        _comment_length,
    ) = record
    if disk_number != 0 or central_directory_disk != 0 or entries_on_disk != total_entries:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "Multi-disk ZIP archives are not valid standalone APK inputs.",
        )
    if (
        total_entries == _ZIP64_SENTINEL_16
        or central_directory_size == _ZIP64_SENTINEL_32
        or central_directory_offset == _ZIP64_SENTINEL_32
    ):
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "ZIP64 APK archives are outside the supported resource limits.",
        )
    if total_entries > limits.max_archive_entries:
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "The APK contains too many archive entries.",
        )
    if central_directory_size > limits.max_central_directory_bytes:
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "The APK central directory exceeds the configured limit.",
        )

    eocd_offset = file_size - tail_size + offset
    if central_directory_offset + central_directory_size != eocd_offset:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "The APK ZIP central-directory offsets are inconsistent.",
        )


def _parse_open_apk(
    stream: IO[bytes],
    *,
    canonical_path: Path,
    initial_stat: os.stat_result,
    artifact_sha256: str,
    limits: ApkParseLimits,
) -> LocalArtifact:
    stream.seek(0)
    with zipfile.ZipFile(stream, mode="r", allowZip64=False) as archive:
        infos = archive.infolist()
        if len(infos) > limits.max_archive_entries:
            raise _ParseFailure(
                LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                "The APK contains too many archive entries.",
            )
        total_uncompressed = sum(info.file_size for info in infos)
        if total_uncompressed > limits.max_total_uncompressed_bytes:
            raise _ParseFailure(
                LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                "The APK declares too much uncompressed archive data.",
            )

        manifests = [info for info in infos if info.filename == _MANIFEST_NAME]
        if not manifests:
            raise _ParseFailure(
                LocalArtifactFailureKind.MISSING_MANIFEST,
                "The APK does not contain AndroidManifest.xml.",
            )
        if len(manifests) != 1:
            raise _ParseFailure(
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "The APK contains ambiguous duplicate manifest entries.",
            )
        resources = [info for info in infos if info.filename == _RESOURCES_NAME]
        if len(resources) > 1:
            raise _ParseFailure(
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "The APK contains ambiguous duplicate resource-table entries.",
            )

        manifest_bytes = _read_member_limited(
            archive,
            manifests[0],
            max_bytes=limits.max_manifest_bytes,
            limits=limits,
        )
        parsed = _parse_manifest(manifest_bytes, limits)

        if parsed.requires_split_handling:
            raise _ParseFailure(
                LocalArtifactFailureKind.UNSUPPORTED_SPLIT,
                "Split or split-dependent APK files are not supported as standalone artifacts.",
            )

        warnings: set[LocalArtifactWarning] = set()
        application_label = _literal_resource_value(parsed.application_label_raw)
        version_name = _literal_resource_value(parsed.version_name_raw)
        needs_resources = (
            application_label is None and parsed.application_label_raw is not None
        ) or (version_name is None and parsed.version_name_raw is not None)
        resource_parser: _ARSCParser | None = None
        if needs_resources and resources:
            try:
                resource_bytes = _read_member_limited(
                    archive,
                    resources[0],
                    max_bytes=limits.max_resources_bytes,
                    limits=limits,
                )
                resource_parser = _ARSCParser(resource_bytes)
            except _ParseFailure:
                raise
            except Exception:
                resource_parser = None

        if application_label is None and parsed.application_label_raw is not None:
            application_label = _resolve_resource_value(
                parsed.application_label_raw,
                resource_parser,
                parsed.package_id,
                limits,
            )
            if application_label is None:
                warnings.add(LocalArtifactWarning.APPLICATION_LABEL_UNRESOLVED)
        if version_name is None and parsed.version_name_raw is not None:
            version_name = _resolve_resource_value(
                parsed.version_name_raw,
                resource_parser,
                parsed.package_id,
                limits,
            )
            if version_name is None:
                warnings.add(LocalArtifactWarning.VERSION_NAME_UNRESOLVED)

    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256=artifact_sha256,
        package_id=parsed.package_id,
        application_label=application_label,
        application_label_reference=_resource_reference(parsed.application_label_raw),
        version_name=version_name,
        version_name_reference=_resource_reference(parsed.version_name_raw),
        version_code=_manifest_scalar(parsed.version_code_raw, limits),
        version_code_major=_manifest_scalar(parsed.version_code_major_raw, limits),
        min_sdk=_manifest_scalar(parsed.min_sdk_raw, limits),
        target_sdk=_manifest_scalar(parsed.target_sdk_raw, limits),
        compile_sdk=_manifest_scalar(parsed.compile_sdk_raw, limits),
        application_debuggable=_manifest_bool(parsed.debuggable_raw),
        permissions=parsed.permissions,
        features=parsed.features,
        icon_reference=parsed.icon_reference,
        file_name=canonical_path.name,
        canonical_path=canonical_path,
        file_size=initial_stat.st_size,
        modified_at=datetime.fromtimestamp(initial_stat.st_mtime, tz=UTC),
        warnings=tuple(sorted(warnings, key=str)),
    )


def _read_member_limited(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    *,
    max_bytes: int,
    limits: ApkParseLimits,
) -> bytes:
    if info.flag_bits & 0x1:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "Encrypted APK metadata entries are not supported.",
        )
    if info.file_size > max_bytes:
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "An APK metadata entry exceeds the configured limit.",
        )
    if info.file_size and (
        info.compress_size <= 0
        or info.file_size
        > info.compress_size * limits.max_selected_member_compression_ratio
    ):
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "An APK metadata entry has a pathological compression ratio.",
        )

    chunks: list[bytes] = []
    total = 0
    with archive.open(info, mode="r") as member:
        while True:
            block = member.read(min(1024 * 1024, max_bytes - total + 1))
            if not block:
                break
            chunks.append(block)
            total += len(block)
            if total > max_bytes:
                raise _ParseFailure(
                    LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                    "An APK metadata entry expands beyond the configured limit.",
                )
    if total != info.file_size:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_ARCHIVE,
            "An APK metadata entry has an inconsistent uncompressed size.",
        )
    return b"".join(chunks)


@dataclass(frozen=True, slots=True)
class _ParsedManifest:
    package_id: str
    application_label_raw: str | None
    version_name_raw: str | None
    version_code_raw: str | None
    version_code_major_raw: str | None
    min_sdk_raw: str | None
    target_sdk_raw: str | None
    compile_sdk_raw: str | None
    debuggable_raw: str | None
    icon_reference: str | None
    permissions: tuple[str, ...]
    features: tuple[str, ...]
    requires_split_handling: bool


def _parse_manifest(data: bytes, limits: ApkParseLimits) -> _ParsedManifest:
    try:
        manifest = _AXMLPrinter(data)
        root = manifest.get_xml_obj()
    except Exception as exc:
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_MANIFEST,
            "AndroidManifest.xml could not be decoded safely.",
        ) from exc
    if not manifest.is_valid() or root is None or root.tag != "manifest":
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_MANIFEST,
            "AndroidManifest.xml is missing a valid manifest root.",
        )

    package_id = root.get("package")
    if (
        not isinstance(package_id, str)
        or len(package_id) > 255
        or _PACKAGE_ID_RE.fullmatch(package_id) is None
    ):
        raise _ParseFailure(
            LocalArtifactFailureKind.MALFORMED_MANIFEST,
            "AndroidManifest.xml has no valid Android package identifier.",
        )

    permissions = _manifest_names(
        root,
        ("uses-permission", "uses-permission-sdk-23"),
        limits,
    )
    features = _manifest_names(root, ("uses-feature",), limits)
    application = root.find("application")
    uses_sdk = root.find("uses-sdk")
    split_markers = (
        _metadata_text(root.get("split"), limits),
        _metadata_text(root.get("configForSplit"), limits),
        _metadata_text(root.get(_android_attribute("configForSplit")), limits),
        _metadata_text(root.get("requiredSplitTypes"), limits),
        _metadata_text(root.get(_android_attribute("requiredSplitTypes")), limits),
        _metadata_text(root.get("splitTypes"), limits),
        _metadata_text(root.get(_android_attribute("splitTypes")), limits),
    )
    split_flags = (
        _manifest_bool(
            _metadata_text(root.get(_android_attribute("isFeatureSplit")), limits)
        ),
        _manifest_bool(
            _metadata_text(root.get(_android_attribute("isSplitRequired")), limits)
        ),
        _required_split_metadata(application, limits),
    )
    return _ParsedManifest(
        package_id=package_id,
        application_label_raw=_element_android_value(application, "label", limits),
        version_name_raw=_element_android_value(root, "versionName", limits),
        version_code_raw=_element_android_value(root, "versionCode", limits),
        version_code_major_raw=_element_android_value(
            root, "versionCodeMajor", limits
        ),
        min_sdk_raw=_element_android_value(uses_sdk, "minSdkVersion", limits),
        target_sdk_raw=_element_android_value(uses_sdk, "targetSdkVersion", limits),
        compile_sdk_raw=_element_android_value(root, "compileSdkVersion", limits),
        debuggable_raw=_element_android_value(application, "debuggable", limits),
        icon_reference=_element_android_value(application, "icon", limits),
        permissions=permissions,
        features=features,
        requires_split_handling=(
            any(split_markers)
            or any(flag is True for flag in split_flags)
            or root.find("uses-split") is not None
        ),
    )


def _manifest_names(
    root: Any,
    tags: tuple[str, ...],
    limits: ApkParseLimits,
) -> tuple[str, ...]:
    values: set[str] = set()
    for tag in tags:
        for element in root.findall(tag):
            value = _element_android_value(element, "name", limits)
            if value is not None:
                values.add(value)
            if len(values) > limits.max_manifest_items:
                raise _ParseFailure(
                    LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
                    "AndroidManifest.xml contains too many metadata items.",
                )
    return tuple(sorted(values))


def _android_attribute(name: str) -> str:
    return f"{_ANDROID_NAMESPACE}{name}"


def _element_android_value(
    element: Any | None,
    name: str,
    limits: ApkParseLimits,
) -> str | None:
    if element is None:
        return None
    canonical = element.get(_android_attribute(name))
    if canonical is not None:
        return _metadata_text(canonical, limits)
    # pyaxmlparser normalises malformed ``android:name`` attributes by removing
    # the prefix when the namespace URI is absent. Limit recovery to the exact
    # Android attribute requested; never search arbitrary attributes.
    for fallback_name in (name, f"android:{name}"):
        fallback = element.get(fallback_name)
        if fallback is not None:
            return _metadata_text(fallback, limits)
    return None


def _required_split_metadata(
    application: Any | None,
    limits: ApkParseLimits,
) -> bool | None:
    if application is None:
        return None
    for element in application.findall("meta-data"):
        name = _element_android_value(element, "name", limits)
        if name == "com.android.vending.splits.required":
            return _manifest_bool(_element_android_value(element, "value", limits))
    return None


def _metadata_text(value: object, limits: ApkParseLimits) -> str | None:
    if value is None:
        return None
    text = str(value).replace("\x00", "").strip()
    if not text:
        return None
    if len(text) > limits.max_metadata_text_chars:
        raise _ParseFailure(
            LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED,
            "AndroidManifest.xml contains an oversized metadata value.",
        )
    return text


def _manifest_scalar(
    value: str | None,
    limits: ApkParseLimits,
) -> ManifestScalar | None:
    text = _metadata_text(value, limits)
    if text is None:
        return None
    try:
        return int(text, 10)
    except ValueError:
        try:
            return int(text, 16) if text.casefold().startswith("0x") else text
        except ValueError:
            return text


def _manifest_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.casefold()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    return None


def _resource_reference(value: str | None) -> str | None:
    return value if value is not None and value.startswith("@") else None


def _literal_resource_value(value: str | None) -> str | None:
    if value is None or value.startswith("@"):
        return None
    return value


def _resolve_resource_value(
    reference: str,
    resources: _ARSCParser | None,
    package_id: str,
    limits: ApkParseLimits,
) -> str | None:
    if resources is None or not reference.startswith("@"):
        return None
    try:
        if package_id not in resources.get_packages_names():
            return None
        resource_id, resource_package = resources.parse_id(reference)
        if resource_package not in {None, "", package_id}:
            return None
        candidates = resources.get_resolved_res_configs(
            resource_id,
            _ARSCResTableConfig.default_config(),
        )
        if not candidates:
            return None
        value = _metadata_text(candidates[0][1], limits)
    except _ParseFailure:
        raise
    except Exception:
        return None
    if value is None or value.startswith("@") or value.startswith("res/"):
        return None
    return value
