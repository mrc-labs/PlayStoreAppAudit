"""Exercise the actual source-built Jammy runtime/framework; never accepts a release."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import datetime as dt
import hashlib
import hmac
import json
import os
import platform
import re
import socket
import ssl
import struct
import subprocess
import sys
import sysconfig
import threading
import warnings
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))


def png_fixture(kind: bytes | None = None, compressed: bytes = b'') -> bytes:
    header = b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('!2I5B', 1, 1, 8, 6, 0, 0, 0))
    prefixes = {b'zTXt': b'note\0\0', b'iTXt': b'note\0\1\0\0\0', b'iCCP': b'profile\0\0'}
    metadata = png_chunk(kind, prefixes[kind] + compressed) if kind else b''
    pixels = png_chunk(b'IDAT', zlib.compress(b'\0\xff\0\0\xff'))
    # iCCP is only legal before IDAT; compressed text is legal at end-read.
    payload = metadata + pixels if kind == b'iCCP' else pixels + metadata
    return header + payload + png_chunk(b'IEND', b'')


def certificate_material(root: Path) -> dict[str, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = dt.datetime.now(dt.UTC)
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Isolated pilot CA')])
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
          .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
          .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=2))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
          .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
          .sign(ca_key, hashes.SHA256()))
    paths = {'ca': root / 'ca.pem', 'key': root / 'server-key.pem'}
    paths['ca'].write_bytes(ca.public_bytes(serialization.Encoding.PEM))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    paths['key'].write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                             serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    for name, start, end in [('valid', -1, 1), ('expired', -3, -2)]:
        cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')]))
                .issuer_name(ca_name).public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now + dt.timedelta(days=start)).not_valid_after(now + dt.timedelta(days=end))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), critical=True)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        paths[name] = root / f'{name}.pem'
        paths[name].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return paths


@contextlib.contextmanager
def tls_server(paths: dict[str, Path], cert: str = 'valid') -> Iterator[int]:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(paths[cert], paths['key'])
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(10)
    failures: list[Exception] = []

    def serve() -> None:
        try:
            connection, _ = listener.accept()
            connection.settimeout(10)
            with connection, context.wrap_socket(connection, server_side=True) as secure:
                secure.recv(4096)
                body = png_fixture()
                secure.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: ' +
                               str(len(body)).encode() + b'\r\nConnection: close\r\n\r\n' + body)
        except ssl.SSLError:
            pass  # Negative clients must reject the peer and abort the handshake.
        except Exception as exc:
            failures.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield listener.getsockname()[1]
    finally:
        thread.join(12)
        listener.close()
        if thread.is_alive() or failures:
            raise RuntimeError(f'Pilot TLS server failed: {failures}')


def python_tls_checks(paths: dict[str, Path]) -> list[str]:
    results = []
    for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
        context = ssl.create_default_context(cafile=str(paths['ca']))
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
        context.minimum_version = context.maximum_version = version
        with (tls_server(paths) as port,
              socket.create_connection(('127.0.0.1', port), timeout=5) as raw,
              context.wrap_socket(raw, server_hostname='localhost') as connection):
            assert connection.version() == version.name.replace('TLSv1_', 'TLSv1.')
            connection.sendall(b'GET / HTTP/1.0\r\n\r\n')
            assert b'200 OK' in connection.recv(4096)
        results.append(version.name + ': trusted handshake PASS')
    for name, hostname, trusted, cert, expected_code in [
        ('hostname', 'wrong.invalid', True, 'valid', 62),
        ('untrusted CA', 'localhost', False, 'valid', 20),
        ('expired', 'localhost', True, 'expired', 10),
    ]:
        context = ssl.create_default_context(cafile=str(paths['ca']) if trusted else None)
        with tls_server(paths, cert) as port, socket.create_connection(('127.0.0.1', port), timeout=5) as raw:
            try:
                context.wrap_socket(raw, server_hostname=hostname)
            except ssl.SSLCertVerificationError as exc:
                assert exc.verify_code == expected_code, (name, exc.verify_code, str(exc))
            else:
                raise AssertionError(f'Python accepted {name}')
        results.append(name + ': rejected PASS')
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        fixed = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    assert ssl.HAS_TLSv1_2
    assert fixed.minimum_version == fixed.maximum_version == ssl.TLSVersion.TLSv1_2
    assert ssl.create_default_context().cert_store_stats()['x509_ca'] > 0
    return results


def qt_tls_checks(paths: dict[str, Path]) -> list[dict[str, Any]]:
    from PySide6.QtNetwork import QSsl, QSslCertificate, QSslConfiguration, QSslSocket

    assert QSslSocket.setActiveBackend('openssl')
    assert QSslSocket.activeBackend() == 'openssl'
    for value in (QSslSocket.sslLibraryBuildVersionString(), QSslSocket.sslLibraryVersionString()):
        assert value.startswith('OpenSSL 4.0.3 '), value
    results = []
    for name, protocol, hostname, trusted, cert, expected in [
        ('TLS1.2', QSsl.SslProtocol.TlsV1_2, 'localhost', True, 'valid', True),
        ('TLS1.3', QSsl.SslProtocol.TlsV1_3, 'localhost', True, 'valid', True),
        ('hostname', QSsl.SslProtocol.SecureProtocols, 'wrong.invalid', True, 'valid', False),
        ('untrusted CA', QSsl.SslProtocol.SecureProtocols, 'localhost', False, 'valid', False),
        ('expired', QSsl.SslProtocol.SecureProtocols, 'localhost', True, 'expired', False),
    ]:
        connection = QSslSocket()
        config = QSslConfiguration.defaultConfiguration()
        config.setCaCertificates(QSslCertificate.fromData(paths['ca'].read_bytes()) if trusted else [])
        config.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
        config.setProtocol(protocol)
        connection.setSslConfiguration(config)
        connection.setPeerVerifyName(hostname)
        errors: list[str] = []
        connection.sslErrors.connect(lambda values, target=errors: target.extend(error.error().name for error in values))
        with tls_server(paths, cert) as port:
            connection.connectToHostEncrypted('127.0.0.1', port)
            encrypted = connection.waitForEncrypted(5000)
            assert encrypted == expected, (name, encrypted, errors, connection.errorString())
            if expected:
                assert not errors
                connection.write(b'GET / HTTP/1.0\r\n\r\n')
                connection.waitForBytesWritten(5000)
                assert connection.waitForReadyRead(5000)
                assert b'200 OK' in bytes(connection.readAll())
            else:
                assert errors, (name, connection.errorString())
            connection.abort()
        results.append({'case': name, 'encrypted': encrypted, 'errors': errors, 'result': 'PASS'})
    return results


def native_images(prefix: Path) -> list[dict[str, Any]]:
    paths = {Path(line.split()[-1]).resolve() for line in Path('/proc/self/maps').read_text().splitlines()
             if '/' in line and not line.endswith(' (deleted)')}
    assert not any(re.match(r'lib(?:ssl|crypto)\.so\.3', p.name) for p in paths), paths
    selected = [p for p in paths if p.is_relative_to(prefix) or p.is_relative_to(Path(sys.prefix))]
    results = []
    for path in sorted(selected):
        if not path.is_file() or path.read_bytes()[:4] != b'\x7fELF':
            continue
        header = subprocess.check_output(['readelf', '-h', str(path)], text=True)
        assert 'Advanced Micro Devices X86-64' in header, path
        versions = subprocess.check_output(['readelf', '--version-info', str(path)], text=True)
        bounds = {}
        for kind, floor in [('GLIBC', (2, 35)), ('GLIBCXX', (3, 4, 29))]:
            found = [tuple(map(int, value.split('.'))) for value in re.findall(rf'\b{kind}_([0-9.]+)', versions)]
            if found:
                bounds[kind] = max(found)
                assert max(found) <= floor, (path, kind, max(found), floor)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        results.append({'path': str(path), 'sha256': digest, 'version_maxima': bounds})
    for name, expected, function in [('libpng16.so', b'1.6.59', 'png_get_libpng_ver')]:
        image = next(p for p in paths if p.name.startswith(name) and p.is_relative_to(prefix))
        query = getattr(ctypes.CDLL(str(image)), function)
        query.restype = ctypes.c_char_p
        assert query(None) == expected
    pcre = next(p for p in paths if p.name.startswith('libpcre2-16.so') and p.is_relative_to(prefix))
    version = ctypes.create_string_buffer(128)
    assert ctypes.CDLL(str(pcre)).pcre2_config_16(11, version) >= 0
    pcre_version = version.raw.decode('utf-16-le').split('\0', 1)[0]
    assert pcre_version.startswith('10.49 '), pcre_version
    qt_images = [p for p in paths if p.name.startswith('libQt6')]
    assert qt_images and all(p.is_relative_to(prefix / 'qt') for p in qt_images)
    for stem in ('libssl.so.4', 'libcrypto.so.4', 'libQt6Core.so.6', 'libQt6Network.so.6'):
        assert any(p.name.startswith(stem) and p.is_relative_to(prefix) for p in paths), stem
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    output = parser.parse_args().output_dir
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert platform.python_version() == '3.14.9' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    import _hashlib
    import _ssl

    import PySide6
    import shiboken6
    from cryptography.hazmat.backends.openssl.backend import backend
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtNetwork import QSslSocket
    from PySide6.QtWidgets import QApplication

    assert PySide6.__version__ == shiboken6.__version__ == qVersion() == '6.12.0'
    assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
    for module, library in [(_ssl, 'libssl.so.4'), (_hashlib, 'libcrypto.so.4')]:
        dependencies = subprocess.check_output(['ldd', module.__file__], text=True)
        assert library in dependencies and str(prefix / 'openssl') in dependencies, dependencies
        (output / f'{module.__name__}-ldd.txt').write_text(dependencies)
    assert _hashlib.openssl_sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert hmac.digest(b'key', b'The quick brown fox jumps over the lazy dog', 'sha256').hex() == 'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8'
    assert hashlib.pbkdf2_hmac('sha256', b'password', b'salt', 1).hex() == '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    cert_root = output / 'isolated-certificates'
    cert_root.mkdir()
    paths = certificate_material(cert_root)
    app = QApplication([])
    assert app.platformName() == 'xcb', app.platformName()
    python_tls = python_tls_checks(paths)
    qt_tls = qt_tls_checks(paths)
    valid = png_fixture()
    image = QImage.fromData(valid)
    pixmap = QPixmap()
    assert image.width() == 1 and image.height() == 1 and pixmap.loadFromData(valid)
    png_results = []
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        for index, data in enumerate((b'x\x9c\x00', zlib.compress(b'metadata' * 64)[:-2], b'not-deflate')):
            fixture = png_fixture(kind, data)
            (output / f'malformed-{kind.decode()}-{index}.png').write_bytes(fixture)
            result = QImage.fromData(fixture)
            pixmap.loadFromData(fixture)
            png_results.append({'kind': kind.decode(), 'case': index, 'decoded': not result.isNull(),
                                'result': 'no native crash; malformed metadata may be rejected'})
    from playstore_app_audit import __version__
    from playstore_app_audit.ui.main_window import MainWindow
    assert __version__ == '2.4.0'
    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    images = native_images(prefix)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'scope': 'native source-stack pilot; not final package acceptance',
              'identity': 'project-modified CPython 3.14.9 / source-built matched Qt-PySide-Shiboken 6.12.0',
              'python_ssl': ssl.OPENSSL_VERSION, 'cryptography_ssl': backend.openssl_version_text(),
              'qt_ssl_build': QSslSocket.sslLibraryBuildVersionString(), 'qt_ssl_runtime': QSslSocket.sslLibraryVersionString(),
              'qt_backend': QSslSocket.activeBackend(), 'python_tls': python_tls, 'qt_tls': qt_tls,
              'hash_vectors': 'SHA256/HMAC-SHA256/PBKDF2-SHA256 PASS', 'png': png_results,
              'gui': 'native xcb MainWindow event-loop PASS', 'loaded_changed_images': images,
              'trust': {'paths': str(ssl.get_default_verify_paths()), 'default_store': ssl.create_default_context().cert_store_stats()},
              'limits': ['One source environment only; no application binary/candidate built.',
                         'Remaining five targets, package closure and other inventory migrations remain open.',
                         'Malformed PNG corpus is regression coverage, not a demonstrated CVE exploit.']}
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
