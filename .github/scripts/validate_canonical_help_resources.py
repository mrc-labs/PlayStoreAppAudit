#!/usr/bin/env python3
"""Validate canonical Help screenshots in a standalone package."""

from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

EXPECTED_HELP_IMAGES: dict[str, tuple[int, int]] = {
    "store-app-audit-phone-maintenance.png": (1560, 900),
    "store-app-audit-local-apk.png": (1560, 900),
    "store-app-audit-changes-history.png": (820, 720),
    "store-app-audit-mass-rename.png": (1080, 640),
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _png_dimensions(
    path: Path,
) -> tuple[int, int]:
    try:
        header = path.read_bytes()[:24]
    except OSError as exc:
        raise RuntimeError(
            f"Could not read PNG resource {path}: {exc}"
        ) from exc

    if (
        len(header) < 24
        or header[:8] != PNG_SIGNATURE
        or header[12:16] != b"IHDR"
    ):
        raise RuntimeError(
            f"Invalid PNG resource: {path}"
        )

    return struct.unpack(
        ">II",
        header[16:24],
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def validate_help_resources(
    package_root: Path,
    *,
    canonical_dir: Path,
) -> dict[str, tuple[Path, ...]]:
    root = package_root.resolve()
    canonical = canonical_dir.resolve()

    if not root.is_dir():
        raise RuntimeError(
            f"Standalone package root does not exist: {root}"
        )

    if not canonical.is_dir():
        raise RuntimeError(
            f"Canonical image directory does not exist: {canonical}"
        )

    expected_names = set(
        EXPECTED_HELP_IMAGES
    )

    canonical_names = {
        path.name
        for path in canonical.iterdir()
        if path.is_file()
    }

    if canonical_names != expected_names:
        raise RuntimeError(
            "Canonical documentation image set mismatch: "
            f"{sorted(canonical_names)!r}"
        )

    canonical_hashes: dict[str, str] = {}

    for filename, expected_dimensions in (
        EXPECTED_HELP_IMAGES.items()
    ):
        source = canonical / filename

        if _png_dimensions(source) != expected_dimensions:
            raise RuntimeError(
                "Unexpected canonical PNG dimensions: "
                f"{source}"
            )

        canonical_hashes[filename] = _sha256(
            source
        )

    found: dict[str, tuple[Path, ...]] = {}
    help_directories: set[Path] = set()

    for filename, expected_dimensions in (
        EXPECTED_HELP_IMAGES.items()
    ):
        matches = tuple(
            sorted(
                path.resolve()
                for path in root.rglob(filename)
                if path.is_file()
                and not path.is_symlink()
                and path.parent.name == "help-images"
            )
        )

        if not matches:
            raise RuntimeError(
                "Standalone package is missing canonical Help image: "
                f"help-images/{filename}"
            )

        for path in matches:
            if _png_dimensions(path) != expected_dimensions:
                raise RuntimeError(
                    "Unexpected packaged Help PNG dimensions: "
                    f"{path}"
                )

            if _sha256(path) != canonical_hashes[filename]:
                raise RuntimeError(
                    "Packaged Help image differs from canonical source: "
                    f"{path}"
                )

            help_directories.add(
                path.parent
            )

        found[filename] = matches

    for directory in help_directories:
        packaged_names = {
            path.name
            for path in directory.iterdir()
            if path.is_file()
            and not path.is_symlink()
        }

        if packaged_names != expected_names:
            raise RuntimeError(
                "Packaged help-images directory does not contain "
                "the exact canonical set: "
                f"{directory}: {sorted(packaged_names)!r}"
            )

    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "package_root",
        type=Path,
        help=(
            "Standalone .dist directory, versioned package, "
            "or macOS .app bundle."
        ),
    )
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        default=Path("docs/images"),
        help=(
            "Source directory containing the committed canonical PNGs."
        ),
    )
    args = parser.parse_args()

    found = validate_help_resources(
        args.package_root,
        canonical_dir=args.canonical_dir,
    )

    for filename, paths in found.items():
        print(
            f"{filename}: "
            + ", ".join(
                str(path)
                for path in paths
            )
        )

    print(
        "Canonical packaged Help screenshot resources: PASS"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
