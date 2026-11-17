import os
import ssl

import certifi
import pytest

from playstore_app_audit.platform import certificates


@pytest.mark.parametrize('platform,packaged', [('win32', True), ('linux', True), ('darwin', False)])
def test_other_runtime_trust_selections_are_preserved(monkeypatch, platform, packaged):
    monkeypatch.setattr(certificates.sys, 'platform', platform)
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.delenv('SSL_CERT_DIR', raising=False)
    certificates.configure_packaged_python_trust(packaged=packaged)
    assert 'SSL_CERT_FILE' not in os.environ and 'SSL_CERT_DIR' not in os.environ


@pytest.mark.parametrize('variable', ['SSL_CERT_FILE', 'SSL_CERT_DIR'])
def test_explicit_operator_trust_is_never_replaced(monkeypatch, variable):
    monkeypatch.setattr(certificates.sys, 'platform', 'darwin')
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.delenv('SSL_CERT_DIR', raising=False)
    monkeypatch.setenv(variable, '/operator-selected-trust')
    certificates.configure_packaged_python_trust(packaged=True)
    assert os.environ[variable] == '/operator-selected-trust'
    assert ('SSL_CERT_FILE' in os.environ) == (variable == 'SSL_CERT_FILE')


@pytest.mark.parametrize('kind', ['valid', 'missing', 'malformed'])
def test_packaged_mac_pem_selection_is_relocatable_and_fail_closed(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(certificates.sys, 'platform', 'darwin')
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.delenv('SSL_CERT_DIR', raising=False)
    from pathlib import Path

    bundle = tmp_path / 'relocated' / 'cacert.pem'
    bundle.parent.mkdir()
    if kind != 'missing':
        bundle.write_bytes(Path(certifi.where()).read_bytes() if kind == 'valid' else b'not a PEM')
    monkeypatch.setattr(certifi, 'where', lambda: str(bundle))
    if kind == 'valid':
        certificates.configure_packaged_python_trust(packaged=True)
        assert ssl.get_default_verify_paths().cafile == str(bundle.resolve())
        context = ssl.create_default_context()
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    else:
        with pytest.raises((FileNotFoundError, ssl.SSLError)):
            certificates.configure_packaged_python_trust(packaged=True)
        assert 'SSL_CERT_FILE' not in os.environ
