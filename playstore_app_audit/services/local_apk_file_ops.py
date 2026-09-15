from __future__ import annotations

import errno
import os
import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from playstore_app_audit.services.local_apk_source import (
    SUPPORTED_LOCAL_PACKAGE_SUFFIXES,
)


class LocalPackageFileMutationStatus(StrEnum):
    RENAMED = "renamed"
    REMOVED = "removed"
    NO_CHANGE = "no_change"
    INVALID_SOURCE = "invalid_source"
    INVALID_NAME = "invalid_name"
    COLLISION = "collision"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class LocalPackageFileMutationResult:
    status: LocalPackageFileMutationStatus
    source: Path
    destination: Path | None = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {
            LocalPackageFileMutationStatus.RENAMED,
            LocalPackageFileMutationStatus.REMOVED,
            LocalPackageFileMutationStatus.NO_CHANGE,
        }


def _supplied_path(value: str | Path) -> Path:
    try:
        return Path(value).expanduser().absolute()
    except (OSError, RuntimeError, TypeError, ValueError):
        return Path(str(value))


def _resolve_source(
    value: str | Path,
) -> tuple[Path, str | None]:
    supplied = _supplied_path(value)
    try:
        source = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        return supplied, "The selected local package file no longer exists."

    if not source.is_file():
        return source, "The selected local package path is not a file."

    if source.suffix.casefold() not in SUPPORTED_LOCAL_PACKAGE_SUFFIXES:
        return source, "The selected file is not a supported local package."

    return source, None


def _validate_new_filename(source: Path, value: str) -> str | None:
    if not isinstance(value, str):
        return "Enter a valid filename."

    if not value or value != value.strip():
        return "Filename must not be empty or start/end with whitespace."

    if value in {".", ".."}:
        return "Filename is not valid."

    if "/" in value or "\\" in value:
        return "Enter a filename only, without a folder path."

    if any(ord(character) < 32 for character in value):
        return "Filename contains unsupported control characters."

    candidate = Path(value)

    if candidate.name != value:
        return "Enter a filename only, without a folder path."

    suffix = candidate.suffix.casefold()
    if suffix not in SUPPORTED_LOCAL_PACKAGE_SUFFIXES:
        return "The renamed file must keep a supported package extension."

    if suffix != source.suffix.casefold():
        return f"Keep the original {source.suffix} package extension."

    return None



_LINK_FALLBACK_ERRNOS = frozenset(
    code
    for code in (
        errno.EXDEV,
        errno.EPERM,
        errno.EACCES,
        errno.ENOSYS,
        getattr(errno, "EOPNOTSUPP", None),
        getattr(errno, "ENOTSUP", None),
    )
    if code is not None
)


def _rollback_destination(destination: Path) -> str:
    try:
        destination.unlink()
    except OSError as exc:
        return f" Rollback also failed: {exc}"
    return ""


def _copy_exclusive_then_remove(
    source: Path,
    destination: Path,
) -> tuple[LocalPackageFileMutationStatus, str]:
    created = False
    try:
        with source.open("rb") as source_handle:
            with destination.open("xb") as destination_handle:
                created = True
                shutil.copyfileobj(
                    source_handle,
                    destination_handle,
                    length=1024 * 1024,
                )
                destination_handle.flush()
                os.fsync(destination_handle.fileno())
        shutil.copystat(source, destination, follow_symlinks=False)
    except FileExistsError:
        return (
            LocalPackageFileMutationStatus.COLLISION,
            "A file or filesystem entry with that name already exists.",
        )
    except OSError as exc:
        rollback = _rollback_destination(destination) if created else ""
        return (
            LocalPackageFileMutationStatus.FAILED,
            f"The file could not be safely renamed: {exc}.{rollback}",
        )

    try:
        source.unlink()
    except OSError as exc:
        rollback = _rollback_destination(destination)
        return (
            LocalPackageFileMutationStatus.FAILED,
            f"The original file could not be removed after the safe copy: {exc}.{rollback}",
        )

    return LocalPackageFileMutationStatus.RENAMED, ""


def _move_without_overwrite(
    source: Path,
    destination: Path,
) -> tuple[LocalPackageFileMutationStatus, str]:
    try:
        # Creating the destination hard link is exclusive: an existing path is
        # never replaced. Both names temporarily reference the same bytes.
        os.link(source, destination)
    except FileExistsError:
        return (
            LocalPackageFileMutationStatus.COLLISION,
            "A file or filesystem entry with that name already exists.",
        )
    except OSError as exc:
        if exc.errno not in _LINK_FALLBACK_ERRNOS:
            return (
                LocalPackageFileMutationStatus.FAILED,
                f"The file could not be safely renamed: {exc}",
            )
        return _copy_exclusive_then_remove(source, destination)

    try:
        source.unlink()
    except OSError as exc:
        rollback = _rollback_destination(destination)
        return (
            LocalPackageFileMutationStatus.FAILED,
            f"The original filename could not be removed: {exc}.{rollback}",
        )

    return LocalPackageFileMutationStatus.RENAMED, ""

def rename_local_package_file(
    source_value: str | Path,
    new_filename: str,
) -> LocalPackageFileMutationResult:
    source, source_error = _resolve_source(source_value)
    if source_error is not None:
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.INVALID_SOURCE,
            source,
            message=source_error,
        )

    name_error = _validate_new_filename(source, new_filename)
    if name_error is not None:
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.INVALID_NAME,
            source,
            message=name_error,
        )

    destination = source.parent / new_filename

    if destination == source:
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.NO_CHANGE,
            source,
            destination,
            "The filename is unchanged.",
        )

    if os.path.normcase(str(destination)) == os.path.normcase(str(source)):
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.COLLISION,
            source,
            destination,
            "The requested filename resolves to the current file on this platform.",
        )

    if os.path.lexists(destination):
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.COLLISION,
            source,
            destination,
            "A file or filesystem entry with that name already exists.",
        )

    status, message = _move_without_overwrite(source, destination)
    return LocalPackageFileMutationResult(
        status,
        source,
        destination,
        message,
    )


def remove_local_package_file(
    source_value: str | Path,
) -> LocalPackageFileMutationResult:
    source, source_error = _resolve_source(source_value)
    if source_error is not None:
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.INVALID_SOURCE,
            source,
            message=source_error,
        )

    try:
        source.unlink()
    except OSError as exc:
        return LocalPackageFileMutationResult(
            LocalPackageFileMutationStatus.FAILED,
            source,
            message=f"The file could not be removed: {exc}",
        )

    return LocalPackageFileMutationResult(
        LocalPackageFileMutationStatus.REMOVED,
        source,
    )
