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


def test_artifact_uploads_use_repository_default_retention() -> None:
    expected = {
        "ui-style-audit.yml": [0],
        "build-windows-exe.yml": [0],
        "assemble-windows-engineering-release.yml": [0],
        "build-linux.yml": [0],
        "build-macos.yml": [0, 0],
        "sign-windows.yml": [0],
        "assemble-release.yml": [0],
    }

    for name, expected_values in expected.items():
        values = _retention_days(_workflow(name))
        assert values == expected_values, (
            f"{name} must defer artifact lifetime to repository settings; "
            f"found {values}"
        )


def test_every_upload_artifact_step_has_explicit_retention_policy() -> None:
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
