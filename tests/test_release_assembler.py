from __future__ import annotations

import importlib
import json
import sys
import tarfile
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github/scripts"
sys.path.insert(0, str(SCRIPTS))

assembler = importlib.import_module("assemble_release_assets")
release = importlib.import_module("release_asset_layout")

VERSION = "9.8.7"
EXPECTED_SHA = "a" * 40

MANIFEST_ARCH = {
    ("windows", "x64"): "AMD64",
    ("windows", "arm64"): "ARM64",
    ("linux", "x64"): "x86_64",
    ("linux", "arm64"): "aarch64",
    ("macos", "x64"): "x86_64",
    ("macos", "arm64"): "arm64",
}


def _write_rc(
    input_dir: Path,
    platform_name: str,
    architecture: str,
    *,
    build_sha: str = EXPECTED_SHA,
    source_factory: Callable[
        [str, str],
        list[tuple[str, bytes, str]],
    ],
) -> Path:
    binary_name = release.binary_asset_filename(
        VERSION,
        platform_name,
        architecture,
    )
    artifact_root = (
        input_dir
        / binary_name.removesuffix(".zip")
    )
    artifact_root.mkdir(parents=True)

    archive_path = artifact_root / binary_name
    build_info_root = (
        "PlayStoreAppAudit.app/Contents/Resources"
        if platform_name == "macos"
        else "PlayStoreAppAudit"
    )

    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            f"{build_info_root}/BUILD-INFO.txt",
            "\n".join(
                [
                    f"Application version: {VERSION}",
                    f"GitHub SHA: {build_sha}",
                    "",
                ]
            ),
        )
        archive.writestr(
            f"{build_info_root}/runtime.bin",
            b"runtime",
        )

    release_dir = (
        artifact_root
        / f"legal-release-v{VERSION}"
    )
    source_dir = release_dir / "source-assets"
    package_legal = release_dir / "package-legal"
    source_dir.mkdir(parents=True)
    package_legal.mkdir(parents=True)

    assets = []

    for filename, data, component in source_factory(
        platform_name,
        architecture,
    ):
        path = source_dir / filename
        path.write_bytes(data)

        assets.append(
            {
                "component": component,
                "filename": filename,
                "sha256": release.sha256_file(path),
                "size": path.stat().st_size,
                "download_url": (
                    f"https://example.invalid/{filename}"
                ),
                "provenance_url": (
                    f"https://example.invalid/meta/{filename}"
                ),
            }
        )

    (source_dir / "SHA256SUMS.txt").write_text(
        "".join(
            f"{item['sha256']}  {item['filename']}\n"
            for item in assets
        ),
        encoding="utf-8",
    )

    bundle = release.build_third_party_source_bundle(
        source_dir,
        release_dir,
        VERSION,
        assets,
    )
    bundle_digest = release.sha256_file(bundle)

    (package_legal / "SOURCE-AVAILABILITY.md").write_text(
        "\n".join(
            [
                "# Third-party corresponding source availability",
                "",
                f"`{bundle.name}`",
                "Verify with `SHA256SUMS.txt` from the same release.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    manifest = {
        "schema_version": 3,
        "application": {
            "name": "Play Store App Audit",
            "version": VERSION,
            "project_license": "GPL-3.0-only",
            "release_tag": f"v{VERSION}",
        },
        "package": {
            "directory_name": "synthetic",
            "platform": platform_name,
            "architecture": MANIFEST_ARCH[
                (platform_name, architecture)
            ],
        },
        "source_bundle": {
            "filename": bundle.name,
            "sha256": bundle_digest,
            "size": bundle.stat().st_size,
        },
        "source_assets": assets,
        "policy": {
            "final_artifact_revalidation_required": True,
        },
    }

    (
        package_legal
        / "LEGAL-MANIFEST.json"
    ).write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    return artifact_root


def _default_sources(
    platform_name: str,
    architecture: str,
) -> list[tuple[str, bytes, str]]:
    del architecture

    return [
        (
            "common-source.tar.xz",
            b"common-source",
            "common",
        ),
        (
            f"{platform_name}-source.tar.xz",
            platform_name.encode("ascii"),
            f"{platform_name}-extra",
        ),
    ]


def _write_all_rcs(
    input_dir: Path,
    *,
    build_sha_factory: Callable[
        [str, str],
        str,
    ]
    | None = None,
    source_factory: Callable[
        [str, str],
        list[tuple[str, bytes, str]],
    ] = _default_sources,
) -> None:
    for platform_name in release.PLATFORMS:
        for architecture in release.ARCHITECTURES:
            build_sha = (
                build_sha_factory(
                    platform_name,
                    architecture,
                )
                if build_sha_factory is not None
                else EXPECTED_SHA
            )

            _write_rc(
                input_dir,
                platform_name,
                architecture,
                build_sha=build_sha,
                source_factory=source_factory,
            )


def test_assemble_release_produces_exact_eight_assets(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    _write_all_rcs(input_dir)

    assets = assembler.assemble_release(
        input_dir,
        output_dir,
        VERSION,
        EXPECTED_SHA,
    )

    expected_names = (
        release.expected_binary_asset_names(VERSION)
        | {
            release.source_bundle_filename(VERSION),
            "SHA256SUMS.txt",
        }
    )

    assert {path.name for path in assets} == expected_names
    assert len(assets) == 8

    release.validate_release_sha256s(
        output_dir,
        VERSION,
        require_all_platforms=True,
    )

    lines = (
        output_dir
        / "SHA256SUMS.txt"
    ).read_text(
        encoding="ascii"
    ).splitlines()

    assert len(lines) == 7

    bundle = (
        output_dir
        / release.source_bundle_filename(VERSION)
    )
    root = release.source_bundle_root(VERSION)

    with tarfile.open(bundle, "r:xz") as archive:
        names = set(archive.getnames())

    assert (
        f"{root}/sources/common-source.tar.xz"
        in names
    )
    for platform_name in release.PLATFORMS:
        assert (
            f"{root}/sources/"
            f"{platform_name}-source.tar.xz"
            in names
        )


def test_assembler_rejects_per_rc_source_bundle_digest(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    _write_all_rcs(input_dir)

    availability = next(
        input_dir.rglob("SOURCE-AVAILABILITY.md")
    )
    release_dir = availability.parents[1]
    manifest = json.loads(
        (
            release_dir
            / "package-legal"
            / "LEGAL-MANIFEST.json"
        ).read_text(encoding="utf-8")
    )
    bundle_digest = manifest["source_bundle"]["sha256"]

    availability.write_text(
        availability.read_text(encoding="utf-8")
        + f"SHA-256 `{bundle_digest}`\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="must not pin the per-RC source bundle SHA-256",
    ):
        assembler.assemble_release(
            input_dir,
            output_dir,
            VERSION,
            EXPECTED_SHA,
        )


def test_assemble_release_rejects_missing_binary(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    _write_all_rcs(input_dir)

    missing = release.binary_asset_filename(
        VERSION,
        "linux",
        "arm64",
    )
    next(input_dir.rglob(missing)).unlink()

    with pytest.raises(
        RuntimeError,
        match="Expected exactly one",
    ):
        assembler.assemble_release(
            input_dir,
            output_dir,
            VERSION,
            EXPECTED_SHA,
        )


def test_assemble_release_rejects_wrong_build_sha(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    def sha_factory(
        platform_name: str,
        architecture: str,
    ) -> str:
        if (
            platform_name == "macos"
            and architecture == "arm64"
        ):
            return "b" * 40
        return EXPECTED_SHA

    _write_all_rcs(
        input_dir,
        build_sha_factory=sha_factory,
    )

    with pytest.raises(
        RuntimeError,
        match="Release candidate commit mismatch",
    ):
        assembler.assemble_release(
            input_dir,
            output_dir,
            VERSION,
            EXPECTED_SHA,
        )


def test_assemble_release_rejects_source_hash_conflict(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()

    def conflicting_sources(
        platform_name: str,
        architecture: str,
    ) -> list[tuple[str, bytes, str]]:
        common = (
            b"conflicting-source"
            if (
                platform_name == "windows"
                and architecture == "arm64"
            )
            else b"common-source"
        )

        return [
            (
                "common-source.tar.xz",
                common,
                "common",
            ),
            (
                f"{platform_name}-source.tar.xz",
                platform_name.encode("ascii"),
                f"{platform_name}-extra",
            ),
        ]

    _write_all_rcs(
        input_dir,
        source_factory=conflicting_sources,
    )

    with pytest.raises(
        RuntimeError,
        match="Conflicting source archive metadata",
    ):
        assembler.assemble_release(
            input_dir,
            output_dir,
            VERSION,
            EXPECTED_SHA,
        )


def test_assemble_release_rejects_nonempty_output(
    tmp_path: Path,
) -> None:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()
    (output_dir / "stale.txt").write_text(
        "stale",
        encoding="utf-8",
    )

    _write_all_rcs(input_dir)

    with pytest.raises(
        RuntimeError,
        match="Output directory must be empty",
    ):
        assembler.assemble_release(
            input_dir,
            output_dir,
            VERSION,
            EXPECTED_SHA,
        )
