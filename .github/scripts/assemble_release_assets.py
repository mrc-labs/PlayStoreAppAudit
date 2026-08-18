from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from release_asset_layout import (
    ARCHITECTURES,
    PLATFORMS,
    binary_asset_filename,
    build_third_party_source_bundle,
    expected_binary_asset_names,
    generate_release_sha256s,
    sha256_file,
    source_bundle_filename,
    validate_release_sha256s,
    validate_third_party_source_bundle,
)

LEGAL_MANIFEST_SCHEMA_VERSION = 3
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ARCH_ALIASES = {
    "amd64": "x64",
    "x86_64": "x64",
    "arm64": "arm64",
    "aarch64": "arm64",
}


def _normalise_expected_sha(value: str) -> str:
    value = value.strip().casefold()
    if FULL_SHA_RE.fullmatch(value) is None:
        raise ValueError("expected_sha must be a full 40-character Git SHA")
    return value


def _normalise_manifest_architecture(value: object) -> str:
    key = str(value).strip().casefold()
    try:
        return ARCH_ALIASES[key]
    except KeyError as exc:
        raise RuntimeError(
            f"Unsupported manifest architecture: {value}"
        ) from exc


def _read_manifest(release_dir: Path) -> dict[str, Any]:
    manifest_path = (
        release_dir
        / "package-legal"
        / "LEGAL-MANIFEST.json"
    )
    if not manifest_path.is_file():
        raise RuntimeError(
            f"Missing legal manifest: {manifest_path}"
        )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    if not isinstance(manifest, dict):
        raise RuntimeError(
            f"Legal manifest is not an object: {manifest_path}"
        )
    return manifest


def _validate_source_asset(
    source_assets_dir: Path,
    raw: object,
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise RuntimeError("Invalid source asset manifest entry")

    filename = str(raw.get("filename", ""))
    if (
        not filename
        or PurePosixPath(filename).name != filename
    ):
        raise RuntimeError(
            f"Unsafe source asset filename: {filename}"
        )

    digest = str(raw.get("sha256", "")).casefold()
    if SHA256_RE.fullmatch(digest) is None:
        raise RuntimeError(
            f"Invalid source asset SHA-256: {filename}"
        )

    try:
        size = int(raw["size"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Invalid source asset size: {filename}"
        ) from exc

    if size < 0:
        raise RuntimeError(
            f"Invalid source asset size: {filename}"
        )

    path = source_assets_dir / filename
    if not path.is_file():
        raise RuntimeError(
            f"Missing staged source asset: {path}"
        )

    if path.stat().st_size != size:
        raise RuntimeError(
            f"Source asset size mismatch: {filename}"
        )

    if sha256_file(path) != digest:
        raise RuntimeError(
            f"Source asset SHA-256 mismatch: {filename}"
        )

    return {
        **raw,
        "filename": filename,
        "sha256": digest,
        "size": size,
    }


def _validate_rc_legal(
    release_dir: Path,
    version: str,
    platform_name: str,
    architecture: str,
) -> list[dict[str, Any]]:
    manifest = _read_manifest(release_dir)

    if (
        manifest.get("schema_version")
        != LEGAL_MANIFEST_SCHEMA_VERSION
    ):
        raise RuntimeError(
            f"Unexpected legal manifest schema: {release_dir}"
        )

    application = manifest.get("application")
    if not isinstance(application, dict):
        raise RuntimeError(
            f"Missing application manifest object: {release_dir}"
        )

    if application.get("version") != version:
        raise RuntimeError(
            f"Application version mismatch: {release_dir}"
        )

    if application.get("release_tag") != f"v{version}":
        raise RuntimeError(
            f"Release tag mismatch: {release_dir}"
        )

    package = manifest.get("package")
    if not isinstance(package, dict):
        raise RuntimeError(
            f"Missing package manifest object: {release_dir}"
        )

    if package.get("platform") != platform_name:
        raise RuntimeError(
            f"Package platform mismatch: {release_dir}"
        )

    if (
        _normalise_manifest_architecture(
            package.get("architecture")
        )
        != architecture
    ):
        raise RuntimeError(
            f"Package architecture mismatch: {release_dir}"
        )

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise RuntimeError(
            f"Missing policy manifest object: {release_dir}"
        )

    if policy.get("final_artifact_revalidation_required") is not True:
        raise RuntimeError(
            "Legal manifest must require final artifact "
            f"revalidation: {release_dir}"
        )

    source_assets_dir = release_dir / "source-assets"
    if not source_assets_dir.is_dir():
        raise RuntimeError(
            f"Missing source-assets directory: {release_dir}"
        )

    raw_assets = manifest.get("source_assets")
    if not isinstance(raw_assets, list) or not raw_assets:
        raise RuntimeError(
            f"Missing source asset manifest entries: {release_dir}"
        )

    assets = [
        _validate_source_asset(source_assets_dir, raw)
        for raw in raw_assets
    ]

    expected_sums = "".join(
        f"{item['sha256']}  {item['filename']}\n"
        for item in assets
    )
    sums_path = source_assets_dir / "SHA256SUMS.txt"
    if not sums_path.is_file():
        raise RuntimeError(
            f"Missing internal source SHA256SUMS.txt: {release_dir}"
        )

    if sums_path.read_text(encoding="utf-8") != expected_sums:
        raise RuntimeError(
            "Internal source SHA256SUMS.txt does not match "
            f"the legal manifest: {release_dir}"
        )

    source_bundle = manifest.get("source_bundle")
    if not isinstance(source_bundle, dict):
        raise RuntimeError(
            f"Missing source bundle manifest object: {release_dir}"
        )

    expected_bundle_name = source_bundle_filename(version)
    if source_bundle.get("filename") != expected_bundle_name:
        raise RuntimeError(
            f"Source bundle filename mismatch: {release_dir}"
        )

    bundle_path = release_dir / expected_bundle_name
    if not bundle_path.is_file():
        raise RuntimeError(
            f"Missing per-RC source bundle: {bundle_path}"
        )

    if source_bundle.get("size") != bundle_path.stat().st_size:
        raise RuntimeError(
            f"Source bundle size mismatch: {release_dir}"
        )

    bundle_digest = sha256_file(bundle_path)
    if source_bundle.get("sha256") != bundle_digest:
        raise RuntimeError(
            f"Source bundle SHA-256 mismatch: {release_dir}"
        )

    validate_third_party_source_bundle(
        bundle_path,
        version,
        assets,
    )

    availability = (
        release_dir
        / "package-legal"
        / "SOURCE-AVAILABILITY.md"
    )
    if not availability.is_file():
        raise RuntimeError(
            f"Missing staged SOURCE-AVAILABILITY.md: {release_dir}"
        )

    availability_text = availability.read_text(
        encoding="utf-8"
    )
    if (
        expected_bundle_name not in availability_text
        or bundle_digest not in availability_text
    ):
        raise RuntimeError(
            "SOURCE-AVAILABILITY.md does not identify the "
            f"validated source bundle: {release_dir}"
        )

    return assets


def _validate_binary_build_sha(
    archive_path: Path,
    expected_sha: str,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        build_info_names = [
            name
            for name in archive.namelist()
            if PurePosixPath(
                name.replace("\\", "/")
            ).name.casefold()
            == "build-info.txt"
        ]

        if len(build_info_names) != 1:
            raise RuntimeError(
                "Expected exactly one BUILD-INFO.txt in "
                f"{archive_path.name}, found "
                f"{len(build_info_names)}"
            )

        text = archive.read(
            build_info_names[0]
        ).decode("utf-8")

    match = re.search(
        r"^GitHub SHA:\s*([0-9A-Fa-f]{40})\s*$",
        text,
        flags=re.MULTILINE,
    )
    if match is None:
        raise RuntimeError(
            f"BUILD-INFO GitHub SHA missing: {archive_path.name}"
        )

    actual_sha = match.group(1).casefold()
    if actual_sha != expected_sha:
        raise RuntimeError(
            "Release candidate commit mismatch for "
            f"{archive_path.name}: {actual_sha} != {expected_sha}"
        )


def _discover_release_candidates(
    input_dir: Path,
    version: str,
    expected_sha: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for platform_name in PLATFORMS:
        for architecture in ARCHITECTURES:
            filename = binary_asset_filename(
                version,
                platform_name,
                architecture,
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
                    f"Expected exactly one {filename}, "
                    f"found {len(matches)}"
                )

            archive_path = matches[0]
            release_dir = (
                archive_path.parent
                / f"legal-release-v{version}"
            )

            if not release_dir.is_dir():
                raise RuntimeError(
                    "Release candidate legal staging must be "
                    "a sibling of its ZIP: "
                    f"{archive_path}"
                )

            _validate_binary_build_sha(
                archive_path,
                expected_sha,
            )
            source_assets = _validate_rc_legal(
                release_dir,
                version,
                platform_name,
                architecture,
            )

            candidates.append(
                {
                    "platform": platform_name,
                    "architecture": architecture,
                    "archive_path": archive_path,
                    "release_dir": release_dir,
                    "source_assets": source_assets,
                }
            )

    return candidates


def _prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        entries = list(output_dir.iterdir())
        if entries:
            raise RuntimeError(
                f"Output directory must be empty: {output_dir}"
            )
    else:
        output_dir.mkdir(parents=True)


def _merge_source_assets(
    candidates: list[dict[str, Any]],
    source_dir: Path,
) -> list[dict[str, Any]]:
    source_dir.mkdir(parents=True, exist_ok=True)
    merged: dict[str, dict[str, Any]] = {}

    for candidate in candidates:
        release_dir = candidate["release_dir"]
        for item in candidate["source_assets"]:
            filename = item["filename"]
            existing = merged.get(filename)

            if existing is not None:
                if (
                    existing["sha256"] != item["sha256"]
                    or existing["size"] != item["size"]
                    or existing.get("component")
                    != item.get("component")
                ):
                    raise RuntimeError(
                        "Conflicting source archive metadata for "
                        f"{filename}"
                    )
                continue

            source_path = (
                release_dir
                / "source-assets"
                / filename
            )
            destination = source_dir / filename
            shutil.copy2(source_path, destination)

            if sha256_file(destination) != item["sha256"]:
                raise RuntimeError(
                    f"Copied source SHA-256 mismatch: {filename}"
                )

            merged[filename] = dict(item)

    return sorted(
        merged.values(),
        key=lambda item: item["filename"].casefold(),
    )


def assemble_release(
    input_dir: Path,
    output_dir: Path,
    version: str,
    expected_sha: str,
) -> list[Path]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    expected_sha = _normalise_expected_sha(expected_sha)

    if not input_dir.is_dir():
        raise RuntimeError(
            f"Input directory does not exist: {input_dir}"
        )

    candidates = _discover_release_candidates(
        input_dir,
        version,
        expected_sha,
    )

    _prepare_output_dir(output_dir)

    for candidate in candidates:
        source = candidate["archive_path"]
        destination = output_dir / source.name
        shutil.copy2(source, destination)

        if sha256_file(destination) != sha256_file(source):
            raise RuntimeError(
                f"Copied binary SHA-256 mismatch: {source.name}"
            )

    with tempfile.TemporaryDirectory(
        prefix="playstore-release-sources-"
    ) as temp_dir:
        source_dir = Path(temp_dir) / "sources"
        source_assets = _merge_source_assets(
            candidates,
            source_dir,
        )

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
        require_all_platforms=True,
    )
    validate_release_sha256s(
        output_dir,
        version,
        require_all_platforms=True,
    )

    expected_names = (
        expected_binary_asset_names(version)
        | {
            source_bundle_filename(version),
            "SHA256SUMS.txt",
        }
    )
    actual_entries = list(output_dir.iterdir())

    if any(not path.is_file() for path in actual_entries):
        raise RuntimeError(
            "Final release output must contain files only"
        )

    actual_names = {path.name for path in actual_entries}
    if actual_names != expected_names:
        raise RuntimeError(
            "Final release asset set mismatch: "
            f"expected {sorted(expected_names)}, "
            f"found {sorted(actual_names)}"
        )

    return sorted(
        actual_entries,
        key=lambda path: path.name.casefold(),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--version",
        required=True,
    )
    parser.add_argument(
        "--expected-sha",
        required=True,
    )
    args = parser.parse_args(argv)

    assets = assemble_release(
        args.input_dir,
        args.output_dir,
        args.version,
        args.expected_sha,
    )

    print("Final release assembly PASS")
    for asset in assets:
        print(asset.name)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
