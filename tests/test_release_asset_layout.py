from __future__ import annotations

import importlib.util
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / ".github/scripts/release_asset_layout.py"

spec = importlib.util.spec_from_file_location(
    "release_asset_layout",
    HELPER,
)
assert spec is not None
assert spec.loader is not None

release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def _asset(path: Path, component: str) -> dict[str, object]:
    return {
        "component": component,
        "filename": path.name,
        "sha256": release.sha256_file(path),
        "size": path.stat().st_size,
        "download_url": f"https://example.invalid/{path.name}",
        "provenance_url": f"https://example.invalid/meta/{path.name}",
    }


def test_source_bundle_has_expected_layout(tmp_path: Path) -> None:
    version = "9.8.7"
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "output"
    source_dir.mkdir()

    qt = source_dir / "qtbase-test.tar.xz"
    certifi = source_dir / "certifi-test.tar.gz"

    qt.write_bytes(b"qt-source")
    certifi.write_bytes(b"certifi-source")

    assets = [
        _asset(qt, "qtbase"),
        _asset(certifi, "certifi"),
    ]

    bundle = release.build_third_party_source_bundle(
        source_dir,
        output_dir,
        version,
        assets,
    )

    assert bundle.name == (
        "PlayStoreAppAudit-v9.8.7-third-party-sources.tar.xz"
    )

    release.validate_third_party_source_bundle(
        bundle,
        version,
        assets,
    )

    root = release.source_bundle_root(version)

    with tarfile.open(bundle, "r:xz") as archive:
        names = archive.getnames()

        assert names == [
            root,
            f"{root}/README.md",
            f"{root}/SHA256SUMS.txt",
            f"{root}/sources",
            f"{root}/sources/certifi-test.tar.gz",
            f"{root}/sources/qtbase-test.tar.xz",
        ]

        sums = archive.extractfile(
            f"{root}/SHA256SUMS.txt"
        )
        assert sums is not None

        sums_text = sums.read().decode("ascii")
        assert "sources/certifi-test.tar.gz" in sums_text
        assert "sources/qtbase-test.tar.xz" in sums_text


def test_source_bundle_is_deterministic(tmp_path: Path) -> None:
    version = "9.8.7"
    source_dir = tmp_path / "sources"
    output_dir = tmp_path / "output"
    source_dir.mkdir()

    first = source_dir / "a.tar.xz"
    second = source_dir / "b.tar.gz"

    first.write_bytes(b"aaa")
    second.write_bytes(b"bbb")

    assets = [
        _asset(first, "first"),
        _asset(second, "second"),
    ]

    bundle = release.build_third_party_source_bundle(
        source_dir,
        output_dir,
        version,
        assets,
    )
    first_bytes = bundle.read_bytes()

    bundle = release.build_third_party_source_bundle(
        source_dir,
        output_dir,
        version,
        list(reversed(assets)),
    )
    second_bytes = bundle.read_bytes()

    assert first_bytes == second_bytes


def test_release_checksum_manifest_is_release_wide(
    tmp_path: Path,
) -> None:
    version = "9.8.7"

    source_bundle = tmp_path / release.source_bundle_filename(version)
    windows = tmp_path / release.binary_asset_filename(
        version,
        "windows",
        "x64",
    )

    source_bundle.write_bytes(b"source-bundle")
    windows.write_bytes(b"windows-package")

    manifest = release.generate_release_sha256s(
        tmp_path,
        version,
    )

    lines = manifest.read_text(encoding="ascii").splitlines()

    assert len(lines) == 2
    assert any(source_bundle.name in line for line in lines)
    assert any(windows.name in line for line in lines)
    assert all(".sha256" not in line for line in lines)


def test_per_package_checksum_sidecars_are_rejected(
    tmp_path: Path,
) -> None:
    version = "9.8.7"

    source_bundle = tmp_path / release.source_bundle_filename(version)
    windows_name = release.binary_asset_filename(
        version,
        "windows",
        "x64",
    )

    source_bundle.write_bytes(b"source")
    (tmp_path / windows_name).write_bytes(b"package")
    (tmp_path / f"{windows_name}.sha256").write_text(
        "obsolete",
        encoding="ascii",
    )

    try:
        release.generate_release_sha256s(
            tmp_path,
            version,
        )
    except RuntimeError as exc:
        assert "sidecars are not allowed" in str(exc)
    else:
        raise AssertionError(
            "Expected per-package .sha256 rejection"
        )


def test_legal_validator_accepts_consolidated_source_bundle(
    tmp_path: Path,
) -> None:
    import importlib
    import sys

    scripts = ROOT / ".github/scripts"
    sys.path.insert(0, str(scripts))

    validator = importlib.import_module(
        "validate_release_legal_bundle"
    )

    version = "9.8.7"

    release_dir = tmp_path / "release"
    source_dir = release_dir / "source-assets"
    package_dir = tmp_path / "package"

    source_dir.mkdir(parents=True)
    package_dir.mkdir()

    source = source_dir / "certifi-test.tar.gz"
    source.write_bytes(b"certifi-source")

    asset = _asset(source, "certifi")
    asset["provenance_url"] = (
        "https://pypi.org/pypi/certifi/9.8.7/json"
    )
    assets = [asset]

    (source_dir / "SHA256SUMS.txt").write_text(
        f"{asset['sha256']}  {asset['filename']}\n",
        encoding="ascii",
    )

    bundle = release.build_third_party_source_bundle(
        source_dir,
        release_dir,
        version,
        assets,
    )

    bundle_hash = release.sha256_file(bundle)

    (package_dir / "SOURCE-AVAILABILITY.md").write_text(
        "\n".join(
            [
                "# Third-party corresponding source availability",
                "",
                f"`{bundle.name}`",
                f"SHA-256 `{bundle_hash}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    manifest = {
        "application": {
            "version": version,
        },
        "source_assets": assets,
        "source_bundle": {
            "filename": bundle.name,
            "sha256": bundle_hash,
            "size": bundle.stat().st_size,
        },
    }

    validator._validate_source_assets(
        release_dir,
        package_dir,
        manifest,
        True,
    )



def test_release_checksum_manifest_can_be_validated(
    tmp_path: Path,
) -> None:
    version = "9.8.7"

    source = tmp_path / release.source_bundle_filename(version)
    package = tmp_path / release.binary_asset_filename(
        version,
        "windows",
        "x64",
    )

    source.write_bytes(b"source")
    package.write_bytes(b"package")

    release.generate_release_sha256s(
        tmp_path,
        version,
    )

    release.validate_release_sha256s(
        tmp_path,
        version,
    )


def test_complete_release_requires_all_six_binary_assets(
    tmp_path: Path,
) -> None:
    version = "9.8.7"

    source = tmp_path / release.source_bundle_filename(version)
    source.write_bytes(b"source")

    for name in release.expected_binary_asset_names(version):
        (tmp_path / name).write_bytes(name.encode("ascii"))

    manifest = release.generate_release_sha256s(
        tmp_path,
        version,
        require_all_platforms=True,
    )

    release.validate_release_sha256s(
        tmp_path,
        version,
        require_all_platforms=True,
    )

    assert len(
        manifest.read_text(encoding="ascii").splitlines()
    ) == 7
