"""Qualify only the matching image module on the retained native ARM64 Mac SDK."""
from __future__ import annotations

import argparse
import json
import lzma
import os
import platform
import ssl
import subprocess
import sys
import sysconfig
from compression import zstd
from pathlib import Path

from complete_qt_imageformats import complete, image_consumers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse-overlay', action='store_true')
    args = parser.parse_args()
    assert sys.platform == 'darwin' and platform.machine() == 'arm64'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 ')
    assert lzma.decompress(lzma.compress(b'codec')) == zstd.decompress(zstd.compress(b'codec')) == b'codec'
    prefix = args.work / 'prefix'
    arguments = ['-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=14.4',
                 '-DCMAKE_OSX_SYSROOT=' + subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip(),
                 '-DCMAKE_C_COMPILER=' + subprocess.check_output(['xcrun', '--find', 'clang'], text=True).strip(),
                 '-DCMAKE_CXX_COMPILER=' + subprocess.check_output(['xcrun', '--find', 'clang++'], text=True).strip(),
                 '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local',
                 '-DCMAKE_INSTALL_RPATH=' + ';'.join(str(prefix / name) for name in ['qt/lib', 'lib', 'openssl/lib'])]
    if args.reuse_overlay:
        assert (args.output / 'imageformats/overlay-intake.json').is_file()
    else:
        complete(args.work, args.output, arguments)
    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QSslSocket
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    assert app.platformName() == 'cocoa'
    assert QSslSocket.setActiveBackend('openssl') and QSslSocket.supportsSsl()
    codecs = image_consumers(args.output / 'imageformats')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    profile = args.work / 'imageformats-profile'
    profile.mkdir()
    (profile / 'PlayStoreAppAudit.portable').write_text('isolated diagnostic\n')
    os.chdir(profile)
    from verify_macos_arm64_runtime_pilot import images

    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(750, app.quit)
    assert app.exec() == 0
    window.close()
    native = images(prefix, args.output)
    assert sum('/imageformats/' in row['path'] for row in native['changed']) >= 5
    subprocess.run([sys.executable, str(root / 'main.py'), 'cli', 'audit', '--help'], check=True)
    subprocess.run([sys.executable, '-m', 'pytest', str(root / 'tests/test_scraper_transport_tls.py'),
                    str(root / 'tests/test_packaged_python_trust.py'), '-q', '-p', 'no:cacheprovider'], cwd=root, check=True)
    (args.output / 'macos-arm64-imageformats-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'codecs': codecs, 'native': native,
        'gui': 'native Cocoa MainWindow event-loop PASS',
        'scope': 'Matching module only; original runtime/QtBase/binding/provider identities preserved. No final package/signing/older-OS acceptance.'}, indent=2))


if __name__ == '__main__':
    main()
