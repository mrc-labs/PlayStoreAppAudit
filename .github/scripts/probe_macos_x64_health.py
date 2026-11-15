"""Cheap native-host health only after two lost Intel runners; no source builds."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from verify_native_runtime_pilot import default_trust_handshake


def main() -> None:
    assert sys.platform == 'darwin' and platform.machine() == 'x86_64'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    output = Path('macos-x64-pilot-evidence')
    output.mkdir(exist_ok=True)
    commands = {
        'xcode': ['xcodebuild', '-version'], 'sdk': ['xcrun', '--sdk', 'macosx', '--show-sdk-version'],
        'clang': ['xcrun', 'clang', '--version'], 'memory': ['sysctl', '-n', 'hw.memsize'],
        'cpu': ['sysctl', '-n', 'machdep.cpu.brand_string'], 'vm': ['vm_stat'],
        'disk': ['df', '-h', os.environ['RUNNER_TEMP']], 'os': ['sw_vers'],
    }
    observed = {name: subprocess.check_output(command, text=True, timeout=30) for name, command in commands.items()}
    report = {'source_sha': os.environ['GITHUB_SHA'], 'machine': platform.machine(), 'python': sys.version,
              'host': observed, 'disk_free_bytes': shutil.disk_usage(os.environ['RUNNER_TEMP']).free,
              'default_trust': default_trust_handshake(), 'scope': 'Fresh native host health only. No download, rebuild, parser, controlled-runtime, framework or candidate qualification.'}
    (output / 'host-health.json').write_text(json.dumps(report, indent=2) + '\n')
    assert observed['xcode'].splitlines()[0] == 'Xcode 26.6'
    assert int(observed['memory']) >= 12 * 1024**3 and report['disk_free_bytes'] >= 20 * 1024**3
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
