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
        for value in re.findall(r"^\s*retention-days:\s*(\d+)\s*$", workflow, re.MULTILINE)
    ]


def test_ui_style_audit_artifacts_expire_after_three_days() -> None:
    assert _retention_days(_workflow("ui-style-audit.yml")) == [3]


def test_v14_windows_pipeline_artifacts_expire_after_seven_days() -> None:
    for name in (
        "build-windows-exe.yml",
        "assemble-windows-engineering-release.yml",
    ):
        values = _retention_days(_workflow(name))
        assert values, f"{name} must set explicit artifact retention"
        assert values == [7], f"unexpected retention in {name}: {values}"
