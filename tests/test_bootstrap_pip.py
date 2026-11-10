from __future__ import annotations

import hashlib
import io
import ssl
from pathlib import Path

import bootstrap_pip as bootstrap
import pytest


class Response(io.BytesIO):
    def __init__(self, payload: bytes, url: str = 'https://files.pythonhosted.org/pip.whl') -> None:
        super().__init__(payload)
        self.url = url

    def geturl(self) -> str:
        return self.url


def test_bootstrap_verifies_tls_hash_and_installs_only_offline(tmp_path, monkeypatch):
    payload = b'verified wheel fixture'
    monkeypatch.setattr(bootstrap, 'SHA256', hashlib.sha256(payload).hexdigest())

    def open_url(url, *, context, timeout):
        assert url == bootstrap.URL and timeout > 0
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        return Response(payload)

    calls = []
    monkeypatch.setattr(bootstrap.urllib.request, 'urlopen', open_url)
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda args, **kwargs: calls.append((args, kwargs)))
    bootstrap.bootstrap(tmp_path)
    install, verify = calls
    assert install[0][-1].endswith('.whl')
    assert all(flag in install[0] for flag in ['--isolated', '--disable-pip-version-check', '--no-index', '--no-deps', '--no-cache-dir'])
    assert install[1]['check'] and verify[1]['check']
    assert not any(arg.startswith(('http:', 'https:')) for arg in install[0])


@pytest.mark.parametrize('failure', ['hash', 'downgrade', 'tls'])
def test_bootstrap_failures_never_invoke_installer(tmp_path, monkeypatch, failure):
    calls = []

    def open_url(*args, **kwargs):
        if failure == 'tls':
            raise ssl.SSLCertVerificationError('untrusted peer')
        return Response(b'corrupt fixture', 'http://bad.invalid/' if failure == 'downgrade' else bootstrap.URL)

    monkeypatch.setattr(bootstrap.urllib.request, 'urlopen', open_url)
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    with pytest.raises((ValueError, ssl.SSLCertVerificationError)):
        bootstrap.bootstrap(tmp_path)
    assert not calls


def test_tool_diagnostic_requires_explicit_mode_and_excludes_expensive_profiles():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / '.github/workflows/ui-style-audit.yml').read_text(encoding='utf-8')
    job = workflow.split('  native-toolchain-delta:', 1)[1].split('\n  capture:', 1)[0]
    assert "if: ${{ inputs.linux_arm64_pilot == 'tools' || inputs.linux_arm64_pilot == 'tools-scons' }}" in job
    for flag in ['component_audit', 'runtime_pilot', 'windows_runtime_pilot',
                 'windows_arm64_runtime_probe', 'windows_arm64_host_tools',
                 'windows_arm64_full_pilot', 'windows_prerequisites_only', 'trust_diagnostics_only']:
        assert "test '${{ inputs." + flag + " }}' = false" in job
    for label in ['windows-x64', 'windows-arm64', 'linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64']:
        assert 'label: ' + label + ',' in job
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in job
    assert 'verify_toolchain_delta.py' in job
    assert not any(token in job for token in ['build_native_runtime_pilot', 'build_windows_runtime_pilot',
                                            'build_macos_', 'assemble-release', 'sign-windows', 'secrets.'])
