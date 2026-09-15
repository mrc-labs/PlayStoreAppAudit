from __future__ import annotations

from pathlib import Path

import errno

import pytest

import playstore_app_audit.services.local_apk_file_ops as file_ops
from playstore_app_audit.services.local_apk_file_ops import (
    LocalPackageFileMutationStatus,
    remove_local_package_file,
    rename_local_package_file,
)


@pytest.mark.parametrize("suffix", [".apk", ".apks", ".apkm", ".xapk"])
def test_rename_supports_all_local_package_formats(
    tmp_path: Path,
    suffix: str,
) -> None:
    source = tmp_path / f"old{suffix}"
    source.write_bytes(b"package")

    result = rename_local_package_file(source, f"new{suffix}")

    assert result.status is LocalPackageFileMutationStatus.RENAMED
    assert result.ok
    assert result.destination == tmp_path / f"new{suffix}"
    assert not source.exists()
    assert result.destination.read_bytes() == b"package"


def test_rename_never_overwrites_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.apk"
    destination = tmp_path / "existing.apk"
    source.write_bytes(b"source")
    destination.write_bytes(b"existing")

    result = rename_local_package_file(source, destination.name)

    assert result.status is LocalPackageFileMutationStatus.COLLISION
    assert not result.ok
    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"existing"


@pytest.mark.parametrize(
    "new_name",
    [
        "",
        " ",
        ".",
        "..",
        "../other.apk",
        "folder/other.apk",
        r"folder\other.apk",
        "changed.apks",
        "changed.txt",
        "bad\nname.apk",
    ],
)
def test_rename_rejects_unsafe_or_changed_names(
    tmp_path: Path,
    new_name: str,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"source")

    result = rename_local_package_file(source, new_name)

    assert result.status is LocalPackageFileMutationStatus.INVALID_NAME
    assert not result.ok
    assert source.exists()


def test_rename_same_filename_is_safe_no_change(tmp_path: Path) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"source")

    result = rename_local_package_file(source, source.name)

    assert result.status is LocalPackageFileMutationStatus.NO_CHANGE
    assert result.ok
    assert source.read_bytes() == b"source"


def test_rename_missing_source_is_typed_failure(tmp_path: Path) -> None:
    source = tmp_path / "missing.apk"

    result = rename_local_package_file(source, "renamed.apk")

    assert result.status is LocalPackageFileMutationStatus.INVALID_SOURCE
    assert not result.ok


def test_rename_rejects_unsupported_source(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("not package", encoding="utf-8")

    result = rename_local_package_file(source, "renamed.txt")

    assert result.status is LocalPackageFileMutationStatus.INVALID_SOURCE
    assert not result.ok
    assert source.exists()


def test_remove_deletes_exact_selected_physical_file(tmp_path: Path) -> None:
    first = tmp_path / "first.apk"
    duplicate = tmp_path / "duplicate.apk"
    first.write_bytes(b"same bytes")
    duplicate.write_bytes(b"same bytes")

    result = remove_local_package_file(first)

    assert result.status is LocalPackageFileMutationStatus.REMOVED
    assert result.ok
    assert not first.exists()
    assert duplicate.read_bytes() == b"same bytes"


def test_remove_missing_source_is_typed_failure(tmp_path: Path) -> None:
    source = tmp_path / "missing.apk"

    result = remove_local_package_file(source)

    assert result.status is LocalPackageFileMutationStatus.INVALID_SOURCE
    assert not result.ok


def test_rename_race_never_overwrites_new_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.apk"
    destination = tmp_path / "raced.apk"
    source.write_bytes(b"source")

    real_link = file_ops.os.link

    def racing_link(src, dst, *args, **kwargs):
        destination.write_bytes(b"other process")
        return real_link(src, dst, *args, **kwargs)

    monkeypatch.setattr(file_ops.os, "link", racing_link)

    result = rename_local_package_file(source, destination.name)

    assert result.status is LocalPackageFileMutationStatus.COLLISION
    assert not result.ok
    assert source.read_bytes() == b"source"
    assert destination.read_bytes() == b"other process"


def test_rename_falls_back_safely_when_hard_links_are_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.apk"
    destination = tmp_path / "renamed.apk"
    source.write_bytes(b"package")

    unsupported = getattr(errno, "EOPNOTSUPP", errno.EPERM)

    def no_hard_links(*_args, **_kwargs):
        raise OSError(unsupported, "hard links unavailable")

    monkeypatch.setattr(file_ops.os, "link", no_hard_links)

    result = rename_local_package_file(source, destination.name)

    assert result.status is LocalPackageFileMutationStatus.RENAMED
    assert result.ok
    assert not source.exists()
    assert destination.read_bytes() == b"package"
