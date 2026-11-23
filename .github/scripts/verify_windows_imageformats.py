"""Add only matching QtImageFormats to a byte-verified native Windows SDK."""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path

from complete_qt_imageformats import complete, image_consumers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    assert platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    prefix = args.work / 'prefix'
    handles = [os.add_dll_directory(str(prefix / directory))
               for directory in ['python', 'qt/bin', 'bin', 'openssl/bin']]
    os.environ['QT_PLUGIN_PATH'] = str(prefix / 'qt/plugins')
    os.environ.pop('QT_QPA_PLATFORM', None)
    complete(args.work, args.output, [
        '-DCMAKE_C_COMPILER=cl', '-DCMAKE_CXX_COMPILER=cl',
        '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
        '-DCMAKE_SYSTEM_PROCESSOR=' + ('ARM64' if arch == 'arm64' else 'AMD64'),
    ])
    from PySide6.QtCore import QTimer
    from PySide6.QtNetwork import QSslSocket
    from PySide6.QtWidgets import QApplication

    app = QApplication([])
    assert app.platformName() == 'windows'
    assert QSslSocket.setActiveBackend('openssl') and QSslSocket.supportsSsl()
    codecs = image_consumers(args.output / 'imageformats')
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    profile = args.work / 'imageformats-profile'
    profile.mkdir()
    (profile / 'PlayStoreAppAudit.portable').write_text('isolated diagnostic\n')
    os.chdir(profile)
    from playstore_app_audit.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    QTimer.singleShot(750, app.quit)
    assert app.exec() == 0
    window.close()
    if arch == 'arm64':
        from verify_windows_arm64_runtime_pilot import images
    else:
        from verify_windows_runtime_pilot import images
    native = images(prefix, args.output)
    assert sum('/imageformats/' in row['path'].replace('\\', '/') for row in native['changed']) >= 5
    subprocess.run([sys.executable, str(root / 'main.py'), 'cli', 'audit', '--help'], check=True)
    subprocess.run([sys.executable, '-m', 'pytest', str(root / 'tests/test_scraper_transport_tls.py'),
                    '-q', '-p', 'no:cacheprovider'], cwd=root, check=True)
    (args.output / 'windows-imageformats-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'arch': arch, 'codecs': codecs, 'native': native,
        'gui': 'native Windows MainWindow event-loop PASS',
        'scope': 'Matching module only. Original runtime/QtBase/binding/provider evidence retained; no final candidate.'}, indent=2))
    assert handles  # Keep secure private DLL directories alive through all consumers.


if __name__ == '__main__':
    main()
