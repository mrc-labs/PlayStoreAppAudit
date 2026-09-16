from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest


def _validator_module() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    path = root / ".github" / "scripts" / "validate_device_specific_profile_resources.py"
    spec = importlib.util.spec_from_file_location(
        "validate_device_specific_profile_resources",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_profile(
    root: Path,
    filename: str,
    profile_id: str,
    api_level: int,
) -> Path:
    destination = (
        root
        / "nested"
        / "playstore_app_audit"
        / "device_profiles"
        / filename
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {
                "schema": 1,
                "profile_id": profile_id,
                "api_level": api_level,
                "profile_hash": "a" * 64,
                "source_url": "https://example.invalid/profile",
                "profile": {
                    "Build.VERSION.SDK_INT": str(api_level),
                },
            }
        ),
        encoding="utf-8",
    )
    return destination


def test_packaged_profile_validator_accepts_both_resources(tmp_path: Path) -> None:
    validator = _validator_module()
    for filename, (profile_id, api_level) in validator.EXPECTED_PROFILES.items():
        _write_profile(tmp_path, filename, profile_id, api_level)

    found = validator.validate_profile_resources(tmp_path)

    assert set(found) == set(validator.EXPECTED_PROFILES)
    assert all(paths for paths in found.values())


def test_packaged_profile_validator_rejects_missing_resource(tmp_path: Path) -> None:
    validator = _validator_module()
    filename, (profile_id, api_level) = next(iter(validator.EXPECTED_PROFILES.items()))
    _write_profile(tmp_path, filename, profile_id, api_level)

    with pytest.raises(RuntimeError, match="missing Device Specific profile resource"):
        validator.validate_profile_resources(tmp_path)


def test_packaged_profile_validator_rejects_wrong_profile_metadata(tmp_path: Path) -> None:
    validator = _validator_module()
    for filename, (profile_id, api_level) in validator.EXPECTED_PROFILES.items():
        _write_profile(tmp_path, filename, profile_id, api_level)

    filename = next(iter(validator.EXPECTED_PROFILES))
    path = next(tmp_path.rglob(filename))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["profile_id"] = "wrong"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unexpected profile_id"):
        validator.validate_profile_resources(tmp_path)


def test_packaged_profile_validator_requires_real_package_path(tmp_path: Path) -> None:
    validator = _validator_module()
    filename, (profile_id, api_level) = next(iter(validator.EXPECTED_PROFILES.items()))
    wrong = tmp_path / "device_profiles" / filename
    wrong.parent.mkdir(parents=True)
    wrong.write_text(
        json.dumps(
            {
                "schema": 1,
                "profile_id": profile_id,
                "api_level": api_level,
                "profile_hash": "a" * 64,
                "source_url": "https://example.invalid/profile",
                "profile": {"Build.VERSION.SDK_INT": str(api_level)},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="missing Device Specific profile resource"):
        validator.validate_profile_resources(tmp_path)



def _repo_text(relative: str) -> str:
    return (
        Path(__file__).resolve().parents[1]
        / relative
    ).read_text(encoding="utf-8")


def test_runtime_smoke_loads_all_production_profile_resources() -> None:
    from playstore_app_audit.app import (
        _validate_device_specific_profiles_for_smoke,
    )

    _validate_device_specific_profiles_for_smoke()


def test_all_nuitka_packagers_include_device_specific_package_data() -> None:
    include = (
        "--include-package-data="
        "playstore_app_audit.device_profiles:*.json"
    )

    assert include in _repo_text(
        ".github/scripts/build_windows_standalone.ps1"
    )
    assert include in _repo_text(
        ".github/workflows/build-linux.yml"
    )
    assert include in _repo_text(
        ".github/workflows/build-macos.yml"
    )


def test_windows_packager_validates_raw_and_versioned_resources() -> None:
    script = _repo_text(
        ".github/scripts/build_windows_standalone.ps1"
    )

    assert (
        "validate_device_specific_profile_resources.py"
        in script
    )
    assert (
        "& $Python $ValidateDeviceSpecificProfiles "
        "$DistDir.FullName"
        in script
    )
    assert (
        "& $Python $ValidateDeviceSpecificProfiles "
        "$PackageDir"
        in script
    )


def test_linux_packager_validates_tree_and_roundtrip() -> None:
    workflow = _repo_text(
        ".github/workflows/build-linux.yml"
    )

    validator = (
        "validate_device_specific_profile_resources.py"
    )

    assert workflow.count(validator) == 2

    first = workflow.index(validator)
    archive = workflow.index(
        'ARCHIVE="$PWD/artifact/$PACKAGE_NAME.zip"'
    )
    second = workflow.index(
        validator,
        first + len(validator),
    )

    assert '"$STANDALONE_DIR"' in workflow[
        first:first + 250
    ]
    assert '"$ROUNDTRIP_DIR"' in workflow[
        second:second + 250
    ]

    assert first < archive < second


def test_macos_packager_validates_app_and_roundtrip() -> None:
    workflow = _repo_text(
        ".github/workflows/build-macos.yml"
    )

    validator = (
        "validate_device_specific_profile_resources.py"
    )

    assert workflow.count(validator) == 2

    normalize = workflow.index(
        'normalize_macos_bundle.py --app "$APP"'
    )
    first = workflow.index(
        validator,
        normalize,
    )

    archive = workflow.index(
        'ZIP="artifact/PlayStoreAppAudit-v'
    )

    roundtrip = workflow.index(
        "RAPP=$(find roundtrip"
    )

    second = workflow.index(
        validator,
        roundtrip,
    )

    assert '"$APP"' in workflow[
        first:first + 250
    ]
    assert '"$RAPP"' in workflow[
        second:second + 250
    ]

    assert (
        normalize
        < first
        < archive
        < roundtrip
        < second
    )
