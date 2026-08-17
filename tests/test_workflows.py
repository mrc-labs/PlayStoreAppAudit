from __future__ import annotations

from pathlib import Path


def test_default_windows_ci_target_is_x64_only() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/build-windows-exe.yml").read_text(encoding="utf-8")

    assert "default: x64" in workflow
    assert "github.event_name == 'push' && '[\"x64\"]'" in workflow
    assert "- arm64" in workflow
    assert "- both" in workflow
    assert "'0x8664'" in workflow


def test_quality_concurrency_is_scoped_to_pull_request() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/quality.yml").read_text(encoding="utf-8")

    assert "github.event.pull_request.number || github.run_id" in workflow
    assert "cancel-in-progress: true" in workflow
