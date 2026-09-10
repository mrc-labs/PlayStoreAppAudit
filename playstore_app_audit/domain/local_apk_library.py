from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifactFormat,
    LocalArtifactWarning,
    ManifestScalar,
)

LOCAL_APK_LIBRARY_SCHEMA_VERSION = 1


class LibraryRootScanStatus(StrEnum):
    NEVER = "never"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LibraryScanIssueKind(StrEnum):
    ROOT_UNAVAILABLE = "root_unavailable"
    DIRECTORY_INACCESSIBLE = "directory_inaccessible"
    FILE_INACCESSIBLE = "file_inaccessible"
    PARSER_FAILURE = "parser_failure"


class LibraryLoadFailureKind(StrEnum):
    IO_ERROR = "io_error"
    MALFORMED_JSON = "malformed_json"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    INVALID_DOCUMENT = "invalid_document"


class LibrarySaveFailureKind(StrEnum):
    INVALID_DOCUMENT = "invalid_document"
    IO_ERROR = "io_error"


@dataclass(frozen=True, slots=True)
class LocalApkLibraryRoot:
    path: Path
    registered_at: datetime
    last_scan_at: datetime | None = None
    last_scan_status: LibraryRootScanStatus = LibraryRootScanStatus.NEVER


@dataclass(frozen=True, slots=True)
class LocalApkLibraryArtifact:
    """Path-independent metadata for one exact APK byte sequence."""

    artifact_format: LocalArtifactFormat
    artifact_sha256: str
    package_id: str
    application_label: str | None
    application_label_reference: str | None
    version_name: str | None
    version_name_reference: str | None
    version_code: ManifestScalar | None
    version_code_major: ManifestScalar | None
    min_sdk: ManifestScalar | None
    target_sdk: ManifestScalar | None
    compile_sdk: ManifestScalar | None
    application_debuggable: bool | None
    permissions: tuple[str, ...]
    features: tuple[str, ...]
    icon_reference: str | None
    file_size: int
    warnings: tuple[LocalArtifactWarning, ...] = ()

    @property
    def artifact_id(self) -> str:
        return self.artifact_sha256

    @property
    def package_lookup_key(self) -> str:
        return self.package_id


@dataclass(frozen=True, slots=True)
class LocalApkLibraryLocation:
    """One known path-to-artifact association, including historical ones."""

    artifact_sha256: str
    path: Path
    root_path: Path
    file_name: str
    modified_at: datetime
    present: bool
    first_seen_at: datetime
    last_seen_at: datetime


@dataclass(frozen=True, slots=True)
class LocalApkLibrary:
    schema_version: int = LOCAL_APK_LIBRARY_SCHEMA_VERSION
    roots: tuple[LocalApkLibraryRoot, ...] = ()
    artifacts: tuple[LocalApkLibraryArtifact, ...] = ()
    locations: tuple[LocalApkLibraryLocation, ...] = ()


@dataclass(frozen=True, slots=True)
class LocalApkLibraryLoadFailure:
    kind: LibraryLoadFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class LocalApkLibraryLoadResult:
    library: LocalApkLibrary | None = None
    failure: LocalApkLibraryLoadFailure | None = None

    def __post_init__(self) -> None:
        if (self.library is None) == (self.failure is None):
            raise ValueError("A Library load result must contain exactly one outcome")

    @property
    def succeeded(self) -> bool:
        return self.library is not None


@dataclass(frozen=True, slots=True)
class LocalApkLibrarySaveFailure:
    kind: LibrarySaveFailureKind
    message: str


@dataclass(frozen=True, slots=True)
class LocalApkLibrarySaveResult:
    path: Path
    failure: LocalApkLibrarySaveFailure | None = None

    @property
    def succeeded(self) -> bool:
        return self.failure is None


@dataclass(frozen=True, slots=True)
class LocalApkLibraryScanIssue:
    root_path: Path
    path: Path
    kind: LibraryScanIssueKind
    message: str
    parser_failure_kind: str | None = None


@dataclass(frozen=True, slots=True)
class LocalApkLibraryScanProgress:
    root_path: Path
    current_path: Path
    discovered_apks: int
    parsed_artifacts: int


@dataclass(frozen=True, slots=True)
class LocalApkLibraryRootScanResult:
    root_path: Path
    status: LibraryRootScanStatus
    discovered_apks: int
    parsed_artifacts: int
    issue_count: int


@dataclass(frozen=True, slots=True)
class LocalApkLibraryScanResult:
    library: LocalApkLibrary
    roots: tuple[LocalApkLibraryRootScanResult, ...]
    issues: tuple[LocalApkLibraryScanIssue, ...]
    cancelled: bool
    omitted_issue_count: int = 0
