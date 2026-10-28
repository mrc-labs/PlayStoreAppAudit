from __future__ import annotations

import hashlib
import json
import ssl
import struct
import zlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import verify_native_runtime_pilot as pilot
from verify_native_runtime_pilot import (
    default_trust_handshake,
    executed_upstream_suites,
    png_fixture,
    qt_fixture_response,
)

ROOT = Path(__file__).resolve().parents[1]


def test_qt_fixture_response_accepts_already_buffered_data_without_waiting(monkeypatch) -> None:
    connection = MagicMock()
    connection.readAll.return_value = b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n'
    wait = MagicMock(side_effect=AssertionError('Buffered response must not wait for new data'))
    monkeypatch.setattr(pilot.threading, 'Event', MagicMock(return_value=MagicMock(wait=wait)))
    assert b'200 OK' in qt_fixture_response(connection)
    wait.assert_not_called()


def test_qt_fixture_response_does_not_accept_a_missing_http_reply(monkeypatch) -> None:
    connection = MagicMock()
    connection.readAll.return_value = b''
    monkeypatch.setattr(pilot.time, 'monotonic', MagicMock(side_effect=[0, 6]))
    with pytest.raises(AssertionError, match='response timed out'):
        qt_fixture_response(connection)


def test_qt_tls_fixture_can_serve_response_from_a_python_thread(tmp_path: Path) -> None:
    from PySide6.QtNetwork import QSslCertificate, QSslConfiguration, QSslSocket
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    assert app
    paths = pilot.certificate_material(tmp_path)
    connection = QSslSocket()
    config = QSslConfiguration.defaultConfiguration()
    config.setCaCertificates(QSslCertificate.fromData(paths['ca'].read_bytes()))
    config.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
    connection.setSslConfiguration(config)
    connection.setPeerVerifyName('localhost')
    with pilot.tls_server(paths) as port:
        connection.connectToHostEncrypted('127.0.0.1', port)
        assert connection.waitForEncrypted(5000), connection.errorString()
        connection.write(b'GET / HTTP/1.0\r\n\r\n')
        assert b'200 OK' in qt_fixture_response(connection)
        connection.abort()


@pytest.mark.parametrize('failure', [None, ssl.SSLCertVerificationError('untrusted'), TimeoutError('offline')])
def test_default_trust_requires_authenticated_handshake_and_accepts_lazy_ca_loading(monkeypatch, failure) -> None:
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    monkeypatch.delenv('SSL_CERT_DIR', raising=False)
    context = MagicMock(verify_mode=ssl.CERT_REQUIRED, check_hostname=True)
    context.cert_store_stats.side_effect = [{'x509_ca': 0}, {'x509_ca': 1}]
    create_context = MagicMock(return_value=context)
    monkeypatch.setattr(pilot.ssl, 'create_default_context', create_context)
    raw = MagicMock()
    monkeypatch.setattr(pilot.socket, 'create_connection', MagicMock(return_value=raw))
    connection = context.wrap_socket.return_value.__enter__.return_value
    connection.getpeercert.return_value = b'authenticated peer DER'
    connection.version.return_value = 'TLSv1.3'
    if failure:
        context.wrap_socket.side_effect = failure
        with pytest.raises(type(failure)):
            default_trust_handshake()
    else:
        result = default_trust_handshake()
        assert result['store_before']['x509_ca'] == 0
        assert result['store_after']['x509_ca'] == 1
        assert result['result'] == 'default-trust authenticated handshake PASS'
        connection.getpeercert.assert_called_once_with(binary_form=True)
    create_context.assert_called_once_with()
    context.wrap_socket.assert_called_once_with(raw.__enter__.return_value, server_hostname='www.python.org')


@pytest.mark.parametrize('variable', ['SSL_CERT_FILE', 'SSL_CERT_DIR'])
def test_default_trust_probe_cannot_hide_an_environment_override(monkeypatch, variable) -> None:
    monkeypatch.setenv(variable, 'injected-trust')
    with pytest.raises(AssertionError):
        default_trust_handshake()


def test_cpython_name_only_junit_dialect_counts_executed_cases(tmp_path: Path) -> None:
    path = tmp_path / 'upstream.xml'
    path.write_text('''<testsuites tests="4" errors="0" failures="0"><testsuite>
      <testcase name="test.test_ssl.ContextTests.test_verify" status="run" result="completed"/>
      <testcase name="test.test_ssl.NetworkTests.test_network"><skipped/></testcase>
      <testcase name="test.test_hashlib.HashLibTestCase.test_sha256"/>
      <testcase name="test.test_hmac.HMACTestCase.test_digest"/>
    </testsuite></testsuites>''', encoding='utf-8')
    assert executed_upstream_suites(path) == {'test_ssl': 1, 'test_hashlib': 1, 'test_hmac': 1}


def test_other_passing_suites_cannot_hide_a_skipped_ssl_suite(tmp_path: Path) -> None:
    path = tmp_path / 'upstream.xml'
    path.write_text('''<testsuites><testsuite>
      <testcase name="test.test_ssl.ContextTests.test_verify"><skipped/></testcase>
      <testcase name="test.test_hashlib.HashLibTestCase.test_sha256"/>
      <testcase name="test.test_hmac.HMACTestCase.test_digest"/>
    </testsuite></testsuites>''', encoding='utf-8')
    with pytest.raises(RuntimeError, match='test_ssl was skipped'):
        executed_upstream_suites(path)


def test_pilot_patch_and_official_sources_are_hash_bound() -> None:
    spec = json.loads((ROOT / '.github/scripts/native_runtime_pilot_sources.json').read_text())
    patch = spec['cpython_patch']
    assert hashlib.sha256((ROOT / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    assert len(spec['sources']) == 8
    for item in [*spec['sources'], spec['cxx_link_sdk'], spec['cxx_link_sdk']['source'],
                 spec['extractor'], spec['extractor']['source']]:
        assert item['url'].startswith('https://')
        assert len(item['sha256']) == 64
        assert int(item['sha256'], 16) > 0


@pytest.mark.parametrize('outcome', ['', '<skipped/>', '<error/>', '<failure/>', 'notrun', 'absent'])
@pytest.mark.parametrize('tar_outcome', ['passed', 'skipped', 'absent'])
def test_security_gate_requires_both_actual_upstream_regressions(tmp_path: Path, outcome: str, tar_outcome: str) -> None:
    from verify_native_runtime_pilot import executed_cpython_security

    xml, log = tmp_path / 'ssl.xml', tmp_path / 'tar.log'
    status = 'status="notrun"' if outcome == 'notrun' else ''
    body = outcome if outcome.startswith('<') else ''
    name = 'other' if outcome == 'absent' else 'test.test_ssl.MemoryBIOTests.test_distrusted_spki'
    xml.write_text(f'<testsuite><testcase name="{name}" {status}>{body}</testcase></testsuite>')
    text = 'test_link_at_destination ... ok\nRan 1 test\n\nOK\n'
    log.write_text(text if tar_outcome == 'passed' else text.replace('ok', 'skipped') if tar_outcome == 'skipped' else 'Ran 1 test\n\nOK\n')
    if outcome or tar_outcome != 'passed':
        with pytest.raises(RuntimeError, match='Executed CPython'):
            executed_cpython_security(xml, log)
    else:
        assert len(executed_cpython_security(xml, log)) == 2


def test_malformed_metadata_corpus_has_valid_crc_and_spec_chunk_order() -> None:
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        image = png_fixture(kind, b'not-deflate')
        assert image.startswith(b'\x89PNG\r\n\x1a\n')
        position, chunks = 8, []
        while position < len(image):
            size = struct.unpack_from('!I', image, position)[0]
            chunk = image[position + 4:position + 8 + size]
            crc = struct.unpack_from('!I', image, position + 8 + size)[0]
            assert crc == zlib.crc32(chunk)
            chunks.append(chunk[:4])
            position += size + 12
        expected = [b'IHDR', kind, b'IDAT', b'IEND'] if kind == b'iCCP' else [b'IHDR', b'IDAT', kind, b'IEND']
        assert chunks == expected
        assert position == len(image)


def test_native_pilot_is_single_target_sha_guarded_and_cannot_produce_a_candidate() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    capture, pilot = workflow.split('\n  runtime-pilot:', 1)
    assert "if: ${{ !inputs.runtime_pilot && !inputs.windows_runtime_pilot && !inputs.windows_arm64_runtime_probe && !inputs.windows_arm64_host_tools && !inputs.windows_arm64_full_pilot && (!inputs.linux_arm64_pilot || inputs.linux_arm64_pilot == 'off') }}" in capture
    assert 'runs-on: ubuntu-22.04' in pilot
    assert 'matrix:' not in pilot
    assert 'test "$EXPECTED_SHA" = "${{ github.sha }}"' in pilot
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in pilot
    assert 'diagnostic-runtime-framework-' in pilot
    assert 'PlayStoreAppAudit-v' not in pilot
    builder = (ROOT / '.github/scripts/build_native_runtime_pilot.sh').read_text()
    for excluded in ('docker ', 'pyside6-deploy', 'python -m nuitka', 'sign-windows', 'assemble-release'):
        assert excluded not in builder
