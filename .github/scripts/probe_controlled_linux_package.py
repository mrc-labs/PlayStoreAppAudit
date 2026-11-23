"""Bounded Qt source-SDK package closure diagnostic; never a release candidate."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    output = Path('controlled-runtime-evidence/linux-package-probe').resolve()
    output.mkdir()
    work = Path(os.environ['RUNNER_TEMP']) / ('qt-package-probe-' + os.environ['GITHUB_RUN_ID'])
    work.mkdir()
    source = work / 'qt_probe.py'
    source.write_text('''import ssl
import socket
import hashlib
import ctypes
import sqlite3
import lzma
import decimal
import zlib
import cffi
from cryptography.hazmat.backends.openssl.backend import backend
from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
app = QtWidgets.QApplication([])
assert QtCore.qVersion() == '6.12.0'
assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
assert backend.openssl_version_text().startswith('OpenSSL 4.0.3 ')
assert sqlite3.connect(':memory:').execute('select 1').fetchone() == (1,)
assert lzma.decompress(lzma.compress(b'closure')) == b'closure'
assert zlib.decompress(zlib.compress(b'closure')) == b'closure'
assert decimal.Decimal('1.25') * 2 == decimal.Decimal('2.50')
callback = cffi.FFI().callback('int(int)', lambda value: value + 1)
assert callback(41) == 42 and ctypes.c_int(42).value == 42
assert QtNetwork.QSslSocket.supportsSsl()
assert QtNetwork.QSslSocket.sslLibraryVersionString().startswith('OpenSSL 4.0.3 ')
for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
    context = ssl.create_default_context()
    context.minimum_version = context.maximum_version = version
    with socket.create_connection(('www.python.org', 443), timeout=15) as tcp:
        with context.wrap_socket(tcp, server_hostname='www.python.org') as tls:
            assert tls.getpeercert() and context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
for version in (QtNetwork.QSsl.SslProtocol.TlsV1_2, QtNetwork.QSsl.SslProtocol.TlsV1_3):
    tls = QtNetwork.QSslSocket()
    config = tls.sslConfiguration()
    config.setProtocol(version)
    tls.setSslConfiguration(config)
    tls.connectToHostEncrypted('www.python.org', 443)
    assert tls.waitForEncrypted(15000), [error.errorString() for error in tls.sslErrors()]
    assert not tls.peerCertificate().isNull()
    tls.abort()
image = QtGui.QImage(2, 2, QtGui.QImage.Format.Format_ARGB32)
image.fill(QtCore.Qt.GlobalColor.red)
buffer = QtCore.QBuffer()
assert buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
assert image.save(buffer, 'PNG')
assert not QtGui.QImage.fromData(buffer.data(), 'PNG').isNull()
window = QtWidgets.QWidget()
window.show()
QtCore.QTimer.singleShot(50, app.quit)
assert app.exec() == 0
print('PASS relocated controlled Qt/SSL/PNG/GUI package')
''', encoding='utf-8')
    from PySide6 import QtCore

    selection = json.loads(Path(os.environ['PSAA_CONTROLLED_RUNTIME_SELECTION']).read_text())
    source_ldd = subprocess.run(['ldd', QtCore.__file__], capture_output=True, text=True)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'selection': selection,
              'source_qtcore': QtCore.__file__, 'source_ldd': source_ldd.stdout,
              'loader_path': os.environ.get('LD_LIBRARY_PATH'),
              'qt_libraries': QtCore.QLibraryInfo.path(QtCore.QLibraryInfo.LibraryPath.LibrariesPath),
              'scope': 'Tiny standalone closure probe, not an application candidate'}
    command = [sys.executable, '-m', 'nuitka', '--mode=standalone', '--enable-plugin=pyside6',
               '--user-package-configuration-file=.github/scripts/controlled-sdk.nuitka-package.config.yml',
               '--noinclude-dlls=libcrypto.so.3', '--noinclude-dlls=libssl.so.3',
               '--include-qt-plugins=platforms,imageformats,tls', '--noinclude-qt-translations',
               '--assume-yes-for-downloads', '--output-dir=' + str(work),
               '--report=' + str(output / 'compilation-report.xml'), str(source)]
    build = subprocess.run(command, check=False)
    report['build_exit'] = build.returncode
    dist = work / 'qt_probe.dist'
    report['files'] = sorted(p.relative_to(dist).as_posix() for p in dist.rglob('*') if p.is_file())
    report['openssl3_members'] = [p for p in report['files'] if Path(p).name in {'libssl.so.3', 'libcrypto.so.3'}]
    report['ldd'] = {}
    for binary in dist.rglob('*'):
        if binary.is_file() and (binary.name.startswith(('QtCore.', 'libQt6Core.so')) or binary.name == 'qt_probe.bin'):
            result = subprocess.run(['ldd', str(binary)], capture_output=True, text=True)
            report['ldd'][binary.relative_to(dist).as_posix()] = result.stdout + result.stderr
    if build.returncode == 0:
        env = {k: v for k, v in os.environ.items() if k not in {'LD_LIBRARY_PATH', 'PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH'}}
        env['QT_QPA_PLATFORM'] = 'offscreen'
        run = subprocess.run([str(dist / 'qt_probe.bin')], env=env, capture_output=True, text=True, timeout=60)
        report.update(package_exit=run.returncode, stdout=run.stdout, stderr=run.stderr)
        abi = subprocess.run([sys.executable, '.github/scripts/inspect_linux_abi.py', str(dist),
                              '--arch', 'arm64', '--output', str(output / 'abi.json')], check=False)
        report['abi_exit'] = abi.returncode
    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'files', 'selection', 'ldd'}}, indent=2))
    if build.returncode or report.get('package_exit') != 0 or report.get('abi_exit') != 0 or report['openssl3_members']:
        raise SystemExit('Controlled source-SDK package closure failed; inspect retained report')


if __name__ == '__main__':
    main()
