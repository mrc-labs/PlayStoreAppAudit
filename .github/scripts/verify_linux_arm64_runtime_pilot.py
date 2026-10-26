"""Check the controlled Noble AArch64 prefix; not a final package validator."""
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

from inspect_linux_abi import readelf
from probe_linux_arm64_runtime import contract, elf
from verify_native_runtime_pilot import (
    certificate_material,
    default_trust_handshake,
    png_fixture,
    python_tls_checks,
    qt_tls_checks,
)


def require_security_case(path: Path) -> None:
    cases = [case for case in ET.parse(path).getroot().iter('testcase') if 'test_distrusted_spki' in case.get('name', '')]
    assert cases and all(case.get('status') != 'notrun' and case.find('skipped') is None and case.find('error') is None and case.find('failure') is None for case in cases), 'Executed CPython compromised-SPKI rejection required'


def images(prefix: Path, output: Path) -> dict:
    paths = {Path(line.split()[-1]).resolve() for line in Path('/proc/self/maps').read_text().splitlines() if '/' in line and not line.endswith(' (deleted)')}
    assert not any(re.match(r'lib(?:ssl|crypto)\.so\.3', p.name) for p in paths)
    assert not any(p.is_relative_to(Path(os.environ['PILOT_WORK']) / 'src/libclang') for p in paths)
    assert not any('cxx-sdk' in str(p) for p in paths), 'No foreign C++ link SDK in this native profile'
    rows = []
    for path in sorted(paths):
        if not (path.is_relative_to(prefix) or path.is_relative_to(Path(sys.prefix))) or not path.is_file():
            continue
        with path.open('rb') as stream:
            if stream.read(4) != b'\x7fELF':
                continue
        row = elf(path, target=True)
        dynamic = readelf(path, '--dynamic')
        row.update(needed=re.findall(r'\(NEEDED\).*?\[(.*?)\]', dynamic), search_paths=re.findall(r'\((?:RPATH|RUNPATH)\).*?\[(.*?)\]', dynamic))
        (output / (path.name + '-version-info.txt')).write_text(readelf(path, '--version-info'))
        (output / (path.name + '-dynamic.txt')).write_text(dynamic)
        rows.append(row)
    for stem, directory in [('libssl.so.4', prefix / 'openssl'), ('libcrypto.so.4', prefix / 'openssl'),
                            ('libQt6Core.so.6', prefix / 'qt'), ('libQt6Network.so.6', prefix / 'qt'), ('libpython3.14', prefix / 'python')]:
        matches = [p for p in paths if p.name.startswith(stem)]
        assert matches and all(p.is_relative_to(directory) for p in matches), (stem, matches)
    assert all(p.is_relative_to(prefix / 'qt') for p in paths if p.name.startswith('libQt6'))
    cpp = [p for p in paths if p.name.startswith('libstdc++.so')]
    assert cpp and all(p.is_relative_to(Path('/usr/lib/aarch64-linux-gnu')) for p in cpp), cpp
    png = next(p for p in paths if p.name.startswith('libpng16.so') and p.is_relative_to(prefix))
    query = ctypes.CDLL(str(png)).png_get_libpng_ver
    query.restype = ctypes.c_char_p
    assert query(None) == b'1.6.59'
    pcre = next(p for p in paths if p.name.startswith('libpcre2-16.so') and p.is_relative_to(prefix))
    value = ctypes.create_string_buffer(128)
    assert ctypes.CDLL(str(pcre)).pcre2_config_16(11, value) >= 0
    version = value.raw.decode('utf-16-le').split('\0', 1)[0]
    assert version.startswith('10.49 ')
    return {'changed':rows, 'all_loaded':list(map(str, sorted(paths))), 'cpp_runtime':list(map(str, cpp)),
        'libpng':'1.6.59', 'pcre2':version, 'ceilings':{'GLIBC':'2.38', 'GLIBCXX':'3.4.32'},
        'limits':'Loaded changed closure only; not all-file package/ADB/source/legal or Ubuntu22.04 ARM64 acceptance'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    prefix = Path(os.environ['PILOT_PREFIX']).resolve()
    arm, _ = contract()
    assert sys.platform == 'linux' and platform.machine() == 'aarch64'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '24.04'
    assert platform.python_version() == arm['python_version'] and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert Path(sys.base_prefix).resolve() == prefix / 'python'
    assert Path(ssl.__file__).resolve().is_relative_to(prefix / 'python')
    assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    import _hashlib
    import _ssl

    import PySide6
    import shiboken6
    from cryptography.hazmat.backends.openssl.backend import backend
    from cryptography.hazmat.bindings import _rust
    from PySide6.QtCore import QTimer, qVersion
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtNetwork import QSslSocket
    from PySide6.QtWidgets import QApplication

    assert PySide6.__version__ == shiboken6.__version__ == qVersion() == '6.12.0'
    assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
    for module, library in [(_ssl, 'libssl.so.4'), (_hashlib, 'libcrypto.so.4')]:
        dependencies = subprocess.check_output(['ldd', module.__file__], text=True)
        assert library in dependencies and str(prefix / 'openssl') in dependencies
        (output / f'{module.__name__}-ldd.txt').write_text(dependencies)
    imports = readelf(Path(_rust.__file__), '--dynamic')
    assert not re.search(r'NEEDED.*lib(?:ssl|crypto)\.so', imports), 'cryptography wheel provider must remain independent/static'
    assert _hashlib.openssl_sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    assert hmac.digest(b'key', b'The quick brown fox jumps over the lazy dog', 'sha256').hex() == 'f7bc83f430538424b13298e6aa6fb143ef4d59a14946175997479dbc2d1a3cd8'
    assert hashlib.pbkdf2_hmac('sha256', b'password', b'salt', 1).hex() == '120fb6cffcf8b32c43e7225256c4f837a86548c92ccc35480805987cb70be17b'
    require_security_case(output / 'cpython-regressions.xml')
    cert_root = output / 'isolated-certificates'
    cert_root.mkdir()
    paths = certificate_material(cert_root)
    app = QApplication([])
    assert app.platformName() == 'xcb'
    default_trust = default_trust_handshake()
    python_tls = python_tls_checks(paths)
    qt_tls = qt_tls_checks(paths)
    valid = png_fixture()
    pixmap = QPixmap()
    assert QImage.fromData(valid).width() == 1 and pixmap.loadFromData(valid)
    png = []
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        for index, data in enumerate((b'x\x9c\x00', zlib.compress(b'metadata' * 64)[:-2], b'not-deflate')):
            fixture = png_fixture(kind, data)
            (output / f'malformed-{kind.decode()}-{index}.png').write_bytes(fixture)
            image = QImage.fromData(fixture)
            pixmap.loadFromData(fixture)
            png.append({'kind':kind.decode(), 'case':index, 'decoded':not image.isNull(), 'result':'no native crash; not exploit reproduction'})
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(250, window.close)
    QTimer.singleShot(5000, app.quit)
    app.exec()
    assert not window.isVisible()
    report = {'source_sha':os.environ['GITHUB_SHA'], 'identity':'project-modified CPython ' + arm['python_version'] + '; unchanged reviewed OpenSSL4 patch bytes; matched source Qt/PySide/Shiboken 6.12.0',
        'python':sys.version, 'architecture':platform.machine(), 'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),
        'python_ssl':ssl.OPENSSL_VERSION, 'cryptography_ssl':backend.openssl_version_text(), 'cryptography_provider':'independent official native wheel; static OpenSSL',
        'qt_ssl_build':QSslSocket.sslLibraryBuildVersionString(), 'qt_ssl_runtime':QSslSocket.sslLibraryVersionString(), 'qt_backend':QSslSocket.activeBackend(),
        'default_trust':default_trust, 'python_tls':python_tls, 'qt_tls':qt_tls, 'hash_vectors':'SHA256/HMAC/PBKDF2 PASS',
        'compromised_spki':'executed upstream test_distrusted_spki PASS', 'png':png, 'gui':'native AArch64 xcb MainWindow event-loop PASS',
        'native':images(prefix, output), 'limits':['Diagnostic source prefix only; no final package.', 'No Ubuntu22.04 ARM64 claim; macOS not authorized.', 'Other source profiles require Python3.14.10 qualification before final acceptance.']}
    (output / 'pilot-results.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
