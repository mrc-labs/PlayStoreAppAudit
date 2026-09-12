from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v2_toolchain_uses_python_314_and_current_qt_pin() -> None:
    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert project["requires-python"] == ">=3.14"
    assert "PySide6-Essentials==6.11.2" in project["dependencies"]
    assert "PySide6-Essentials==6.11.2" in requirements


def test_local_windows_build_helper_tracks_v2_toolchain_and_source_details() -> None:
    helper = (ROOT / "build_windows_exe.bat").read_text(encoding="utf-8")

    assert "py -3.14" in helper
    assert '"Nuitka==4.2.1"' in helper
    assert "_set_view_preset('Source Details')" in helper
    assert "_set_view_preset('Device')" not in helper


def test_release_freshness_policy_requires_two_distinct_gates() -> None:
    policy = (
        ROOT / "docs" / "RELEASE_COMPONENT_FRESHNESS.md"
    ).read_text(encoding="utf-8")

    assert "Release-phase entry gate" in policy
    assert "Final pre-release gate" in policy
    assert "immediately before the exact release SHA is frozen" in policy
    assert "Pre-releases, release candidates, betas, alphas" in policy
    assert "A release may not pass either gate" in policy


def test_v2_release_entry_freshness_audit_is_recorded_but_not_final() -> None:
    evidence = (
        ROOT / "docs" / "V2_0_RELEASE_ENTRY_FRESHNESS.md"
    ).read_text(encoding="utf-8")

    assert "Audit date: 2026-09-13 CEST" in evidence
    assert "PASS for release-phase entry" in evidence
    assert "3.14.7" in evidence
    assert "PySide6-Essentials / Shiboken6 | 6.11.2 | 6.11.2" in evidence
    assert "Nuitka | 4.2.1 | 4.2.1" in evidence
    assert "Android Platform-Tools | upstream latest endpoint | 37.0.1" in evidence
    assert "must not be copied forward as proof" in evidence
    assert "repeat the full audit" in evidence
