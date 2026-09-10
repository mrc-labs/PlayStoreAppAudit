from __future__ import annotations

import base64
import hashlib
import os
import subprocess
import sys
import tomllib
import warnings
import zipfile
from dataclasses import replace
from datetime import UTC
from pathlib import Path
from typing import IO
from xml.etree import ElementTree

import pytest

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseResult,
    LocalArtifactWarning,
)
from playstore_app_audit.services import local_apk

# Apache-2.0 test asset from androguard/axml commit
# 5fdb362964fb98ff33631d5181c584121fa9b1b1. Its upstream filename is
# tests/data/AXML/AndroidManifest.xml and its SHA-256 is
# 29fc36efa313e8269f55e5ab86a5e81481de26b98f9c82cc506a8d13eba080f1.
_BINARY_MANIFEST = base64.b64decode(
    """
AwAIADwFAAABABwAtAIAABUAAAAAAAAAAAAAAHAAAAAAAAAAAAAAABoAAAA0AAAAQgAAAE4AAABmAAAAcgAAAIQAAADcAAAA
4AAAAPIAAAAGAQAANgEAAEABAABaAQAAbgEAAIYBAACkAQAAtAEAAOwBAAAAAgAACwB2AGUAcgBzAGkAbwBuAEMAbwBkAGUA
AAALAHYAZQByAHMAaQBvAG4ATgBhAG0AZQAAAAUAbABhAGIAZQBsAAAABABpAGMAbwBuAAAACgBkAGUAYgB1AGcAZwBhAGIA
bABlAAAABABuAGEAbQBlAAAABwBhAG4AZAByAG8AaQBkAAAAKgBoAHQAdABwADoALwAvAHMAYwBoAGUAbQBhAHMALgBhAG4A
ZAByAG8AaQBkAC4AYwBvAG0ALwBhAHAAawAvAHIAZQBzAC8AYQBuAGQAcgBvAGkAZAAAAAAAAAAHAHAAYQBjAGsAYQBnAGUA
AAAIAG0AYQBuAGkAZgBlAHMAdAAAABYAbwByAGcALgB0ADAAdAAwAC4AYQBuAGQAcgBvAGcAdQBhAHIAZAAuAFQAQwAAAAMA
MQAuADAAAAALAGEAcABwAGwAaQBjAGEAdABpAG8AbgAAAAgAYQBjAHQAaQB2AGkAdAB5AAAACgBUAEMAQQBjAHQAaQB2AGkA
dAB5AAAADQBpAG4AdABlAG4AdAAtAGYAaQBsAHQAZQByAAAABgBhAGMAdABpAG8AbgAAABoAYQBuAGQAcgBvAGkAZAAuAGkA
bgB0AGUAbgB0AC4AYQBjAHQAaQBvAG4ALgBNAEEASQBOAAAACABjAGEAdABlAGcAbwByAHkAAAAgAGEAbgBkAHIAbwBpAGQA
LgBpAG4AdABlAG4AdAAuAGMAYQB0AGUAZwBvAHIAeQAuAEwAQQBVAE4AQwBIAEUAUgAAAIABCAAgAAAAGwIBARwCAQEBAAEB
AgABAQ8AAQEDAAEBAAEQABgAAAACAAAA/////wYAAAAHAAAAAgEQAGAAAAACAAAA//////////8KAAAAFAAUAAMAAAAAAAAA
BwAAAAAAAAD/////CAAAEAEAAAAHAAAAAQAAAAwAAAAIAAADDAAAAP////8JAAAACwAAAAgAAAMLAAAAAgEQAGAAAAAGAAAA
//////////8NAAAAFAAUAAMAAAAAAAAABwAAAAIAAAD/////CAAAAQAABH8HAAAAAwAAAP////8IAAABAAACfwcAAAAEAAAA
/////wgAABL/////AgEQAEwAAAAHAAAA//////////8OAAAAFAAUAAIAAAAAAAAABwAAAAIAAAD/////CAAAAQAABH8HAAAA
BQAAAA8AAAAIAAADDwAAAAIBEAAkAAAACQAAAP//////////EAAAABQAFAAAAAAAAAAAAAIBEAA4AAAACgAAAP//////////
EQAAABQAFAABAAAAAAAAAAcAAAAFAAAAEgAAAAgAAAMSAAAAAwEQABgAAAAKAAAA//////////8RAAAAAgEQADgAAAALAAAA
//////////8TAAAAFAAUAAEAAAAAAAAABwAAAAUAAAAUAAAACAAAAxQAAAADARAAGAAAAAsAAAD//////////xMAAAADARAA
GAAAAAwAAAD//////////xAAAAADARAAGAAAAA0AAAD//////////w4AAAADARAAGAAAAA4AAAD//////////w0AAAADARAA
GAAAAA8AAAD//////////woAAAABARAAGAAAAA8AAAD/////BgAAAAcAAAA=
"""
)

# Same upstream commit, tests/data/ARSC/TestActivity_resources.arsc,
# SHA-256 ea55896f60b40697440799b6e24d5ec281c1bc7462a8118a2a2768e881e16a9c.
_RESOURCE_TABLE = base64.b64decode(
    """
AgAMAJQEAAABAAAAAQAcAOwAAAAGAAAAAAAAAAABAAA0AAAAAAAAAAAAAAAWAAAAMwAAAFAAAABtAAAAmAAAABMTcmVzL2xh
eW91dC9tYWluLnhtbAAaGnJlcy9kcmF3YWJsZS1sZHBpL2ljb24ucG5nABoacmVzL2RyYXdhYmxlLW1kcGkvaWNvbi5wbmcA
GhpyZXMvZHJhd2FibGUtaGRwaS9pY29uLnBuZwAoKEhlbGxvIFdvcmxkLCBUZXN0QWN0aXZpdHkhIGtpa29vbG9sbW9kaWYA
GhpUZXN0c0FuZHJvZ3VhcmRBcHBsaWNhdGlvbgAAAAAAAhwBnAMAAH8AAAB0AGUAcwB0AHMALgBhAG4AZAByAG8AZwB1AGEA
cgBkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAHAEAAAQAAABsAQAABAAAAAEAHABQAAAABAAAAAAAAAAAAQAALAAAAAAAAAAAAAAABwAAABIAAAAbAAAA
BARhdHRyAAgIZHJhd2FibGUABgZsYXlvdXQABgZzdHJpbmcAAQAcAFAAAAAEAAAAAAAAAAABAAAsAAAAAAAAAAAAAAAHAAAA
DgAAABYAAAAEBGljb24ABARtYWluAAUFaGVsbG8ACAhhcHBfbmFtZQAAAAACAhAAEAAAAAEAAAAAAAAAAgIQABQAAAACAAAA
AQAAAAABAAABAjgATAAAAAIAAAABAAAAPAAAACQAAAAAAAAAAAAAAAAAeAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAIAAAA
AAAAAAgAAAMBAAAAAQI4AEwAAAACAAAAAQAAADwAAAAkAAAAAAAAAAAAAAAAAKAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAA
CAAAAAAAAAAIAAADAgAAAAECOABMAAAAAgAAAAEAAAA8AAAAJAAAAAAAAAAAAAAAAADwAAAAAAAAAAAABAAAAAAAAAAAAAAA
AAAAAAgAAAAAAAAACAAAAwMAAAACAhAAFAAAAAMAAAABAAAAAAAAAAECOABMAAAAAwAAAAEAAAA8AAAAJAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAABAAAACAAAAwAAAAACAhAAGAAAAAQAAAACAAAAAAAAAAAAAAABAjgA
YAAAAAQAAAACAAAAQAAAACQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAACAAAAAIAAAAIAAAD
BAAAAAgAAAADAAAACAAAAwUAAAA=
"""
)


def _write_apk(
    path: Path,
    *,
    extra_entry: bytes | None = None,
    resources: bytes | None = None,
    manifest: bytes = _BINARY_MANIFEST,
    compression: int = zipfile.ZIP_DEFLATED,
) -> Path:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        archive.writestr("AndroidManifest.xml", manifest)
        if resources is not None:
            archive.writestr("resources.arsc", resources)
        if extra_entry is not None:
            archive.writestr("assets/identity-marker", extra_entry)
    return path


def _artifact(result: LocalArtifactParseResult) -> LocalArtifact:
    assert result.failure is None
    assert result.artifact is not None
    return result.artifact


def test_parses_bounded_standalone_apk_metadata(tmp_path: Path) -> None:
    apk_path = _write_apk(tmp_path / "sample.APK")

    artifact = _artifact(local_apk.parse_local_apk(apk_path))

    assert artifact.artifact_format is LocalArtifactFormat.APK
    assert artifact.artifact_sha256 == hashlib.sha256(apk_path.read_bytes()).hexdigest()
    assert artifact.artifact_id == artifact.artifact_sha256
    assert artifact.package_id == "org.t0t0.androguard.TC"
    assert artifact.package_lookup_key == "org.t0t0.androguard.TC"
    assert artifact.application_label is None
    assert artifact.application_label_reference == "@7F040000"
    assert artifact.version_name == "1.0"
    assert artifact.version_name_reference is None
    assert artifact.version_code == 1
    assert artifact.long_version_code == 1
    assert artifact.version_code_major is None
    assert artifact.min_sdk is None
    assert artifact.target_sdk is None
    assert artifact.compile_sdk is None
    assert artifact.application_debuggable is True
    assert artifact.permissions == ()
    assert artifact.features == ()
    assert artifact.icon_reference == "@7F020000"
    assert artifact.file_name == "sample.APK"
    assert artifact.canonical_path == apk_path.resolve()
    assert artifact.file_size == apk_path.stat().st_size
    assert artifact.modified_at.tzinfo is UTC
    assert artifact.warnings == (
        LocalArtifactWarning.APPLICATION_LABEL_UNRESOLVED,
    )


def test_artifact_identity_is_distinct_from_package_identity(tmp_path: Path) -> None:
    first = _artifact(local_apk.parse_local_apk(_write_apk(tmp_path / "first.apk")))
    second = _artifact(
        local_apk.parse_local_apk(
            _write_apk(tmp_path / "second.apk", extra_entry=b"different exact bytes")
        )
    )

    assert first.package_lookup_key == second.package_lookup_key
    assert first.artifact_id != second.artifact_id


def test_same_size_same_mtime_rewrite_cannot_mix_hash_and_parsed_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = _write_apk(tmp_path / "changing.apk", compression=zipfile.ZIP_STORED)
    original_bytes = path.read_bytes()
    original_stat = path.stat()
    changed_manifest = _BINARY_MANIFEST.replace(
        b"1\x00.\x000\x00",
        b"2\x00.\x000\x00",
        1,
    )
    replacement = _write_apk(
        tmp_path / "replacement.apk",
        manifest=changed_manifest,
        compression=zipfile.ZIP_STORED,
    ).read_bytes()
    assert len(replacement) == len(original_bytes)

    original_preflight = local_apk._preflight_zip_structure

    def replace_source_after_snapshot(
        stream: IO[bytes],
        file_size: int,
        limits: local_apk.ApkParseLimits,
    ) -> None:
        original_preflight(stream, file_size, limits)
        path.write_bytes(replacement)
        os.utime(
            path,
            ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
        )

    monkeypatch.setattr(
        local_apk,
        "_preflight_zip_structure",
        replace_source_after_snapshot,
    )

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.IO_ERROR
    assert result.failure.artifact_sha256 == hashlib.sha256(original_bytes).hexdigest()


def test_resolves_default_string_resource_only_for_matching_package() -> None:
    resources = local_apk._ARSCParser(_RESOURCE_TABLE)

    assert (
        local_apk._resolve_resource_value(
            "@7F040001",
            resources,
            "tests.androguard",
            local_apk.DEFAULT_APK_PARSE_LIMITS,
        )
        == "TestsAndroguardApplication"
    )
    assert (
        local_apk._resolve_resource_value(
            "@7F040001",
            resources,
            "org.example.other",
            local_apk.DEFAULT_APK_PARSE_LIMITS,
        )
        is None
    )


@pytest.mark.parametrize("suffix", [".apks", ".aab", ".zip"])
def test_rejects_unsupported_artifact_formats(tmp_path: Path, suffix: str) -> None:
    path = tmp_path / f"artifact{suffix}"
    path.write_bytes(b"not inspected")

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.UNSUPPORTED_FORMAT
    assert result.failure.artifact_sha256 is None


def test_reports_missing_and_non_file_paths(tmp_path: Path) -> None:
    missing = local_apk.parse_local_apk(tmp_path / "missing.apk")
    directory = local_apk.parse_local_apk(tmp_path)

    assert missing.failure is not None
    assert missing.failure.kind is LocalArtifactFailureKind.NOT_FOUND
    assert directory.failure is not None
    assert directory.failure.kind is LocalArtifactFailureKind.NOT_A_FILE


def test_reports_truncated_and_missing_manifest_archives(tmp_path: Path) -> None:
    truncated_path = tmp_path / "truncated.apk"
    truncated_path.write_bytes(b"PK\x03\x04truncated")
    truncated = local_apk.parse_local_apk(truncated_path)

    no_manifest_path = tmp_path / "no-manifest.apk"
    with zipfile.ZipFile(no_manifest_path, "w") as archive:
        archive.writestr("classes.dex", b"dex\n035\x00")
    no_manifest = local_apk.parse_local_apk(no_manifest_path)

    assert truncated.failure is not None
    assert truncated.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE
    assert truncated.failure.artifact_sha256 == hashlib.sha256(
        truncated_path.read_bytes()
    ).hexdigest()
    assert no_manifest.failure is not None
    assert no_manifest.failure.kind is LocalArtifactFailureKind.MISSING_MANIFEST


def test_rejects_duplicate_manifest_entries(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.apk"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", _BINARY_MANIFEST)
            archive.writestr("AndroidManifest.xml", _BINARY_MANIFEST)

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE


def test_rejects_duplicate_resource_table_entries(tmp_path: Path) -> None:
    path = tmp_path / "duplicate-resources.apk"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("AndroidManifest.xml", _BINARY_MANIFEST)
            archive.writestr("resources.arsc", _RESOURCE_TABLE)
            archive.writestr("resources.arsc", _RESOURCE_TABLE)

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE


def test_rejects_encrypted_manifest_entry(tmp_path: Path) -> None:
    path = _write_apk(tmp_path / "encrypted.apk")
    payload = bytearray(path.read_bytes())
    local_header = payload.find(b"PK\x03\x04")
    central_header = payload.find(b"PK\x01\x02")
    assert local_header >= 0 and central_header >= 0
    for flag_offset in (local_header + 6, central_header + 8):
        flags = int.from_bytes(payload[flag_offset : flag_offset + 2], "little")
        payload[flag_offset : flag_offset + 2] = (flags | 1).to_bytes(2, "little")
    path.write_bytes(payload)

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_ARCHIVE


def test_rejects_malformed_binary_manifest(tmp_path: Path) -> None:
    path = tmp_path / "bad-manifest.apk"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AndroidManifest.xml", b"not Android binary XML")

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.MALFORMED_MANIFEST


def test_enforces_archive_and_selected_member_limits(tmp_path: Path) -> None:
    path = _write_apk(tmp_path / "limited.apk", extra_entry=b"x")

    file_limited = local_apk.parse_local_apk(
        path,
        limits=replace(
            local_apk.DEFAULT_APK_PARSE_LIMITS,
            max_apk_bytes=path.stat().st_size - 1,
        ),
    )
    entry_limited = local_apk.parse_local_apk(
        path,
        limits=replace(local_apk.DEFAULT_APK_PARSE_LIMITS, max_archive_entries=1),
    )
    manifest_limited = local_apk.parse_local_apk(
        path,
        limits=replace(local_apk.DEFAULT_APK_PARSE_LIMITS, max_manifest_bytes=100),
    )
    central_directory_limited = local_apk.parse_local_apk(
        path,
        limits=replace(
            local_apk.DEFAULT_APK_PARSE_LIMITS,
            max_central_directory_bytes=10,
        ),
    )
    total_uncompressed_limited = local_apk.parse_local_apk(
        path,
        limits=replace(
            local_apk.DEFAULT_APK_PARSE_LIMITS,
            max_total_uncompressed_bytes=100,
        ),
    )
    compression_ratio_limited = local_apk.parse_local_apk(
        path,
        limits=replace(
            local_apk.DEFAULT_APK_PARSE_LIMITS,
            max_selected_member_compression_ratio=1,
        ),
    )
    resources_path = _write_apk(
        tmp_path / "resource-limited.apk",
        resources=b"x" * 101,
    )
    resources_limited = local_apk.parse_local_apk(
        resources_path,
        limits=replace(local_apk.DEFAULT_APK_PARSE_LIMITS, max_resources_bytes=100),
    )

    assert file_limited.failure is not None
    assert file_limited.failure.kind is LocalArtifactFailureKind.FILE_TOO_LARGE
    assert file_limited.failure.artifact_sha256 is None
    for result in (
        entry_limited,
        manifest_limited,
        central_directory_limited,
        total_uncompressed_limited,
        compression_ratio_limited,
        resources_limited,
    ):
        assert result.failure is not None
        assert result.failure.kind is LocalArtifactFailureKind.ARCHIVE_LIMIT_EXCEEDED


def test_detected_split_apk_has_typed_unsupported_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = _write_apk(tmp_path / "split.apk")
    parsed = local_apk._ParsedManifest(
        package_id="org.example.app",
        application_label_raw=None,
        version_name_raw=None,
        version_code_raw=None,
        version_code_major_raw=None,
        min_sdk_raw=None,
        target_sdk_raw=None,
        compile_sdk_raw=None,
        debuggable_raw=None,
        icon_reference=None,
        permissions=(),
        features=(),
        requires_split_handling=True,
    )
    monkeypatch.setattr(local_apk, "_parse_manifest", lambda _data, _limits: parsed)

    result = local_apk.parse_local_apk(path)

    assert result.failure is not None
    assert result.failure.kind is LocalArtifactFailureKind.UNSUPPORTED_SPLIT
    assert result.failure.artifact_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "manifest_xml",
    [
        '<manifest package="org.example.app" split="config.en" />',
        (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="org.example.app"><uses-split android:name="feature" /></manifest>'
        ),
        (
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="org.example.app"><application><meta-data '
            'android:name="com.android.vending.splits.required" android:value="true" />'
            "</application></manifest>"
        ),
    ],
)
def test_manifest_split_markers_are_detected(
    monkeypatch: pytest.MonkeyPatch,
    manifest_xml: str,
) -> None:
    root = ElementTree.fromstring(manifest_xml)

    class FakePrinter:
        def __init__(self, _data: bytes) -> None:
            pass

        def get_xml_obj(self) -> ElementTree.Element:
            return root

        def is_valid(self) -> bool:
            return True

    monkeypatch.setattr(local_apk, "_AXMLPrinter", FakePrinter)

    parsed = local_apk._parse_manifest(
        b"controlled manifest",
        local_apk.DEFAULT_APK_PARSE_LIMITS,
    )

    assert parsed.requires_split_handling is True


def test_parse_result_requires_exactly_one_outcome(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="exactly one"):
        LocalArtifactParseResult()
    with pytest.raises(ValueError, match="exactly one"):
        LocalArtifactParseResult(
            artifact=_artifact(local_apk.parse_local_apk(_write_apk(tmp_path / "ok.apk"))),
            failure=local_apk.parse_local_apk(tmp_path / "missing.apk").failure,
        )


def test_pyaxmlparser_dependency_is_pinned_on_both_runtime_surfaces() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").splitlines()

    assert "pyaxmlparser==0.3.31" in project["project"]["dependencies"]
    assert "pyaxmlparser==0.3.31" in requirements


def test_parser_import_does_not_configure_process_root_logging() -> None:
    code = (
        "import logging; before=tuple(logging.getLogger().handlers); "
        "import playstore_app_audit.services.local_apk; "
        "assert tuple(logging.getLogger().handlers) == before"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
