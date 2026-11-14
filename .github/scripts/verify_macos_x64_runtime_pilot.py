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
import zipfile
import zlib
from pathlib import Path

from probe_macos_x64_runtime import contract, macho
from verify_macos_arm64_runtime_pilot import (
    allowed_origin,
    executed_codec_suites,
    loaded_images,
    loaded_png,
    qt_checks,
)
from verify_native_runtime_pilot import (
    certificate_material,
    default_trust_handshake,
    executed_cpython_security,
    png_fixture,
    python_tls_checks,
)


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
    assert executable['minimum_os'] == python_library['minimum_os'] == ['10.15'], 'Preserve the Python executable/library deployment separately from Qt/package ceiling'
    qt = [p for p in paths if re.match(r'Qt\w+', p.name) and '.framework' in str(p)]
    assert qt and all(p.is_relative_to(prefix / 'qt') for p in qt), qt
    png = loaded_png(paths, prefix)
    query = ctypes.CDLL(str(png)).png_get_libpng_ver
    query.restype = ctypes.c_char_p
    assert query(None) == b'1.6.59'
    png_image = next(row for row in rows if Path(row['path']) == png)
    qt_gui = next(row for row in rows if Path(row['path']).name == 'QtGui')
    assert set(png_image['install_names']) & set(qt_gui['dependencies']), 'QtGui must link the actual measured libpng provider'
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
    report = {'changed': rows, 'all_loaded': list(map(str, paths)), 'python_executable': executable['path'], 'python_executable_minos': executable['minimum_os'], 'libpng': '1.6.59', 'libpng_provider': str(png), 'libpng_linkage': 'QtGui LC_LOAD_DYLIB matches measured provider LC_ID_DYLIB', 'pcre2': pcre_version, 'codecs': codecs, 'maximum_minos': max((v for row in rows for v in row['minimum_os']), key=lambda v: tuple(map(int, v.split('.')))), 'limit': 'Loaded source-prefix closure only; not all-file package/ADB or older-OS acceptance'}
    (output / 'macho-loaded-images.json').write_text(json.dumps(report, indent=2))
    return report


def source_wheel_provenance(output: Path, rust_path: Path) -> dict:
    """Prove the modified-runtime module is the retained native source wheel."""
    report = json.loads((output / 'cryptography-source-provenance.json').read_text())
    assert report['source_sha'] == os.environ['GITHUB_SHA'], 'Foreign wheel source head'
    assert Path(report['wheel']).name == report['wheel'], 'Wheel must be inside evidence'
    wheel = output / 'wheels' / report['wheel']
    assert hashlib.sha256(wheel.read_bytes()).hexdigest() == report['wheel_sha256'], 'Changed retained wheel'
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist() if name.startswith('cryptography/hazmat/bindings/_rust.') and name.endswith('.so')]
        assert len(members) == 1, 'Missing/ambiguous cryptography native wheel module'
        assert archive.read(members[0]) == rust_path.read_bytes(), 'Runtime module differs from qualified source wheel'
    row = macho(rust_path, target=True, output=output)
    assert not any(re.search(r'lib(?:crypto|ssl)', value, re.I) for value in row['dependencies']), 'cryptography must retain independent static OpenSSL'
    return {**report, 'runtime_native': row, 'runtime_module_matches_retained_wheel': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--native-prerequisites', action='store_true')
    parser.add_argument('--qt-native-backend', action='store_true')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    os.environ['QT_SSL_USE_TEMPORARY_KEYCHAIN'] = '1'
    assert sys.platform == 'darwin' and platform.machine() == 'x86_64' and not sysconfig.get_config_var('Py_GIL_DISABLED')
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
    from cryptography.hazmat.bindings import _rust
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
    report = {'source_sha': os.environ['GITHUB_SHA'], 'identity': 'project-modified CPython3.14.10 and matched source Qt/PySide/Shiboken6.12.0; native macOS Intel/x64 diagnostic, not unchanged official binaries', 'python': sys.version, 'machine': platform.machine(), 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'), 'python_ssl': ssl.OPENSSL_VERSION, 'cryptography_ssl': backend.openssl_version_text(), 'cryptography_provider': 'independent project source-built cryptography50.0.2 wheel/static OpenSSL4; native Intel Rust1.99.1, no dynamic SSL import', 'default_trust': defaults, 'python_tls': python_tls, 'cpython_security': security, 'qt_default_backend': default_qt_backend, 'qt_openssl': qt_tls, 'qt_securetransport': json.loads((output / 'qt-securetransport.json').read_text()), 'hash_vectors': 'SHA256/HMAC/PBKDF2 PASS', 'png': png_rows, 'gui': 'native Cocoa MainWindow event-loop PASS', 'native': images(prefix, output), 'limits': ['Source prefix only; no Nuitka package, portability/signing/final acceptance.', 'Python SPKI does not qualify Qt/native/OS/cryptography CA security.', 'SecureTransport is legacy TLS1.2; qualified OpenSSL backend provides TLS1.3.']}
    report['cryptography_source_provenance'] = source_wheel_provenance(output, Path(_rust.__file__).resolve())
    report['cpython_codec_suites'] = codec_suites
    all_rows = {row['path']: row for row in [*report['native']['changed'], *report['qt_securetransport']['changed_images']]}
    report['all_backend_loaded_changed_images'] = len(all_rows)
    report['all_backend_maximum_minos'] = max((v for row in all_rows.values() for v in row['minimum_os']), key=lambda v: tuple(map(int, v.split('.'))))
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
