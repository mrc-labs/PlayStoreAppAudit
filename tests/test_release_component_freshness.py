from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

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
    assert '"Nuitka==4.2.2"' in helper
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


def test_development_setup_environments_track_and_guard_stable_python_314() -> None:
    setups = 0
    for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        if "actions/setup-python@" not in workflow:
            continue
        assert "3.14.8" not in workflow, path.name
        if path.name == "quality.yml":
            assert '- "3.14"' in workflow
        for setup in re.finditer(r"uses: actions/setup-python@[^\n]+", workflow):
            setups += 1
            following = workflow[setup.end():]
            guard = following.index("- name: Verify stable Python 3.14")
            assert "uses:" not in following[:guard], path.name
            assert "run:" not in following[:guard], path.name
            assert "check-latest: true" in following[:guard], path.name
            assert 'python-version: "3.14"' in following[:guard] or (
                path.name == "quality.yml"
                and "python-version: ${{ matrix.python-version }}" in following[:guard]
            )
            step = following[guard:].split("\n      - ", 1)[0]
            assert "platform.python_version()" in step
            assert "assert sys.version_info[:2] == (3, 14)" in step
            assert "sys.version_info.releaselevel == 'final'" in step
            if "shell: pwsh" in step:
                assert "if ($LASTEXITCODE -ne 0) { throw" in step
            else:
                assert "set -euo pipefail" in step
    assert setups == 11


@pytest.mark.parametrize(
    ("version", "releaselevel", "expected_exit"),
    [("3.14.7", "final", 0), ("3.14.8", "final", 0),
     ("3.14.9", "final", 0), ("3.15.0", "final", 1),
     ("3.13.9", "final", 1), ("3.14.9", "candidate", 1), ("3.14.8", "candidate", 1)],
)
def test_development_runtime_guard_accepts_only_final_python_314(
    version: str, releaselevel: str, expected_exit: int,
) -> None:
    workflow = (ROOT / ".github/workflows/build-linux.yml").read_text(encoding="utf-8")
    command = re.search(r'python -c "([^"\n]*actual=platform[^"\n]*)"', workflow)
    assert command is not None
    parts = tuple(map(int, version.split('.')))
    script = (
        "import platform, sys; from collections import namedtuple; "
        "VersionInfo=namedtuple('VersionInfo', 'major minor micro releaselevel serial'); "
        f"sys.version_info=VersionInfo(*{parts!r}, {releaselevel!r}, 0); "
        f"platform.python_version=lambda: {version!r}; " + command[1]
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, check=False)
    assert result.returncode == expected_exit


def test_development_native_helpers_preserve_resolved_patch_and_current_rust() -> None:
    windows_helper = (ROOT / ".github/scripts/build_windows_standalone.ps1").read_text(encoding="utf-8")
    assert "assert sys.version_info[:2] == (3, 14)" in windows_helper
    assert "sys.version_info.releaselevel == 'final'" in windows_helper
    assert "assert struct.calcsize('P') * 8 == 64" in windows_helper
    sysroot = (ROOT / ".github/scripts/prepare_linux_x64_sysroot.sh").read_text(encoding="utf-8")
    assert 'test "$resolved_python" = 3.14.8' not in sysroot
    assert "sys.version_info[:2] == (3, 14)" in sysroot
    assert 'sys.version_info.releaselevel == "final"' in sysroot
    assert '--version "$resolved_python"' in sysroot
    assert '= "$resolved_python"' in sysroot
    macos = (ROOT / ".github/workflows/build-macos.yml").read_text(encoding="utf-8")
    assert "--default-toolchain 1.99.0" in macos
    assert 'rustc 1.99.0 ' in macos
    windows = (ROOT / ".github/workflows/build-windows-exe.yml").read_text(encoding="utf-8")
    assert "rustup toolchain install 1.99.0 --profile minimal" in windows
    assert "host: aarch64-pc-windows-msvc" in windows


def test_linux_vendor_openssl_is_refreshed_and_security_floor_enforced() -> None:
    linux = (ROOT / ".github/workflows/build-linux.yml").read_text(encoding="utf-8")
    assert "libssl3t64 \\" in linux
    assert 'dpkg --compare-versions "$ssl_package_version" ge 3.0.13-0ubuntu3.16' in linux
    assert "env -u LD_LIBRARY_PATH openssl version" in linux
    sysroot = (ROOT / ".github/scripts/prepare_linux_x64_sysroot.sh").read_text(encoding="utf-8")
    assert 'dpkg --compare-versions "$ssl_package_version" ge 3.0.2-0ubuntu1.30' in sysroot


def test_v22_historical_freeze_and_future_exact_patch_requirement_remain() -> None:
    evidence = (ROOT / "docs/V2_2_FINAL_PRE_RELEASE_FRESHNESS.md").read_text(encoding="utf-8")
    assert "**3.14.8**" in evidence
    assert "All **11 setup environments across nine workflows**" in evidence
    assert "requiring success only for the selected patch" in evidence
    policy = (ROOT / "docs/RELEASE_COMPONENT_FRESHNESS.md").read_text(encoding="utf-8")
    assert "Before freezing the release SHA" in policy
    assert "major.minor.patch" in policy
    assert "platform.python_version()" in policy


def test_v22_published_context_separates_release_identity_from_development() -> None:
    status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    handoff = (ROOT / "docs/HANDOFF_V2.2.md").read_text(encoding="utf-8")
    for context in (status, handoff):
        assert "21b6646571b7e93044b76fe4d18a04eeec092f18" in context
        assert "95a402b25f65bf22db58f831076bca747e2c9103" in context
        assert "401714084" in context
        assert "3.14.8" in context and "check-latest: true" in context
        for run_id in ("36987000922", "36988301118", "36988304138", "36988307201", "36993205418"):
            assert run_id in context
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "**Latest published release:** [v2.3.0]" in readme
    draft = (ROOT / "docs/V2_2_RELEASE_BODY_DRAFT.md").read_text(encoding="utf-8")
    assert "historical draft (superseded)" in draft
    assert "PENDING" not in draft
