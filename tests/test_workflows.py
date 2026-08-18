from __future__ import annotations

from pathlib import Path


def test_windows_release_build_is_manual_and_sha_guarded() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/build-windows-exe.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "\n  push:" not in workflow

    assert "default: x64" in workflow
    assert "- arm64" in workflow
    assert "- both" in workflow

    assert "expected_sha:" in workflow
    assert "required: true" in workflow
    assert "EXPECTED_SHA: ${{ inputs.expected_sha }}" in workflow
    assert "DISPATCH_SHA: ${{ github.sha }}" in workflow
    assert "ref: ${{ github.sha }}" in workflow

    assert "github.event_name == 'push'" not in workflow
    assert "'0x8664'" in workflow


def test_quality_runs_on_pull_requests_and_relevant_main_pushes() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (
        root / ".github/workflows/quality.yml"
    ).read_text(encoding="utf-8")

    assert "pull_request:" in workflow
    assert "push:" in workflow
    assert workflow.count("branches: [main]") == 2
    assert '".github/workflows/*.yml"' in workflow
    assert "github.event.pull_request.number || github.ref" in workflow
    assert "cancel-in-progress: true" in workflow

    assert 'python-version:' in workflow
    assert '- "3.13"' in workflow
    assert '- "3.14"' in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow
    assert "EXPECTED_PYTHON: ${{ matrix.python-version }}" in workflow
