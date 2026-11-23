"""Native tiny source-SDK bundle relocation probe; never an application candidate."""
from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

from inspect_macos_package import inspect
from normalize_macos_bundle import DEVICE_PROFILE_FILENAMES, DEVICE_PROFILE_RESOURCE_PARENT, normalize_bundle
from relocate_macos_sdk_rpaths import relocate


def main() -> None:
    selection_path = Path(os.environ['PSAA_CONTROLLED_RUNTIME_SELECTION'])
    selection = json.loads(selection_path.read_text())
    arch = selection['target'].removeprefix('macos-')
    assert sys.platform == 'darwin' and arch in {'arm64', 'x64'}
    output = Path('controlled-runtime-evidence/macos-package-probe').resolve()
    output.mkdir(parents=True)
    work = Path(os.environ['RUNNER_TEMP']) / ('macos-package-probe-' + os.environ['GITHUB_RUN_ID'])
    work.mkdir()
    source = work / 'PlayStoreAppAuditClosureProbe.py'
    source.write_text('''import ssl, socket, hashlib, sys
from playstore_app_audit.platform.certificates import configure_packaged_python_trust
configure_packaged_python_trust(packaged=True)
from PySide6 import QtCore, QtGui, QtNetwork, QtWidgets
app = QtWidgets.QApplication([])
assert QtCore.qVersion() == '6.12.0'
assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
assert hashlib.sha256(b'abc').hexdigest() == 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
for version in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
    context = ssl.create_default_context()
    context.minimum_version = context.maximum_version = version
    with socket.create_connection(('www.python.org',443), timeout=15) as tcp:
        with context.wrap_socket(tcp, server_hostname='www.python.org') as tls:
            assert tls.getpeercert() and context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
backend = sys.argv[1]
versions = [QtNetwork.QSsl.SslProtocol.TlsV1_2, QtNetwork.QSsl.SslProtocol.TlsV1_3] if backend == 'openssl' else [QtNetwork.QSsl.SslProtocol.TlsV1_2]
for backend, versions in [(backend, versions)]:
    assert QtNetwork.QSslSocket.setActiveBackend(backend)
    for version in versions:
        tls = QtNetwork.QSslSocket()
        config = tls.sslConfiguration()
        config.setProtocol(version)
        tls.setSslConfiguration(config)
        tls.connectToHostEncrypted('www.python.org',443)
        assert tls.waitForEncrypted(15000), [e.errorString() for e in tls.sslErrors()]
        assert not tls.peerCertificate().isNull()
        tls.abort()
        del tls
image=QtGui.QImage(2,2,QtGui.QImage.Format.Format_ARGB32)
image.fill(QtCore.Qt.GlobalColor.red)
buffer=QtCore.QBuffer()
assert buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly) and image.save(buffer,'PNG')
assert not QtGui.QImage.fromData(buffer.data(),'PNG').isNull()
widget=QtWidgets.QWidget()
widget.show()
QtCore.QTimer.singleShot(50, app.quit)
assert app.exec()==0
print('PASS relocated native macOS package: Python PEM and distinct Qt/Keychain trust, TLS/hash/PNG/GUI')
''', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(Path.cwd()),
           'MACOSX_DEPLOYMENT_TARGET': '11.0' if arch == 'arm64' else '10.15'}
    command = [sys.executable, '-m', 'nuitka', '--mode=app-dist', '--enable-plugin=pyside6',
               '--noinclude-qt-translations',
               '--user-package-configuration-file=.github/scripts/controlled-sdk.nuitka-package.config.yml',
               '--include-qt-plugins=platforms,imageformats,tls', '--assume-yes-for-downloads',
               '--noinclude-dlls=libssl.dylib', '--noinclude-dlls=libcrypto.dylib',
               '--noinclude-dlls=libssl.3.dylib', '--noinclude-dlls=libcrypto.3.dylib',
               '--include-data-dir=docs/images=help-images', '--output-dir=' + str(work),
               '--report=' + str(output / 'compilation-report.xml')]
    # Use the producer's actual canonical data layout/signing path, even though
    # this probe deliberately compiles only the affected runtime consumers.
    xml = Path(find_spec('pyaxmlparser').origin).parent / 'resources/public.xml'
    assert xml.is_file()
    command.append('--include-data-files=' + str(xml) + '=pyaxmlparser/resources/public.xml')
    for filename in DEVICE_PROFILE_FILENAMES:
        relative = (Path(DEVICE_PROFILE_RESOURCE_PARENT) / filename).as_posix()
        command.append('--include-data-files=' + relative + '=' + relative)
    subprocess.run([*command, str(source)], env=env, check=True)
    apps = list(work.glob('*.app'))
    assert len(apps) == 1
    app = apps[0]
    # The producer creates Resources with its icon; this icon-free probe needs
    # the same directory before the unchanged strict resource normalization.
    (app / 'Contents/Resources').mkdir(exist_ok=True)
    normalize_bundle(app)
    relocation = relocate(app, selection_path, arch)
    (output / 'relocation.json').write_text(json.dumps(relocation, indent=2))
    images = inspect(app, arch)
    (output / 'images.json').write_text(json.dumps(images, indent=2))
    subprocess.run([sys.executable, '.github/scripts/sign_macos_app.py', '--app', str(app), '--identity', '-'], check=True)
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    executable = app / 'Contents/MacOS' / info['CFBundleExecutable']
    for key in ('PYTHONHOME', 'PYTHONPATH', 'QT_PLUGIN_PATH', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR'):
        env.pop(key, None)
    env['QT_QPA_PLATFORM'] = 'offscreen'
    results = {}
    for backend in ['openssl', 'securetransport']:
        result = subprocess.run([str(executable), backend], env=env, capture_output=True, text=True, timeout=90)
        results[backend] = {'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
        print(backend, result.stdout, result.stderr)
    (output / 'result.json').write_text(json.dumps({'source_sha': os.environ['GITHUB_SHA'],
        'target': selection['target'], 'compiled_source_sha': selection['compiled_source_sha'],
        'maximum_minos': images['measured_maximum_deployment'], 'images': len(images['images']),
        'backends': results,
        'scope': 'Native diagnostic standalone, ad-hoc only; not the final application or older-OS execution'}, indent=2))
    assert all(result['exit'] == 0 for result in results.values()), results


if __name__ == '__main__':
    main()
