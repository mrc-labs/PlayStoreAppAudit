#!/usr/bin/env python3
"""Validate Device Specific reference-profile resources in a standalone package."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EXPECTED_PROFILES = {
    "android10_api29_oneplus8pro.json": (
        "android10_api29_oneplus8pro",
        29,
    ),
    "android13_api33_s20plus.json": (
        "android13_api33_s20plus",
        33,
    ),
}


def _load_profile(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not read profile resource {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Profile resource is not a JSON object: {path}")
    return payload


def validate_profile_resources(package_root: Path) -> dict[str, tuple[Path, ...]]:
    """Require both production profile resources and validate every packaged copy."""

    root = package_root.resolve()
    if not root.is_dir():
        raise RuntimeError(f"Standalone package root does not exist: {root}")

    found: dict[str, tuple[Path, ...]] = {}
    for filename, (profile_id, api_level) in EXPECTED_PROFILES.items():
        matches = tuple(
            sorted(
                path.resolve()
                for path in root.rglob(filename)
                if path.is_file()
                and path.parent.name == "device_profiles"
                and path.parent.parent.name == "playstore_app_audit"
            )
        )
        if not matches:
            raise RuntimeError(
                "Standalone package is missing Device Specific profile resource: "
                f"playstore_app_audit/device_profiles/{filename}"
            )

        for path in matches:
            payload = _load_profile(path)
            if payload.get("schema") != 1:
                raise RuntimeError(f"Unexpected profile schema in {path}")
            if payload.get("profile_id") != profile_id:
                raise RuntimeError(f"Unexpected profile_id in {path}")
            if payload.get("api_level") != api_level:
                raise RuntimeError(f"Unexpected api_level in {path}")
            profile = payload.get("profile")
            if not isinstance(profile, dict) or not profile:
                raise RuntimeError(f"Profile payload is missing in {path}")
            if str(profile.get("Build.VERSION.SDK_INT") or "") != str(api_level):
                raise RuntimeError(f"Profile SDK does not match api_level in {path}")
            if not str(payload.get("profile_hash") or "").strip():
                raise RuntimeError(f"Profile hash is missing in {path}")
            if not str(payload.get("source_url") or "").strip():
                raise RuntimeError(f"Profile provenance URL is missing in {path}")

        found[filename] = matches
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "package_root",
        type=Path,
        help="Standalone .dist directory or macOS .app bundle root.",
    )
    args = parser.parse_args()

    found = validate_profile_resources(args.package_root)
    for filename, paths in found.items():
        rendered = ", ".join(str(path) for path in paths)
        print(f"{filename}: {rendered}")
    print("Device Specific standalone profile resources: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
