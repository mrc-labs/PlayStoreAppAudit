from __future__ import annotations

import argparse
import hashlib
import io
import re
import tarfile
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Any

APP_ASSET_PREFIX = "PlayStoreAppAudit"
PLATFORMS = ("windows", "macos", "linux")
ARCHITECTURES = ("x64", "arm64")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_version(version: str) -> str:
    if VERSION_RE.fullmatch(version) is None:
        raise ValueError(f"Invalid release version: {version}")
    return version


def source_bundle_filename(version: str) -> str:
    return f"{APP_ASSET_PREFIX}-v{_validate_version(version)}-third-party-sources.tar.xz"


def source_bundle_root(version: str) -> str:
    return f"{APP_ASSET_PREFIX}-v{_validate_version(version)}-third-party-sources"


def binary_asset_filename(version: str, platform: str, architecture: str) -> str:
    version = _validate_version(version)

    if platform not in PLATFORMS:
        raise ValueError(f"Unsupported platform: {platform}")

    if architecture not in ARCHITECTURES:
        raise ValueError(f"Unsupported architecture: {architecture}")

    return f"{APP_ASSET_PREFIX}-v{version}-{platform}-{architecture}.zip"


def expected_binary_asset_names(version: str) -> set[str]:
    return {
        binary_asset_filename(version, platform, architecture)
        for platform in PLATFORMS
        for architecture in ARCHITECTURES
    }


def _normalise_assets(
    assets: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    result = []

    for raw in assets:
        filename = str(raw["filename"])

        if PurePosixPath(filename).name != filename:
            raise ValueError(f"Unsafe filename: {filename}")

        digest = str(raw["sha256"]).lower()
        if SHA256_RE.fullmatch(digest) is None:
            raise ValueError(f"Invalid SHA-256: {filename}")

        result.append(
            {
                **raw,
                "filename": filename,
                "sha256": digest,
                "size": int(raw["size"]),
            }
        )

    return sorted(result, key=lambda item: item["filename"].casefold())


def build_third_party_source_bundle(
    source_dir: Path,
    output_dir: Path,
    version: str,
    assets: Iterable[dict[str, Any]],
) -> Path:
    assets = _normalise_assets(assets)
    root = source_bundle_root(version)
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle = output_dir / source_bundle_filename(version)
    temp = bundle.with_suffix(bundle.suffix + ".tmp")
    temp.unlink(missing_ok=True)

    readme_lines = [
        "# Third-party corresponding sources",
        "",
        f"Play Store App Audit v{version}",
        "",
        "Exact upstream source archives are stored under `sources/`.",
        "",
    ]

    sums = []

    for item in assets:
        path = source_dir / item["filename"]

        if not path.is_file():
            raise RuntimeError(f"Missing source: {item['filename']}")

        if sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch: {item['filename']}")

        sums.append(
            f"{item['sha256']}  sources/{item['filename']}"
        )

    def info(name: str, size: int = 0, directory: bool = False):
        item = tarfile.TarInfo(name)
        item.uid = item.gid = 0
        item.uname = item.gname = ""
        item.mtime = 0
        item.mode = 0o755 if directory else 0o644
        item.size = 0 if directory else size
        if directory:
            item.type = tarfile.DIRTYPE
        return item

    with tarfile.open(temp, "w:xz") as archive:
        archive.addfile(info(root, directory=True))

        readme = "\n".join(readme_lines).encode()
        archive.addfile(
            info(f"{root}/README.md", len(readme)),
            io.BytesIO(readme),
        )

        sums_bytes = ("\n".join(sums) + "\n").encode("ascii")
        archive.addfile(
            info(f"{root}/SHA256SUMS.txt", len(sums_bytes)),
            io.BytesIO(sums_bytes),
        )

        archive.addfile(
            info(f"{root}/sources", directory=True)
        )

        for item in assets:
            path = source_dir / item["filename"]
            with path.open("rb") as handle:
                archive.addfile(
                    info(
                        f"{root}/sources/{item['filename']}",
                        path.stat().st_size,
                    ),
                    handle,
                )

    temp.replace(bundle)
    return bundle



def validate_third_party_source_bundle(
    bundle: Path,
    version: str,
    assets: Iterable[dict[str, Any]],
) -> None:
    assets = _normalise_assets(assets)
    expected_name = source_bundle_filename(version)
    root = source_bundle_root(version)

    if bundle.name != expected_name:
        raise RuntimeError(
            f"Unexpected source bundle name: {bundle.name}"
        )

    expected_members = [
        root,
        f"{root}/README.md",
        f"{root}/SHA256SUMS.txt",
        f"{root}/sources",
        *[
            f"{root}/sources/{item['filename']}"
            for item in assets
        ],
    ]

    expected_sums = "".join(
        f"{item['sha256']}  sources/{item['filename']}\n"
        for item in assets
    )

    with tarfile.open(bundle, "r:xz") as archive:
        members = archive.getmembers()
        names = [member.name for member in members]

        if names != expected_members:
            raise RuntimeError(
                "Unexpected third-party source bundle layout"
            )

        for member in members:
            if member.issym() or member.islnk():
                raise RuntimeError(
                    f"Links are forbidden in source bundle: {member.name}"
                )

            parts = PurePosixPath(member.name).parts
            if member.name.startswith("/") or ".." in parts:
                raise RuntimeError(
                    f"Unsafe source bundle path: {member.name}"
                )

        sums_handle = archive.extractfile(
            f"{root}/SHA256SUMS.txt"
        )
        if sums_handle is None:
            raise RuntimeError(
                "Unable to read source bundle SHA256SUMS.txt"
            )

        actual_sums = sums_handle.read().decode("ascii")
        if actual_sums != expected_sums:
            raise RuntimeError(
                "Source bundle SHA256SUMS.txt is not canonical"
            )

        for item in assets:
            handle = archive.extractfile(
                f"{root}/sources/{item['filename']}"
            )
            if handle is None:
                raise RuntimeError(
                    f"Unable to read bundled source: {item['filename']}"
                )

            data = handle.read()

            digest = hashlib.sha256(data).hexdigest()
            if digest != item["sha256"]:
                raise RuntimeError(
                    f"Bundled source SHA-256 mismatch: {item['filename']}"
                )

            if len(data) != item["size"]:
                raise RuntimeError(
                    f"Bundled source size mismatch: {item['filename']}"
                )

def generate_release_sha256s(
    asset_dir: Path,
    version: str,
    *,
    require_all_platforms: bool = False,
) -> Path:
    source_name = source_bundle_filename(version)
    allowed = expected_binary_asset_names(version) | {source_name}

    files = sorted(
        [
            path
            for path in asset_dir.iterdir()
            if path.is_file()
            and path.name != "SHA256SUMS.txt"
        ],
        key=lambda path: path.name.casefold(),
    )

    names = {path.name for path in files}

    if any(name.endswith(".sha256") for name in names):
        raise RuntimeError("Per-package .sha256 sidecars are not allowed")

    unexpected = names - allowed
    if unexpected:
        raise RuntimeError(
            f"Unexpected release assets: {sorted(unexpected)}"
        )

    if source_name not in names:
        raise RuntimeError("Third-party source bundle missing")

    binary_names = expected_binary_asset_names(version)
    present_binaries = names & binary_names

    if not present_binaries:
        raise RuntimeError("At least one binary release package is required")

    if require_all_platforms:
        expected = binary_names | {source_name}
        missing = sorted(expected - names)

        if missing:
            raise RuntimeError(
                f"Complete release is missing assets: {missing}"
            )

    manifest = asset_dir / "SHA256SUMS.txt"

    manifest.write_text(
        "".join(
            f"{sha256_file(path)}  {path.name}\n"
            for path in files
        ),
        encoding="ascii",
    )

    return manifest



def validate_release_sha256s(
    asset_dir: Path,
    version: str,
    *,
    require_all_platforms: bool = False,
) -> None:
    manifest = asset_dir / "SHA256SUMS.txt"

    if not manifest.is_file():
        raise RuntimeError("Release-wide SHA256SUMS.txt is missing")

    source_name = source_bundle_filename(version)
    binary_names = expected_binary_asset_names(version)
    allowed = binary_names | {source_name}

    files = sorted(
        [
            path
            for path in asset_dir.iterdir()
            if path.is_file()
            and path.name != "SHA256SUMS.txt"
        ],
        key=lambda path: path.name.casefold(),
    )

    names = {path.name for path in files}

    unexpected = names - allowed
    if unexpected:
        raise RuntimeError(
            f"Unexpected release assets: {sorted(unexpected)}"
        )

    if source_name not in names:
        raise RuntimeError("Third-party source bundle missing")

    if not (names & binary_names):
        raise RuntimeError("At least one binary release package is required")

    if require_all_platforms:
        missing = sorted(allowed - names)
        if missing:
            raise RuntimeError(
                f"Complete release is missing assets: {missing}"
            )

    expected_lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in files
    ]

    actual_lines = manifest.read_text(
        encoding="ascii"
    ).splitlines()

    if actual_lines != expected_lines:
        raise RuntimeError(
            "Release-wide SHA256SUMS.txt does not match "
            "the canonical asset set and hashes"
        )

def main() -> int:
    parser = argparse.ArgumentParser()

    commands = parser.add_subparsers(
        dest="command",
        required=True,
    )

    for command in ("generate", "validate"):
        command_parser = commands.add_parser(command)
        command_parser.add_argument(
            "--asset-dir",
            type=Path,
            required=True,
        )
        command_parser.add_argument(
            "--version",
            required=True,
        )
        command_parser.add_argument(
            "--require-all-platforms",
            action="store_true",
        )

    args = parser.parse_args()

    if args.command == "generate":
        manifest = generate_release_sha256s(
            args.asset_dir,
            args.version,
            require_all_platforms=args.require_all_platforms,
        )
        print(manifest)
        return 0

    validate_release_sha256s(
        args.asset_dir,
        args.version,
        require_all_platforms=args.require_all_platforms,
    )

    print("Release-wide SHA256SUMS.txt validation PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())