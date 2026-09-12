from __future__ import annotations

import hashlib
import json
import threading
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseFailure,
    LocalArtifactParseResult,
)
from playstore_app_audit.services import local_package_container


def _artifact(path: Path) -> LocalArtifact:
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256="a" * 64,
        package_id="com.example.container",
        application_label="Container App",
        application_label_reference=None,
        version_name="2.0",
        version_name_reference=None,
        version_code=20,
        version_code_major=None,
        min_sdk=24,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=(),
        features=(),
        icon_reference=None,
        file_name=path.name,
        canonical_path=path,
        file_size=path.stat().st_size,
        modified_at=datetime.now(UTC),
    )


def _write_container(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


@pytest.mark.parametrize(
    ("suffix", "base_name", "expected_format"),
    [
        (".apks", "splits/base-master.apk", LocalArtifactFormat.APKS),
        (".apkm", "base.apk", LocalArtifactFormat.APKM),
        (".xapk", "com.example.container.apk", LocalArtifactFormat.XAPK),
    ],
)
def test_container_selects_base_and_retains_physical_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    base_name: str,
    expected_format: LocalArtifactFormat,
) -> None:
    entries = {base_name: b"base", "config.arm64.apk": b"split"}
    if suffix == ".xapk":
        entries["manifest.json"] = json.dumps(
            {"package_name": "com.example.container"}
        ).encode()
    container = _write_container(tmp_path / f"sample{suffix}", entries)
    extracted_paths: list[Path] = []

    def parse(
        extracted: Path, *, allow_split_dependencies: bool
    ) -> LocalArtifactParseResult:
        extracted_paths.append(extracted)
        assert allow_split_dependencies
        assert extracted.read_bytes() == b"base"
        return LocalArtifactParseResult(artifact=_artifact(extracted))

    monkeypatch.setattr(local_package_container, "parse_local_apk", parse)
    result = local_package_container.parse_local_package(container)

    assert result.failure is None
    assert result.artifact is not None
    assert result.artifact.artifact_format is expected_format
    assert result.artifact.canonical_path == container.resolve()
    assert result.artifact.file_name == container.name
    assert result.artifact.file_size == container.stat().st_size
    assert result.artifact.artifact_sha256 == hashlib.sha256(container.read_bytes()).hexdigest()
    assert extracted_paths and not extracted_paths[0].exists()


@pytest.mark.parametrize("unsafe", ["../base.apk", "/base.apk", "C:/base.apk"])
def test_container_rejects_unsafe_archive_paths(tmp_path: Path, unsafe: str) -> None:
    container = _write_container(tmp_path / "unsafe.apkm", {unsafe: b"apk"})

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE


def test_container_rejects_archive_without_apk(tmp_path: Path) -> None:
    container = _write_container(tmp_path / "empty.xapk", {"manifest.json": b"{}"})

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.NO_BASE_APK


def test_container_rejects_ambiguous_base(tmp_path: Path) -> None:
    container = _write_container(
        tmp_path / "ambiguous.apkm",
        {"first.apk": b"one", "second.apk": b"two"},
    )

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.AMBIGUOUS_BASE_APK


def test_xapk_selects_single_package_named_base_without_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _write_container(
        tmp_path / "real-world.xapk",
        {
            "config.arm64_v8a.apk": b"architecture split",
            "config.en.apk": b"language split",
            "com.example.realapp.apk": b"base",
            "config.xxhdpi.apk": b"density split",
        },
    )
    selected: list[Path] = []

    def parse(
        extracted: Path, *, allow_split_dependencies: bool
    ) -> LocalArtifactParseResult:
        selected.append(extracted)
        assert allow_split_dependencies
        assert extracted.read_bytes() == b"base"
        return LocalArtifactParseResult(artifact=_artifact(extracted))

    monkeypatch.setattr(local_package_container, "parse_local_apk", parse)

    result = local_package_container.parse_local_package(container)

    assert result.failure is None
    assert result.artifact is not None
    assert result.artifact.artifact_format is LocalArtifactFormat.XAPK
    assert selected and not selected[0].exists()


def test_xapk_multiple_package_named_candidates_remain_ambiguous(tmp_path: Path) -> None:
    container = _write_container(
        tmp_path / "multiple-packages.xapk",
        {
            "com.example.first.apk": b"first",
            "com.example.second.apk": b"second",
            "config.en.apk": b"language split",
        },
    )

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.AMBIGUOUS_BASE_APK


def test_xapk_with_only_config_and_split_entries_has_no_credible_base(
    tmp_path: Path,
) -> None:
    container = _write_container(
        tmp_path / "only-splits.xapk",
        {
            "config.arm64_v8a.apk": b"architecture split",
            "config.en.apk": b"language split",
            "split_config.xxhdpi.apk": b"density split",
        },
    )

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.NO_BASE_APK


def test_container_enforces_count_size_and_ratio_limits(tmp_path: Path) -> None:
    count = _write_container(
        tmp_path / "count.apks",
        {"base.apk": b"apk", "extra.txt": b"x"},
    )
    count_result = local_package_container.parse_local_package(
        count,
        limits=local_package_container.ContainerInspectionLimits(max_entries=1),
    )
    assert count_result.failure is not None
    assert count_result.failure.kind is LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED

    size = _write_container(tmp_path / "size.apkm", {"base.apk": b"12345"})
    size_result = local_package_container.parse_local_package(
        size,
        limits=local_package_container.ContainerInspectionLimits(
            max_entry_uncompressed_bytes=4
        ),
    )
    assert size_result.failure is not None
    assert size_result.failure.kind is LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED

    total = _write_container(
        tmp_path / "total.apkm",
        {"base.apk": b"123", "other.txt": b"456"},
    )
    total_result = local_package_container.parse_local_package(
        total,
        limits=local_package_container.ContainerInspectionLimits(
            max_total_uncompressed_bytes=5
        ),
    )
    assert total_result.failure is not None
    assert total_result.failure.kind is LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED

    ratio = _write_container(tmp_path / "ratio.xapk", {"base.apk": b"0" * 10_000})
    ratio_result = local_package_container.parse_local_package(
        ratio,
        limits=local_package_container.ContainerInspectionLimits(max_compression_ratio=2),
    )
    assert ratio_result.failure is not None
    assert ratio_result.failure.kind is LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED


def test_container_rejects_archive_symlink(tmp_path: Path) -> None:
    container = tmp_path / "symlink.apkm"
    link = zipfile.ZipInfo("link.apk")
    link.create_system = 3
    link.external_attr = 0o120777 << 16
    with zipfile.ZipFile(container, "w") as archive:
        archive.writestr(link, "base.apk")
        archive.writestr("base.apk", b"apk")

    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE


def test_container_temp_cleanup_after_parser_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _write_container(tmp_path / "failure.apkm", {"base.apk": b"apk"})
    extracted_paths: list[Path] = []

    def fail(
        extracted: Path, *, allow_split_dependencies: bool
    ) -> LocalArtifactParseResult:
        extracted_paths.append(extracted)
        assert allow_split_dependencies
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                extracted,
                LocalArtifactFailureKind.MALFORMED_MANIFEST,
                "synthetic failure",
            )
        )

    monkeypatch.setattr(local_package_container, "parse_local_apk", fail)
    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.path == container.resolve()
    assert extracted_paths and not extracted_paths[0].exists()


def test_container_temp_cleanup_after_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _write_container(tmp_path / "cancelled.apkm", {"base.apk": b"apk"})
    cancel_event = threading.Event()
    extracted_paths: list[Path] = []

    def cancel(
        extracted: Path, *, allow_split_dependencies: bool
    ) -> LocalArtifactParseResult:
        extracted_paths.append(extracted)
        assert allow_split_dependencies
        cancel_event.set()
        return LocalArtifactParseResult(artifact=_artifact(extracted))

    monkeypatch.setattr(local_package_container, "parse_local_apk", cancel)
    result = local_package_container.parse_local_package(
        container, cancel_event=cancel_event
    )

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.CANCELLED
    assert extracted_paths and not extracted_paths[0].exists()


def test_container_temp_cleanup_after_unexpected_parser_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    container = _write_container(tmp_path / "unexpected.apkm", {"base.apk": b"apk"})
    extracted_paths: list[Path] = []

    def crash(extracted: Path, *, allow_split_dependencies: bool) -> LocalArtifactParseResult:
        extracted_paths.append(extracted)
        assert allow_split_dependencies
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(local_package_container, "parse_local_apk", crash)
    result = local_package_container.parse_local_package(container)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE
    assert extracted_paths and not extracted_paths[0].exists()
