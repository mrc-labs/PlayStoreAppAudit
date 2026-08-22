from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github/scripts"
sys.path.insert(0, str(SCRIPTS))

assembler = importlib.import_module("assemble_windows_engineering_release")
release = importlib.import_module("release_asset_layout")

VERSION = "9.8.7"
EXPECTED_SHA = "a" * 40
WORKFLOW = ROOT / ".github/workflows/assemble-windows-engineering-release.yml"


def _candidate(tmp_path: Path, architecture: str = "x64") -> dict[str, object]:
    root = tmp_path / architecture
    root.mkdir(parents=True)

    archive_path = root / release.binary_asset_filename(
        VERSION,
        "windows",
        architecture,
    )
    archive_path.write_bytes(f"windows-{architecture}".encode("ascii"))

    release_dir = root / f"legal-release-v{VERSION}"
    source_dir = release_dir / "source-assets"
    source_dir.mkdir(parents=True)

    common = source_dir / "common-source.tar.xz"
    common.write_bytes(b"common-source")
    arch_source = source_dir / f"windows-{architecture}-source.tar.xz"
    arch_source.write_bytes(architecture.encode("ascii"))

    source_assets = []
    for path, component in (
        (common, "common"),
        (arch_source, f"windows-{architecture}"),
    ):
        source_assets.append(
            {
                "component": component,
                "filename": path.name,
                "sha256": release.sha256_file(path),
                "size": path.stat().st_size,
            }
        )

    return {
        "platform": "windows",
        "architecture": architecture,
        "archive_path": archive_path,
        "release_dir": release_dir,
        "source_assets": source_assets,
    }


def test_windows_engineering_assembler_emits_exact_three_assets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    candidate = _candidate(tmp_path / "candidate")
    monkeypatch.setattr(
        assembler,
        "_discover_windows_candidate",
        lambda *_args: candidate,
    )

    assets = assembler.assemble_windows_engineering_release(
        input_dir,
        output_dir,
        VERSION,
        EXPECTED_SHA,
    )

    expected_names = {
        release.binary_asset_filename(VERSION, "windows", "x64"),
        release.source_bundle_filename(VERSION),
        "SHA256SUMS.txt",
    }

    assert {path.name for path in assets} == expected_names
    assert len(assets) == 3
    release.validate_release_sha256s(
        output_dir,
        VERSION,
        require_all_platforms=False,
    )


def test_windows_engineering_discovery_rejects_arm64_input(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    x64_name = release.binary_asset_filename(VERSION, "windows", "x64")
    arm64_name = release.binary_asset_filename(VERSION, "windows", "arm64")
    (input_dir / x64_name).write_bytes(b"x64")
    (input_dir / arm64_name).write_bytes(b"unexpected")

    with pytest.raises(RuntimeError, match="x64 only"):
        assembler._discover_windows_candidate(
            input_dir,
            VERSION,
            EXPECTED_SHA,
        )


def test_windows_engineering_workflow_is_manual_exact_sha_and_unsigned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "expected_sha:" in text
    assert "windows_run_id:" in text
    assert "contents: read" in text
    assert "actions: read" in text
    assert '"refs/heads/main"' in text
    assert '"Build Windows - Qt6"' in text
    assert "Sign Windows release candidates" not in text
    assert "actions/download-artifact@v8" in text
    assert "run-id: ${{ inputs.windows_run_id }}" in text
    assert (
        "PlayStoreAppAudit-v${{ steps.project_version.outputs.version }}-windows-x64"
        in text
    )
    assert "windows-*" not in text
    assert "windows-arm64" in text
    assert "target=x64 only" in text
    assert "assemble_windows_engineering_release.py" in text
    assert '--expected-sha "$EXPECTED_SHA"' in text
    assert "--require-all-platforms" not in text
    assert 'test "$asset_count" = "3"' in text
    assert "Windows architecture: x64 only" in text
    assert "Signing: intentionally unsigned engineering profile" in text
    assert "production signing is deferred to v2.0 or later" in text
    assert text.count("actions/upload-artifact@v7") == 1

    forbidden = (
        "pyside6-deploy",
        "sign-windows.yml",
        "artifact-signing-action",
        "gh release",
        "git tag",
        "create-release",
        "softprops/action-gh-release",
    )
    for marker in forbidden:
        assert marker not in text
