from __future__ import annotations

import tomllib
from pathlib import Path

from playstore_app_audit import __version__


def test_package_version_matches_project_metadata() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]


def test_v110_release_version() -> None:
    assert __version__ == "1.1.0"


def test_release_version_is_semver_triplet() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
