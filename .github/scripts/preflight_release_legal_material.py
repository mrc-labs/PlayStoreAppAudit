#!/usr/bin/env python3
"""Fail early when deterministic release legal/source prerequisites cannot resolve."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import platform
import re
import tempfile
import tomllib
from pathlib import Path
from typing import Any

import prepare_release_legal_bundle as legal

QT_SOURCE_COMPONENTS = (
    "pyside-setup",
    "qtbase",
    "qtimageformats",
    "qtsvg",
)

_EXACT_PYSIDE_REQUIREMENT = re.compile(
    r"^\s*PySide6-Essentials\s*==\s*([0-9]+(?:\.[0-9]+)+)\s*$",
    re.IGNORECASE,
)


def _read_exact_pyside_pin(repo_root: Path) -> str:
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )

    matches: list[str] = []
    for requirement in pyproject["project"].get("dependencies", []):
        match = _EXACT_PYSIDE_REQUIREMENT.fullmatch(requirement)
        if match is not None:
            matches.append(match.group(1))

    if len(matches) != 1:
        raise RuntimeError(
            "Release preflight requires exactly one exact "
            "PySide6-Essentials==VERSION project dependency"
        )

    return matches[0]


def _validate_source_spec(spec: legal.SourceAssetSpec) -> None:
    if not spec.filename or Path(spec.filename).name != spec.filename:
        raise RuntimeError(
            f"Invalid source filename for {spec.component}: {spec.filename!r}"
        )

    if not spec.url.startswith("https://"):
        raise RuntimeError(
            f"Source URL must use HTTPS for {spec.component}: {spec.url}"
        )

    if not spec.provenance_url.startswith("https://"):
        raise RuntimeError(
            "Source provenance URL must use HTTPS for "
            f"{spec.component}: {spec.provenance_url}"
        )

    if legal.SHA256_HEX_RE.fullmatch(spec.sha256) is None:
        raise RuntimeError(
            f"Invalid SHA-256 metadata for {spec.component}: {spec.sha256!r}"
        )


def run_preflight(
    repo_root: Path,
    *,
    expected_nuitka_version: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    project_version = legal._read_project_version(repo_root)

    expected_pyside_version = _read_exact_pyside_pin(repo_root)
    pyside_version = metadata.version("PySide6-Essentials")
    shiboken_version = metadata.version("shiboken6")

    if pyside_version != expected_pyside_version:
        raise RuntimeError(
            "Installed PySide6-Essentials does not match the exact project pin: "
            f"installed={pyside_version}, expected={expected_pyside_version}"
        )

    if shiboken_version != pyside_version:
        raise RuntimeError(
            "PySide6-Essentials/shiboken6 version mismatch: "
            f"{pyside_version} vs {shiboken_version}"
        )

    source_specs = [
        legal._qt_source_spec(component, pyside_version)
        for component in QT_SOURCE_COMPONENTS
    ]

    certifi_version = metadata.version("certifi")
    source_specs.append(legal._certifi_source_spec(certifi_version))

    for spec in source_specs:
        _validate_source_spec(spec)

    components = [spec.component for spec in source_specs]
    if len(set(components)) != len(components):
        raise RuntimeError(
            f"Duplicate source components resolved during preflight: {components}"
        )

    filenames = [spec.filename for spec in source_specs]
    if len(set(filenames)) != len(filenames):
        raise RuntimeError(
            f"Duplicate source filenames resolved during preflight: {filenames}"
        )

    expected_components = {*QT_SOURCE_COMPONENTS, "certifi"}
    if set(components) != expected_components:
        raise RuntimeError(
            "Unexpected legal source component set: "
            f"expected={sorted(expected_components)}, actual={sorted(components)}"
        )

    with tempfile.TemporaryDirectory(prefix="playstore-legal-preflight-") as tmp:
        licenses_root = Path(tmp) / "licenses"

        cpython_license = legal._copy_cpython_license(licenses_root)
        cpython_license_path = licenses_root.parent / cpython_license
        if (
            not cpython_license_path.is_file()
            or cpython_license_path.stat().st_size < 1000
            or "Python Software Foundation"
            not in cpython_license_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        ):
            raise RuntimeError(
                "Resolved CPython license payload failed preflight validation"
            )

        nuitka_version, nuitka_files = legal._copy_nuitka_legal_files(
            licenses_root
        )
        if nuitka_version != expected_nuitka_version:
            raise RuntimeError(
                "Installed Nuitka version does not match the release build pin: "
                f"installed={nuitka_version}, expected={expected_nuitka_version}"
            )
        if len(nuitka_files) != 3:
            raise RuntimeError(
                "Expected three required Nuitka legal files, got "
                f"{len(nuitka_files)}: {nuitka_files}"
            )

    return {
        "project_version": project_version,
        "python_version": platform.python_version(),
        "pyside6_essentials_version": pyside_version,
        "shiboken6_version": shiboken_version,
        "nuitka_version": expected_nuitka_version,
        "certifi_version": certifi_version,
        "cpython_license": "resolved",
        "nuitka_legal_files": sorted(nuitka_files),
        "source_assets": [
            {
                "component": spec.component,
                "filename": spec.filename,
                "url": spec.url,
                "sha256": spec.sha256.lower(),
                "provenance_url": spec.provenance_url,
            }
            for spec in source_specs
        ],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument(
        "--expected-nuitka-version",
        required=True,
        help="Exact Nuitka version pinned by the release workflow",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_preflight(
        args.repo_root,
        expected_nuitka_version=args.expected_nuitka_version,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
