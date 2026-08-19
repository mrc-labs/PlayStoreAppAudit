from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def _retention_days(workflow: str) -> list[int]:
    return [
        int(value)
        for value in re.findall(
            r"^\s*retention-days:\s*(\d+)\s*$",
            workflow,
            re.MULTILINE,
        )
    ]


def test_ui_style_audit_artifacts_expire_after_three_days() -> None:
    assert _retention_days(_workflow("ui-style-audit.yml")) == [3]


def test_release_pipeline_artifacts_expire_after_seven_days() -> None:
    expected = {
        "build-windows-exe.yml": [7],
        "assemble-windows-engineering-release.yml": [7],
        "build-linux.yml": [7],
        "build-macos.yml": [7, 7],
        "sign-windows.yml": [7],
        "assemble-release.yml": [7],
    }

    for name, expected_values in expected.items():
        values = _retention_days(_workflow(name))
        assert values, f"{name} must set explicit artifact retention"
        assert values == expected_values, (
            f"unexpected retention in {name}: {values}"
        )


def test_every_upload_artifact_step_has_explicit_retention() -> None:
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = path.read_text(encoding="utf-8")
        uploads = workflow.count("uses: actions/upload-artifact@")

        if uploads == 0:
            continue

        retentions = _retention_days(workflow)

        assert len(retentions) == uploads, (
            f"{path.name} has {uploads} upload-artifact steps "
            f"but {len(retentions)} explicit retention values"
        )