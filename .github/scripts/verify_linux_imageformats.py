"""Native image-module/GUI/ELF consumer; never rebuild the existing Linux SDK."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from complete_qt_imageformats import complete, image_consumers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['linux-x64', 'linux-arm64'], required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'linux'
    arm = args.target == 'linux-arm64'
    assert platform.machine() == ('aarch64' if arm else 'x86_64')
    compiler = 'gcc-13' if arm else 'gcc-11'
    assert subprocess.check_output([compiler, '-dumpversion'], text=True).strip().split('.')[0] == ('13' if arm else '11')
    prefix = args.work / 'prefix'
    complete(args.work, args.output, [
        '-DCMAKE_C_COMPILER=' + compiler, '-DCMAKE_CXX_COMPILER=' + ('g++-13' if arm else 'g++-11'),
        '-DCMAKE_CXX_FLAGS=' + os.environ.get('CXXFLAGS', ''),
        '-DCMAKE_INSTALL_RPATH=' + ';'.join(str(prefix / name) for name in ['qt/lib', 'python/lib', 'lib', 'openssl/lib'])])
    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QSslSocket
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    assert app.platformName() == 'xcb'
    assert QSslSocket.setActiveBackend('openssl') and QSslSocket.supportsSsl()
    codecs = image_consumers(args.output / 'imageformats')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    profile = args.work / 'imageformats-profile'
    profile.mkdir(exist_ok=True)
    (profile / 'PlayStoreAppAudit.portable').write_text('isolated diagnostic\n')
    os.chdir(profile)
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(750, app.quit)
    assert app.exec() == 0
    window.close()
    if arm:
        from verify_linux_arm64_runtime_pilot import images
        native = images(prefix, args.output)
    else:
        from verify_native_runtime_pilot import native_images
        native = {'changed': native_images(prefix), 'ceilings': {'GLIBC': '2.35', 'GLIBCXX': '3.4.29'}}
    assert sum('/imageformats/' in row['path'] for row in native['changed']) >= 5
    subprocess.run([sys.executable, str(root / 'main.py'), 'cli', 'audit', '--help'], check=True)
    subprocess.run([sys.executable, '-m', 'pytest', str(root / 'tests/test_scraper_transport_tls.py'),
                    '-q', '-p', 'no:cacheprovider'], cwd=root, check=True)
    (args.output / 'linux-imageformats-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'target': args.target, 'codecs': codecs, 'native': native,
        'gui': 'native xcb MainWindow event-loop PASS under Xvfb',
        'scope': 'Matching module only; original controlled runtime/QtBase/binding/provider identities retained. No final package.'}, indent=2))


if __name__ == '__main__':
    main()
