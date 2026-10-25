"""Measure the controlled Windows x64 runtime, providers, CRT and OS trust."""
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
import struct
import subprocess
import sys
import sysconfig
import zlib
from pathlib import Path
from typing import Any

from inspect_pe import read_pe_machine
from verify_native_runtime_pilot import (
    certificate_material,
    default_trust_handshake,
    png_fixture,
    python_tls_checks,
    qt_fixture_response,
    tls_server,
)

DLL_HANDLES: list[Any] = []


def pe_versions(path: Path) -> dict[str, tuple[int, int]]:
    data = path.read_bytes()
    offset = struct.unpack_from('<I', data, 0x3C)[0] + 24
    assert struct.unpack_from('<H', data, offset)[0] == 0x20B, path
    return {'os':struct.unpack_from('<HH', data, offset + 40),
            'subsystem':struct.unpack_from('<HH', data, offset + 48)}


def validate_imports(imports: str) -> None:
    assert not re.search(r'lib(?:ssl|crypto)[-_]3(?:[-.]|\b)', imports, re.I), imports
    assert not re.search(r'(?:vcruntime\d+(?:_\d+)?d|msvcp\d+d|ucrtbased)\.dll', imports, re.I), imports


def require_certificate_rejection(case: str, encrypted: bool, errors: list[str]) -> None:
    assert not encrypted and errors, (case, encrypted, errors)
    expected = {
        'HostNameMismatch': {'HostNameMismatch'},
        'CertificateExpired': {'CertificateExpired'},
        'untrusted': {'CertificateUntrusted', 'SelfSignedCertificateInChain', 'UnableToGetIssuerCertificate',
                      'UnableToGetLocalIssuerCertificate', 'UnableToVerifyFirstCertificate'},
    }
    assert set(errors) & expected[case], (case, errors)


def loaded_modules() -> list[Path]:
    from ctypes import wintypes

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    process = kernel.GetCurrentProcess()
    modules = (wintypes.HMODULE * 4096)()
    needed = wintypes.DWORD()
    kernel.K32EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel.K32GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    assert kernel.K32EnumProcessModules(process, modules, ctypes.sizeof(modules), ctypes.byref(needed))
    assert needed.value <= ctypes.sizeof(modules)
    paths = []
    for module in modules[:needed.value // ctypes.sizeof(wintypes.HMODULE)]:
        name = ctypes.create_unicode_buffer(32768)
        assert kernel.K32GetModuleFileNameExW(process, module, name, len(name))
        paths.append(Path(name.value).resolve())
    return sorted(set(paths))


def qt_checks(paths: dict[str, Path], backend: str) -> dict[str, Any]:
    from PySide6.QtNetwork import QSsl, QSslCertificate, QSslConfiguration, QSslSocket

    available = QSslSocket.availableBackends()
    assert backend in available and QSslSocket.setActiveBackend(backend), available
    assert QSslSocket.activeBackend() == backend
    build = QSslSocket.sslLibraryBuildVersionString()
    runtime = QSslSocket.sslLibraryVersionString()
    if backend == 'openssl':
        assert build.startswith('OpenSSL 4.0.3 ') and runtime.startswith('OpenSSL 4.0.3 '), (build, runtime)
    rows = []
    for case, protocol, hostname, trusted, leaf, expected_error in [
        ('TLS1.2', QSsl.SslProtocol.TlsV1_2, 'localhost', True, 'valid', None),
        ('TLS1.3', QSsl.SslProtocol.TlsV1_3, 'localhost', True, 'valid', None),
        ('hostname', QSsl.SslProtocol.SecureProtocols, 'wrong.invalid', True, 'valid', 'HostNameMismatch'),
        ('untrusted CA', QSsl.SslProtocol.SecureProtocols, 'localhost', False, 'valid', 'untrusted'),
        ('expired', QSsl.SslProtocol.SecureProtocols, 'localhost', True, 'expired', 'CertificateExpired'),
    ]:
        socket = QSslSocket()
        config = QSslConfiguration.defaultConfiguration()
        config.setCaCertificates(QSslCertificate.fromData(paths['ca'].read_bytes()) if trusted else [])
        config.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
        config.setProtocol(protocol)
        socket.setSslConfiguration(config)
        socket.setPeerVerifyName(hostname)
        errors: list[str] = []
        socket.sslErrors.connect(lambda values, target=errors: target.extend(e.error().name for e in values))
        with tls_server(paths, leaf) as port:
            socket.connectToHostEncrypted('127.0.0.1', port)
            encrypted = socket.waitForEncrypted(10000)
            negotiated = socket.sessionProtocol().name if encrypted else None
            assert encrypted == (expected_error is None), (backend, case, errors, socket.errorString())
            if expected_error is None:
                assert not errors and socket.sessionProtocol() == protocol
                socket.write(b'GET / HTTP/1.0\r\n\r\n')
                assert b'200 OK' in qt_fixture_response(socket)
            else:
                require_certificate_rejection(expected_error, encrypted, errors)
            rows.append({'case':case, 'encrypted':encrypted, 'protocol':negotiated, 'errors':errors, 'result':'PASS'})
            socket.abort()
    socket = QSslSocket()
    socket.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
    errors = []
    socket.sslErrors.connect(lambda values: errors.extend(e.error().name for e in values))
    socket.connectToHostEncrypted('www.python.org', 443)
    assert socket.waitForEncrypted(20000), (backend, errors, socket.errorString())
    assert not errors and not socket.peerCertificate().isNull()
    rows.append({'case':'Windows default trust / www.python.org', 'encrypted':True, 'protocol':socket.sessionProtocol().name, 'errors':errors, 'result':'PASS'})
    socket.abort()
    return {'active':backend,'available':available,'build_version':build,'runtime_version':runtime,
            'implementation':'Windows Schannel OS API; not OpenSSL' if backend == 'schannel' else 'linked project OpenSSL 4.0.3', 'cases':rows}


def images(prefix: Path, output: Path) -> dict[str, Any]:
    modules = loaded_modules()
    all_names = '\n'.join(p.name for p in modules)
    validate_imports(all_names)
    assert not any('libclang' in str(p).lower() for p in modules)
    assert any(p.name.lower() == 'vcruntime140.dll' for p in modules), 'Dynamic MSVC CRT not loaded'
    assert any(p.name.lower() == 'msvcp140.dll' for p in modules), 'Dynamic C++ CRT not loaded'
    selected = [p for p in modules if p.is_relative_to(prefix) or p.is_relative_to(Path(sys.prefix).resolve())]
    rows = []
    for path in selected:
        assert read_pe_machine(path) == 0x8664, path
        versions = pe_versions(path)
        assert versions['os'] <= (10, 0) and versions['subsystem'] <= (10, 0), (path, versions)
        dependencies = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
        validate_imports(dependencies)
        (output / (path.name + '-dependents.txt')).write_text(dependencies)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        rows.append({'path':str(path), 'sha256':digest, 'machine':'AMD64', 'versions':versions, 'dependencies':dependencies})
    for name in ('python314.dll','Qt6Core.dll','Qt6Network.dll','libssl-4-x64.dll','libcrypto-4-x64.dll'):
        assert any(p.name.lower() == name.lower() and p.is_relative_to(prefix) for p in modules), name
    assert all(p.is_relative_to(prefix / 'qt') for p in modules if p.name.startswith('Qt6'))
    assert all(p.is_relative_to(prefix / 'python') for p in modules if p.name.lower() == 'python314.dll')
    png = next(p for p in modules if p.name.lower() == 'libpng16.dll' and p.is_relative_to(prefix))
    query = ctypes.CDLL(str(png)).png_get_libpng_ver
    query.restype = ctypes.c_char_p
    assert query(None) == b'1.6.59'
    pcre = next(p for p in modules if p.name.lower() == 'pcre2-16.dll' and p.is_relative_to(prefix))
    version = ctypes.create_unicode_buffer(128)
    assert ctypes.CDLL(str(pcre)).pcre2_config_16(11, version) >= 0
    assert version.value.startswith('10.49 '), version.value
    return {'changed':rows, 'all_loaded':list(map(str, modules)),
            'crt':[str(p) for p in modules if re.match(r'(?:vcruntime|msvcp|ucrtbase)', p.name, re.I)],
            'libpng':'1.6.59','pcre2':version.value,
            'limit':'Loaded diagnostic closure and PE header bounds; not clean Windows 10 packaged launch acceptance'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--qt-backend', choices=['schannel'])
    parser.add_argument('--bootstrap-schannel', action='store_true')
    args = parser.parse_args()
    output = args.output_dir
    if args.bootstrap_schannel:
        from PySide6.QtWidgets import QApplication

        assert sys.platform == 'win32' and platform.machine().upper() == 'AMD64'
        output.mkdir(parents=True)
        app = QApplication([])
        assert app.platformName() == 'windows'
        report = qt_checks(certificate_material(output), 'schannel')
        modules = loaded_modules()
        assert any(p.name.lower() == 'schannel.dll' for p in modules)
        report.update(source_sha=os.environ['GITHUB_SHA'], os=platform.platform(),
                      scope='Bootstrap native Schannel/verifier prerequisite only; not controlled-stack acceptance',
                      native_tls_modules=[str(p) for p in modules if p.name.lower() in ('schannel.dll','crypt32.dll','sspicli.dll','secur32.dll')])
        (output / 'bootstrap-schannel.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    assert sys.platform == 'win32' and platform.machine().upper() == 'AMD64'
    assert platform.python_version() == '3.14.9' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert Path(sys.base_prefix).resolve() == prefix / 'python'
    assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    for directory in (prefix / 'qt/bin', prefix / 'openssl/bin', prefix / 'bin'):
        DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    import _hashlib
    import _ssl

    import PySide6
    import shiboken6
    from cryptography.hazmat.backends.openssl.backend import backend
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtWidgets import QApplication

    assert PySide6.__version__ == shiboken6.__version__ == qVersion() == '6.12.0'
    assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
    for module, library in [(_ssl,'libssl-4-x64.dll'), (_hashlib,'libcrypto-4-x64.dll')]:
        dependencies = subprocess.check_output(['dumpbin','/nologo','/dependents',module.__file__], text=True)
        assert library in dependencies, dependencies
        validate_imports(dependencies)
    certificates = output / 'isolated-certificates'
    certificates.mkdir(exist_ok=True)
    paths = certificate_material(certificates)
    app = QApplication([])
    assert app.platformName() == 'windows', app.platformName()
    if args.qt_backend:
        report = qt_checks(paths, args.qt_backend)
        report['loaded_modules'] = list(map(str, loaded_modules()))
        assert any(Path(p).name.lower() == 'schannel.dll' for p in report['loaded_modules'])
        (output / 'qt-schannel.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return
    defaults = default_trust_handshake()
    roots = {hashlib.sha256(c[0]).hexdigest() for store in ('ROOT','CA') for c in ssl.enum_certificates(store) if c[1] == 'x509_asn'}
    context = ssl.create_default_context()
    loaded = {hashlib.sha256(c).hexdigest() for c in context.get_ca_certs(binary_form=True)}
    assert roots & loaded, 'Default OpenSSL context did not load Windows OS certificates'
    defaults.update(windows_store_unique=len(roots), context_ca_count=len(loaded), os_store_intersection=len(roots & loaded))
    python_tls = python_tls_checks(paths)
    assert _hashlib.openssl_sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert hmac.digest(b'key', b'The quick brown fox jumps over the lazy dog','sha256').hex() == 'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8'
    assert hashlib.pbkdf2_hmac('sha256',b'password',b'salt',1).hex() == '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    qt_tls = qt_checks(paths, 'openssl')
    (output / 'trust-tls.json').write_text(json.dumps({'python':defaults,'python_tls':python_tls,'qt_openssl':qt_tls},indent=2))
    subprocess.run([sys.executable, __file__, '--output-dir', str(output), '--qt-backend', 'schannel'], check=True)
    valid = png_fixture()
    pixmap = QPixmap()
    assert QImage.fromData(valid).width() == 1 and pixmap.loadFromData(valid)
    png_rows = []
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        for index, data in enumerate((b'x\x9c\x00', zlib.compress(b'metadata' * 64)[:-2], b'not-deflate')):
            fixture = png_fixture(kind, data)
            (output / f'malformed-{kind.decode()}-{index}.png').write_bytes(fixture)
            image = QImage.fromData(fixture)
            pixmap.loadFromData(fixture)
            png_rows.append({'kind':kind.decode(),'case':index,'decoded':not image.isNull(),'result':'no native crash; not exploit reproduction'})
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    native = images(prefix, output)
    report = {'source_sha':os.environ['GITHUB_SHA'],'identity':'project-modified CPython 3.14.9, matched source Qt/PySide/Shiboken 6.12.0',
        'python':sys.version,'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),'architecture':platform.machine(),
        'python_ssl':ssl.OPENSSL_VERSION,'cryptography_ssl':backend.openssl_version_text(),
        'cryptography_provider':'independent wheel statically linked OpenSSL; not Python DLL provider',
        'default_trust':defaults,'python_tls':python_tls,'qt_openssl':qt_tls,
        'qt_schannel':json.loads((output / 'qt-schannel.json').read_text()), 'hash_vectors':'SHA256/HMAC/PBKDF2 PASS',
        'png':png_rows, 'native':native,'gui':'native Windows MainWindow event-loop PASS',
        'limits':['Diagnostic prefix only; no final application binary/package built.', 'Linux evidence unchanged; other four targets and remaining migrations open.', 'PE header checks do not substitute for actual older-OS package launch.']}
    (output / 'pilot-results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
