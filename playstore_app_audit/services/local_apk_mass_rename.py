from __future__ import annotations

import os
import unicodedata
import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from string import Formatter

import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_file_ops as file_ops
from playstore_app_audit.services.local_apk_source import (
    SUPPORTED_LOCAL_PACKAGE_SUFFIXES,
)


class MassRenamePlanStatus(StrEnum):
    RENAME = "rename"
    UNCHANGED = "unchanged"
    INVALID = "invalid"
    CONFLICT = "conflict"


class MassRenameBatchStatus(StrEnum):
    COMPLETED = "completed"
    NO_CHANGES = "no_changes"
    BLOCKED = "blocked"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass(frozen=True, slots=True)
class MassRenamePlanEntry:
    source: Path
    destination: Path | None
    rendered_filename: str
    status: MassRenamePlanStatus
    message: str = ""
    source_size: int | None = None
    source_mtime_ns: int | None = None


@dataclass(frozen=True, slots=True)
class MassRenamePlan:
    template: str
    entries: tuple[MassRenamePlanEntry, ...]
    error: str = ""

    @property
    def has_blocking_issues(self) -> bool:
        return bool(self.error) or any(
            entry.status
            in {
                MassRenamePlanStatus.INVALID,
                MassRenamePlanStatus.CONFLICT,
            }
            for entry in self.entries
        )

    @property
    def rename_count(self) -> int:
        return sum(
            entry.status is MassRenamePlanStatus.RENAME
            for entry in self.entries
        )


@dataclass(frozen=True, slots=True)
class MassRenameExecutionEntry:
    source: Path
    destination: Path | None
    status: file_ops.LocalPackageFileMutationStatus
    final_location: Path | None
    message: str = ""


@dataclass(frozen=True, slots=True)
class MassRenameExecutionResult:
    status: MassRenameBatchStatus
    entries: tuple[MassRenameExecutionEntry, ...]
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {
            MassRenameBatchStatus.COMPLETED,
            MassRenameBatchStatus.NO_CHANGES,
        }


_TOKEN_FIELDS: dict[str, tuple[str, ...]] = {
    "packagename": ("package_name",),
    "appname": ("local_apk_label", "app_name"),
    "playname": ("play_title",),
    "category": (
        "play_category",
        "play_genre",
        "store_category",
    ),
    "localversion": ("local_apk_version_name",),
}

_PORTABLE_FORBIDDEN = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }
)

_MAX_PORTABLE_FILENAME_BYTES = 240


def _portable_path_key(path: Path) -> str:
    return unicodedata.normalize(
        "NFC",
        str(path.absolute()),
    ).casefold()


def _exact_path_key(path: Path) -> str:
    return unicodedata.normalize(
        "NFC",
        str(path.absolute()),
    )


def _same_file(first: Path, second: Path) -> bool:
    try:
        return os.path.samefile(first, second)
    except (FileNotFoundError, OSError):
        return False


def _supplied_path(value: object) -> Path:
    try:
        return Path(str(value)).expanduser().absolute()
    except (OSError, RuntimeError, TypeError, ValueError):
        return Path(str(value))


def _resolve_source(value: object) -> tuple[Path, str | None]:
    supplied = _supplied_path(value)

    try:
        source = Path(str(value)).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, TypeError, ValueError):
        return supplied, "The local package file no longer exists."

    if not source.is_file():
        return source, "The local package path is not a file."

    if source.suffix.casefold() not in SUPPORTED_LOCAL_PACKAGE_SUFFIXES:
        return source, "The file is not a supported local package."

    return source, None


def _template_parts(
    template: str,
) -> tuple[tuple[tuple[str, str | None], ...], str]:
    if not isinstance(template, str) or not template.strip():
        return (), "Enter a Mass Rename template."

    try:
        parsed = tuple(Formatter().parse(template))
    except ValueError as exc:
        return (), f"Invalid template syntax: {exc}"

    parts: list[tuple[str, str | None]] = []

    for literal, field_name, format_spec, conversion in parsed:
        if any(
            ord(character) < 32
            or character in _PORTABLE_FORBIDDEN
            for character in literal
        ):
            return (
                (),
                "Template literal text contains characters that are "
                "not portable in filenames.",
            )

        if field_name is None:
            parts.append((literal, None))
            continue

        if format_spec or conversion:
            return (
                (),
                "Format specifications and conversions are not supported "
                "in Mass Rename templates.",
            )

        token = field_name.casefold()

        if token not in _TOKEN_FIELDS:
            return (
                (),
                f"Unknown Mass Rename token: {{{field_name}}}.",
            )

        parts.append((literal, token))

    return tuple(parts), ""


def _metadata_value(
    row: Mapping[str, object],
    token: str,
) -> object | None:
    for field in _TOKEN_FIELDS[token]:
        value = row.get(field)
        if value is None:
            continue
        if str(value).strip():
            return value
    return None


def _sanitize_token_value(value: object) -> str:
    text = unicodedata.normalize(
        "NFC",
        str(value).strip(),
    )

    safe = "".join(
        "_"
        if ord(character) < 32
        or character in _PORTABLE_FORBIDDEN
        else character
        for character in text
    )

    return safe.strip(" .")


def _render_template(
    parts: tuple[tuple[str, str | None], ...],
    row: Mapping[str, object],
) -> tuple[str, str]:
    output: list[str] = []

    for literal, token in parts:
        output.append(literal)

        if token is None:
            continue

        raw_value = _metadata_value(row, token)
        if raw_value is None:
            return (
                "",
                f"Missing metadata for {{{token}}}.",
            )

        safe_value = _sanitize_token_value(raw_value)
        if not safe_value:
            return (
                "",
                f"Metadata for {{{token}}} does not produce a usable "
                "filename value.",
            )

        output.append(safe_value)

    return "".join(output), ""


def _portable_filename_error(
    filename: str,
    expected_suffix: str,
) -> str:
    if not filename or filename != filename.strip():
        return "Filename must not be empty or start/end with whitespace."

    if filename in {".", ".."}:
        return "Filename is not valid."

    if any(
        ord(character) < 32
        or character in _PORTABLE_FORBIDDEN
        for character in filename
    ):
        return "Filename contains characters that are not portable."

    if filename.endswith("."):
        return "Filename must not end with a dot."

    if Path(filename).name != filename:
        return "Mass Rename may not create or traverse directories."

    if len(filename.encode("utf-8")) > _MAX_PORTABLE_FILENAME_BYTES:
        return "Filename is too long for the portable filename policy."

    reserved_basename = filename.split(".", 1)[0].casefold()
    if reserved_basename in _WINDOWS_RESERVED_BASENAMES:
        return (
            "Filename uses a Windows-reserved device basename "
            f"({reserved_basename.upper()})."
        )

    suffix = Path(filename).suffix.casefold()
    if suffix != expected_suffix.casefold():
        return (
            f"Mass Rename must preserve the original "
            f"{expected_suffix} package extension."
        )

    return ""


def _rendered_filename(
    rendered: str,
    source: Path,
) -> tuple[str, str]:
    if not rendered:
        return "", "The template produced an empty filename."

    rendered_suffix = Path(rendered).suffix.casefold()

    if rendered_suffix in SUPPORTED_LOCAL_PACKAGE_SUFFIXES:
        if rendered_suffix != source.suffix.casefold():
            return (
                "",
                f"The template explicitly produced {rendered_suffix}, "
                f"but this file uses {source.suffix}.",
            )
        filename = rendered
    else:
        filename = f"{rendered}{source.suffix}"

    error = _portable_filename_error(
        filename,
        source.suffix,
    )
    return filename, error


def _mark_conflict(
    entries: list[MassRenamePlanEntry],
    indexes: Sequence[int],
    message: str,
) -> None:
    for index in indexes:
        entry = entries[index]
        entries[index] = replace(
            entry,
            status=MassRenamePlanStatus.CONFLICT,
            message=message,
        )


def plan_local_package_mass_rename(
    rows: Sequence[Mapping[str, object]],
    template: str,
) -> MassRenamePlan:
    parts, template_error = _template_parts(template)

    if template_error:
        return MassRenamePlan(
            template=template,
            entries=(),
            error=template_error,
        )

    entries: list[MassRenamePlanEntry] = []

    for row in rows:
        if not local_apk_audit.is_local_apk_source(
            row.get("source_mode")
        ):
            continue

        location = str(
            row.get("local_apk_location") or ""
        ).strip()

        if not location:
            continue

        source, source_error = _resolve_source(location)

        if source_error:
            entries.append(
                MassRenamePlanEntry(
                    source=source,
                    destination=None,
                    rendered_filename="",
                    status=MassRenamePlanStatus.INVALID,
                    message=source_error,
                )
            )
            continue

        try:
            stat = source.stat()
        except OSError as exc:
            entries.append(
                MassRenamePlanEntry(
                    source=source,
                    destination=None,
                    rendered_filename="",
                    status=MassRenamePlanStatus.INVALID,
                    message=f"Could not inspect source file: {exc}",
                )
            )
            continue

        rendered, render_error = _render_template(
            parts,
            row,
        )

        if render_error:
            entries.append(
                MassRenamePlanEntry(
                    source=source,
                    destination=None,
                    rendered_filename="",
                    status=MassRenamePlanStatus.INVALID,
                    message=render_error,
                    source_size=stat.st_size,
                    source_mtime_ns=stat.st_mtime_ns,
                )
            )
            continue

        filename, filename_error = _rendered_filename(
            rendered,
            source,
        )

        if filename_error:
            entries.append(
                MassRenamePlanEntry(
                    source=source,
                    destination=None,
                    rendered_filename=filename,
                    status=MassRenamePlanStatus.INVALID,
                    message=filename_error,
                    source_size=stat.st_size,
                    source_mtime_ns=stat.st_mtime_ns,
                )
            )
            continue

        destination = source.parent / filename
        status = (
            MassRenamePlanStatus.UNCHANGED
            if destination.name == source.name
            else MassRenamePlanStatus.RENAME
        )

        entries.append(
            MassRenamePlanEntry(
                source=source,
                destination=destination,
                rendered_filename=filename,
                status=status,
                source_size=stat.st_size,
                source_mtime_ns=stat.st_mtime_ns,
            )
        )

    if not entries:
        return MassRenamePlan(
            template=template,
            entries=(),
            error="No eligible Local APK/package files are loaded.",
        )

    source_groups: dict[str, list[int]] = defaultdict(list)

    for index, entry in enumerate(entries):
        source_groups[_portable_path_key(entry.source)].append(index)

    for indexes in source_groups.values():
        if len(indexes) > 1:
            _mark_conflict(
                entries,
                indexes,
                "The same physical source path appears more than once "
                "in the batch.",
            )

    destination_groups: dict[str, list[int]] = defaultdict(list)

    for index, entry in enumerate(entries):
        if (
            entry.destination is None
            or entry.status is MassRenamePlanStatus.INVALID
        ):
            continue

        destination_groups[
            _portable_path_key(entry.destination)
        ].append(index)

    for indexes in destination_groups.values():
        if len(indexes) > 1:
            _mark_conflict(
                entries,
                indexes,
                "Multiple files would resolve to the same portable "
                "destination filename.",
            )

    exact_source_indexes = {
        _exact_path_key(entry.source): index
        for index, entry in enumerate(entries)
    }

    for index, entry in enumerate(tuple(entries)):
        if (
            entry.status is not MassRenamePlanStatus.RENAME
            or entry.destination is None
            or not os.path.lexists(entry.destination)
        ):
            continue

        if _same_file(entry.source, entry.destination):
            continue

        occupying_index = exact_source_indexes.get(
            _exact_path_key(entry.destination)
        )

        if (
            occupying_index is not None
            and entries[occupying_index].status
            is MassRenamePlanStatus.RENAME
        ):
            continue

        entries[index] = replace(
            entry,
            status=MassRenamePlanStatus.CONFLICT,
            message=(
                "An unrelated filesystem entry already occupies the "
                "proposed destination."
            ),
        )

    return MassRenamePlan(
        template=template,
        entries=tuple(entries),
    )


def _source_signature_matches(
    entry: MassRenamePlanEntry,
) -> bool:
    try:
        stat = entry.source.stat()
    except OSError:
        return False

    return (
        entry.source.is_file()
        and stat.st_size == entry.source_size
        and stat.st_mtime_ns == entry.source_mtime_ns
    )


def _temporary_path(source: Path) -> Path:
    for _attempt in range(100):
        candidate = (
            source.parent
            / f".saa-rename-{uuid.uuid4().hex}{source.suffix}"
        )
        if not os.path.lexists(candidate):
            return candidate

    raise OSError(
        "Could not allocate a temporary Mass Rename filename."
    )


def _rename_path_without_overwrite(
    source: Path,
    destination: Path,
) -> tuple[file_ops.LocalPackageFileMutationStatus, str]:
    if source.parent != destination.parent:
        return (
            file_ops.LocalPackageFileMutationStatus.INVALID_NAME,
            "Mass Rename may not move files between directories.",
        )

    result = file_ops.rename_local_package_file(
        source,
        destination.name,
    )
    return result.status, result.message


def _execution_entry(
    entry: MassRenamePlanEntry,
    status: file_ops.LocalPackageFileMutationStatus,
    final_location: Path | None,
    message: str = "",
) -> MassRenameExecutionEntry:
    return MassRenameExecutionEntry(
        source=entry.source,
        destination=entry.destination,
        status=status,
        final_location=final_location,
        message=message,
    )


def _blocked_execution(
    plan: MassRenamePlan,
    message: str,
) -> MassRenameExecutionResult:
    results = tuple(
        _execution_entry(
            entry,
            (
                file_ops.LocalPackageFileMutationStatus.NO_CHANGE
                if entry.status is MassRenamePlanStatus.UNCHANGED
                else file_ops.LocalPackageFileMutationStatus.FAILED
            ),
            entry.source if os.path.lexists(entry.source) else None,
            (
                "Filename is unchanged."
                if entry.status is MassRenamePlanStatus.UNCHANGED
                else message
            ),
        )
        for entry in plan.entries
    )

    return MassRenameExecutionResult(
        status=MassRenameBatchStatus.BLOCKED,
        entries=results,
        message=message,
    )


def _preflight_execution_error(
    plan: MassRenamePlan,
) -> str:
    rename_entries = tuple(
        entry
        for entry in plan.entries
        if entry.status is MassRenamePlanStatus.RENAME
    )

    for entry in rename_entries:
        if not _source_signature_matches(entry):
            return (
                f"Source changed or disappeared after preview: "
                f"{entry.source.name}"
            )

    exact_sources = {
        _exact_path_key(entry.source): entry
        for entry in rename_entries
    }

    for entry in rename_entries:
        destination = entry.destination
        if destination is None:
            return "Mass Rename plan contains a missing destination."

        if not os.path.lexists(destination):
            continue

        if _same_file(entry.source, destination):
            continue

        occupying_entry = exact_sources.get(
            _exact_path_key(destination)
        )

        if occupying_entry is not None:
            continue

        return (
            "A destination became occupied after preview: "
            f"{destination.name}"
        )

    return ""


def _restore_staged(
    plan: MassRenamePlan,
    staged: Mapping[int, Path],
) -> tuple[dict[int, Path | None], bool]:
    final_locations: dict[int, Path | None] = {}
    stranded = False

    for index, temporary in reversed(tuple(staged.items())):
        entry = plan.entries[index]

        if not os.path.lexists(temporary):
            if os.path.lexists(entry.source):
                final_locations[index] = entry.source
            elif (
                entry.destination is not None
                and os.path.lexists(entry.destination)
            ):
                final_locations[index] = entry.destination
                stranded = True
            else:
                final_locations[index] = None
                stranded = True
            continue

        status, _message = _rename_path_without_overwrite(
            temporary,
            entry.source,
        )

        if status is file_ops.LocalPackageFileMutationStatus.RENAMED:
            final_locations[index] = entry.source
        else:
            final_locations[index] = temporary
            stranded = True

    return final_locations, stranded


def execute_local_package_mass_rename(
    plan: MassRenamePlan,
) -> MassRenameExecutionResult:
    if plan.has_blocking_issues:
        return _blocked_execution(
            plan,
            plan.error
            or "Mass Rename preview contains blocking issues.",
        )

    rename_indexes = tuple(
        index
        for index, entry in enumerate(plan.entries)
        if entry.status is MassRenamePlanStatus.RENAME
    )

    if not rename_indexes:
        return MassRenameExecutionResult(
            status=MassRenameBatchStatus.NO_CHANGES,
            entries=tuple(
                _execution_entry(
                    entry,
                    file_ops.LocalPackageFileMutationStatus.NO_CHANGE,
                    entry.source,
                    "Filename is unchanged.",
                )
                for entry in plan.entries
            ),
            message="No files require renaming.",
        )

    preflight_error = _preflight_execution_error(plan)
    if preflight_error:
        return _blocked_execution(
            plan,
            preflight_error,
        )

    staged: dict[int, Path] = {}
    results: dict[int, MassRenameExecutionEntry] = {}

    for index, entry in enumerate(plan.entries):
        if entry.status is MassRenamePlanStatus.UNCHANGED:
            results[index] = _execution_entry(
                entry,
                file_ops.LocalPackageFileMutationStatus.NO_CHANGE,
                entry.source,
                "Filename is unchanged.",
            )

    for index in rename_indexes:
        entry = plan.entries[index]

        try:
            temporary = _temporary_path(entry.source)
        except OSError as exc:
            restored, stranded = _restore_staged(
                plan,
                staged,
            )

            for staged_index, location in restored.items():
                staged_entry = plan.entries[staged_index]
                results[staged_index] = _execution_entry(
                    staged_entry,
                    file_ops.LocalPackageFileMutationStatus.FAILED,
                    location,
                    "Batch staging was aborted and rollback was "
                    "attempted.",
                )

            results[index] = _execution_entry(
                entry,
                file_ops.LocalPackageFileMutationStatus.FAILED,
                entry.source
                if os.path.lexists(entry.source)
                else None,
                str(exc),
            )

            for pending_index in rename_indexes:
                if pending_index in results:
                    continue
                pending_entry = plan.entries[pending_index]
                results[pending_index] = _execution_entry(
                    pending_entry,
                    file_ops.LocalPackageFileMutationStatus.FAILED,
                    pending_entry.source,
                    "Not attempted because batch staging failed.",
                )

            return MassRenameExecutionResult(
                status=(
                    MassRenameBatchStatus.PARTIAL
                    if stranded
                    else MassRenameBatchStatus.FAILED
                ),
                entries=tuple(
                    results[index]
                    for index in range(len(plan.entries))
                ),
                message="Mass Rename staging failed.",
            )

        status, message = _rename_path_without_overwrite(
            entry.source,
            temporary,
        )

        if status is not file_ops.LocalPackageFileMutationStatus.RENAMED:
            restored, stranded = _restore_staged(
                plan,
                staged,
            )

            for staged_index, location in restored.items():
                staged_entry = plan.entries[staged_index]
                results[staged_index] = _execution_entry(
                    staged_entry,
                    file_ops.LocalPackageFileMutationStatus.FAILED,
                    location,
                    "Batch staging was aborted and rollback was "
                    "attempted.",
                )

            results[index] = _execution_entry(
                entry,
                file_ops.LocalPackageFileMutationStatus.FAILED,
                entry.source
                if os.path.lexists(entry.source)
                else temporary
                if os.path.lexists(temporary)
                else None,
                message or "Could not stage source file.",
            )

            for pending_index in rename_indexes:
                if pending_index in results:
                    continue
                pending_entry = plan.entries[pending_index]
                results[pending_index] = _execution_entry(
                    pending_entry,
                    file_ops.LocalPackageFileMutationStatus.FAILED,
                    pending_entry.source,
                    "Not attempted because batch staging failed.",
                )

            return MassRenameExecutionResult(
                status=(
                    MassRenameBatchStatus.PARTIAL
                    if stranded
                    else MassRenameBatchStatus.FAILED
                ),
                entries=tuple(
                    results[index]
                    for index in range(len(plan.entries))
                ),
                message="Mass Rename staging failed.",
            )

        staged[index] = temporary

    finalized: set[int] = set()

    for position, index in enumerate(rename_indexes):
        entry = plan.entries[index]
        temporary = staged[index]
        destination = entry.destination

        if destination is None:
            status = file_ops.LocalPackageFileMutationStatus.FAILED
            message = "Mass Rename plan contains a missing destination."
        else:
            status, message = _rename_path_without_overwrite(
                temporary,
                destination,
            )

        if status is file_ops.LocalPackageFileMutationStatus.RENAMED:
            finalized.add(index)
            results[index] = _execution_entry(
                entry,
                status,
                destination,
            )
            continue

        affected_indexes = rename_indexes[position:]
        stranded = False

        for rollback_index in affected_indexes:
            rollback_entry = plan.entries[rollback_index]
            rollback_temp = staged[rollback_index]

            if not os.path.lexists(rollback_temp):
                if os.path.lexists(rollback_entry.source):
                    final_location = rollback_entry.source
                elif (
                    rollback_entry.destination is not None
                    and os.path.lexists(
                        rollback_entry.destination
                    )
                ):
                    final_location = rollback_entry.destination
                    stranded = True
                else:
                    final_location = None
                    stranded = True

                results[rollback_index] = _execution_entry(
                    rollback_entry,
                    file_ops.LocalPackageFileMutationStatus.FAILED,
                    final_location,
                    (
                        message
                        if rollback_index == index
                        else "Not completed because a later batch "
                        "rename failed."
                    ),
                )
                continue

            restore_status, restore_message = (
                _rename_path_without_overwrite(
                    rollback_temp,
                    rollback_entry.source,
                )
            )

            if (
                restore_status
                is file_ops.LocalPackageFileMutationStatus.RENAMED
            ):
                final_location = rollback_entry.source
            else:
                final_location = rollback_temp
                stranded = True

            failure_message = (
                message
                if rollback_index == index
                else "Not completed because another batch rename failed."
            )

            if restore_message:
                failure_message = (
                    f"{failure_message} Rollback: {restore_message}"
                )

            results[rollback_index] = _execution_entry(
                rollback_entry,
                file_ops.LocalPackageFileMutationStatus.FAILED,
                final_location,
                failure_message,
            )

        return MassRenameExecutionResult(
            status=(
                MassRenameBatchStatus.PARTIAL
                if finalized or stranded
                else MassRenameBatchStatus.FAILED
            ),
            entries=tuple(
                results[result_index]
                for result_index in range(len(plan.entries))
            ),
            message=(
                "Mass Rename stopped after an unexpected filesystem "
                "failure. Per-file results report the final locations."
            ),
        )

    return MassRenameExecutionResult(
        status=MassRenameBatchStatus.COMPLETED,
        entries=tuple(
            results[index]
            for index in range(len(plan.entries))
        ),
        message=(
            f"Renamed {len(rename_indexes)} local package file(s)."
        ),
    )
