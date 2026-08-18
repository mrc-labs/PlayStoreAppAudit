from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from release_asset_layout import (
    expected_binary_asset_names,
    source_bundle_filename,
)

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "scripts"
    / "release_asset_layout.py"
)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_rejects_incomplete_full_release(
    tmp_path: Path,
) -> None:
    version = "1.3.0"

    (tmp_path / source_bundle_filename(version)).write_bytes(
        b"source"
    )

    first_binary = sorted(
        expected_binary_asset_names(version)
    )[0]

    (tmp_path / first_binary).write_bytes(b"binary")

    result = _run_cli(
        "generate",
        "--asset-dir",
        str(tmp_path),
        "--version",
        version,
        "--require-all-platforms",
    )

    assert result.returncode != 0
    assert "Complete release is missing assets" in result.stderr


def test_cli_generates_and_validates_complete_release(
    tmp_path: Path,
) -> None:
    version = "1.3.0"

    source_name = source_bundle_filename(version)
    (tmp_path / source_name).write_bytes(b"source")

    for name in expected_binary_asset_names(version):
        (tmp_path / name).write_bytes(
            name.encode("utf-8")
        )

    generated = _run_cli(
        "generate",
        "--asset-dir",
        str(tmp_path),
        "--version",
        version,
        "--require-all-platforms",
    )

    assert generated.returncode == 0, generated.stderr

    manifest = tmp_path / "SHA256SUMS.txt"
    lines = manifest.read_text(
        encoding="ascii"
    ).splitlines()

    assert len(lines) == 7
    assert all(
        "SHA256SUMS.txt" not in line
        for line in lines
    )

    validated = _run_cli(
        "validate",
        "--asset-dir",
        str(tmp_path),
        "--version",
        version,
        "--require-all-platforms",
    )

    assert validated.returncode == 0, validated.stderr
    assert (
        "Release-wide SHA256SUMS.txt validation PASS"
        in validated.stdout
    )