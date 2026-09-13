from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
PREFLIGHT = ".github/scripts/preflight_release_legal_material.py"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def test_linux_legal_preflight_runs_before_nuitka_packaging() -> None:
    workflow = _workflow("build-linux.yml")

    assert workflow.count("Preflight release legal material") == 1
    assert workflow.count(PREFLIGHT) == 1
    assert '--expected-nuitka-version "4.2.1"' in workflow

    preflight = workflow.index("Preflight release legal material")
    configure = workflow.index("Configure Qt deployment")
    compile_package = workflow.index("pyside6-deploy -c pysidedeploy.spec -f")
    strict_gate = workflow.index("prepare_release_legal_bundle.py")

    assert preflight < configure < compile_package < strict_gate


def test_macos_legal_preflight_runs_before_nuitka_packaging() -> None:
    workflow = _workflow("build-macos.yml")

    assert workflow.count("Preflight release legal material") == 1
    assert workflow.count(PREFLIGHT) == 1
    assert '--expected-nuitka-version "4.2.1"' in workflow

    preflight = workflow.index("Preflight release legal material")
    configure = workflow.index("Configure Qt deployment")
    compile_package = workflow.index("pyside6-deploy -c pysidedeploy.spec -f")
    strict_gate = workflow.index("prepare_release_legal_bundle.py")

    assert preflight < configure < compile_package < strict_gate


def test_windows_legal_preflight_runs_before_heavy_build() -> None:
    workflow = _workflow("build-windows-exe.yml")

    assert workflow.count("Preflight release legal material") == 1
    assert workflow.count(PREFLIGHT) >= 3
    assert '--expected-nuitka-version "4.2.1"' in workflow

    preflight = workflow.index("Preflight release legal material")
    tests = workflow.index("Static checks and regression tests")
    heavy_build = workflow.index("Build and validate Windows standalone package")

    assert preflight < tests < heavy_build


def test_preflight_does_not_replace_strict_post_build_gate() -> None:
    for name in (
        "build-windows-exe.yml",
        "build-linux.yml",
        "build-macos.yml",
    ):
        workflow = _workflow(name)
        assert "preflight_release_legal_material.py" in workflow
        assert "prepare_release_legal_bundle.py" in workflow
        assert "validate_release_legal_bundle.py" in workflow
