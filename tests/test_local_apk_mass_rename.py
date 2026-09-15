from __future__ import annotations

from pathlib import Path

import pytest

import playstore_app_audit.services.local_apk_mass_rename as mass_rename
from playstore_app_audit.services.local_apk_file_ops import (
    LocalPackageFileMutationStatus,
)
from playstore_app_audit.services.local_apk_mass_rename import (
    MassRenameBatchStatus,
    MassRenamePlanStatus,
    execute_local_package_mass_rename,
    plan_local_package_mass_rename,
)


def _row(
    path: Path,
    *,
    package: str = "com.example.app",
    app_name: str = "Example App",
    play_name: str = "Example Store App",
    local_version: str = "1.2.3",
    category: str | None = "Tools",
    sha: str = "a" * 64,
) -> dict[str, object]:
    row: dict[str, object] = {
        "source_mode": "local_apk",
        "local_apk_location": str(path),
        "local_apk_file_name": path.name,
        "local_apk_label": app_name,
        "app_name": app_name,
        "package_name": package,
        "play_title": play_name,
        "local_apk_version_name": local_version,
        "local_apk_sha256": sha,
    }

    if category is not None:
        row["play_category"] = category

    return row


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ("{packagename}", "com.example.app.apk"),
        ("{appname}", "Example App.apk"),
        ("{playname}", "Example Store App.apk"),
        ("{category}", "Tools.apk"),
        ("{localversion}", "1.2.3.apk"),
        (
            "{packagename} - {localversion}",
            "com.example.app - 1.2.3.apk",
        ),
    ],
)
def test_required_templates_render(
    tmp_path: Path,
    template: str,
    expected: str,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        template,
    )

    assert not plan.has_blocking_issues
    assert len(plan.entries) == 1
    assert plan.entries[0].status is MassRenamePlanStatus.RENAME
    assert plan.entries[0].rendered_filename == expected
    assert plan.entries[0].destination == tmp_path / expected
    assert source.exists()


def test_token_values_are_sanitized_for_portable_filenames(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source, app_name='Atlas: Notes/Pro*')],
        "{appname}",
    )

    assert not plan.has_blocking_issues
    assert (
        plan.entries[0].rendered_filename
        == "Atlas_ Notes_Pro_.apk"
    )


@pytest.mark.parametrize(
    "template",
    [
        "{unknown}",
        "{packagename",
        "{packagename!r}",
        "{packagename:>20}",
        "../{packagename}",
        r"..\{packagename}",
    ],
)
def test_invalid_template_is_blocking(
    tmp_path: Path,
    template: str,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        template,
    )

    assert plan.has_blocking_issues
    assert plan.error
    assert source.exists()


def test_missing_metadata_is_explicitly_invalid(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source, category=None)],
        "{category}",
    )

    assert plan.has_blocking_issues
    assert plan.entries[0].status is MassRenamePlanStatus.INVALID
    assert "{category}" in plan.entries[0].message


@pytest.mark.parametrize(
    "suffix",
    [".apk", ".apks", ".apkm", ".xapk"],
)
def test_original_package_suffix_is_preserved(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = tmp_path / f"source{suffix}"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        "{packagename}",
    )

    assert not plan.has_blocking_issues
    assert (
        plan.entries[0].rendered_filename
        == f"com.example.app{suffix}"
    )


def test_explicit_changed_package_suffix_is_rejected(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.xapk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        "renamed.apk",
    )

    assert plan.has_blocking_issues
    assert plan.entries[0].status is MassRenamePlanStatus.INVALID


@pytest.mark.parametrize(
    "template",
    [
        "CON",
        "bad:name",
        "bad?name",
        "bad*name",
    ],
)
def test_nonportable_literal_filename_is_rejected(
    tmp_path: Path,
    template: str,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        template,
    )

    assert plan.has_blocking_issues


def test_existing_unrelated_destination_is_conflict(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    destination = tmp_path / "Example App.apk"
    source.write_bytes(b"source")
    destination.write_bytes(b"existing")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        "{appname}",
    )

    assert plan.has_blocking_issues
    assert plan.entries[0].status is MassRenamePlanStatus.CONFLICT
    assert destination.read_bytes() == b"existing"


def test_intra_batch_destination_collision_is_blocking(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    plan = plan_local_package_mass_rename(
        [
            _row(first, app_name="Same Name"),
            _row(second, app_name="Same Name"),
        ],
        "{appname}",
    )

    assert plan.has_blocking_issues
    assert all(
        entry.status is MassRenamePlanStatus.CONFLICT
        for entry in plan.entries
    )


def test_case_normalized_destination_collision_is_blocking(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    plan = plan_local_package_mass_rename(
        [
            _row(first, app_name="Atlas"),
            _row(second, app_name="ATLAS"),
        ],
        "{appname}",
    )

    assert plan.has_blocking_issues
    assert all(
        entry.status is MassRenamePlanStatus.CONFLICT
        for entry in plan.entries
    )


def test_unchanged_entry_is_not_an_error(
    tmp_path: Path,
) -> None:
    source = tmp_path / "com.example.app.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source)],
        "{packagename}",
    )

    assert not plan.has_blocking_issues
    assert plan.rename_count == 0
    assert plan.entries[0].status is MassRenamePlanStatus.UNCHANGED

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.NO_CHANGES
    assert result.ok
    assert source.read_bytes() == b"package"


def test_duplicate_package_and_sha_are_not_collapsed_by_identity(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()

    first = first_dir / "first.apk"
    second = second_dir / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    rows = [
        _row(
            first,
            package="com.example.same",
            sha="f" * 64,
        ),
        _row(
            second,
            package="com.example.same",
            sha="f" * 64,
        ),
    ]

    plan = plan_local_package_mass_rename(
        rows,
        "{packagename}",
    )

    assert not plan.has_blocking_issues
    assert len(plan.entries) == 2
    assert plan.rename_count == 2
    assert plan.entries[0].source != plan.entries[1].source


def test_swap_cycle_executes_without_data_loss(
    tmp_path: Path,
) -> None:
    first = tmp_path / "A.apk"
    second = tmp_path / "B.apk"
    first.write_bytes(b"content-A")
    second.write_bytes(b"content-B")

    plan = plan_local_package_mass_rename(
        [
            _row(first, app_name="B"),
            _row(second, app_name="A"),
        ],
        "{appname}",
    )

    assert not plan.has_blocking_issues
    assert plan.rename_count == 2

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.COMPLETED
    assert result.ok
    assert (tmp_path / "A.apk").read_bytes() == b"content-B"
    assert (tmp_path / "B.apk").read_bytes() == b"content-A"
    assert not tuple(tmp_path.glob(".saa-rename-*"))


def test_execution_blocks_if_source_disappears_after_preview(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    plan = plan_local_package_mass_rename(
        [_row(source, app_name="Renamed")],
        "{appname}",
    )

    source.unlink()

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.BLOCKED
    assert not result.ok
    assert not (tmp_path / "Renamed.apk").exists()


def test_execution_blocks_if_destination_appears_after_preview(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    destination = tmp_path / "Renamed.apk"
    source.write_bytes(b"source")

    plan = plan_local_package_mass_rename(
        [_row(source, app_name="Renamed")],
        "{appname}",
    )

    destination.write_bytes(b"other process")

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.BLOCKED
    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"other process"


def test_execution_blocks_if_source_changes_after_preview(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"before")

    plan = plan_local_package_mass_rename(
        [_row(source, app_name="Renamed")],
        "{appname}",
    )

    source.write_bytes(b"changed-content")

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.BLOCKED
    assert source.read_bytes() == b"changed-content"
    assert not (tmp_path / "Renamed.apk").exists()


def test_unexpected_final_failure_is_reported_as_partial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "one.apk"
    second = tmp_path / "two.apk"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    plan = plan_local_package_mass_rename(
        [
            _row(first, app_name="one-new"),
            _row(second, app_name="two-new"),
        ],
        "{appname}",
    )

    real_rename = mass_rename._rename_path_without_overwrite

    def injected_failure(
        source: Path,
        destination: Path,
    ) -> tuple[LocalPackageFileMutationStatus, str]:
        if destination.name == "two-new.apk":
            return (
                LocalPackageFileMutationStatus.FAILED,
                "injected final failure",
            )
        return real_rename(source, destination)

    monkeypatch.setattr(
        mass_rename,
        "_rename_path_without_overwrite",
        injected_failure,
    )

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.PARTIAL
    assert not result.ok

    assert (tmp_path / "one-new.apk").read_bytes() == b"one"
    assert second.read_bytes() == b"two"
    assert not (tmp_path / "two-new.apk").exists()

    assert result.entries[0].status is LocalPackageFileMutationStatus.RENAMED
    assert result.entries[0].final_location == tmp_path / "one-new.apk"

    assert result.entries[1].status is LocalPackageFileMutationStatus.FAILED
    assert result.entries[1].final_location == second
    assert "injected final failure" in result.entries[1].message


def test_blocking_plan_never_mutates_any_file(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    plan = plan_local_package_mass_rename(
        [
            _row(first, app_name="Same"),
            _row(second, app_name="Same"),
        ],
        "{appname}",
    )

    result = execute_local_package_mass_rename(plan)

    assert result.status is MassRenameBatchStatus.BLOCKED
    assert first.read_bytes() == b"first"
    assert second.read_bytes() == b"second"
    assert not (tmp_path / "Same.apk").exists()
