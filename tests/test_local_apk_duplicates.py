from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from playstore_app_audit.services import local_apk_duplicates as duplicates
from playstore_app_audit.services import local_apk_file_ops as file_ops


def row(
    path: Path,
    *,
    sha: str | None = None,
    package: str = "com.example.app",
    code: int | str | None = 1,
    name: str | None = "1.0",
) -> dict[str, object]:
    return {
        "source_mode": "local_apk",
        "local_apk_location": str(path),
        "local_apk_sha256": sha if sha is not None else hashlib.sha256(path.read_bytes()).hexdigest(),
        "package_name": package,
        "app_name": "Example",
        "local_apk_version_code": code,
        "local_apk_version_name": name,
    }


def review(paths: list[Path]) -> duplicates.DuplicateReview:
    return duplicates.snapshot_duplicate_review(
        duplicates.analyze_local_apk_duplicates(
            [row(path) for path in paths],
            paths,
        )
    )


@pytest.fixture
def copies(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / f"copy-{index}.apk" for index in range(3)]
    for path in paths:
        path.write_bytes(b"identical package bytes")
    return paths


def test_distinct_paths_same_sha_group_even_different_packages(copies: list[Path]) -> None:
    rows = [row(path, package=f"com.example.app{index}") for index, path in enumerate(copies)]
    result = duplicates.analyze_local_apk_duplicates(rows, copies)
    assert len(result.exact_groups) == 1
    assert tuple(file.source for file in result.exact_groups[0].files) == tuple(copies)
    assert len(rows) == 3
    assert not result.version_findings


def test_repeated_normalized_path_is_not_duplicate(copies: list[Path]) -> None:
    path = copies[0]
    alias = path.parent / "sub" / ".." / path.name
    result = duplicates.analyze_local_apk_duplicates(
        [row(path), row(alias, sha=row(path)["local_apk_sha256"])], copies
    )
    assert not result.has_findings


@pytest.mark.parametrize("sha", ["", "g" * 64, "a" * 63, "a" * 65, " " + "a" * 64, None])
def test_invalid_or_missing_sha_no_group(copies: list[Path], sha: str | None) -> None:
    rows = [row(path) for path in copies]
    for item in rows:
        item["local_apk_sha256"] = sha
    assert not duplicates.analyze_local_apk_duplicates(rows, copies).has_findings


def test_sha_hex_case_normalized(copies: list[Path]) -> None:
    rows = [row(path) for path in copies]
    rows[0]["local_apk_sha256"] = str(rows[0]["local_apk_sha256"]).upper()
    assert len(duplicates.analyze_local_apk_duplicates(rows, copies).exact_groups) == 1


def test_variant_is_information_only(copies: list[Path]) -> None:
    copies[1].write_bytes(b"other build")
    result = duplicates.analyze_local_apk_duplicates([row(path) for path in copies[:2]], copies[:2])
    assert not result.exact_groups
    assert [finding.kind for finding in result.version_findings] == [
        duplicates.VersionFindingKind.SAME_VERSION_VARIANT
    ]
    assert not duplicates.plan_duplicate_cleanup(result, [copies[1]]).executable


def test_multiple_versions_never_use_store_metadata(copies: list[Path]) -> None:
    rows = [row(copies[0]), row(copies[1], code=2, name="2.0")]
    for item in rows:
        item["play_version"] = "1.0"
        item["local_apk_sha256"] = ""
    result = duplicates.analyze_local_apk_duplicates(rows, copies)
    assert not result.exact_groups
    assert [finding.kind for finding in result.version_findings] == [
        duplicates.VersionFindingKind.MULTIPLE_VERSIONS
    ]
    assert not duplicates.plan_duplicate_cleanup(result, copies[:1]).executable


@pytest.mark.parametrize("code,name", [(None, None), (None, ""), (True, None), ([], None)])
def test_missing_or_invalid_version_not_guessed(copies: list[Path], code: object, name: str | None) -> None:
    rows = [row(path, sha=str(index) * 64, code=code, name=name) for index, path in enumerate(copies)]
    assert not duplicates.analyze_local_apk_duplicates(rows, copies).has_findings


def test_version_tuple_preserves_exact_fields(copies: list[Path]) -> None:
    rows = [row(copies[0], code=1), row(copies[1], code="1")]
    rows[0]["local_apk_long_version_code"] = 1
    result = duplicates.analyze_local_apk_duplicates(rows, copies)
    assert result.version_findings[0].kind is duplicates.VersionFindingKind.MULTIPLE_VERSIONS


def test_inactive_nonlocal_and_conflicting_rows_excluded(copies: list[Path]) -> None:
    rows = [row(path) for path in copies]
    rows[1]["source_mode"] = "app_list"
    assert not duplicates.analyze_local_apk_duplicates(rows, copies[:2]).has_findings
    conflicting = row(copies[0], sha="f" * 64)
    assert not duplicates.analyze_local_apk_duplicates([rows[0], conflicting, rows[2]], copies).has_findings


def test_discovery_does_not_hash(copies: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [row(path) for path in copies]
    monkeypatch.setattr(hashlib, "file_digest", lambda *_args: pytest.fail("Discovery must not hash"))
    assert duplicates.analyze_local_apk_duplicates(rows, copies).has_findings


def test_selection_none_all_and_n_minus_one(copies: list[Path]) -> None:
    preview = review(copies)
    assert not duplicates.plan_duplicate_cleanup(preview, []).executable
    invalid = duplicates.plan_duplicate_cleanup(preview, copies)
    assert invalid.error and not invalid.executable
    assert duplicates.execute_duplicate_cleanup(invalid).count(duplicates.DuplicateCleanupStatus.BLOCKED) == 3
    valid = duplicates.plan_duplicate_cleanup(preview, copies[:-1])
    assert valid.executable and valid.selected_count == 2
    assert [file.source for file in valid.groups[0].keepers] == copies[-1:]
    assert all(path.exists() for path in copies)


def test_only_selected_removed_unrelated_untouched(copies: list[Path], tmp_path: Path) -> None:
    unrelated = tmp_path / "unrelated.apk"
    unrelated.write_bytes(b"different")
    plan = duplicates.plan_duplicate_cleanup(review([*copies, unrelated]), copies[:-1])
    result = duplicates.execute_duplicate_cleanup(plan)
    assert result.count(duplicates.DuplicateCleanupStatus.REMOVED) == 2
    assert not any(path.exists() for path in copies[:-1])
    assert copies[-1].read_bytes() == b"identical package bytes"
    assert unrelated.read_bytes() == b"different"


@pytest.mark.parametrize("role", ["selected", "keeper"])
@pytest.mark.parametrize("change", ["missing", "content", "directory", "same_size_restored_mtime", "replace"])
def test_stale_member_blocks_whole_group_before_deletion(copies: list[Path], role: str, change: str) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:-1])
    path = copies[0] if role == "selected" else copies[-1]
    old_stat = path.stat()
    if change == "missing":
        path.unlink()
    elif change == "directory":
        path.unlink()
        path.mkdir()
    elif change == "replace":
        path.unlink()
        path.write_bytes(b"identical package bytes")
    else:
        path.write_bytes(b"changed package bytes!!")
        if change == "same_size_restored_mtime":
            assert path.stat().st_size == old_stat.st_size
            os.utime(path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    result = duplicates.execute_duplicate_cleanup(plan)
    assert result.count(duplicates.DuplicateCleanupStatus.BLOCKED) == 2
    assert result.count(duplicates.DuplicateCleanupStatus.REMOVED) == 0
    assert copies[1].exists()


@pytest.mark.parametrize("role", ["selected", "keeper"])
def test_hash_mismatch_even_matching_metadata(
    copies: list[Path], role: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:-1])
    path = copies[0] if role == "selected" else copies[-1]
    path.write_bytes(b"changed package bytes!!")
    # Force the metadata guard to match to prove bytes are independently hashed.
    signature = plan.groups[0].selected[0].signature
    monkeypatch.setattr(duplicates, "_signature", lambda _stat: signature)
    group = plan.groups[0]
    plan = replace(
        plan,
        groups=(
            replace(
                group,
                selected=tuple(replace(file, signature=signature) for file in group.selected),
                keepers=tuple(replace(file, signature=signature) for file in group.keepers),
            ),
        ),
    )
    result = duplicates.execute_duplicate_cleanup(plan)
    assert all(entry.status is duplicates.DuplicateCleanupStatus.BLOCKED for entry in result.entries)
    assert "SHA-256" in result.entries[0].message
    assert copies[1].exists()


def test_independent_safe_group_completes(copies: list[Path], tmp_path: Path) -> None:
    safe = [tmp_path / f"safe-{index}.apk" for index in range(2)]
    for path in safe:
        path.write_bytes(b"independent")
    plan = duplicates.plan_duplicate_cleanup(review([*copies, *safe]), [*copies[:-1], safe[0]])
    copies[-1].unlink()
    result = duplicates.execute_duplicate_cleanup(plan)
    assert [entry.status for entry in result.entries] == [duplicates.DuplicateCleanupStatus.BLOCKED] * 2 + [
        duplicates.DuplicateCleanupStatus.REMOVED
    ]
    assert all(path.exists() for path in copies[:-1])
    assert safe[1].read_bytes() == b"independent"
    assert "1 removed, 2 blocked/stale, 0 failed" in result.message


def test_failure_stops_affected_group_but_not_independent(
    copies: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    safe = [tmp_path / f"safe-{index}.apk" for index in range(2)]
    for path in safe:
        path.write_bytes(b"independent")
    plan = duplicates.plan_duplicate_cleanup(review([*copies, *safe]), [*copies[:-1], safe[0]])
    real_remove = file_ops.remove_local_package_file
    calls: list[Path] = []

    def remove(path: Path) -> file_ops.LocalPackageFileMutationResult:
        calls.append(path)
        if path == copies[0]:
            return file_ops.LocalPackageFileMutationResult(
                file_ops.LocalPackageFileMutationStatus.FAILED, path, message="injected failure"
            )
        return real_remove(path)

    monkeypatch.setattr(file_ops, "remove_local_package_file", remove)
    result = duplicates.execute_duplicate_cleanup(plan)
    assert calls == [copies[0], safe[0]]
    assert [entry.status for entry in result.entries] == [
        duplicates.DuplicateCleanupStatus.FAILED,
        duplicates.DuplicateCleanupStatus.BLOCKED,
        duplicates.DuplicateCleanupStatus.REMOVED,
    ]
    assert all(path.exists() for path in copies)


def test_keeper_rechecked_between_mutations(copies: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:-1])
    real_remove = file_ops.remove_local_package_file

    def remove(path: Path) -> file_ops.LocalPackageFileMutationResult:
        result = real_remove(path)
        copies[-1].write_bytes(b"externally changed keeper")
        return result

    monkeypatch.setattr(file_ops, "remove_local_package_file", remove)
    result = duplicates.execute_duplicate_cleanup(plan)
    assert [entry.status for entry in result.entries] == [
        duplicates.DuplicateCleanupStatus.REMOVED,
        duplicates.DuplicateCleanupStatus.BLOCKED,
    ]
    assert copies[1].exists()


def test_preview_missing_or_unsupported_file_is_not_executable(copies: list[Path], tmp_path: Path) -> None:
    preview = duplicates.analyze_local_apk_duplicates([row(path) for path in copies], copies)
    copies[0].unlink()
    assert not duplicates.plan_duplicate_cleanup(
        duplicates.snapshot_duplicate_review(preview), copies[:1]
    ).executable
    unsupported = tmp_path / "copy.txt"
    unsupported.write_bytes(copies[1].read_bytes())
    assert not duplicates.plan_duplicate_cleanup(review([unsupported, copies[1]]), [unsupported]).executable


def test_forged_plan_cannot_remove_keeper_or_repeat_physical_path(copies: list[Path]) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:1])
    group = plan.groups[0]
    for unsafe_group in (
        replace(group, keepers=()),
        replace(group, keepers=group.selected),
        replace(group, sha256="invalid"),
    ):
        result = duplicates.execute_duplicate_cleanup(replace(plan, groups=(unsafe_group,)))
        assert result.error
    assert all(path.exists() for path in copies)


def test_retargeted_path_blocks_group(copies: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:-1])
    real_resolve = file_ops._resolve_source

    def resolve(value: str | Path) -> tuple[Path, str | None]:
        if Path(value) == copies[0]:
            return copies[-1], None
        return real_resolve(value)

    monkeypatch.setattr(file_ops, "_resolve_source", resolve)
    result = duplicates.execute_duplicate_cleanup(plan)
    assert result.count(duplicates.DuplicateCleanupStatus.BLOCKED) == 2
    assert "physical path changed" in result.entries[0].message
    assert all(path.exists() for path in copies)


def test_selection_never_resolves_to_a_different_reviewed_copy(
    copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    preview = review(copies)
    real_key = duplicates._path_key

    def key(value: object) -> str:
        return real_key(copies[-1] if Path(str(value)) == copies[0] else value)

    monkeypatch.setattr(duplicates, "_path_key", key)
    plan = duplicates.plan_duplicate_cleanup(preview, copies[:1])
    assert [file.source for file in plan.groups[0].selected] == copies[:1]
    assert [file.source for file in plan.groups[0].keepers] == copies[1:]
    assert duplicates.execute_duplicate_cleanup(plan).count(duplicates.DuplicateCleanupStatus.BLOCKED) == 1
    assert all(path.exists() for path in copies)


def test_file_change_during_hashing_blocks_group(copies: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:-1])
    real_digest = hashlib.file_digest

    def digest(handle: object, algorithm: str) -> object:
        result = real_digest(handle, algorithm)
        if Path(handle.name) == copies[-1]:
            copies[-1].write_bytes(b"changed during verification")
        return result

    monkeypatch.setattr(hashlib, "file_digest", digest)
    result = duplicates.execute_duplicate_cleanup(plan)
    assert result.count(duplicates.DuplicateCleanupStatus.BLOCKED) == 2
    assert all(path.exists() for path in copies)


def test_keeper_change_while_target_is_rehashed_blocks_mutation(
    copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = duplicates.plan_duplicate_cleanup(review(copies), copies[:1])
    real_digest = hashlib.file_digest
    target_hash_count = 0

    def digest(handle: object, algorithm: str) -> object:
        nonlocal target_hash_count
        result = real_digest(handle, algorithm)
        if Path(handle.name) == copies[0]:
            target_hash_count += 1
            if target_hash_count == 2:
                copies[-1].write_bytes(b"keeper changed during final target hash")
        return result

    monkeypatch.setattr(hashlib, "file_digest", digest)
    result = duplicates.execute_duplicate_cleanup(plan)
    assert result.count(duplicates.DuplicateCleanupStatus.BLOCKED) == 1
    assert "group revalidation" in result.entries[0].message
    assert all(path.exists() for path in copies)
