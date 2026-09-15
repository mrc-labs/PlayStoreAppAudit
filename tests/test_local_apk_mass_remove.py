from __future__ import annotations

from pathlib import Path

import pytest

import playstore_app_audit.services.local_apk_file_ops as file_ops
import playstore_app_audit.services.local_apk_mass_remove as mass_remove
from playstore_app_audit.services.local_apk_mass_remove import (
    MassRemoveBatchStatus,
    MassRemovePlanStatus,
    MassRemoveTarget,
    execute_local_package_mass_remove,
    plan_local_package_mass_remove,
)


def _row(
    path: Path,
    relationship: str,
    *,
    package: str = "com.example.app",
    app_name: str = "Example App",
    sha: str = "a" * 64,
) -> dict[str, object]:
    resolved = path.resolve(strict=False)

    return {
        "source_mode": "local_apk",
        "local_apk_location": str(resolved),
        "local_apk_file_name": resolved.name,
        "local_apk_version_comparison": relationship,
        "package_name": package,
        "app_name": app_name,
        "local_apk_label": app_name,
        "local_apk_sha256": sha,
    }


def test_outdated_plan_selects_only_exact_outdated(
    tmp_path: Path,
) -> None:
    outdated = tmp_path / "outdated.apk"
    unknown = tmp_path / "unknown.apk"
    current = tmp_path / "current.apk"

    for path in (outdated, unknown, current):
        path.write_bytes(path.name.encode())

    rows = [
        _row(outdated, "Outdated"),
        _row(unknown, "Unknown"),
        _row(current, "Match"),
    ]

    plan = plan_local_package_mass_remove(
        rows,
        (outdated, unknown, current),
        MassRemoveTarget.OUTDATED,
    )

    assert plan.error == ""
    assert plan.runnable_count == 1
    assert plan.blocked_count == 0
    assert plan.entries[0].source == outdated.resolve()
    assert outdated.exists()
    assert unknown.exists()
    assert current.exists()


def test_unknown_plan_selects_only_exact_unknown(
    tmp_path: Path,
) -> None:
    relationships = (
        "Unknown",
        "N/A",
        "",
        "Device Specific",
        "Device-specific",
        "Not Found",
        "Different",
        "Newer",
        "Match",
        "Outdated",
    )

    paths: list[Path] = []
    rows: list[dict[str, object]] = []

    for index, relationship in enumerate(relationships):
        path = tmp_path / f"file-{index}.apk"
        path.write_bytes(b"package")
        paths.append(path)
        rows.append(_row(path, relationship))

    plan = plan_local_package_mass_remove(
        rows,
        tuple(paths),
        MassRemoveTarget.UNKNOWN,
    )

    assert plan.runnable_count == 1
    assert plan.blocked_count == 0
    assert len(plan.entries) == 1
    assert plan.entries[0].relationship == "Unknown"
    assert plan.entries[0].source == paths[0].resolve()


def test_plan_is_read_only(
    tmp_path: Path,
) -> None:
    source = tmp_path / "outdated.apk"
    source.write_bytes(b"unchanged")

    plan = plan_local_package_mass_remove(
        [_row(source, "Outdated")],
        (source,),
        MassRemoveTarget.OUTDATED,
    )

    assert plan.runnable_count == 1
    assert source.read_bytes() == b"unchanged"


def test_duplicate_package_and_sha_remain_path_independent(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"same")
    second.write_bytes(b"same")

    rows = [
        _row(
            first,
            "Outdated",
            package="com.example.same",
            sha="f" * 64,
        ),
        _row(
            second,
            "Outdated",
            package="com.example.same",
            sha="f" * 64,
        ),
    ]

    plan = plan_local_package_mass_remove(
        rows,
        (first, second),
        MassRemoveTarget.OUTDATED,
    )

    assert plan.runnable_count == 2
    assert {
        entry.source for entry in plan.entries
    } == {
        first.resolve(),
        second.resolve(),
    }


def test_exact_duplicate_physical_path_is_deduplicated(
    tmp_path: Path,
) -> None:
    source = tmp_path / "same.apk"
    source.write_bytes(b"same")

    rows = [
        _row(source, "Outdated"),
        _row(
            source,
            "Outdated",
            package="com.example.duplicate-row",
        ),
    ]

    plan = plan_local_package_mass_remove(
        rows,
        (source,),
        MassRemoveTarget.OUTDATED,
    )

    assert len(plan.entries) == 1
    assert plan.runnable_count == 1


def test_non_candidate_matching_row_is_blocked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "outdated.apk"
    other = tmp_path / "loaded.apk"
    source.write_bytes(b"outdated")
    other.write_bytes(b"loaded")

    plan = plan_local_package_mass_remove(
        [_row(source, "Outdated")],
        (other,),
        MassRemoveTarget.OUTDATED,
    )

    assert plan.runnable_count == 0
    assert plan.blocked_count == 1
    assert (
        plan.entries[0].status
        is MassRemovePlanStatus.BLOCKED
    )
    assert "active Local APK source" in plan.entries[0].message
    assert source.exists()


def test_disappeared_source_is_blocked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "missing.apk"

    plan = plan_local_package_mass_remove(
        [_row(source, "Unknown")],
        (source,),
        MassRemoveTarget.UNKNOWN,
    )

    assert plan.runnable_count == 0
    assert plan.blocked_count == 1
    assert "no longer exists" in plan.entries[0].message


def test_unsupported_suffix_is_blocked(
    tmp_path: Path,
) -> None:
    source = tmp_path / "package.zip"
    source.write_bytes(b"not-supported")

    plan = plan_local_package_mass_remove(
        [_row(source, "Unknown")],
        (source,),
        MassRemoveTarget.UNKNOWN,
    )

    assert plan.runnable_count == 0
    assert plan.blocked_count == 1
    assert "not a supported" in plan.entries[0].message


def test_entire_source_guard_only_when_every_candidate_is_runnable(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    all_plan = plan_local_package_mass_remove(
        [
            _row(first, "Outdated"),
            _row(second, "Outdated"),
        ],
        (first, second),
        MassRemoveTarget.OUTDATED,
    )

    partial_plan = plan_local_package_mass_remove(
        [
            _row(first, "Outdated"),
            _row(second, "Match"),
        ],
        (first, second),
        MassRemoveTarget.OUTDATED,
    )

    assert all_plan.removes_entire_source
    assert not partial_plan.removes_entire_source


def test_execution_blocks_if_source_changes_after_preview(
    tmp_path: Path,
) -> None:
    source = tmp_path / "outdated.apk"
    source.write_bytes(b"before")

    plan = plan_local_package_mass_remove(
        [_row(source, "Outdated")],
        (source,),
        MassRemoveTarget.OUTDATED,
    )

    source.write_bytes(b"changed-after-preview")

    result = execute_local_package_mass_remove(plan)

    assert result.status is MassRemoveBatchStatus.FAILED
    assert result.removed_count == 0
    assert source.read_bytes() == b"changed-after-preview"
    assert "changed after the preview" in result.entries[0].message


def test_execution_continues_after_one_remove_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    plan = plan_local_package_mass_remove(
        [
            _row(first, "Outdated"),
            _row(second, "Outdated"),
        ],
        (first, second),
        MassRemoveTarget.OUTDATED,
    )

    real_remove = file_ops.remove_local_package_file

    def injected_remove(path: str | Path):
        if Path(path).name == "first.apk":
            return file_ops.LocalPackageFileMutationResult(
                status=(
                    file_ops.LocalPackageFileMutationStatus.FAILED
                ),
                source=Path(path),
                message="Injected remove failure",
            )
        return real_remove(path)

    monkeypatch.setattr(
        mass_remove.file_ops,
        "remove_local_package_file",
        injected_remove,
    )

    result = execute_local_package_mass_remove(plan)

    assert result.status is MassRemoveBatchStatus.PARTIAL
    assert result.removed_count == 1

    assert first.read_bytes() == b"first"
    assert not second.exists()

    by_name = {
        entry.source.name: entry
        for entry in result.entries
    }

    assert (
        by_name["first.apk"].status
        is file_ops.LocalPackageFileMutationStatus.FAILED
    )
    assert (
        by_name["first.apk"].final_location
        == first.resolve()
    )
    assert "Injected remove failure" in by_name["first.apk"].message

    assert (
        by_name["second.apk"].status
        is file_ops.LocalPackageFileMutationStatus.REMOVED
    )
    assert by_name["second.apk"].final_location is None


def test_successful_execution_removes_only_targeted_files(
    tmp_path: Path,
) -> None:
    outdated = tmp_path / "outdated.apk"
    match = tmp_path / "match.apk"
    outdated.write_bytes(b"outdated")
    match.write_bytes(b"match")

    plan = plan_local_package_mass_remove(
        [
            _row(outdated, "Outdated"),
            _row(match, "Match"),
        ],
        (outdated, match),
        MassRemoveTarget.OUTDATED,
    )

    result = execute_local_package_mass_remove(plan)

    assert result.status is MassRemoveBatchStatus.COMPLETED
    assert result.ok
    assert result.removed_count == 1
    assert not outdated.exists()
    assert match.read_bytes() == b"match"


def test_no_matching_rows_is_no_changes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "match.apk"
    source.write_bytes(b"match")

    plan = plan_local_package_mass_remove(
        [_row(source, "Match")],
        (source,),
        MassRemoveTarget.UNKNOWN,
    )

    assert plan.runnable_count == 0
    assert plan.entries == ()
    assert plan.error

    result = execute_local_package_mass_remove(plan)

    assert result.status is MassRemoveBatchStatus.NO_CHANGES
    assert result.ok
    assert source.exists()
