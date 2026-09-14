#!/usr/bin/env python3
"""Keep approved data in Resources while preserving Nuitka's runtime paths."""

from __future__ import annotations

import argparse
import os
from hashlib import sha256
from pathlib import Path

CERTIFI_LINK_TARGET = str(Path("..") / "Resources" / "certifi")
PYAXMLPARSER_LINK_TARGET = str(
    Path("..") / ".." / "Resources" / "pyaxmlparser" / "resources"
)
MACHO_MAGICS = {
    bytes.fromhex(value)
    for value in (
        "feedface",
        "cefaedfe",
        "feedfacf",
        "cffaedfe",
        "cafebabe",
        "bebafeca",
        "cafebabf",
        "bfbafeca",
    )
}


def _is_macho(path: Path) -> bool:
    with path.open("rb") as stream:
        return stream.read(4) in MACHO_MAGICS


def _regular_cacert(directory: Path) -> Path:
    cacert = directory / "cacert.pem"
    if cacert.is_symlink() or not cacert.is_file():
        raise RuntimeError(f"Expected a regular certifi CA file: {cacert}")
    return cacert


def _check_certifi_data(directory: Path) -> None:
    _regular_cacert(directory)
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink():
                raise RuntimeError(f"certifi data contains a symlink: {path}")
        for name in files:
            path = Path(root) / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"certifi data contains a non-regular file: {path}")
            if _is_macho(path):
                raise RuntimeError(f"Refusing to move Mach-O code into Resources: {path}")


def _regular_public_xml(directory: Path) -> Path:
    public_xml = directory / "public.xml"
    if public_xml.is_symlink() or not public_xml.is_file():
        raise RuntimeError(f"Expected a regular pyaxmlparser public.xml: {public_xml}")
    return public_xml


def _check_pyaxmlparser_data(directory: Path) -> None:
    _regular_public_xml(directory)
    for root, dirs, files in os.walk(directory, followlinks=False):
        dirs.sort()
        files.sort()
        for name in dirs:
            path = Path(root) / name
            if path.is_symlink():
                raise RuntimeError(f"pyaxmlparser data contains a symlink: {path}")
        for name in files:
            path = Path(root) / name
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f"pyaxmlparser data contains a non-regular file: {path}")
            if _is_macho(path):
                raise RuntimeError(f"Refusing to move Mach-O code into Resources: {path}")


def _normalize_pyaxmlparser(macos: Path, resources: Path) -> str:
    package = macos / "pyaxmlparser"
    if package.is_symlink() or not package.is_dir():
        raise RuntimeError(f"Expected a real pyaxmlparser package directory: {package}")
    link = package / "resources"
    destination_parent = resources / "pyaxmlparser"
    destination = destination_parent / "resources"
    if destination_parent.is_symlink() or (
        destination_parent.exists() and not destination_parent.is_dir()
    ):
        raise RuntimeError(f"Expected a real pyaxmlparser resource parent: {destination_parent}")
    if link.is_symlink():
        if destination.is_symlink() or not destination.is_dir():
            raise RuntimeError(f"Expected a real pyaxmlparser resource directory: {destination}")
        _check_pyaxmlparser_data(destination)
        return sha256(_regular_public_xml(destination).read_bytes()).hexdigest()
    if not link.is_dir():
        raise RuntimeError(f"Expected Nuitka pyaxmlparser data directory: {link}")
    if destination.exists() or destination.is_symlink():
        raise RuntimeError(f"pyaxmlparser resource destination already exists: {destination}")
    _check_pyaxmlparser_data(link)
    expected_hash = sha256(_regular_public_xml(link).read_bytes()).hexdigest()
    created_parent = not destination_parent.exists()
    destination_parent.mkdir(exist_ok=True)
    link.rename(destination)
    try:
        link.symlink_to(PYAXMLPARSER_LINK_TARGET, target_is_directory=True)
    except OSError:
        destination.rename(link)
        if created_parent:
            destination_parent.rmdir()
        raise
    return expected_hash


def _non_code_macos_files(macos: Path) -> list[str]:
    non_code: list[str] = []
    for root, dirs, files in os.walk(macos, followlinks=False):
        dirs[:] = sorted(name for name in dirs if not (Path(root) / name).is_symlink())
        files.sort()
        for name in files:
            path = Path(root) / name
            if path.is_symlink():
                continue
            if not path.is_file() or not _is_macho(path):
                non_code.append(path.relative_to(macos).as_posix())
    return sorted(non_code)


def _validate_layout(app: Path, expected_hash: str, expected_public_hash: str) -> None:
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    link = macos / "certifi"
    destination = resources / "certifi"

    if not link.is_symlink():
        raise RuntimeError(f"Expected the relative certifi runtime symlink: {link}")
    target = Path(os.readlink(link))
    if target.is_absolute() or target.parts != ("..", "Resources", "certifi"):
        raise RuntimeError(f"Expected the relative certifi runtime symlink: {link}")
    if destination.is_symlink() or not destination.is_dir():
        raise RuntimeError(f"Expected a real certifi resource directory: {destination}")
    if link.resolve(strict=True) != destination.resolve(strict=True):
        raise RuntimeError(f"certifi runtime symlink does not resolve inside the app: {link}")

    resource_cacert = _regular_cacert(destination)
    runtime_cacert = _regular_cacert(link)
    resource_hash = sha256(resource_cacert.read_bytes()).hexdigest()
    runtime_hash = sha256(runtime_cacert.read_bytes()).hexdigest()
    if resource_hash != expected_hash or runtime_hash != expected_hash:
        raise RuntimeError("certifi CA bytes changed during bundle normalization")

    package = macos / "pyaxmlparser"
    link = package / "resources"
    destination_parent = resources / "pyaxmlparser"
    destination = destination_parent / "resources"
    if package.is_symlink() or not package.is_dir():
        raise RuntimeError(f"Expected a real pyaxmlparser package directory: {package}")
    if not link.is_symlink():
        raise RuntimeError(f"Expected the relative pyaxmlparser runtime symlink: {link}")
    target = Path(os.readlink(link))
    if target.is_absolute() or target.parts != (
        "..", "..", "Resources", "pyaxmlparser", "resources"
    ):
        raise RuntimeError(f"Expected the relative pyaxmlparser runtime symlink: {link}")
    if destination_parent.is_symlink() or not destination_parent.is_dir():
        raise RuntimeError(f"Expected a real pyaxmlparser resource parent: {destination_parent}")
    if destination.is_symlink() or not destination.is_dir():
        raise RuntimeError(f"Expected a real pyaxmlparser resource directory: {destination}")
    if link.resolve(strict=True) != destination.resolve(strict=True):
        raise RuntimeError(f"pyaxmlparser runtime symlink does not resolve inside the app: {link}")
    resource_public = _regular_public_xml(destination)
    runtime_public = _regular_public_xml(link)
    if (
        sha256(resource_public.read_bytes()).hexdigest() != expected_public_hash
        or sha256(runtime_public.read_bytes()).hexdigest() != expected_public_hash
    ):
        raise RuntimeError("pyaxmlparser public.xml bytes changed during bundle normalization")

    remaining = _non_code_macos_files(macos)
    if remaining:
        raise RuntimeError(
            "Non-Mach-O regular files remain under Contents/MacOS: "
            + ", ".join(remaining)
        )


def normalize_bundle(app: Path) -> str:
    if app.is_symlink() or not app.is_dir() or app.suffix.casefold() != ".app":
        raise RuntimeError(f"Expected a real macOS .app bundle: {app}")

    contents = app / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"
    for directory in (contents, macos, resources):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError(f"Expected a real bundle directory: {directory}")

    link = macos / "certifi"
    destination = resources / "certifi"
    if link.is_symlink():
        _check_certifi_data(destination)
        expected_hash = sha256(_regular_cacert(destination).read_bytes()).hexdigest()
    else:
        if not link.is_dir():
            raise RuntimeError(f"Expected Nuitka certifi data directory: {link}")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError(f"certifi resource destination already exists: {destination}")
        _check_certifi_data(link)
        expected_hash = sha256(_regular_cacert(link).read_bytes()).hexdigest()
        link.rename(destination)
        try:
            link.symlink_to(CERTIFI_LINK_TARGET, target_is_directory=True)
        except OSError:
            destination.rename(link)
            raise

    expected_public_hash = _normalize_pyaxmlparser(macos, resources)
    _validate_layout(app, expected_hash, expected_public_hash)
    return expected_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", required=True, type=Path)
    args = parser.parse_args()
    digest = normalize_bundle(args.app)
    print(f"macOS certifi bundle normalization PASS; cacert.pem SHA-256: {digest}")
    public_xml = args.app / "Contents" / "Resources" / "pyaxmlparser" / "resources" / "public.xml"
    print(
        "macOS pyaxmlparser bundle normalization PASS; public.xml SHA-256: "
        + sha256(public_xml.read_bytes()).hexdigest()
    )
    print("No non-Mach-O regular files remain under Contents/MacOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
