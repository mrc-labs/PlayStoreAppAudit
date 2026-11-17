"""Measure native ARM64 providers and trust using the accepted Windows checks."""
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
from pathlib import Path
from typing import Any

from probe_windows_arm64_runtime import require_arm64
from verify_native_runtime_pilot import (
    certificate_material,
    default_trust_handshake,
    png_fixture,
    python_tls_checks,
)
from verify_windows_arm64_crypto import validate_imports as validate_crypto_imports
from verify_windows_runtime_pilot import (
    controlled_qt_origin,
    loaded_modules,
    pe_versions,
    qt_checks,
    validate_imports,
    validate_qtcore_imports,
)

DLL_HANDLES: list[Any] = []


def images(prefix: Path, output: Path) -> dict[str, Any]:
    from cryptography.hazmat.bindings import _rust

    modules = loaded_modules()
    validate_imports('\n'.join(path.name for path in modules))
    assert not any('libclang' in str(path).lower() for path in modules), 'Build-host parser leaked into runtime'
    for name in ('vcruntime140.dll', 'msvcp140.dll'):
        assert any(path.name.lower() == name for path in modules), ('Dynamic CRT missing', name)
    package = Path(sys.prefix).resolve() / 'Lib/site-packages/PySide6'
    origins = {str(path):controlled_qt_origin(path, prefix, package) for path in modules
        if path.name.startswith('Qt6') or path.is_relative_to(prefix / 'qt/plugins') or path.is_relative_to(package / 'plugins')}
    selected = [path for path in modules if path.is_relative_to(prefix) or path.is_relative_to(Path(sys.prefix).resolve())]
    rows = []
    for path in selected:
        require_arm64(path)
        versions = pe_versions(path)
        assert versions['os'] <= (10, 0) and versions['subsystem'] <= (10, 0), (path, versions)
        imports = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
        validate_imports(imports)
        if path == Path(_rust.__file__).resolve():
            validate_crypto_imports(imports)
        (output / (path.name + '-dependents.txt')).write_text(imports, encoding='utf-8')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        rows.append({'path':str(path), 'machine':'ARM64', 'sha256':digest,
            'versions':versions, 'controlled_qt_original':origins.get(str(path)), 'dependencies':imports})
    for name in ('python314.dll', 'Qt6Core.dll', 'Qt6Network.dll', 'libssl-4-arm64.dll', 'libcrypto-4-arm64.dll'):
        assert any(path.name.lower() == name.lower() and (path.is_relative_to(prefix) or str(path) in origins) for path in modules), name
    assert origins and all(path.is_relative_to(prefix / 'python') for path in modules if path.name.lower() == 'python314.dll')
    for path in modules:
        if path.name.lower() not in ('libssl-4-arm64.dll', 'libcrypto-4-arm64.dll'):
            continue
        assert path.is_relative_to(prefix / 'python') or path.is_relative_to(prefix / 'openssl'), ('Foreign shared provider', path)
        original = prefix / 'openssl/bin' / path.name
        assert hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(original.read_bytes()).digest(), ('Python provider differs from controlled OpenSSL output', path)
    png = next(path for path in modules if path.name.lower() == 'libpng16.dll' and path.is_relative_to(prefix))
    query = ctypes.CDLL(str(png)).png_get_libpng_ver
    query.restype = ctypes.c_char_p
    assert query(None) == b'1.6.59'
    pcre = next(path for path in modules if path.name.lower() == 'pcre2-16.dll' and path.is_relative_to(prefix))
    version = ctypes.create_unicode_buffer(128)
    assert ctypes.CDLL(str(pcre)).pcre2_config_16(11, version) >= 0
    assert version.value.startswith('10.49 ')
    return {'changed':rows, 'all_loaded':list(map(str, modules)), 'libpng':'1.6.59', 'pcre2':version.value,
        'crt':[str(path) for path in modules if re.match(r'(?:vcruntime|msvcp|ucrtbase)', path.name, re.I)],
        'limits':'Loaded diagnostic closure/header bounds; not final-package or clean older-Windows launch acceptance'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--qt-backend', choices=['schannel'])
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(exist_ok=True)
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert Path(sys.base_prefix).resolve() == prefix / 'python'
    require_arm64(Path(sys.executable))
    for directory in (prefix / 'qt/bin', prefix / 'bin', prefix / 'openssl/bin'):
        DLL_HANDLES.append(os.add_dll_directory(str(directory)))
    import _hashlib
    import _ssl

    import PySide6
    import shiboken6
    from cryptography.hazmat.backends.openssl.backend import backend
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtWidgets import QApplication

    assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
    assert PySide6.__version__ == shiboken6.__version__ == qVersion() == '6.12.0'
    for module, name in ((_ssl, 'libssl-4-arm64.dll'), (_hashlib, 'libcrypto-4-arm64.dll')):
        require_arm64(Path(module.__file__))
        imports = subprocess.check_output(['dumpbin', '/dependents', module.__file__], text=True)
        assert name in imports
        validate_imports(imports)
    imports = subprocess.check_output(['dumpbin', '/dependents', prefix / 'qt/bin/Qt6Core.dll'], text=True)
    validate_qtcore_imports(imports)
    certificates = output / 'isolated-certificates'
    certificates.mkdir(exist_ok=True)
    paths = certificate_material(certificates)
    app = QApplication([])
    assert app.platformName() == 'windows'
    if args.qt_backend:
        report = qt_checks(paths, 'schannel')
        report['loaded_modules'] = list(map(str, loaded_modules()))
        assert any(Path(path).name.lower() == 'schannel.dll' for path in report['loaded_modules'])
        (output / 'qt-schannel.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        return
    defaults = default_trust_handshake()
    roots = {hashlib.sha256(cert[0]).hexdigest() for store in ('ROOT', 'CA') for cert in ssl.enum_certificates(store) if cert[1] == 'x509_asn'}
    context = ssl.create_default_context()
    loaded = {hashlib.sha256(cert).hexdigest() for cert in context.get_ca_certs(binary_form=True)}
    assert roots & loaded, 'Default context must load Windows OS certificates'
    defaults.update(windows_store_unique=len(roots), context_ca_count=len(loaded), os_store_intersection=len(roots & loaded))
    python_tls = python_tls_checks(paths)
    assert _hashlib.openssl_sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert hmac.digest(b'key', b'The quick brown fox jumps over the lazy dog', 'sha256').hex() == 'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8'
    assert hashlib.pbkdf2_hmac('sha256', b'password', b'salt', 1).hex() == '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    openssl = qt_checks(paths, 'openssl')
    (output / 'trust-tls.json').write_text(json.dumps({'python':defaults, 'python_tls':python_tls, 'qt_openssl':openssl}, indent=2), encoding='utf-8')
    subprocess.run([sys.executable, __file__, '--output-dir', str(output), '--qt-backend', 'schannel'], check=True)
    valid = png_fixture()
    pixmap = QPixmap()
    assert QImage.fromData(valid).width() == 1 and pixmap.loadFromData(valid)
    png_rows = []
    import zlib

    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        for index, data in enumerate((b'x\x9c\x00', zlib.compress(b'metadata' * 64)[:-2], b'not-deflate')):
            fixture = png_fixture(kind, data)
            (output / f'malformed-{kind.decode()}-{index}.png').write_bytes(fixture)
            image = QImage.fromData(fixture)
            pixmap.loadFromData(fixture)
            png_rows.append({'kind':kind.decode(), 'case':index, 'decoded':not image.isNull(), 'result':'no native crash; not exploit reproduction'})
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    from verify_native_runtime_pilot import executed_cpython_security

    security = executed_cpython_security(output / 'cpython-regressions.xml', output / 'tarfile-security-regression.log')
    native = images(prefix, output)
    report = {'source_sha':os.environ['GITHUB_SHA'], 'identity':'project-modified native ARM64 CPython 3.14.10 and matched source Qt/PySide/Shiboken 6.12.0; same three accepted patches',
        'architecture':platform.machine(), 'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'), 'python':sys.version,
        'cpython_security':security, 'python_ssl':ssl.OPENSSL_VERSION, 'cryptography_ssl':backend.openssl_version_text(),
        'cryptography_provider':'independent native source build; static OpenSSL / dynamic CRT',
        'default_trust':defaults, 'python_tls':python_tls, 'qt_openssl':openssl,
        'qt_schannel':json.loads((output / 'qt-schannel.json').read_text(encoding='utf-8')),
        'hash_vectors':'SHA256/HMAC/PBKDF2 PASS', 'png':png_rows, 'gui':'native Windows ARM64 MainWindow event-loop PASS',
        'native':native, 'limits':['Diagnostic source prefix, no Nuitka package or final candidate.', 'Linux/x64 source inputs unchanged; three other targets and remaining migrations open.']}
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
