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
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import sysconfig
import threading
import time
import warnings
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from inspect_linux_abi import readelf as read_elf
from inspect_linux_abi import required_versions, version_floor


def diagnose_cxx_abi(output: Path, *, link_directory: Path | None = None, require_compatible: bool = True) -> None:
    """Measure the compiler AND its link SDK before any component downloads."""
    compiler = shutil.which(os.environ.get('CXX', 'c++'))
    assert compiler, 'No native C++ compiler available for ABI preflight'
    source = output / 'cxx-abi-probe.cpp'
    binary = output / 'cxx-abi-probe.so'
    source.write_text('#include <condition_variable>\n#include <mutex>\n'
                      'void probe(std::condition_variable &cv, std::unique_lock<std::mutex> &lock) { cv.wait(lock); }\n')
    command = [compiler, '-std=c++17', '-fPIC', '-shared', str(source), '-pthread', '-o', str(binary)]
    if link_directory is not None:
        command.insert(1, '-L' + str(link_directory))
    subprocess.run(command, check=True)
    versions = read_elf(binary, '--version-info')
    symbols = read_elf(binary, '--dyn-syms')
    (output / 'cxx-abi-probe-versions.txt').write_text(versions)
    (output / 'cxx-abi-probe-symbols.txt').write_text(symbols)
    library = subprocess.check_output([compiler, '-print-file-name=libstdc++.so'], text=True).strip()
    if link_directory is not None:
        library = str(link_directory / 'libstdc++.so')
    needs = required_versions(versions)
    maximum = version_floor(needs, 'GLIBCXX_')
    compatible = maximum is None or tuple(map(int, maximum.removeprefix('GLIBCXX_').split('.'))) <= (3, 4, 29)
    packages = subprocess.run(['dpkg-query', '-W', 'gcc-11', 'g++-11', 'libstdc++-11-dev', 'libstdc++6'],
                              capture_output=True, text=True, check=False)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'compiler': compiler,
              'compiler_version': subprocess.check_output([compiler, '--version'], text=True),
              'command': command, 'link_library': library, 'resolved_link_library': str(Path(library).resolve()),
              'packages': packages.stdout, 'package_query_stderr': packages.stderr,
              'required_versions': needs, 'glibcxx': maximum, 'accepted_glibcxx': 'GLIBCXX_3.4.29',
              'compatible': compatible, 'probe_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'note': 'A small SDK probe is not a substitute for full Qt/PySide/extension ABI validation.'}
    (output / 'cxx-sdk-diagnostics.json').write_text(json.dumps(report, indent=2) + '\n')
    print('C++ SDK ABI diagnostic:', json.dumps(report), flush=True)
    if require_compatible and not compatible:
        raise RuntimeError(f'C++ link SDK requires {maximum}, accepted GLIBCXX_3.4.29; stopped before component downloads')


def default_trust_handshake() -> dict[str, Any]:
    """Exercise OS defaults, including hashed directories populated lazily."""
    assert not os.environ.get('SSL_CERT_FILE') and not os.environ.get('SSL_CERT_DIR')
    context = ssl.create_default_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    before = context.cert_store_stats()
    hostname = 'www.python.org'
    with (socket.create_connection((hostname, 443), timeout=20) as raw,
          context.wrap_socket(raw, server_hostname=hostname) as connection):
        certificate = connection.getpeercert(binary_form=True)
        assert certificate
        result = {'host': hostname, 'protocol': connection.version(),
                  'peer_sha256': hashlib.sha256(certificate).hexdigest(),
                  'verify_mode': context.verify_mode.name, 'check_hostname': context.check_hostname,
                  'store_before': before, 'store_after': context.cert_store_stats(),
                  'result': 'default-trust authenticated handshake PASS'}
    return result


def diagnose_system_trust(output: Path) -> None:
    """Read the runner's real trust layout before installing or building anything."""
    output.mkdir(parents=True, exist_ok=True)
    commands = {}
    for name, command in {
        'openssl_version': ['/usr/bin/openssl', 'version', '-a'],
        'openssl_directory': ['/usr/bin/openssl', 'version', '-d'],
        'ca_packages': ['dpkg-query', '-W', 'openssl', 'ca-certificates'],
    }.items():
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        commands[name] = {'command': command, 'exit_code': process.returncode,
                          'stdout': process.stdout, 'stderr': process.stderr}
    match = re.fullmatch(r'OPENSSLDIR: "(.+)"\s*', commands['openssl_directory']['stdout'])
    assert match, commands['openssl_directory']
    system_directory = Path(match[1])
    defaults = ssl.get_default_verify_paths()
    candidates = {system_directory, system_directory / 'cert.pem', system_directory / 'certs',
                  Path('/usr/lib/ssl'), Path('/usr/lib/ssl/cert.pem'), Path('/usr/lib/ssl/certs'),
                  Path('/etc/ssl'), Path('/etc/ssl/cert.pem'), Path('/etc/ssl/certs'),
                  Path('/etc/ssl/certs/ca-certificates.crt')}
    candidates.update(Path(value) for key, value in defaults._asdict().items()
                      if value and not key.endswith('_env'))

    def describe(path: Path) -> dict[str, Any]:
        data: dict[str, Any] = {'path': str(path), 'exists': path.exists(),
                                'readable': os.access(path, os.R_OK),
                                'searchable': os.access(path, os.X_OK),
                                'symlink': os.readlink(path) if path.is_symlink() else None,
                                'resolved': str(path.resolve())}
        if path.exists() or path.is_symlink():
            metadata = path.lstat()
            data.update(mode=oct(metadata.st_mode), uid=metadata.st_uid, gid=metadata.st_gid)
        if path.is_file() and os.access(path, os.R_OK):
            payload = path.read_bytes()
            data.update(size=len(payload), sha256=hashlib.sha256(payload).hexdigest(),
                        pem_certificates=payload.count(b'-----BEGIN CERTIFICATE-----'))
        return data

    paths = []
    for path in sorted(candidates):
        data = describe(path)
        process = subprocess.run(['namei', '-l', str(path)], capture_output=True, text=True, check=False)
        data['namei'] = process.stdout + process.stderr
        if path.is_dir():
            data['hashed_entries'] = [describe(entry) for entry in sorted(path.iterdir())
                                      if re.fullmatch(r'[0-9a-f]{8}\.\d+', entry.name)]
        paths.append(data)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'os_release': Path('/etc/os-release').read_text(),
              'python_ssl': ssl.OPENSSL_VERSION, 'default_verify_paths': defaults._asdict(),
              'environment': {key: os.environ.get(key) for key in ('SSL_CERT_FILE', 'SSL_CERT_DIR')},
              'commands': commands, 'paths': paths}
    # Persist layout even when the subsequent authenticated network probe fails.
    destination = output / 'system-trust-diagnostics.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    report['default_trust'] = default_trust_handshake()
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    # Measure the host before explicitly qualifying the selected target link SDK.
    diagnose_cxx_abi(output, require_compatible=False)


def executed_upstream_suites(xml_path: Path) -> dict[str, int]:
    """Require actual cases, including CPython's name-only JUnit dialect."""
    root = ET.parse(xml_path).getroot()
    counts = dict.fromkeys(('test_ssl', 'test_hashlib', 'test_hmac'), 0)
    for case in root.iter('testcase'):
        if case.find('failure') is not None or case.find('error') is not None:
            raise RuntimeError('Upstream regression contains a failure/error')
        if case.find('skipped') is not None or case.attrib.get('status') == 'notrun':
            continue
        identity = case.attrib.get('classname', '') + '.' + case.attrib.get('name', '')
        for module in counts:
            if re.search(rf'(?:^|\.){module}\.', identity):
                counts[module] += 1
    for module, count in counts.items():
        if not count:
            raise RuntimeError(f'{module} was skipped rather than exercised')
    return counts


def executed_cpython_security(xml_path: Path, tar_log: Path) -> dict[str, str]:
    """A passing suite must include executed SPKI and tar-filter security cases."""
    cases = [case for case in ET.parse(xml_path).getroot().iter('testcase')
             if 'test_distrusted_spki' in case.get('name', '')]
    if not cases or any(case.get('status') == 'notrun' or any(case.find(tag) is not None
                       for tag in ('skipped', 'error', 'failure')) for case in cases):
        raise RuntimeError('Executed CPython compromised-SPKI rejection required')
    text = tar_log.read_text(encoding='utf-8')
    if 'test_link_at_destination' not in text or 'Ran 1 test' not in text or '\nOK\n' not in text or 'skipped' in text:
        raise RuntimeError('Executed CPython tar destination-link rejection required')
    return {'compromised_spki': 'executed rejection PASS', 'tar_destination_link': 'executed rejection PASS'}


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
    return results


def qt_fixture_response(connection: Any) -> bytes:
    """Receive the local fixture header without starving its Python server thread."""
    from PySide6.QtCore import QCoreApplication

    deadline = time.monotonic() + 5
    response = bytearray()
    yield_threads = threading.Event()
    while b'\r\n\r\n' not in response:
        response.extend(bytes(connection.readAll()))
        if b'\r\n\r\n' in response:
            break
        if time.monotonic() >= deadline:
            raise AssertionError(f'Local Qt TLS response timed out: {bytes(response)!r}; {connection.errorString()}')
        QCoreApplication.processEvents()
        yield_threads.wait(.01)
    return bytes(response)


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
                assert connection.sessionProtocol() == protocol
                connection.write(b'GET / HTTP/1.0\r\n\r\n')
                assert b'200 OK' in qt_fixture_response(connection)
            else:
                assert errors, (name, connection.errorString())
            negotiated = connection.sessionProtocol().name if encrypted else None
            connection.abort()
        results.append({'case': name, 'encrypted': encrypted, 'negotiated_protocol': negotiated,
                        'errors': errors, 'result': 'PASS'})
        print('Qt TLS case:', json.dumps(results[-1]), flush=True)
    # Exercise the real framework defaults separately from the isolated CA fixtures.
    connection = QSslSocket()
    connection.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
    errors = []
    connection.sslErrors.connect(lambda values: errors.extend(error.error().name for error in values))
    connection.connectToHostEncrypted('www.python.org', 443)
    assert connection.waitForEncrypted(20000), (errors, connection.errorString())
    assert not errors and not connection.peerCertificate().isNull()
    results.append({'case': 'OS default trust / www.python.org', 'encrypted': True, 'errors': errors,
                    'negotiated_protocol': connection.sessionProtocol().name,
                    'peer_serial': bytes(connection.peerCertificate().serialNumber()).decode(), 'result': 'PASS'})
    connection.abort()
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
        header = read_elf(path, '--file-header')
        assert 'Advanced Micro Devices X86-64' in header, path
        versions = read_elf(path, '--version-info')
        (Path(os.environ['PILOT_EVIDENCE']) / f'{path.name}-version-info.txt').write_text(versions)
        needs = required_versions(versions)
        bounds = {}
        for kind, floor in [('GLIBC', (2, 35)), ('GLIBCXX', (3, 4, 29))]:
            maximum = version_floor(needs, kind + '_')
            if maximum:
                numeric = tuple(map(int, maximum.removeprefix(kind + '_').split('.')))
                bounds[kind] = numeric
                assert numeric <= floor, (path, kind, numeric, floor)
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
    python_images = [p for p in paths if p.name.startswith('libpython3.14')]
    assert python_images and all(p.is_relative_to(prefix / 'python') for p in python_images)
    generator_prefix = Path(os.environ['PILOT_WORK']) / 'src/libclang'
    assert not any(p.is_relative_to(generator_prefix) for p in paths)
    sdk_prefix = Path(os.environ['PILOT_CXX_SDK_ROOT']).resolve()
    assert not any(p.is_relative_to(sdk_prefix) for p in paths), 'Target link SDK must never be loaded at runtime'
    for stem in ('libssl.so.4', 'libcrypto.so.4', 'libQt6Core.so.6', 'libQt6Network.so.6'):
        assert any(p.name.startswith(stem) and p.is_relative_to(prefix) for p in paths), stem
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--diagnose-system-trust', action='store_true')
    arguments = parser.parse_args()
    output = arguments.output_dir
    if arguments.diagnose_system_trust:
        diagnose_system_trust(output)
        return
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert Path(sys.base_prefix).resolve() == prefix / 'python'
    assert Path(ssl.__file__).resolve().is_relative_to(prefix / 'python')
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
    default_trust = default_trust_handshake()
    (output / 'python-default-trust.json').write_text(json.dumps(default_trust, indent=2) + '\n')
    print('Python default trust:', json.dumps(default_trust), flush=True)
    python_tls = python_tls_checks(paths)
    (output / 'python-tls.json').write_text(json.dumps(python_tls, indent=2) + '\n')
    qt_tls = qt_tls_checks(paths)
    (output / 'qt-tls.json').write_text(json.dumps(qt_tls, indent=2) + '\n')
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
    # Direct script execution starts sys.path in .github/scripts, not the checkout.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from playstore_app_audit import __version__
    from playstore_app_audit.ui.main_window import MainWindow
    assert __version__ == '2.4.0'
    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    security = executed_cpython_security(output / 'cpython-regressions.xml', output / 'tarfile-security-regression.log')
    images = native_images(prefix)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'scope': 'native source-stack pilot; not final package acceptance',
              'identity': 'project-modified CPython 3.14.10 / source-built matched Qt-PySide-Shiboken 6.12.0',
              'cpython_security': security,
              'python_ssl': ssl.OPENSSL_VERSION, 'cryptography_ssl': backend.openssl_version_text(),
              'qt_ssl_build': QSslSocket.sslLibraryBuildVersionString(), 'qt_ssl_runtime': QSslSocket.sslLibraryVersionString(),
              'qt_backend': QSslSocket.activeBackend(), 'python_tls': python_tls, 'qt_tls': qt_tls,
              'hash_vectors': 'SHA256/HMAC-SHA256/PBKDF2-SHA256 PASS', 'png': png_results,
              'gui': 'native xcb MainWindow event-loop PASS', 'loaded_changed_images': images,
              'trust': {'paths': str(ssl.get_default_verify_paths()), 'default_handshake': default_trust},
              'limits': ['One source environment only; no application binary/candidate built.',
                         'Remaining five targets, package closure and other inventory migrations remain open.',
                         'Malformed PNG corpus is regression coverage, not a demonstrated CVE exploit.']}
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
