"""Changed native Mac provider/text/data/CA consumers, separate from packaging."""
from __future__ import annotations

import ctypes
import datetime as dt
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from importlib.metadata import version
from pathlib import Path

from probe_qt_ca_security import trust_rejected
from probe_qt_cldr49_runtime import qualify
from verify_native_runtime_pilot import qt_cbor_regressions, qt_markdown_flag_regressions


def private_text_linkage(prefix: Path) -> dict:
    gui = prefix / 'qt/lib/QtGui.framework/Versions/A/QtGui'
    linkage = subprocess.check_output(['otool', '-L', str(gui)], text=True)
    dyld = ctypes.CDLL(None)
    dyld._dyld_image_count.restype = ctypes.c_uint32
    dyld._dyld_get_image_name.argtypes = [ctypes.c_uint32]
    dyld._dyld_get_image_name.restype = ctypes.c_char_p
    paths = {Path(dyld._dyld_get_image_name(i).decode()).resolve() for i in range(dyld._dyld_image_count())}
    result = {}
    for stem in ['libharfbuzz.', 'libmd4c.']:
        selected = [path for path in paths if path.name.startswith(stem)]
        assert len(selected) == 1 and selected[0].is_relative_to(prefix.resolve()), (stem, selected)
        path = selected[0]
        identity = subprocess.check_output(['otool', '-D', str(path)], text=True).splitlines()[1:]
        assert len(identity) == 1 and identity[0].strip() in linkage, (stem, identity, linkage)
        result[stem] = {'loaded': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'install_name': identity[0].strip(), 'consumer': str(gui)}
    return result


def native_text() -> list[dict]:
    from PySide6.QtGui import QFont, QFontDatabase, QRawFont, QTextLayout

    rows = []
    for text, script in [('office', QFontDatabase.WritingSystem.Latin), ('\u0633\u0644\u0627\u0645', QFontDatabase.WritingSystem.Arabic)]:
        for family in QFontDatabase.families(script):
            font = QFont(family, 12)
            raw = QRawFont.fromFont(font)
            if raw.isValid() and all(raw.supportsCharacter(ord(c)) for c in text):
                break
        else:
            raise AssertionError('No actual native font covers the required text')
        layout = QTextLayout(text, font)
        layout.beginLayout()
        line = layout.createLine()
        assert line.isValid()
        line.setLineWidth(500)
        layout.endLayout()
        runs = layout.glyphRuns()
        glyphs = [glyph for run in runs for glyph in run.glyphIndexes()]
        assert glyphs and all(glyph != 0 for glyph in glyphs) and len(set(glyphs)) > 1
        assert line.naturalTextWidth() > 0
        assert all(run.rawFont().familyName() == raw.familyName() for run in runs)
        rows.append({'text': text, 'selected_native_font': raw.familyName(), 'glyphs': glyphs})
    return rows


def qt_incident_security(output: Path, backend: str) -> dict:
    from cryptography import x509
    from PySide6.QtCore import QCryptographicHash
    from PySide6.QtNetwork import QSsl, QSslCertificate, QSslSocket

    assert QSslSocket.activeBackend() == backend
    directory = output / 'provider-security-inputs'
    spec = json.loads((Path(__file__).resolve().parent / 'provider_ca_security_sources.json').read_text())
    for row in spec['sources']:
        assert hashlib.sha256((directory / row['name']).read_bytes()).hexdigest() == row['sha256']
    compromised = json.loads((directory / 'impacted-intermediates.json').read_text())
    keys = {row['spki_sha256'].lower() for row in compromised}
    assert len(keys) == 8
    for row in compromised:
        certificates = QSslCertificate.fromData(row['pem'].encode())
        assert len(certificates) == 1 and certificates[0].isBlacklisted()
        assert bytes(certificates[0].digest(QCryptographicHash.Algorithm.Sha256)).hex() == row['sha256'].lower()
    manual = QSslSocket.isFeatureSupported(QSsl.SupportedFeature.CertificateVerification)
    assert manual or backend == 'securetransport', ('Unexpected missing manual verification', backend)
    rows = []
    with zipfile.ZipFile(directory / 'chains.zip') as archive:
        names = sorted(n for n in archive.namelist() if n.endswith('.pem'))
        assert len(names) == 16
        for name in names:
            data = archive.read(name)
            parsed = x509.load_pem_x509_certificates(data)
            now = dt.datetime.now(dt.UTC)
            assert all(c.not_valid_before_utc <= now < c.not_valid_after_utc for c in parsed), ('Stale fixture', name)
            certificates = QSslCertificate.fromData(data)
            hosts = parsed[0].extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
            assert hosts and not hosts[0].startswith('*')
            blocked = [c for c in certificates if c.isBlacklisted()]
            blocked_keys = {hashlib.sha256(bytes(c.publicKey().toDer())).hexdigest() for c in blocked}
            assert keys.intersection(blocked_keys), (backend, name, 'Missing compromised-key blacklist')
            if manual:
                errors = QSslCertificate.verify(certificates, hosts[0])
                labels = [e.error().name for e in errors]
                assert 'CertificateBlacklisted' in labels, (backend, name, labels)
            else:
                # SecureTransport has no manual certificate verifier. Its empty
                # verify() result is not evidence of trust or a blacklist guard.
                # Inspect the actual compiled blacklist, then require native TLS
                # refusal below; never switch providers to manufacture success.
                labels = None
            row = {'fixture': name, 'provided_chain_errors': labels,
                   'blacklisted_spki': sorted(blocked_keys),
                   'kind': 'offline supplied-chain guard' if manual else 'offline blacklist inspection; manual verification unsupported'}
            if 'rollover/' not in name:
                socket = QSslSocket()
                socket.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
                actual_errors = []
                socket.sslErrors.connect(lambda errors, collected=actual_errors: collected.extend(e.error().name for e in errors))
                socket.connectToHostEncrypted(hosts[0], 443)
                accepted = socket.waitForEncrypted(10000)
                peers = socket.peerCertificateChain()
                actual_keys = {hashlib.sha256(bytes(c.publicKey().toDer())).hexdigest() for c in peers}
                socket.abort()
                assert not accepted and trust_rejected(actual_errors) and keys.intersection(actual_keys), (backend, name, actual_errors, socket.errorString())
                row.update(kind='actual default-trust TLS refusal', socket_errors=actual_errors,
                           compromised_peer_keys=sorted(keys.intersection(actual_keys)))
            rows.append(row)
    assert sum(r['kind'] == 'actual default-trust TLS refusal' for r in rows) == 14
    result = {'backend': backend, 'cases': rows, 'native_tls_refusals': 14, 'offline_guard_refusals': 2 if manual else 0, 'offline_blacklist_checks': 2, 'manual_verification_supported': manual,
              'scope': 'Actual provider14 native default-trust TLS refusals plus16 compiled blacklist inspections; manual supplied-chain refusal only when supported; not raw OS root revocation'}
    (output / ('qt-incident-' + backend + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    return result


def verify_maintenance(output: Path, prefix: Path, arch: str) -> dict:
    import _ctypes
    import _decimal
    import _sqlite3
    import zlib

    import _cffi_backend
    import cffi

    assert _sqlite3.sqlite_version == '3.54.1' and _decimal.__libmpdec_version__ == '4.0.1' and zlib.ZLIB_RUNTIME_VERSION == '1.4'
    assert cffi.__version__ == _cffi_backend.__version__ == '2.1.1'
    assert version('cffi') == ('2.1.1+psaa.libffi380' if arch == 'arm64' else '2.1.1')
    ffi = ctypes.CDLL(str(prefix / 'lib/libffi.8.dylib'))
    ffi.ffi_get_version.restype = ctypes.c_char_p
    assert ffi.ffi_get_version() == b'3.8.0'
    linkage = {}
    for module, stem in [(_ctypes, 'libffi'), (_sqlite3, 'libsqlite3'), (_decimal, 'libmpdec'), (_cffi_backend, 'libffi')]:
        text = subprocess.check_output(['otool', '-L', module.__file__], text=True)
        selected = [line.strip() for line in text.splitlines()[1:] if stem in line]
        assert selected and all('/usr/lib/' not in line for line in selected), (module.__file__, selected)
        linkage[module.__name__] = selected
    cases = list(ET.parse(output / 'cpython-codec-regressions.xml').getroot().iter('testcase'))
    assert not any(c.find(t) is not None for c in cases for t in ['error', 'failure'])
    counts = {name: sum(name in (c.get('classname', '') + '.' + c.get('name', '')) and c.find('skipped') is None and c.get('status') != 'notrun' for c in cases)
              for name in ['test_lzma', 'test_zstd', 'test_zlib', 'test_ctypes', 'test_decimal', 'test_sqlite3']}
    assert all(counts.values()), counts
    cffi_cases = list(ET.parse(output / 'cffi-runtime-tests.xml').getroot().iter('testcase'))
    assert cffi_cases and not any(c.find(t) is not None for c in cffi_cases for t in ['error', 'failure'])
    assert any(c.get('name') == 'test_call_function_9' and c.find('skipped') is None for c in cffi_cases)
    result = {'stdlib_provider_linkage': linkage, 'libffi': '3.8.0', 'stdlib_executed_cases': counts,
              'private_qt_text_linkage': private_text_linkage(prefix),
              'cffi_distribution': version('cffi'), 'cffi_executed': sum(c.find('skipped') is None for c in cffi_cases),
              'cbor': qt_cbor_regressions(), 'native_font_shaping': native_text(),
              'markdown': qt_markdown_flag_regressions(), 'cldr49': qualify(output / 'qt-cldr49-runtime-input.xml'),
              'qt_openssl_incident_security': qt_incident_security(output, 'openssl')}
    (output / 'macos-maintenance-consumers.json').write_text(json.dumps(result, indent=2) + '\n')
    return result
