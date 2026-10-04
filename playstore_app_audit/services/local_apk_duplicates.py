from __future__ import annotations

import hashlib
import os
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from playstore_app_audit.services import local_apk_audit
from playstore_app_audit.services import local_apk_file_ops as file_ops

VersionIdentity = tuple[int | str | None, int | str | None, int | str | None]
FileSignature = tuple[int, int, int, int]


def _path_key(value: object) -> str:
    try:
        return os.path.normcase(str(Path(str(value)).expanduser().resolve(strict=False)))
    except OSError, RuntimeError, TypeError, ValueError:
        return os.path.normcase(str(value))


def _signature(stat: os.stat_result) -> FileSignature:
    # Windows stat/fstat ctime semantics differ. Identity and preview guards
    # use device/inode, size and mtime; current bytes always require SHA-256.
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _selection_key(path: Path) -> str:
    # Selection addresses the path displayed in the frozen review. Resolving
    # it again could silently select a different copy after symlink retargeting.
    return os.path.normcase(os.path.normpath(str(path.expanduser().absolute())))


@dataclass(frozen=True, slots=True)
class DuplicateFile:
    source: Path
    path_key: str
    sha256: str
    package_name: str
    app_name: str
    version: VersionIdentity | None
    signature: FileSignature | None = None
    error: str = ""

    @property
    def version_label(self) -> str:
        if self.version is None:
            return "Unknown local version"
        code, long_code, name = self.version
        return f"{name if name is not None else 'Unknown name'} (code {long_code if long_code is not None else code})"


@dataclass(frozen=True, slots=True)
class ExactDuplicateGroup:
    sha256: str
    files: tuple[DuplicateFile, ...]


class VersionFindingKind(StrEnum):
    SAME_VERSION_VARIANT = "Same Version Variant"
    MULTIPLE_VERSIONS = "Multiple Versions"


@dataclass(frozen=True, slots=True)
class VersionFinding:
    kind: VersionFindingKind
    package_name: str
    files: tuple[DuplicateFile, ...]


@dataclass(frozen=True, slots=True)
class DuplicateReview:
    exact_groups: tuple[ExactDuplicateGroup, ...]
    version_findings: tuple[VersionFinding, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.exact_groups or self.version_findings)


def _version_identity(row: Mapping[str, object]) -> VersionIdentity | None:
    values = tuple(
        row.get(key)
        for key in (
            "local_apk_version_code",
            "local_apk_long_version_code",
            "local_apk_version_name",
        )
    )
    if any(
        value is not None and (isinstance(value, bool) or not isinstance(value, (int, str)))
        for value in values
    ):
        return None
    if all(value is None or value == "" for value in values):
        return None
    return values


def analyze_local_apk_duplicates(
    rows: Sequence[Mapping[str, object]],
    candidates: Sequence[Path],
) -> DuplicateReview:
    """Discover from current row evidence only; never hash files for availability."""
    candidate_keys = {_path_key(path) for path in candidates}
    by_path: dict[str, DuplicateFile] = {}
    conflicts: set[str] = set()
    for row in rows:
        location = str(row.get("local_apk_location") or "").strip()
        if not location or not local_apk_audit.is_local_apk_source(row.get("source_mode")):
            continue
        key = _path_key(location)
        if key not in candidate_keys:
            continue
        sha = str(row.get("local_apk_sha256") or "")
        sha = sha.lower() if re.fullmatch(r"[0-9a-fA-F]{64}", sha) else ""
        file = DuplicateFile(
            Path(location).expanduser().absolute(),
            key,
            sha,
            str(row.get("package_name") or ""),
            str(row.get("local_apk_label") or row.get("app_name") or ""),
            _version_identity(row),
        )
        previous = by_path.get(key)
        if previous and (previous.sha256, previous.package_name, previous.version) != (
            file.sha256,
            file.package_name,
            file.version,
        ):
            conflicts.add(key)
        by_path.setdefault(key, file)

    by_sha: dict[str, list[DuplicateFile]] = defaultdict(list)
    by_package: dict[str, list[DuplicateFile]] = defaultdict(list)
    for key, file in by_path.items():
        if key in conflicts:
            continue
        if file.sha256:
            by_sha[file.sha256].append(file)
        if file.package_name and file.version is not None:
            by_package[file.package_name].append(file)
    exact = tuple(ExactDuplicateGroup(sha, tuple(files)) for sha, files in by_sha.items() if len(files) > 1)
    findings: list[VersionFinding] = []
    for package, files in by_package.items():
        by_version: dict[VersionIdentity, list[DuplicateFile]] = defaultdict(list)
        for file in files:
            by_version[file.version].append(file)
        for version_files in by_version.values():
            valid_files = tuple(file for file in version_files if file.sha256)
            if len({file.sha256 for file in valid_files}) > 1:
                findings.append(VersionFinding(VersionFindingKind.SAME_VERSION_VARIANT, package, valid_files))
        if len(by_version) > 1:
            findings.append(VersionFinding(VersionFindingKind.MULTIPLE_VERSIONS, package, tuple(files)))
    return DuplicateReview(exact, tuple(findings))


def snapshot_duplicate_review(review: DuplicateReview) -> DuplicateReview:
    """Capture preview metadata once, before the user makes a removal selection."""
    groups: list[ExactDuplicateGroup] = []
    for group in review.exact_groups:
        files: list[DuplicateFile] = []
        for file in group.files:
            try:
                resolved, error = file_ops._resolve_source(file.source)
                if error or os.path.normcase(str(resolved)) != file.path_key:
                    raise ValueError(error or "The physical path changed before review.")
                files.append(replace(file, signature=_signature(resolved.stat())))
            except (OSError, RuntimeError, ValueError) as exc:
                files.append(replace(file, error=str(exc)))
        groups.append(ExactDuplicateGroup(group.sha256, tuple(files)))
    return DuplicateReview(tuple(groups), review.version_findings)


@dataclass(frozen=True, slots=True)
class DuplicateCleanupGroup:
    sha256: str
    selected: tuple[DuplicateFile, ...]
    keepers: tuple[DuplicateFile, ...]


@dataclass(frozen=True, slots=True)
class DuplicateCleanupPlan:
    groups: tuple[DuplicateCleanupGroup, ...] = ()
    error: str = ""

    @property
    def selected_count(self) -> int:
        return sum(len(group.selected) for group in self.groups)

    @property
    def executable(self) -> bool:
        return bool(self.groups) and not self.error and not _plan_error(self.groups)


def _plan_error(groups: tuple[DuplicateCleanupGroup, ...]) -> str:
    seen: set[str] = set()
    for group in groups:
        if not group.selected or not group.keepers:
            return "Keep at least one unselected exact copy in every group."
        if not re.fullmatch(r"[0-9a-f]{64}", group.sha256):
            return "Invalid exact SHA-256 identity."
        for file in (*group.selected, *group.keepers):
            if file.path_key in seen:
                return "A physical path cannot appear twice in a cleanup plan."
            seen.add(file.path_key)
            if file.sha256 != group.sha256 or file.signature is None or file.error:
                return file.error or "The review has no valid physical file evidence."
    return ""


def plan_duplicate_cleanup(review: DuplicateReview, selected_paths: Sequence[Path]) -> DuplicateCleanupPlan:
    selected_keys = {_selection_key(path) for path in selected_paths}
    known = {_selection_key(file.source) for group in review.exact_groups for file in group.files}
    if selected_keys - known:
        return DuplicateCleanupPlan(error="Selection contains a path outside the exact duplicate review.")
    groups = tuple(
        DuplicateCleanupGroup(
            group.sha256,
            tuple(file for file in group.files if _selection_key(file.source) in selected_keys),
            tuple(file for file in group.files if _selection_key(file.source) not in selected_keys),
        )
        for group in review.exact_groups
        if any(_selection_key(file.source) in selected_keys for file in group.files)
    )
    return DuplicateCleanupPlan(groups, _plan_error(groups))


class DuplicateCleanupStatus(StrEnum):
    REMOVED = "removed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DuplicateCleanupEntry:
    source: Path
    sha256: str
    status: DuplicateCleanupStatus
    message: str = ""


@dataclass(frozen=True, slots=True)
class DuplicateCleanupResult:
    entries: tuple[DuplicateCleanupEntry, ...]
    error: str = ""

    def count(self, status: DuplicateCleanupStatus) -> int:
        return sum(entry.status is status for entry in self.entries)

    @property
    def message(self) -> str:
        return self.error or (
            f"Duplicate cleanup: {self.count(DuplicateCleanupStatus.REMOVED)} removed, "
            f"{self.count(DuplicateCleanupStatus.BLOCKED)} blocked/stale, "
            f"{self.count(DuplicateCleanupStatus.FAILED)} failed."
        )


def _revalidate(file: DuplicateFile, expected_sha: str) -> str:
    try:
        resolved, error = file_ops._resolve_source(file.source)
        if error:
            return error
        # Compare with the frozen key, never a newly resolved preview path.
        if os.path.normcase(str(resolved)) != file.path_key:
            return "The physical path changed after review."
        with resolved.open("rb") as handle:
            before = _signature(os.fstat(handle.fileno()))
            if before != file.signature:
                return "The file changed after review."
            sha = hashlib.file_digest(handle, "sha256").hexdigest()
            after = _signature(os.fstat(handle.fileno()))
        if sha != expected_sha:
            return "Current file SHA-256 differs from the reviewed exact copy."
        if before != after or _signature(resolved.stat()) != after or _path_key(file.source) != file.path_key:
            return "The file changed during revalidation."
    except (OSError, RuntimeError, ValueError) as exc:
        return f"Could not revalidate the physical file: {exc}"
    return ""


def _group_error(files: Sequence[DuplicateFile], sha: str) -> str:
    for file in files:
        if error := _revalidate(file, sha):
            return f"{file.source}: {error}"
    return ""


def _final_metadata_error(files: Sequence[DuplicateFile]) -> str:
    """Catch path/metadata changes while another group member was hashed."""
    for file in files:
        try:
            resolved, error = file_ops._resolve_source(file.source)
            if error or os.path.normcase(str(resolved)) != file.path_key:
                return f"{file.source}: {error or 'The physical path changed during revalidation.'}"
            if _signature(resolved.stat()) != file.signature:
                return f"{file.source}: The file changed during group revalidation."
        except (OSError, RuntimeError, ValueError) as exc:
            return f"{file.source}: Could not recheck file metadata: {exc}"
    return ""


def execute_duplicate_cleanup(plan: DuplicateCleanupPlan) -> DuplicateCleanupResult:
    error = plan.error or _plan_error(plan.groups)
    if error:
        return DuplicateCleanupResult(
            tuple(
                DuplicateCleanupEntry(file.source, group.sha256, DuplicateCleanupStatus.BLOCKED, error)
                for group in plan.groups
                for file in group.selected
            ),
            error,
        )
    results: list[DuplicateCleanupEntry] = []
    for group in plan.groups:
        # Preflight every selected file and every preview keeper before the
        # first deletion. No deletion in a stale group is authorized.
        blocked = _group_error((*group.selected, *group.keepers), group.sha256)
        for file in group.selected:
            if not blocked:
                # Rehash target and keepers immediately before each mutation.
                # External filesystem writers cannot be locked portably; keep
                # this check adjacent to the canonical deletion primitive.
                blocked = _group_error((*group.keepers, file), group.sha256)
                if not blocked:
                    blocked = _final_metadata_error((*group.keepers, file))
            if blocked:
                results.append(
                    DuplicateCleanupEntry(file.source, group.sha256, DuplicateCleanupStatus.BLOCKED, blocked)
                )
                continue
            mutation = file_ops.remove_local_package_file(file.source)
            status = (
                DuplicateCleanupStatus.REMOVED
                if mutation.status is file_ops.LocalPackageFileMutationStatus.REMOVED
                else DuplicateCleanupStatus.FAILED
            )
            results.append(DuplicateCleanupEntry(file.source, group.sha256, status, mutation.message))
            if status is DuplicateCleanupStatus.FAILED:
                blocked = "This group stopped after a deletion failure. Review its current files again."
    return DuplicateCleanupResult(tuple(results))
