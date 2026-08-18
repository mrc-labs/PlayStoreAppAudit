from __future__ import annotations

import json
import tomllib
import zipfile
from pathlib import Path

import pytest

import playstore_app_audit.app as application
import playstore_app_audit.services.device_insights as device_insights
from playstore_app_audit import __version__


def test_package_version_matches_project_metadata() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"]


def test_v130_release_version() -> None:
    assert __version__ == "1.3.0"


def test_release_qt_baseline_is_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements = (
        root / "requirements.txt"
    ).read_text(encoding="utf-8").splitlines()

    qt_requirement = "PySide6-Essentials==6.11.1"
    assert qt_requirement in project["project"]["dependencies"]
    assert qt_requirement in requirements


def test_release_version_is_semver_triplet() -> None:
    parts = __version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_diagnostic_bundle_identifies_the_canonical_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(device_insights.state, "load_settings", lambda: {})
    monkeypatch.setattr(device_insights, "portable_mode_active", lambda: False)
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    bundle = device_insights.create_diagnostic_bundle(tmp_path / "diagnostics.zip", [])

    with zipfile.ZipFile(bundle) as archive:
        system = json.loads(archive.read("system.json"))

    assert system["app_version"] == __version__


def test_qt_application_version_comes_from_the_canonical_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    created: list[object] = []

    class FakeApplication:
        def __init__(self, _arguments: list[str]) -> None:
            self.application_version = ""
            created.append(self)

        def setApplicationName(self, _name: str) -> None:
            pass

        def setApplicationVersion(self, version: str) -> None:
            self.application_version = version

        def setOrganizationName(self, _name: str) -> None:
            pass

        def setStyle(self, _style: str) -> None:
            pass

        def setWindowIcon(self, _icon: object) -> None:
            pass

        def exec(self) -> int:
            return 0

    class FakeWindow:
        def show(self) -> None:
            pass

    monkeypatch.delenv(application.SMOKE_TEST_ENV, raising=False)
    monkeypatch.setattr(application, "QApplication", FakeApplication)
    monkeypatch.setattr(application, "QIcon", lambda _path: object())
    monkeypatch.setattr(application, "MainWindow", FakeWindow)
    monkeypatch.setattr(application, "ensure_runtime_icon", lambda: tmp_path / "icon.ico")

    assert application.main() == 0
    assert len(created) == 1
    assert created[0].application_version == __version__  # type: ignore[attr-defined]


def test_windows_build_metadata_is_derived_from_the_canonical_version() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-windows-exe.yml"
    ).read_text(encoding="utf-8")
    builder = (
        root / ".github/scripts/build_windows_standalone.ps1"
    ).read_text(encoding="utf-8")

    assert "from playstore_app_audit import __version__; print(__version__)" in workflow
    assert "build_windows_standalone.ps1" in workflow
    assert "-ExpectedPeMachine $env:EXPECTED_PE_MACHINE" in workflow
    assert "-ExpectedPlatformMachine $env:EXPECTED_PLATFORM_MACHINE" in workflow
    assert "-UseMSVC" in workflow

    assert "--mode=standalone" in builder
    assert "from playstore_app_audit import __version__; print(__version__)" in builder
    assert "--file-version=$AppVersion" in builder
    assert "--product-version=$AppVersion" in builder
    assert '$ExpectedWindowsVersion = "$AppVersion.0"' in builder


def test_local_windows_build_uses_canonical_version_and_x64_validation() -> None:
    root = Path(__file__).resolve().parents[1]
    helper = (root / "build_windows_exe.bat").read_text(encoding="utf-8")
    builder = (
        root / ".github/scripts/build_windows_standalone.ps1"
    ).read_text(encoding="utf-8")
    validator = (
        root / ".github/scripts/validate_windows_standalone.py"
    ).read_text(encoding="utf-8")

    assert "build_windows_standalone.ps1" in helper
    assert '-ExpectedPeMachine "0x8664"' in helper
    assert '-ExpectedPlatformMachine "AMD64"' in helper

    assert "--mode=standalone" in builder
    assert "from playstore_app_audit import __version__; print(__version__)" in builder
    assert "--file-version=$AppVersion" in builder
    assert "--product-version=$AppVersion" in builder
    assert '$ExpectedWindowsVersion = "$AppVersion.0"' in builder
    assert "$InspectPe --expect $ExpectedPeMachine" in builder
    assert "validate_windows_standalone.py" in builder

    assert '"virtualkeyboard" in rel_compact' in validator
    assert '"Qt Virtual Keyboard runtime is intentionally excluded"' in validator
    assert '"qpdf.dll"' in validator
