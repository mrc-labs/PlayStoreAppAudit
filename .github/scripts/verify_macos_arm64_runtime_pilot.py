"""Verify one native source prefix and explicit macOS TLS/trust integrations."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import hmac
import json
import os
import platform
import re
import ssl
import subprocess
import sys
import sysconfig
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from probe_macos_arm64_runtime import contract, macho
from verify_native_runtime_pilot import (
    certificate_material,
    default_trust_handshake,
    executed_cpython_security,
    png_fixture,
    python_tls_checks,
    qt_fixture_response,
    tls_server,
)


def loaded_images() -> list[Path]:
    dyld = ctypes.CDLL(None)
    count = dyld._dyld_image_count
    count.restype = ctypes.c_uint32
    name = dyld._dyld_get_image_name
    name.argtypes = [ctypes.c_uint32]
    name.restype = ctypes.c_char_p
    return sorted({Path(name(i).decode()).resolve() for i in range(count())})


def executed_codec_suites(path: Path) -> dict[str, int]:
    cases = list(ET.parse(path).getroot().iter('testcase'))
    assert not any(case.find('error') is not None or case.find('failure') is not None for case in cases)
    counts = {module: sum(module in (case.get('classname', '') + '.' + case.get('name', '')) and case.get('status') != 'notrun' and case.find('skipped') is None for case in cases) for module in ('test_lzma', 'test_zstd')}
    assert all(counts.values()), 'Both native CPython codec suites must actually execute'
    return counts


def allowed_origin(path: Path, prefix: Path, venv: Path) -> bool:
    return path.is_relative_to(prefix) or path.is_relative_to(venv) or path.as_posix().startswith(('/System/', '/usr/lib/', '/Library/Apple/System/'))


def qt_checks(paths: dict[str, Path], backend: str) -> dict:
    from PySide6.QtNetwork import QSsl, QSslCertificate, QSslConfiguration, QSslSocket

    assert QSslSocket.setActiveBackend(backend) and QSslSocket.activeBackend() == backend
    build, runtime = QSslSocket.sslLibraryBuildVersionString(), QSslSocket.sslLibraryVersionString()
    if backend == 'openssl':
        assert build.startswith('OpenSSL 4.0.3 ') and runtime.startswith('OpenSSL 4.0.3 '), (build, runtime)
    roots = QSslConfiguration.defaultConfiguration().caCertificates()
    cases = [('TLS1.2', QSsl.SslProtocol.TlsV1_2, 'localhost', True, 'valid', True)]
    if backend == 'openssl':
        cases += [('TLS1.3', QSsl.SslProtocol.TlsV1_3, 'localhost', True, 'valid', True)]
    # SecureTransport supports TLS1.2, not TLS1.3. Do not claim a skipped
    # unsupported native handshake as a passing OpenSSL protocol test.
    cases += [('hostname', QSsl.SslProtocol.SecureProtocols, 'wrong.invalid', True, 'valid', False),
              ('untrusted CA', QSsl.SslProtocol.SecureProtocols, 'localhost', False, 'valid', False),
              ('expired', QSsl.SslProtocol.SecureProtocols, 'localhost', True, 'expired', False)]
    rows = []
    for label, protocol, hostname, trusted, cert, expected in cases:
        connection = QSslSocket()
        configuration = QSslConfiguration.defaultConfiguration()
        configuration.setCaCertificates(QSslCertificate.fromData(paths['ca'].read_bytes()) if trusted else [])
        configuration.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
        configuration.setProtocol(protocol)
        connection.setSslConfiguration(configuration)
        connection.setPeerVerifyName(hostname)
        errors = []
        connection.sslErrors.connect(lambda values, selected=errors: selected.extend(e.error().name for e in values))
        with tls_server(paths, cert) as port:
            connection.connectToHostEncrypted('127.0.0.1', port)
            encrypted = connection.waitForEncrypted(5000)
            assert encrypted == expected, (backend, label, encrypted, connection.errorString(), errors)
            if expected:
                assert not errors
                connection.write(b'GET / HTTP/1.0\r\n\r\n')
                connection.waitForBytesWritten(1000)
                assert b'200 OK' in qt_fixture_response(connection)
            else:
                assert errors, (backend, label)
            rows.append({'case': label, 'encrypted': encrypted, 'errors': errors, 'protocol': connection.sessionProtocol().name, 'result': 'PASS'})
            connection.abort()
    # A fresh default configuration: no fixture cafile or CA override here.
    connection = QSslSocket()
    configuration = QSslConfiguration.defaultConfiguration()
    assert configuration.caCertificates() == roots
    configuration.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
    connection.setSslConfiguration(configuration)
    connection.setPeerVerifyName('www.python.org')
    errors = []
    connection.sslErrors.connect(lambda values: errors.extend(e.error().name for e in values))
    connection.connectToHostEncrypted('www.python.org', 443)
    assert connection.waitForEncrypted(20000) and not errors and not connection.peerCertificate().isNull(), (backend, errors, connection.errorString())
    rows.append({'case': 'default trust / www.python.org', 'encrypted': True, 'protocol': connection.sessionProtocol().name, 'errors': errors, 'result': 'PASS'})
    connection.abort()
    system_roots = QSslConfiguration.systemCaCertificates()
    fingerprints = {hashlib.sha256(bytes(cert.toDer())).hexdigest() for cert in system_roots}
    root_text = (paths['ca'].parent.parent / 'keychain-system-roots.pem').read_text()
    keychain = {hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest() for pem in re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', root_text, re.S)}
    intersection = sorted(fingerprints & keychain)
    assert intersection, 'Qt defaults must retain evidenced system-root anchors'
    return {'backend': backend, 'build': build, 'runtime': runtime, 'default_ca_count': len(roots), 'system_ca_count': len(system_roots), 'keychain_system_root_intersection': len(intersection), 'cases': rows,
            'protocol_limit': 'SecureTransport legacy TLS1.2 only; not an OpenSSL4/TLS1.3 provider' if backend == 'securetransport' else 'TLS1.2 and TLS1.3 qualified',
            'trust': 'native Keychain API' if backend == 'securetransport' else 'Qt default verification; Qt system-root collection intersects Keychain; not a claim of Python certifi integration',
            'loaded_images': list(map(str, loaded_images()))}


def changed_images(prefix: Path, paths: list[Path]) -> list[dict]:
    assert not any(re.search(r'lib(?:ssl|crypto)[.\-]3', p.name) for p in paths), 'OpenSSL3 fallback rejected'
    assert not any('libclang' in str(p).lower() for p in paths), 'Build-host parser leaked into runtime'
    assert not any(str(p).startswith(('/opt/homebrew/', '/usr/local/', '/Library/Frameworks/Python.framework')) for p in paths), 'Foreign build/SDK provider loaded'
    assert all(allowed_origin(p, prefix, Path(sys.prefix).resolve()) for p in paths), ('Foreign non-system runtime image', [str(p) for p in paths if not allowed_origin(p, prefix, Path(sys.prefix).resolve())])
    rows = []
    for path in paths:
        if not (path.is_relative_to(prefix) or path.is_relative_to(Path(sys.prefix).resolve())):
            continue
        assert path.is_file(), path
        controlled = path.is_relative_to(prefix) or any(part in ('PySide6', 'shiboken6') for part in path.parts)
        row = macho(path, target=True, allow_universal=not controlled, output=Path(os.environ['PILOT_EVIDENCE']))
        signature = subprocess.run(['codesign', '-dv', '--verbose=2', str(path)], text=True, capture_output=True)
        row['signature'] = {'inspection_returncode': signature.returncode, 'detail': signature.stdout + signature.stderr, 'action': 'inspection only; no credential activation or production signing'}
        assert not any('/opt/homebrew' in p or '/usr/local/' in p for p in row['rpaths']), row
        if 'cryptography' in path.parts and path.name.startswith('_rust'):
            assert not any(re.search(r'lib(?:crypto|ssl)', value, re.I) for value in row['dependencies']), 'Independent cryptography must retain static OpenSSL'
        rows.append(row)
    return rows


def images(prefix: Path, output: Path) -> dict:
    paths = loaded_images()
    rows = changed_images(prefix, paths)
    for stem, origin in [('libpython3.14', prefix / 'python'), ('libssl.4.dylib', prefix / 'openssl'), ('libcrypto.4.dylib', prefix / 'openssl')]:
        found = [p for p in paths if p.name.startswith(stem)]
        assert found and all(p.is_relative_to(origin) for p in found), (stem, found)
    executable = next(row for row in rows if Path(row['path']) == Path(sys.executable).resolve())
    python_library = next(row for row in rows if Path(row['path']).name.startswith('libpython3.14'))
    assert executable['minimum_os'] == python_library['minimum_os'] == ['11.0'], 'Preserve the Python executable/library deployment separately from Qt/package ceiling'
    qt = [p for p in paths if re.match(r'Qt\w+', p.name) and '.framework' in str(p)]
    assert qt and all(p.is_relative_to(prefix / 'qt') for p in qt), qt
    png = next(p for p in paths if p.name.startswith('libpng16') and p.is_relative_to(prefix))
    query = ctypes.CDLL(str(png)).png_get_libpng_ver
    query.restype = ctypes.c_char_p
    assert query(None) == b'1.6.59'
    pcre = next(p for p in paths if p.name.startswith('libpcre2-16') and p.is_relative_to(prefix))
    value = ctypes.create_string_buffer(128)
    assert ctypes.CDLL(str(pcre)).pcre2_config_16(11, value) >= 0
    pcre_version = value.raw.decode('utf-16-le').split('\0', 1)[0]
    assert pcre_version.startswith('10.49 ')
    codecs = {}
    for stem, function, expected in [('liblzma.', 'lzma_version_string', '5.8.4'), ('libzstd.', 'ZSTD_versionString', '1.5.7')]:
        library = next(p for p in paths if p.name.startswith(stem) and p.is_relative_to(prefix))
        query = getattr(ctypes.CDLL(str(library)), function)
        query.restype = ctypes.c_char_p
        assert query().decode() == expected
        codecs[stem] = {'version': expected, 'path': str(library)}
    for stem, expected in [('_lzma.', 'liblzma.'), ('_zstd.', 'libzstd.')]:
        module = next(row for row in rows if Path(row['path']).name.startswith(stem))
        dependencies = [name for name in module['dependencies'] if expected in name]
        assert dependencies and not any(name.startswith('/usr/lib/') for name in dependencies), ('Stdlib codec must link controlled source', module)
    report = {'changed': rows, 'all_loaded': list(map(str, paths)), 'python_executable': executable['path'], 'python_executable_minos': executable['minimum_os'], 'libpng': '1.6.59', 'pcre2': pcre_version, 'codecs': codecs, 'maximum_minos': max((v for row in rows for v in row['minimum_os']), key=lambda v: tuple(map(int, v.split('.')))), 'limit': 'Loaded source-prefix closure only; not all-file package/ADB or older-OS acceptance'}
    (output / 'macho-loaded-images.json').write_text(json.dumps(report, indent=2))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--native-prerequisites', action='store_true')
    parser.add_argument('--qt-native-backend', action='store_true')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    os.environ['QT_SSL_USE_TEMPORARY_KEYCHAIN'] = '1'
    assert sys.platform == 'darwin' and platform.machine() == 'arm64' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH'):
        assert not os.environ.get(name), ('Trust/loader override rejected', name)
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    assert app.platformName() == 'cocoa'
    certs = output / ('prerequisite-certificates' if args.native_prerequisites else 'native-certificates' if args.qt_native_backend else 'isolated-certificates')
    certs.mkdir()
    paths = certificate_material(certs)
    if args.native_prerequisites or args.qt_native_backend:
        if args.qt_native_backend:
            assert platform.python_version() == '3.14.10' and ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
            assert Path(sys.base_prefix).resolve() == Path(os.environ['PILOT_PREFIX']) / 'python'
        report = qt_checks(paths, 'securetransport')
        if args.qt_native_backend:
            report['changed_images'] = changed_images(Path(os.environ['PILOT_PREFIX']), loaded_images())
        report.update(source_sha=os.environ['GITHUB_SHA'], scope='stock native backend prerequisite only' if args.native_prerequisites else 'controlled Qt native backend; separate from OpenSSL')
        (output / ('native-tls-prerequisites.json' if args.native_prerequisites else 'qt-securetransport.json')).write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2), flush=True)
        return
    arm, base = contract()
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    assert platform.python_version() == arm['python_version'] and Path(sys.base_prefix).resolve() == prefix / 'python'
    assert Path(ssl.__file__).resolve().is_relative_to(prefix / 'python') and ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    import _hashlib
    import lzma
    from compression import zstd

    import certifi
    import PySide6
    import shiboken6
    from cryptography.hazmat.backends.openssl.backend import backend
    from PySide6.QtGui import QImage, QPixmap

    assert PySide6.__version__ == shiboken6.__version__ == qVersion() == '6.12.0'
    assert zlib.ZLIB_RUNTIME_VERSION == '1.3.2'
    assert lzma.decompress(lzma.compress(b'native')) == zstd.decompress(zstd.compress(b'native')) == b'native'
    codec_suites = executed_codec_suites(output / 'cpython-codec-regressions.xml')
    assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
    trust_file = prefix / 'trust/cert.pem'
    assert Path(ssl.get_default_verify_paths().cafile).resolve() == trust_file
    assert trust_file.read_bytes() == Path(certifi.where()).read_bytes()
    assert certifi.__version__ == '2026.10.23'
    defaults = default_trust_handshake()
    defaults.update(integration='private default OpenSSL PEM/certifi2026.10.23, not Keychain', cafile=str(trust_file), pem_sha256=hashlib.sha256(trust_file.read_bytes()).hexdigest())
    python_tls = python_tls_checks(paths)
    security = executed_cpython_security(output / 'cpython-regressions.xml', output / 'tarfile-security-regression.log')
    assert _hashlib.openssl_sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert hmac.digest(b'key', b'The quick brown fox jumps over the lazy dog', 'sha256').hex() == 'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8'
    assert hashlib.pbkdf2_hmac('sha256', b'password', b'salt', 1).hex() == '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    from PySide6.QtNetwork import QSslSocket

    default_qt_backend = QSslSocket.activeBackend()
    assert default_qt_backend in ('openssl', 'securetransport'), default_qt_backend
    qt_tls = qt_checks(paths, 'openssl')
    subprocess.run([sys.executable, __file__, '--output-dir', str(output), '--qt-native-backend'], check=True)
    pixmap = QPixmap()
    assert QImage.fromData(png_fixture()).width() == 1 and pixmap.loadFromData(png_fixture())
    png_rows = []
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        for index, compressed in enumerate((b'x\x9c\x00', zlib.compress(b'metadata' * 64)[:-2], b'not-deflate')):
            fixture = png_fixture(kind, compressed)
            (output / f'malformed-{kind.decode()}-{index}.png').write_bytes(fixture)
            image = QImage.fromData(fixture)
            pixmap.loadFromData(fixture)
            png_rows.append({'kind': kind.decode(), 'case': index, 'decoded': not image.isNull(), 'result': 'no native crash; regression corpus, not exploit reproduction'})
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    profile = Path(os.environ['PILOT_WORK']) / 'profile'
    profile.mkdir(exist_ok=True)
    (profile / 'PlayStoreAppAudit.portable').write_text('isolated diagnostic profile\n')
    os.chdir(profile)
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    report = {'source_sha': os.environ['GITHUB_SHA'], 'identity': 'project-modified CPython3.14.10 and matched source Qt/PySide/Shiboken6.12.0; native macOS ARM64 diagnostic, not unchanged official binaries', 'python': sys.version, 'machine': platform.machine(), 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'), 'python_ssl': ssl.OPENSSL_VERSION, 'cryptography_ssl': backend.openssl_version_text(), 'cryptography_provider': 'independent official native-capable wheel/static OpenSSL4; actual selected ARM64 slice, not a Rosetta target', 'default_trust': defaults, 'python_tls': python_tls, 'cpython_security': security, 'qt_default_backend': default_qt_backend, 'qt_openssl': qt_tls, 'qt_securetransport': json.loads((output / 'qt-securetransport.json').read_text()), 'hash_vectors': 'SHA256/HMAC/PBKDF2 PASS', 'png': png_rows, 'gui': 'native Cocoa MainWindow event-loop PASS', 'native': images(prefix, output), 'limits': ['Source prefix only; no Nuitka package, portability/signing/final acceptance.', 'Python SPKI does not qualify Qt/native/OS/cryptography CA security.', 'SecureTransport is legacy TLS1.2; qualified OpenSSL backend provides TLS1.3.']}
    report['cpython_codec_suites'] = codec_suites
    all_rows = {row['path']: row for row in [*report['native']['changed'], *report['qt_securetransport']['changed_images']]}
    report['all_backend_loaded_changed_images'] = len(all_rows)
    report['all_backend_maximum_minos'] = max((v for row in all_rows.values() for v in row['minimum_os']), key=lambda v: tuple(map(int, v.split('.'))))
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
