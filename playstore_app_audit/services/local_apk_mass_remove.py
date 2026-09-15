from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_file_ops as file_ops
from playstore_app_audit.services.local_apk_source import (
    SUPPORTED_LOCAL_PACKAGE_SUFFIXES,
)


class MassRemoveTarget(StrEnum):
    OUTDATED = "Outdated"
    UNKNOWN = "Unknown"


class MassRemovePlanStatus(StrEnum):
    RUNNABLE = "runnable"
    BLOCKED = "blocked"


class MassRemoveBatchStatus(StrEnum):
    COMPLETED = "completed"
    NO_CHANGES = "no_changes"
    BLOCKED = "blocked"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class MassRemovePlanEntry:
    source: Path
    file_name: str
    relationship: str
    package_name: str
    app_name: str
    status: MassRemovePlanStatus
    message: str = ""
    source_size: int | None = None
    source_mtime_ns: int | None = None


@dataclass(frozen=True, slots=True)
class MassRemovePlan:
    target: MassRemoveTarget
    entries: tuple[MassRemovePlanEntry, ...]
    active_candidate_count: int
    error: str = ""

    @property
    def runnable_count(self) -> int:
        return sum(
            entry.status is MassRemovePlanStatus.RUNNABLE
            for entry in self.entries
        )

    @property
    def blocked_count(self) -> int:
        return sum(
            entry.status is MassRemovePlanStatus.BLOCKED
            for entry in self.entries
        )

    @property
    def removes_entire_source(self) -> bool:
        return (
            self.active_candidate_count > 0
            and self.runnable_count == self.active_candidate_count
        )


@dataclass(frozen=True, slots=True)
class MassRemoveExecutionEntry:
    source: Path
    status: file_ops.LocalPackageFileMutationStatus
    final_location: Path | None
    message: str = ""


@dataclass(frozen=True, slots=True)
class MassRemoveExecutionResult:
    status: MassRemoveBatchStatus
    entries: tuple[MassRemoveExecutionEntry, ...]
    message: str = ""

    @property
    def removed_count(self) -> int:
        return sum(
            entry.status
            is file_ops.LocalPackageFileMutationStatus.REMOVED
            for entry in self.entries
        )

    @property
    def failed_count(self) -> int:
        return len(self.entries) - self.removed_count

    @property
    def ok(self) -> bool:
        return self.status in {
            MassRemoveBatchStatus.COMPLETED,
            MassRemoveBatchStatus.NO_CHANGES,
        }


def _path_key(value: object) -> str:
    try:
        path = Path(str(value)).expanduser().resolve(
            strict=False
        )
        return os.path.normcase(str(path))
    except (OSError, RuntimeError, TypeError, ValueError):
        return os.path.normcase(str(value))


def _supplied_path(value: object) -> Path:
    try:
        return Path(str(value)).expanduser().absolute()
    except (OSError, RuntimeError, TypeError, ValueError):
        return Path(str(value))


def _resolve_source(
    value: object,
) -> tuple[Path, str | None]:
    supplied = _supplied_path(value)

    try:
        source = Path(str(value)).expanduser().resolve(
            strict=True
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return (
            supplied,
            "The local package file no longer exists.",
        )

    if not source.is_file():
        return (
            source,
            "The local package path is not a file.",
        )

    if (
        source.suffix.casefold()
        not in SUPPORTED_LOCAL_PACKAGE_SUFFIXES
    ):
        return (
            source,
            "The file is not a supported local package.",
        )

    return source, None


def _blocked_entry(
    *,
    source: Path,
    file_name: str,
    relationship: str,
    package_name: str,
    app_name: str,
    message: str,
) -> MassRemovePlanEntry:
    return MassRemovePlanEntry(
        source=source,
        file_name=file_name,
        relationship=relationship,
        package_name=package_name,
        app_name=app_name,
        status=MassRemovePlanStatus.BLOCKED,
        message=message,
    )


def plan_local_package_mass_remove(
    rows: Sequence[Mapping[str, object]],
    candidates: Sequence[Path],
    target: MassRemoveTarget,
) -> MassRemovePlan:
    candidate_keys = {
        _path_key(candidate)
        for candidate in candidates
    }

    entries: list[MassRemovePlanEntry] = []
    seen_paths: set[str] = set()

    for row in rows:
        if not local_apk_audit.is_local_apk_source(
            row.get("source_mode")
        ):
            continue

        relationship = str(
            row.get("local_apk_version_comparison") or ""
        )

        if relationship != target.value:
            continue

        raw_location = str(
            row.get("local_apk_location") or ""
        ).strip()
        file_name = str(
            row.get("local_apk_file_name") or ""
        ).strip()
        package_name = str(
            row.get("package_name") or ""
        ).strip()
        app_name = str(
            row.get("local_apk_label")
            or row.get("app_name")
            or ""
        ).strip()

        if not raw_location:
            entries.append(
                _blocked_entry(
                    source=Path(file_name or "unknown"),
                    file_name=file_name or "Unknown file",
                    relationship=relationship,
                    package_name=package_name,
                    app_name=app_name,
                    message=(
                        "The result row has no usable physical "
                        "Local APK path."
                    ),
                )
            )
            continue

        supplied = _supplied_path(raw_location)
        supplied_key = _path_key(supplied)

        # The batch identity is the physical path only. Package ID and
        # SHA-256 deliberately do not participate in deduplication.
        if supplied_key in seen_paths:
            continue
        seen_paths.add(supplied_key)

        if supplied_key not in candidate_keys:
            entries.append(
                _blocked_entry(
                    source=supplied,
                    file_name=file_name or supplied.name,
                    relationship=relationship,
                    package_name=package_name,
                    app_name=app_name,
                    message=(
                        "The file is no longer part of the active "
                        "Local APK source."
                    ),
                )
            )
            continue

        source, source_error = _resolve_source(
            raw_location
        )

        if source_error:
            entries.append(
                _blocked_entry(
                    source=source,
                    file_name=file_name or source.name,
                    relationship=relationship,
                    package_name=package_name,
                    app_name=app_name,
                    message=source_error,
                )
            )
            continue

        try:
            stat = source.stat()
        except OSError as exc:
            entries.append(
                _blocked_entry(
                    source=source,
                    file_name=file_name or source.name,
                    relationship=relationship,
                    package_name=package_name,
                    app_name=app_name,
                    message=(
                        f"Could not inspect the source file: {exc}"
                    ),
                )
            )
            continue

        entries.append(
            MassRemovePlanEntry(
                source=source,
                file_name=file_name or source.name,
                relationship=relationship,
                package_name=package_name,
                app_name=app_name,
                status=MassRemovePlanStatus.RUNNABLE,
                source_size=stat.st_size,
                source_mtime_ns=stat.st_mtime_ns,
            )
        )

    error = ""
    if not entries:
        error = (
            f"No current Local APK/package files are "
            f"classified as {target.value}."
        )

    return MassRemovePlan(
        target=target,
        entries=tuple(entries),
        active_candidate_count=len(candidate_keys),
        error=error,
    )


def _source_signature_matches(
    entry: MassRemovePlanEntry,
) -> tuple[bool, str]:
    try:
        resolved = entry.source.resolve(strict=True)
    except (OSError, RuntimeError):
        return (
            False,
            "The source disappeared after the preview.",
        )

    if _path_key(resolved) != _path_key(entry.source):
        return (
            False,
            "The source path changed after the preview.",
        )

    if not resolved.is_file():
        return (
            False,
            "The source is no longer a file.",
        )

    if (
        resolved.suffix.casefold()
        not in SUPPORTED_LOCAL_PACKAGE_SUFFIXES
    ):
        return (
            False,
            "The source is no longer a supported local package.",
        )

    try:
        stat = resolved.stat()
    except OSError as exc:
        return (
            False,
            f"Could not revalidate the source file: {exc}",
        )

    if (
        stat.st_size != entry.source_size
        or stat.st_mtime_ns != entry.source_mtime_ns
    ):
        return (
            False,
            "The source changed after the preview.",
        )

    return True, ""


def execute_local_package_mass_remove(
    plan: MassRemovePlan,
) -> MassRemoveExecutionResult:
    runnable_entries = tuple(
        entry
        for entry in plan.entries
        if entry.status is MassRemovePlanStatus.RUNNABLE
    )

    blocked_results = [
        MassRemoveExecutionEntry(
            source=entry.source,
            status=(
                file_ops.LocalPackageFileMutationStatus.INVALID_SOURCE
            ),
            final_location=(
                entry.source
                if entry.source.exists()
                else None
            ),
            message=entry.message,
        )
        for entry in plan.entries
        if entry.status is MassRemovePlanStatus.BLOCKED
    ]

    if not runnable_entries:
        status = (
            MassRemoveBatchStatus.BLOCKED
            if blocked_results
            else MassRemoveBatchStatus.NO_CHANGES
        )
        return MassRemoveExecutionResult(
            status=status,
            entries=tuple(blocked_results),
            message=(
                plan.error
                or "No Local APK/package files can be removed."
            ),
        )

    results: list[MassRemoveExecutionEntry] = list(
        blocked_results
    )

    for entry in runnable_entries:
        valid, validation_message = (
            _source_signature_matches(entry)
        )

        if not valid:
            results.append(
                MassRemoveExecutionEntry(
                    source=entry.source,
                    status=(
                        file_ops.LocalPackageFileMutationStatus.INVALID_SOURCE
                    ),
                    final_location=(
                        entry.source
                        if entry.source.exists()
                        else None
                    ),
                    message=validation_message,
                )
            )
            continue

        mutation = file_ops.remove_local_package_file(
            entry.source
        )

        if (
            mutation.status
            is file_ops.LocalPackageFileMutationStatus.REMOVED
        ):
            final_location = None
        else:
            final_location = (
                entry.source
                if entry.source.exists()
                else None
            )

        results.append(
            MassRemoveExecutionEntry(
                source=entry.source,
                status=mutation.status,
                final_location=final_location,
                message=mutation.message,
            )
        )

    removed_count = sum(
        result.status
        is file_ops.LocalPackageFileMutationStatus.REMOVED
        for result in results
    )
    failure_count = len(results) - removed_count

    if removed_count == len(runnable_entries) and not blocked_results:
        status = MassRemoveBatchStatus.COMPLETED
        message = (
            f"Removed {removed_count} "
            f"{plan.target.value.lower()} local package file(s)."
        )
    elif removed_count > 0:
        status = MassRemoveBatchStatus.PARTIAL
        message = (
            f"Removed {removed_count} file(s); "
            f"{failure_count} file(s) were not removed."
        )
    else:
        status = MassRemoveBatchStatus.FAILED
        message = "No files could be removed."

    return MassRemoveExecutionResult(
        status=status,
        entries=tuple(results),
        message=message,
    )
