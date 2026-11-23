from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from audit_runtime_components import module_image
from probe_cpython_openssl4 import classify_link

ROOT = Path(__file__).resolve().parents[1]


def test_builtin_provider_is_reported_without_inventing_an_extension_file() -> None:
    module = SimpleNamespace(__spec__=SimpleNamespace(origin="built-in"))
    result = module_image(module)
    assert result["provider"] == "built-in"
    assert result["origin"] == "built-in"
    assert "sha256" not in result


def test_native_api_probe_distinguishes_link_success_and_removed_methods() -> None:
    assert classify_link(0, "") == "linkable"
    assert classify_link(2, "error LNK2019: unresolved external symbol TLSv1_method") == "blocked-removed-legacy-method-api"


@pytest.mark.parametrize("output", [
    "fatal error C1083: Cannot open include file: openssl/ssl.h",
    "error LNK2019: unresolved external symbol BCryptGenRandom",
    "LNK1112: module machine type x64 conflicts with ARM64",
])
def test_probe_does_not_misreport_environment_failures_as_python_incompatibility(output: str) -> None:
    with pytest.raises(RuntimeError, match="Unexpected compiler/link failure"):
        classify_link(2, output)


def test_six_target_diagnostics_are_sha_guarded_and_cannot_upload_style_or_release_assets() -> None:
    workflow = (ROOT / ".github/workflows/ui-style-audit.yml").read_text(encoding="utf-8")
    assert 'test "$EXPECTED_SHA" = "${{ github.sha }}"' in workflow
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in workflow
    for target in ("windows-x64", "windows-arm64", "linux-x64", "linux-arm64", "macos-x64", "macos-arm64"):
        assert f'"label":"{target}"' in workflow
    for step in workflow.split("      - name: ")[1:]:
        if step.startswith(("Capture ", "Validate audit evidence", "Upload UI audit")):
            assert "!inputs.component_audit" in step
    upload = workflow.split("      - name: Upload non-release component diagnostic evidence", 1)[1]
    assert "always() && inputs.component_audit" in upload
    assert "diagnostic-components-" in upload
    assert "PlayStoreAppAudit-v" not in upload
    assert "pyside6-deploy" not in workflow
    assert "python -m nuitka" not in workflow
