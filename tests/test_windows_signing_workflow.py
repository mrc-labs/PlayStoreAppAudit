from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/sign-windows.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_windows_signing_is_manual_exact_sha_and_source_run_guarded() -> None:
    text = _workflow()

    assert "workflow_dispatch:" in text
    assert "\n  push:" not in text
    assert "\n  pull_request:" not in text
    assert "expected_sha:" in text
    assert "build_run_id:" in text
    assert 'DISPATCH_REF: ${{ github.ref }}' in text
    assert '"refs/heads/main"' in text
    assert '"Build Windows - Qt6"' in text
    assert '"workflow_dispatch"' in text
    assert '"completed"' in text
    assert '"success"' in text
    assert 'run.get("head_sha"' in text
    assert "head_repository" in text


def test_windows_signing_uses_public_trust_action_on_supported_runner() -> None:
    text = _workflow()

    assert "runs-on: windows-2025" in text
    assert "azure/login@v3" in text
    assert "azure/artifact-signing-action@v2" in text
    assert "id-token: write" in text
    assert "WINDOWS_ARTIFACT_SIGNING_ENDPOINT" in text
    assert "WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME" in text
    assert "WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME" in text
    assert "files: ${{ steps.prepare.outputs.app_exe }}" in text
    assert "files-folder:" not in text
    assert "files-folder-filter:" not in text
    assert "correlation-id:" not in text
    assert "file-digest: SHA256" in text
    assert "timestamp-rfc3161: http://timestamp.acs.microsoft.com" in text
    assert "timestamp-digest: SHA256" in text


def test_windows_signing_changes_only_owned_primary_executable_and_build_info() -> None:
    text = _workflow()

    assert "Expected exactly one top-level PlayStoreAppAudit.exe" in text
    assert "Signing folder must contain exactly one top-level EXE" in text
    assert "Get-AuthenticodeSignature" in text
    assert "Status -ne 'NotSigned'" in text
    assert "non-signing-target-sha256.json" in text
    assert "Non-signing-target file changed during signing" in text
    assert "Microsoft Artifact Signing Public Trust" in text
    assert "TimeStamperCertificate" in text


def test_windows_signing_refreshes_strict_legal_evidence_before_repack() -> None:
    text = _workflow()

    refresh = text.index("--refresh-runtime-evidence")
    validate = text.index("validate_release_legal_bundle.py")
    archive = text.index("Compress-Archive -LiteralPath $env:PACKAGE_DIR")

    assert refresh < validate < archive
    assert "--public" in text
    assert "validate_windows_standalone.py" in text
    assert "LEGAL-MANIFEST.json leaked" in text
    assert "validation-evidence leaked" in text


def test_windows_signing_has_native_post_sign_verification_for_both_arches() -> None:
    text = _workflow()

    assert "Verify signed Windows ${{ matrix.arch }} package natively" in text
    assert "runner: windows-2025" in text
    assert "runner: windows-11-arm" in text
    assert "expected_runner_arch: X64" in text
    assert "expected_runner_arch: ARM64" in text
    assert "expected_pe_machine: \"0x8664\"" in text
    assert "expected_pe_machine: \"0xAA64\"" in text
    assert "Signed packaged application smoke test failed" in text


def test_windows_signing_uses_preflight_version_for_matrix_artifacts() -> None:
    text = _workflow()

    assert "version: ${{ steps.project_version.outputs.version }}" in text
    assert text.count("needs.preflight.outputs.version") >= 5
    assert "needs.sign-windows.outputs.version" not in text
    assert "PlayStoreAppAudit-v${{ needs.preflight.outputs.version }}-windows-${{ matrix.arch }}" in text
