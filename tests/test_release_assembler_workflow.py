from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/assemble-release.yml"


def test_release_assembler_workflow_is_manual_and_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "\n  workflow_run:" not in text

    for input_name in (
        "expected_sha:",
        "windows_run_id:",
        "linux_run_id:",
        "macos_run_id:",
    ):
        assert input_name in text

    assert "desktop_run_id:" not in text

    assert "contents: read" in text
    assert "actions: read" in text

    assert "actions/checkout@v7" in text
    assert "ref: ${{ github.sha }}" in text
    assert 'DISPATCH_REF: ${{ github.ref }}' in text
    assert '"refs/heads/main"' in text

    assert "Build Windows - Qt6" in text
    assert "Build Linux - Qt6 (manual)" in text
    assert "Build macOS - Qt6 (manual)" in text
    assert "Build macOS / Linux - Qt6 (manual)" not in text
    assert '"workflow_dispatch"' in text
    assert '"completed"' in text
    assert '"success"' in text
    assert 'run.get("head_sha"' in text
    assert "Windows, Linux and macOS run IDs must be different" in text

    assert text.count("actions/download-artifact@v8") == 3
    assert text.count("github-token: ${{ github.token }}") == 3
    assert text.count("repository: ${{ github.repository }}") == 3

    assert (
        "PlayStoreAppAudit-v${{ "
        "steps.project_version.outputs.version }}-windows-*"
    ) in text
    assert (
        "PlayStoreAppAudit-v${{ "
        "steps.project_version.outputs.version }}-linux-*"
    ) in text
    assert (
        "PlayStoreAppAudit-v${{ "
        "steps.project_version.outputs.version }}-macos-*"
    ) in text

    assert "run-id: ${{ inputs.windows_run_id }}" in text
    assert "run-id: ${{ inputs.linux_run_id }}" in text
    assert "run-id: ${{ inputs.macos_run_id }}" in text

    assert "assemble_release_assets.py" in text
    assert '--expected-sha "$EXPECTED_SHA"' in text
    assert "--require-all-platforms" in text
    assert 'test "$asset_count" = "8"' in text

    assert text.count("actions/upload-artifact@v7") == 1
    assert "final-release/" in text

    forbidden = (
        "pyside6-deploy",
        "build_windows_standalone.ps1",
        "gh release",
        "git tag",
        "create-release",
        "softprops/action-gh-release",
    )
    for marker in forbidden:
        assert marker not in text
