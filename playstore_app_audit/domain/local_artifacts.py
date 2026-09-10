from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class LocalArtifactFormat(StrEnum):
    APK = "apk"


class LocalArtifactWarning(StrEnum):
    APPLICATION_LABEL_UNRESOLVED = "application_label_unresolved"
    VERSION_NAME_UNRESOLVED = "version_name_unresolved"


class LocalArtifactFailureKind(StrEnum):
    NOT_FOUND = "not_found"
    NOT_A_FILE = "not_a_file"
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_TOO_LARGE = "file_too_large"
    IO_ERROR = "io_error"
    MALFORMED_ARCHIVE = "malformed_archive"
    ARCHIVE_LIMIT_EXCEEDED = "archive_limit_exceeded"
    MISSING_MANIFEST = "missing_manifest"
    MALFORMED_MANIFEST = "malformed_manifest"
    UNSUPPORTED_SPLIT = "unsupported_split"


ManifestScalar = int | str


@dataclass(frozen=True, slots=True)
class LocalArtifact:
    """Immutable metadata for one exact local APK file.

    ``artifact_sha256`` identifies file bytes. ``package_id`` identifies the
    Android package and is deliberately a separate value so later Store work
    can fan one package result out to multiple distinct artifacts.
    """

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
    file_name: str
    canonical_path: Path
    file_size: int
    modified_at: datetime
    warnings: tuple[LocalArtifactWarning, ...] = ()

    @property
    def artifact_id(self) -> str:
        return self.artifact_sha256

    @property
    def package_lookup_key(self) -> str:
        return self.package_id

    @property
    def long_version_code(self) -> int | None:
        if not isinstance(self.version_code, int):
            return None
        if self.version_code_major is None:
            return self.version_code
        if not isinstance(self.version_code_major, int):
            return None
        return (self.version_code_major << 32) | self.version_code


@dataclass(frozen=True, slots=True)
class LocalArtifactParseFailure:
    path: Path
    kind: LocalArtifactFailureKind
    message: str
    artifact_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class LocalArtifactParseResult:
    artifact: LocalArtifact | None = None
    failure: LocalArtifactParseFailure | None = None

    def __post_init__(self) -> None:
        if (self.artifact is None) == (self.failure is None):
            raise ValueError("A parse result must contain exactly one outcome")

    @property
    def succeeded(self) -> bool:
        return self.artifact is not None
