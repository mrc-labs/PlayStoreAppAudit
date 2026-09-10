from __future__ import annotations

import json
import os
import re
import stat
import tempfile
import threading
from collections.abc import Callable, Iterable, Mapping
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playstore_app_audit.domain.local_apk_library import (
    LOCAL_APK_LIBRARY_SCHEMA_VERSION,
    LibraryLoadFailureKind,
    LibraryRootScanStatus,
    LibrarySaveFailureKind,
    LibraryScanIssueKind,
    LocalApkLibrary,
    LocalApkLibraryArtifact,
    LocalApkLibraryLoadFailure,
    LocalApkLibraryLoadResult,
    LocalApkLibraryLocation,
    LocalApkLibraryRoot,
    LocalApkLibraryRootScanResult,
    LocalApkLibrarySaveFailure,
    LocalApkLibrarySaveResult,
    LocalApkLibraryScanIssue,
    LocalApkLibraryScanProgress,
    LocalApkLibraryScanResult,
)
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFormat,
    LocalArtifactParseResult,
    LocalArtifactWarning,
    ManifestScalar,
)
from playstore_app_audit.platform.runtime import app_data_dir
from playstore_app_audit.services.local_apk import parse_local_apk

LIBRARY_FILENAME = "local_apk_library.json"
DEFAULT_MAX_SCAN_ISSUES = 1_000
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_REPARSE_POINT_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)

ArtifactParser = Callable[[Path], LocalArtifactParseResult]
ScanProgressCallback = Callable[[LocalApkLibraryScanProgress], None]
Clock = Callable[[], datetime]


class _InvalidDocument(ValueError):
    pass


def local_apk_library_path() -> Path:
    return app_data_dir() / LIBRARY_FILENAME


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _normalise_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("Library timestamps must include a timezone")
    return value.astimezone(UTC)


def _normalise_path(path: str | Path) -> Path:
    return Path(os.path.abspath(os.path.normpath(os.path.expanduser(str(path)))))


def _path_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _location_key(artifact_sha256: str, path: Path) -> tuple[str, str]:
    return artifact_sha256, _path_key(path)


def _is_reparse_point(file_stat: os.stat_result) -> bool:
    return bool(_REPARSE_POINT_FLAG and file_stat.st_file_attributes & _REPARSE_POINT_FLAG)


class LocalApkLibraryService:
    """Persist and explicitly rescan the local-only APK Library.

    Scanning invokes only the project-owned APK parser. Store/provider lookup is
    intentionally a separate later operation through ``LocalArtifactStoreService``.
    """

    def __init__(
        self,
        path: Path | None = None,
        *,
        parser: ArtifactParser = parse_local_apk,
        clock: Clock = _utc_now,
        max_scan_issues: int = DEFAULT_MAX_SCAN_ISSUES,
    ) -> None:
        self.path = path or local_apk_library_path()
        self._parser = parser
        self._clock = clock
        self._max_scan_issues = max(1, max_scan_issues)

    def empty_library(self) -> LocalApkLibrary:
        return LocalApkLibrary()

    def load(self) -> LocalApkLibraryLoadResult:
        if not self.path.exists():
            return LocalApkLibraryLoadResult(library=self.empty_library())
        try:
            raw = self.path.read_text(encoding="utf-8")
        except UnicodeError:
            return LocalApkLibraryLoadResult(
                failure=LocalApkLibraryLoadFailure(
                    LibraryLoadFailureKind.MALFORMED_JSON,
                    "The Local APK Library is not valid UTF-8 JSON and was left unchanged.",
                )
            )
        except OSError:
            return LocalApkLibraryLoadResult(
                failure=LocalApkLibraryLoadFailure(
                    LibraryLoadFailureKind.IO_ERROR,
                    "The Local APK Library could not be read.",
                )
            )
        try:
            document = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError):
            return LocalApkLibraryLoadResult(
                failure=LocalApkLibraryLoadFailure(
                    LibraryLoadFailureKind.MALFORMED_JSON,
                    "The Local APK Library is not valid JSON and was left unchanged.",
                )
            )
        if isinstance(document, Mapping):
            schema_version = document.get("schema_version")
            if type(schema_version) is int and schema_version != LOCAL_APK_LIBRARY_SCHEMA_VERSION:
                return LocalApkLibraryLoadResult(
                    failure=LocalApkLibraryLoadFailure(
                        LibraryLoadFailureKind.UNSUPPORTED_SCHEMA,
                        f"Unsupported Local APK Library schema version: {schema_version}.",
                    )
                )
        try:
            library = _library_from_document(document)
        except _InvalidDocument as exc:
            return LocalApkLibraryLoadResult(
                failure=LocalApkLibraryLoadFailure(
                    LibraryLoadFailureKind.INVALID_DOCUMENT,
                    f"Invalid Local APK Library document: {exc}",
                )
            )
        return LocalApkLibraryLoadResult(library=library)

    def save(self, library: LocalApkLibrary) -> LocalApkLibrarySaveResult:
        try:
            document = _library_to_document(library)
            _library_from_document(document)
        except (TypeError, ValueError, _InvalidDocument) as exc:
            return LocalApkLibrarySaveResult(
                path=self.path,
                failure=LocalApkLibrarySaveFailure(
                    LibrarySaveFailureKind.INVALID_DOCUMENT,
                    f"The Local APK Library is invalid: {exc}",
                ),
            )

        temporary_path: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temporary_path = Path(temporary_name)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(document, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.path)
        except OSError:
            if temporary_path is not None:
                with suppress(OSError):
                    temporary_path.unlink(missing_ok=True)
            return LocalApkLibrarySaveResult(
                path=self.path,
                failure=LocalApkLibrarySaveFailure(
                    LibrarySaveFailureKind.IO_ERROR,
                    "The Local APK Library could not be written atomically.",
                ),
            )
        return LocalApkLibrarySaveResult(path=self.path)

    def register_roots(
        self,
        library: LocalApkLibrary,
        roots: Iterable[str | Path],
    ) -> LocalApkLibrary:
        now = _normalise_datetime(self._clock())
        roots_by_key = {_path_key(root.path): root for root in library.roots}
        for supplied_root in roots:
            root_path = _normalise_path(supplied_root)
            roots_by_key.setdefault(
                _path_key(root_path),
                LocalApkLibraryRoot(path=root_path, registered_at=now),
            )
        return replace(
            library,
            roots=tuple(sorted(roots_by_key.values(), key=lambda item: _path_key(item.path))),
        )

    def rescan(
        self,
        library: LocalApkLibrary,
        *,
        roots: Iterable[str | Path] | None = None,
        cancel_event: threading.Event | None = None,
        progress_callback: ScanProgressCallback | None = None,
    ) -> LocalApkLibraryScanResult:
        cancelled = cancel_event or threading.Event()
        now = _normalise_datetime(self._clock())
        registered_by_key = {_path_key(root.path): root for root in library.roots}
        if roots is None:
            selected_roots = tuple(sorted(registered_by_key.values(), key=lambda item: _path_key(item.path)))
        else:
            selected_keys = {_path_key(_normalise_path(root)) for root in roots}
            unknown = selected_keys.difference(registered_by_key)
            if unknown:
                raise ValueError("Every scanned root must first be registered")
            selected_roots = tuple(registered_by_key[key] for key in sorted(selected_keys))

        artifacts_by_sha = {artifact.artifact_sha256: artifact for artifact in library.artifacts}
        locations_by_key = {
            _location_key(location.artifact_sha256, location.path): location for location in library.locations
        }
        issues: list[LocalApkLibraryScanIssue] = []
        omitted_issue_count = 0
        root_results: list[LocalApkLibraryRootScanResult] = []

        def add_issue(issue: LocalApkLibraryScanIssue) -> None:
            nonlocal omitted_issue_count
            if len(issues) < self._max_scan_issues:
                issues.append(issue)
            else:
                omitted_issue_count += 1

        for root in selected_roots:
            root_result = self._scan_root(
                root.path,
                now,
                artifacts_by_sha,
                locations_by_key,
                cancelled,
                progress_callback,
                add_issue,
            )
            root_results.append(root_result)
            registered_by_key[_path_key(root.path)] = replace(
                root,
                last_scan_at=now,
                last_scan_status=root_result.status,
            )
            if root_result.status is LibraryRootScanStatus.CANCELLED:
                break

        updated = LocalApkLibrary(
            schema_version=library.schema_version,
            roots=tuple(sorted(registered_by_key.values(), key=lambda item: _path_key(item.path))),
            artifacts=tuple(sorted(artifacts_by_sha.values(), key=lambda item: item.artifact_sha256)),
            locations=tuple(
                sorted(
                    locations_by_key.values(),
                    key=lambda item: (item.artifact_sha256, _path_key(item.path)),
                )
            ),
        )
        return LocalApkLibraryScanResult(
            library=updated,
            roots=tuple(root_results),
            issues=tuple(issues),
            cancelled=cancelled.is_set(),
            omitted_issue_count=omitted_issue_count,
        )

    def _scan_root(
        self,
        root_path: Path,
        now: datetime,
        artifacts_by_sha: dict[str, LocalApkLibraryArtifact],
        locations_by_key: dict[tuple[str, str], LocalApkLibraryLocation],
        cancel_event: threading.Event,
        progress_callback: ScanProgressCallback | None,
        add_issue: Callable[[LocalApkLibraryScanIssue], None],
    ) -> LocalApkLibraryRootScanResult:
        discovered_apks = 0
        parsed_artifacts = 0
        issue_count = 0
        traversal_issue = False
        seen_candidate_paths: set[str] = set()

        def issue(value: LocalApkLibraryScanIssue) -> None:
            nonlocal issue_count
            issue_count += 1
            add_issue(value)

        if cancel_event.is_set():
            return LocalApkLibraryRootScanResult(root_path, LibraryRootScanStatus.CANCELLED, 0, 0, 0)

        try:
            root_stat = root_path.lstat()
            root_is_usable = stat.S_ISDIR(root_stat.st_mode) and not _is_reparse_point(root_stat)
        except OSError:
            root_is_usable = False
        if not root_is_usable:
            issue(
                LocalApkLibraryScanIssue(
                    root_path,
                    root_path,
                    LibraryScanIssueKind.ROOT_UNAVAILABLE,
                    "The registered Library root is unavailable or is a directory link.",
                )
            )
            return LocalApkLibraryRootScanResult(root_path, LibraryRootScanStatus.FAILED, 0, 0, issue_count)

        directories = [root_path]
        while directories and not cancel_event.is_set():
            current_directory = directories.pop()
            if progress_callback is not None:
                progress_callback(
                    LocalApkLibraryScanProgress(
                        root_path,
                        current_directory,
                        discovered_apks,
                        parsed_artifacts,
                    )
                )
            if cancel_event.is_set():
                break
            try:
                with os.scandir(current_directory) as iterator:
                    entries = sorted(iterator, key=lambda entry: (entry.name.casefold(), entry.name))
            except OSError:
                traversal_issue = True
                issue(
                    LocalApkLibraryScanIssue(
                        root_path,
                        current_directory,
                        LibraryScanIssueKind.DIRECTORY_INACCESSIBLE,
                        "A Library directory could not be read.",
                    )
                )
                continue

            child_directories: list[Path] = []
            for entry in entries:
                if cancel_event.is_set():
                    break
                entry_path = _normalise_path(entry.path)
                try:
                    entry_stat = entry.stat(follow_symlinks=False)
                except OSError:
                    traversal_issue = True
                    if entry_path.suffix.casefold() == ".apk":
                        seen_candidate_paths.add(_path_key(entry_path))
                    issue(
                        LocalApkLibraryScanIssue(
                            root_path,
                            entry_path,
                            LibraryScanIssueKind.FILE_INACCESSIBLE,
                            "A Library entry could not be inspected.",
                        )
                    )
                    continue
                if stat.S_ISLNK(entry_stat.st_mode) or _is_reparse_point(entry_stat):
                    continue
                if stat.S_ISDIR(entry_stat.st_mode):
                    child_directories.append(entry_path)
                    continue
                if not stat.S_ISREG(entry_stat.st_mode) or entry_path.suffix.casefold() != ".apk":
                    continue

                discovered_apks += 1
                seen_candidate_paths.add(_path_key(entry_path))
                if progress_callback is not None:
                    progress_callback(
                        LocalApkLibraryScanProgress(
                            root_path,
                            entry_path,
                            discovered_apks,
                            parsed_artifacts,
                        )
                    )
                if cancel_event.is_set():
                    break
                try:
                    parse_result = self._parser(entry_path)
                except Exception as exc:
                    self._invalidate_present_location(entry_path, locations_by_key)
                    issue(
                        LocalApkLibraryScanIssue(
                            root_path,
                            entry_path,
                            LibraryScanIssueKind.PARSER_FAILURE,
                            f"The APK parser failed unexpectedly: {exc}",
                        )
                    )
                    continue
                if parse_result.failure is not None:
                    self._invalidate_present_location(entry_path, locations_by_key)
                    issue(
                        LocalApkLibraryScanIssue(
                            root_path,
                            entry_path,
                            LibraryScanIssueKind.PARSER_FAILURE,
                            parse_result.failure.message,
                            parse_result.failure.kind.value,
                        )
                    )
                    continue
                artifact = parse_result.artifact
                if artifact is None:
                    continue
                parsed_artifacts += 1
                self._merge_artifact(
                    artifact,
                    entry_path,
                    root_path,
                    now,
                    artifacts_by_sha,
                    locations_by_key,
                )
            directories.extend(reversed(child_directories))

        if cancel_event.is_set():
            status = LibraryRootScanStatus.CANCELLED
        elif traversal_issue:
            status = LibraryRootScanStatus.PARTIAL
        else:
            status = LibraryRootScanStatus.COMPLETED
            root_key = _path_key(root_path)
            for key, location in tuple(locations_by_key.items()):
                if (
                    location.present
                    and _path_key(location.root_path) == root_key
                    and _path_key(location.path) not in seen_candidate_paths
                ):
                    locations_by_key[key] = replace(location, present=False)

        return LocalApkLibraryRootScanResult(
            root_path,
            status,
            discovered_apks,
            parsed_artifacts,
            issue_count,
        )

    @staticmethod
    def _merge_artifact(
        artifact: LocalArtifact,
        location_path: Path,
        root_path: Path,
        now: datetime,
        artifacts_by_sha: dict[str, LocalApkLibraryArtifact],
        locations_by_key: dict[tuple[str, str], LocalApkLibraryLocation],
    ) -> None:
        sha256 = artifact.artifact_sha256
        artifacts_by_sha[sha256] = _artifact_record(artifact)
        LocalApkLibraryService._invalidate_present_location(location_path, locations_by_key)

        key = _location_key(sha256, location_path)
        existing = locations_by_key.get(key)
        first_seen_at = existing.first_seen_at if existing is not None else now
        locations_by_key[key] = LocalApkLibraryLocation(
            artifact_sha256=sha256,
            path=location_path,
            root_path=root_path,
            file_name=location_path.name,
            modified_at=_normalise_datetime(artifact.modified_at),
            present=True,
            first_seen_at=first_seen_at,
            last_seen_at=now,
        )

    @staticmethod
    def _invalidate_present_location(
        location_path: Path,
        locations_by_key: dict[tuple[str, str], LocalApkLibraryLocation],
    ) -> None:
        path_key = _path_key(location_path)
        for key, location in tuple(locations_by_key.items()):
            if location.present and _path_key(location.path) == path_key:
                locations_by_key[key] = replace(location, present=False)

    def auditable_artifacts(self, library: LocalApkLibrary) -> tuple[LocalArtifact, ...]:
        """Return one deterministic present representative per exact SHA-256.

        Duplicate physical copies remain in ``library.locations``; Store-facing
        work receives one reconstructed artifact per byte identity. Distinct SHA
        values remain distinct even when their package lookup keys are equal.
        """

        locations_by_sha: dict[str, list[LocalApkLibraryLocation]] = {}
        for location in library.locations:
            if location.present:
                locations_by_sha.setdefault(location.artifact_sha256, []).append(location)
        artifacts: list[LocalArtifact] = []
        for record in sorted(library.artifacts, key=lambda item: item.artifact_sha256):
            locations = locations_by_sha.get(record.artifact_sha256)
            if not locations:
                continue
            representative = min(locations, key=lambda item: _path_key(item.path))
            artifacts.append(_reconstruct_artifact(record, representative))
        return tuple(artifacts)


def _artifact_record(artifact: LocalArtifact) -> LocalApkLibraryArtifact:
    return LocalApkLibraryArtifact(
        artifact_format=artifact.artifact_format,
        artifact_sha256=artifact.artifact_sha256,
        package_id=artifact.package_id,
        application_label=artifact.application_label,
        application_label_reference=artifact.application_label_reference,
        version_name=artifact.version_name,
        version_name_reference=artifact.version_name_reference,
        version_code=artifact.version_code,
        version_code_major=artifact.version_code_major,
        min_sdk=artifact.min_sdk,
        target_sdk=artifact.target_sdk,
        compile_sdk=artifact.compile_sdk,
        application_debuggable=artifact.application_debuggable,
        permissions=artifact.permissions,
        features=artifact.features,
        icon_reference=artifact.icon_reference,
        file_size=artifact.file_size,
        warnings=artifact.warnings,
    )


def _reconstruct_artifact(
    artifact: LocalApkLibraryArtifact,
    location: LocalApkLibraryLocation,
) -> LocalArtifact:
    return LocalArtifact(
        artifact_format=artifact.artifact_format,
        artifact_sha256=artifact.artifact_sha256,
        package_id=artifact.package_id,
        application_label=artifact.application_label,
        application_label_reference=artifact.application_label_reference,
        version_name=artifact.version_name,
        version_name_reference=artifact.version_name_reference,
        version_code=artifact.version_code,
        version_code_major=artifact.version_code_major,
        min_sdk=artifact.min_sdk,
        target_sdk=artifact.target_sdk,
        compile_sdk=artifact.compile_sdk,
        application_debuggable=artifact.application_debuggable,
        permissions=artifact.permissions,
        features=artifact.features,
        icon_reference=artifact.icon_reference,
        file_name=location.file_name,
        canonical_path=location.path,
        file_size=artifact.file_size,
        modified_at=location.modified_at,
        warnings=artifact.warnings,
    )


def _library_to_document(library: LocalApkLibrary) -> dict[str, Any]:
    return {
        "schema_version": library.schema_version,
        "roots": [
            {
                "path": str(root.path),
                "registered_at": root.registered_at.isoformat(),
                "last_scan_at": root.last_scan_at.isoformat() if root.last_scan_at else None,
                "last_scan_status": root.last_scan_status.value,
            }
            for root in sorted(library.roots, key=lambda item: _path_key(item.path))
        ],
        "artifacts": [
            {
                "artifact_format": artifact.artifact_format.value,
                "artifact_sha256": artifact.artifact_sha256,
                "package_id": artifact.package_id,
                "application_label": artifact.application_label,
                "application_label_reference": artifact.application_label_reference,
                "version_name": artifact.version_name,
                "version_name_reference": artifact.version_name_reference,
                "version_code": artifact.version_code,
                "version_code_major": artifact.version_code_major,
                "min_sdk": artifact.min_sdk,
                "target_sdk": artifact.target_sdk,
                "compile_sdk": artifact.compile_sdk,
                "application_debuggable": artifact.application_debuggable,
                "permissions": list(artifact.permissions),
                "features": list(artifact.features),
                "icon_reference": artifact.icon_reference,
                "file_size": artifact.file_size,
                "warnings": [warning.value for warning in artifact.warnings],
            }
            for artifact in sorted(library.artifacts, key=lambda item: item.artifact_sha256)
        ],
        "locations": [
            {
                "artifact_sha256": location.artifact_sha256,
                "path": str(location.path),
                "root_path": str(location.root_path),
                "file_name": location.file_name,
                "modified_at": location.modified_at.isoformat(),
                "present": location.present,
                "first_seen_at": location.first_seen_at.isoformat(),
                "last_seen_at": location.last_seen_at.isoformat(),
            }
            for location in sorted(
                library.locations,
                key=lambda item: (item.artifact_sha256, _path_key(item.path)),
            )
        ],
    }


def _library_from_document(document: object) -> LocalApkLibrary:
    mapping = _mapping(document, "document")
    schema_version = mapping.get("schema_version")
    if type(schema_version) is not int:
        raise _InvalidDocument("schema_version must be an integer")
    if schema_version != LOCAL_APK_LIBRARY_SCHEMA_VERSION:
        raise _InvalidDocument(f"unsupported schema version {schema_version}")
    roots = tuple(_root_from_document(value) for value in _list(mapping.get("roots"), "roots"))
    artifacts = tuple(
        _artifact_from_document(value) for value in _list(mapping.get("artifacts"), "artifacts")
    )
    locations = tuple(
        _location_from_document(value) for value in _list(mapping.get("locations"), "locations")
    )
    library = LocalApkLibrary(schema_version, roots, artifacts, locations)
    _validate_library_relationships(library)
    return LocalApkLibrary(
        schema_version,
        tuple(sorted(roots, key=lambda item: _path_key(item.path))),
        tuple(sorted(artifacts, key=lambda item: item.artifact_sha256)),
        tuple(sorted(locations, key=lambda item: (item.artifact_sha256, _path_key(item.path)))),
    )


def _root_from_document(value: object) -> LocalApkLibraryRoot:
    mapping = _mapping(value, "root")
    return LocalApkLibraryRoot(
        path=_absolute_path(mapping.get("path"), "root.path"),
        registered_at=_datetime(mapping.get("registered_at"), "root.registered_at"),
        last_scan_at=_optional_datetime(mapping.get("last_scan_at"), "root.last_scan_at"),
        last_scan_status=_enum(
            LibraryRootScanStatus,
            mapping.get("last_scan_status"),
            "root.last_scan_status",
        ),
    )


def _artifact_from_document(value: object) -> LocalApkLibraryArtifact:
    mapping = _mapping(value, "artifact")
    sha256 = _string(mapping.get("artifact_sha256"), "artifact.artifact_sha256")
    if not _SHA256_RE.fullmatch(sha256):
        raise _InvalidDocument("artifact.artifact_sha256 must be a lowercase SHA-256")
    file_size = mapping.get("file_size")
    if type(file_size) is not int or file_size < 0:
        raise _InvalidDocument("artifact.file_size must be a non-negative integer")
    debuggable = mapping.get("application_debuggable")
    if debuggable is not None and type(debuggable) is not bool:
        raise _InvalidDocument("artifact.application_debuggable must be boolean or null")
    return LocalApkLibraryArtifact(
        artifact_format=_enum(
            LocalArtifactFormat, mapping.get("artifact_format"), "artifact.artifact_format"
        ),
        artifact_sha256=sha256,
        package_id=_nonempty_string(mapping.get("package_id"), "artifact.package_id"),
        application_label=_optional_string(mapping.get("application_label"), "artifact.application_label"),
        application_label_reference=_optional_string(
            mapping.get("application_label_reference"), "artifact.application_label_reference"
        ),
        version_name=_optional_string(mapping.get("version_name"), "artifact.version_name"),
        version_name_reference=_optional_string(
            mapping.get("version_name_reference"), "artifact.version_name_reference"
        ),
        version_code=_manifest_scalar(mapping.get("version_code"), "artifact.version_code"),
        version_code_major=_manifest_scalar(mapping.get("version_code_major"), "artifact.version_code_major"),
        min_sdk=_manifest_scalar(mapping.get("min_sdk"), "artifact.min_sdk"),
        target_sdk=_manifest_scalar(mapping.get("target_sdk"), "artifact.target_sdk"),
        compile_sdk=_manifest_scalar(mapping.get("compile_sdk"), "artifact.compile_sdk"),
        application_debuggable=debuggable,
        permissions=_string_tuple(mapping.get("permissions"), "artifact.permissions"),
        features=_string_tuple(mapping.get("features"), "artifact.features"),
        icon_reference=_optional_string(mapping.get("icon_reference"), "artifact.icon_reference"),
        file_size=file_size,
        warnings=tuple(
            _enum(LocalArtifactWarning, item, "artifact.warnings item")
            for item in _list(mapping.get("warnings"), "artifact.warnings")
        ),
    )


def _location_from_document(value: object) -> LocalApkLibraryLocation:
    mapping = _mapping(value, "location")
    sha256 = _string(mapping.get("artifact_sha256"), "location.artifact_sha256")
    if not _SHA256_RE.fullmatch(sha256):
        raise _InvalidDocument("location.artifact_sha256 must be a lowercase SHA-256")
    present = mapping.get("present")
    if type(present) is not bool:
        raise _InvalidDocument("location.present must be boolean")
    return LocalApkLibraryLocation(
        artifact_sha256=sha256,
        path=_absolute_path(mapping.get("path"), "location.path"),
        root_path=_absolute_path(mapping.get("root_path"), "location.root_path"),
        file_name=_nonempty_string(mapping.get("file_name"), "location.file_name"),
        modified_at=_datetime(mapping.get("modified_at"), "location.modified_at"),
        present=present,
        first_seen_at=_datetime(mapping.get("first_seen_at"), "location.first_seen_at"),
        last_seen_at=_datetime(mapping.get("last_seen_at"), "location.last_seen_at"),
    )


def _validate_library_relationships(library: LocalApkLibrary) -> None:
    root_keys = [_path_key(root.path) for root in library.roots]
    if len(root_keys) != len(set(root_keys)):
        raise _InvalidDocument("registered root paths must be unique")
    artifact_ids = [artifact.artifact_sha256 for artifact in library.artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise _InvalidDocument("artifact SHA-256 identities must be unique")
    artifact_id_set = set(artifact_ids)
    location_keys = [_location_key(location.artifact_sha256, location.path) for location in library.locations]
    if len(location_keys) != len(set(location_keys)):
        raise _InvalidDocument("artifact/path location associations must be unique")
    present_paths: set[str] = set()
    for location in library.locations:
        if location.artifact_sha256 not in artifact_id_set:
            raise _InvalidDocument("every location must reference a known artifact SHA-256")
        if _path_key(location.root_path) not in root_keys:
            raise _InvalidDocument("every location must reference a registered root")
        try:
            common_path = os.path.commonpath(
                [_path_key(location.path), _path_key(location.root_path)]
            )
        except ValueError as exc:
            raise _InvalidDocument("a location path must be under its registered root") from exc
        if common_path != _path_key(location.root_path):
            raise _InvalidDocument("a location path must be under its registered root")
        if location.first_seen_at > location.last_seen_at:
            raise _InvalidDocument("location first_seen_at must not exceed last_seen_at")
        path_key = _path_key(location.path)
        if location.present and path_key in present_paths:
            raise _InvalidDocument("one filesystem path cannot currently reference two artifacts")
        if location.present:
            present_paths.add(path_key)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise _InvalidDocument(f"{label} must be an object")
    return value


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise _InvalidDocument(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise _InvalidDocument(f"{label} must be a string")
    return value


def _nonempty_string(value: object, label: str) -> str:
    result = _string(value, label)
    if not result:
        raise _InvalidDocument(f"{label} must not be empty")
    return result


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    return _string(value, label)


def _string_tuple(value: object, label: str) -> tuple[str, ...]:
    values = _list(value, label)
    if not all(isinstance(item, str) for item in values):
        raise _InvalidDocument(f"{label} must contain only strings")
    return tuple(values)  # type: ignore[arg-type]


def _manifest_scalar(value: object, label: str) -> ManifestScalar | None:
    if value is None or isinstance(value, str) or type(value) is int:
        return value
    raise _InvalidDocument(f"{label} must be an integer, string or null")


def _datetime(value: object, label: str) -> datetime:
    text = _string(value, label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return _normalise_datetime(parsed)
    except ValueError as exc:
        raise _InvalidDocument(f"{label} must be an ISO-8601 timestamp with timezone") from exc


def _optional_datetime(value: object, label: str) -> datetime | None:
    if value is None:
        return None
    return _datetime(value, label)


def _absolute_path(value: object, label: str) -> Path:
    path = Path(_nonempty_string(value, label))
    if not path.is_absolute():
        raise _InvalidDocument(f"{label} must be absolute")
    return path


def _enum(enum_type: type[Any], value: object, label: str) -> Any:
    if not isinstance(value, str):
        raise _InvalidDocument(f"{label} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise _InvalidDocument(f"{label} has an unsupported value") from exc
