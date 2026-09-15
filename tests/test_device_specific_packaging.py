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
