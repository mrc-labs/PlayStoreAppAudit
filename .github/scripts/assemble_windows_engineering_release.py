from __future__ import annotations

import argparse
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from assemble_release_assets import (
    _merge_source_assets,
    _normalise_expected_sha,
    _prepare_output_dir,
    _validate_binary_build_sha,
    _validate_rc_legal,
)
from release_asset_layout import (
    ARCHITECTURES,
    binary_asset_filename,
    build_third_party_source_bundle,
    generate_release_sha256s,
    sha256_file,
    source_bundle_filename,
    validate_release_sha256s,
    validate_third_party_source_bundle,
)

ENGINEERING_ARCHITECTURE = "x64"


def _discover_windows_candidate(
    input_dir: Path,
    version: str,
    expected_sha: str,
) -> dict[str, Any]:
    filename = binary_asset_filename(
        version,
        "windows",
        ENGINEERING_ARCHITECTURE,
    )
    matches = sorted(
        (
            path
            for path in input_dir.rglob(filename)
            if path.is_file()
        ),
        key=lambda path: str(path).casefold(),
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one {filename}, found {len(matches)}"
        )

    for architecture in ARCHITECTURES:
        if architecture == ENGINEERING_ARCHITECTURE:
            continue
        unexpected_name = binary_asset_filename(
            version,
            "windows",
            architecture,
        )
        unexpected_matches = [
            path
            for path in input_dir.rglob(unexpected_name)
            if path.is_file()
        ]
        if unexpected_matches:
            raise RuntimeError(
                "Windows engineering release input must contain x64 only; "
                f"found {len(unexpected_matches)} {unexpected_name} artifact(s)"
            )

    archive_path = matches[0]
    release_dir = archive_path.parent / f"legal-release-v{version}"

    if not release_dir.is_dir():
        raise RuntimeError(
            "Release candidate legal staging must be a sibling of its ZIP: "
            f"{archive_path}"
        )

    _validate_binary_build_sha(archive_path, expected_sha)
    source_assets = _validate_rc_legal(
        release_dir,
        version,
        "windows",
        ENGINEERING_ARCHITECTURE,
    )

    return {
        "platform": "windows",
        "architecture": ENGINEERING_ARCHITECTURE,
        "archive_path": archive_path,
        "release_dir": release_dir,
        "source_assets": source_assets,
    }


def assemble_windows_engineering_release(
    input_dir: Path,
    output_dir: Path,
    version: str,
    expected_sha: str,
) -> list[Path]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    expected_sha = _normalise_expected_sha(expected_sha)

    if not input_dir.is_dir():
        raise RuntimeError(f"Input directory does not exist: {input_dir}")

    candidate = _discover_windows_candidate(
        input_dir,
        version,
        expected_sha,
    )
    candidates = [candidate]

    _prepare_output_dir(output_dir)

    source = candidate["archive_path"]
    destination = output_dir / source.name
    shutil.copy2(source, destination)

    if sha256_file(destination) != sha256_file(source):
        raise RuntimeError(
            f"Copied binary SHA-256 mismatch: {source.name}"
        )

    with tempfile.TemporaryDirectory(
        prefix="playstore-windows-engineering-sources-"
    ) as temp_dir:
        source_dir = Path(temp_dir) / "sources"
        source_assets = _merge_source_assets(candidates, source_dir)

        bundle = build_third_party_source_bundle(
            source_dir,
            output_dir,
            version,
            source_assets,
        )
        validate_third_party_source_bundle(
            bundle,
            version,
            source_assets,
        )

    generate_release_sha256s(
        output_dir,
        version,
        require_all_platforms=False,
    )
    validate_release_sha256s(
        output_dir,
        version,
        require_all_platforms=False,
    )

    expected_names = {
        binary_asset_filename(
            version,
            "windows",
            ENGINEERING_ARCHITECTURE,
        ),
        source_bundle_filename(version),
        "SHA256SUMS.txt",
    }

    actual_entries = list(output_dir.iterdir())
    if any(not path.is_file() for path in actual_entries):
        raise RuntimeError(
            "Windows engineering release output must contain files only"
        )

    actual_names = {path.name for path in actual_entries}
    if actual_names != expected_names:
        raise RuntimeError(
            "Windows engineering release asset set mismatch: "
            f"expected {sorted(expected_names)}, found {sorted(actual_names)}"
        )

    return sorted(
        actual_entries,
        key=lambda path: path.name.casefold(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--expected-sha", required=True)
    args = parser.parse_args(argv)

    assets = assemble_windows_engineering_release(
        args.input_dir,
        args.output_dir,
        args.version,
        args.expected_sha,
    )

    print("Windows x64 engineering release assembly PASS")
    for asset in assets:
        print(asset.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
