#!/usr/bin/env python3
"""Sign a macOS app bundle inside-out without using codesign --deep for signing."""

from __future__ import annotations

import argparse
import subprocess
from collections.abc import Iterable
from pathlib import Path

NESTED_BUNDLE_SUFFIXES = {
    ".app",
    ".appex",
    ".bundle",
    ".framework",
    ".plugin",
    ".xpc",
}


def _path_depth(path: Path) -> int:
    return len(path.parts)


def _sort_inside_out(paths: Iterable[Path]) -> list[Path]:
    return sorted(
        paths,
        key=lambda path: (
            -_path_depth(path),
            str(path).casefold(),
        ),
    )


def _is_macho(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False

    result = subprocess.run(
        ["file", "-b", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return "Mach-O" in result.stdout


def discover_macho_files(app: Path) -> list[Path]:
    return _sort_inside_out(
        path
        for path in app.rglob("*")
        if _is_macho(path)
    )


def discover_nested_bundles(app: Path) -> list[Path]:
    return _sort_inside_out(
        path
        for path in app.rglob("*")
        if (
            path.is_dir()
            and path.suffix.casefold() in NESTED_BUNDLE_SUFFIXES
            and path != app
        )
    )


def _codesign_command(
    target: Path,
    *,
    identity: str,
    keychain: Path | None,
    production: bool,
) -> list[str]:
    command = [
        "codesign",
        "--force",
        "--sign",
        identity,
    ]

    if keychain is not None:
        command.extend(["--keychain", str(keychain)])

    if production:
        command.extend(["--options", "runtime", "--timestamp"])

    command.append(str(target))
    return command


def _sign_target(
    target: Path,
    *,
    identity: str,
    keychain: Path | None,
    production: bool,
) -> None:
    subprocess.run(
        _codesign_command(
            target,
            identity=identity,
            keychain=keychain,
            production=production,
        ),
        check=True,
    )


def sign_app(
    app: Path,
    *,
    identity: str,
    keychain: Path | None = None,
    production: bool = False,
) -> None:
    app = app.resolve()
    if not app.is_dir() or app.suffix.casefold() != ".app":
        raise RuntimeError(f"Expected a macOS .app bundle: {app}")

    if production and not identity.strip():
        raise RuntimeError("Production signing requires a signing identity")

    if production and keychain is None:
        raise RuntimeError("Production signing requires an explicit keychain")

    for path in discover_macho_files(app):
        _sign_target(
            path,
            identity=identity,
            keychain=keychain,
            production=production,
        )

    for bundle in discover_nested_bundles(app):
        _sign_target(
            bundle,
            identity=identity,
            keychain=keychain,
            production=production,
        )

    _sign_target(
        app,
        identity=identity,
        keychain=keychain,
        production=production,
    )

    subprocess.run(
        [
            "codesign",
            "--verify",
            "--deep",
            "--strict",
            "--verbose=2",
            str(app),
        ],
        check=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--identity", required=True)
    parser.add_argument("--keychain", type=Path)
    parser.add_argument(
        "--production",
        action="store_true",
        help="Enable hardened runtime and secure timestamping",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    sign_app(
        args.app,
        identity=args.identity,
        keychain=args.keychain,
        production=args.production,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
