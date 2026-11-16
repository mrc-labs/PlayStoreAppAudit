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


def qualify_icon_service(output: Path, *, allow_runner_mitigation: bool = False) -> None:
    """Fail before SDK downloads if the measured native IconServices path hangs."""
    output.mkdir(exist_ok=True)
    executable = output.resolve() / 'native-cocoa-icon-service'
    source = Path(__file__).with_name('macos_icon_service_probe.mm').resolve()
    subprocess.run(['xcrun', 'clang++', '-arch', 'x86_64', '-mmacosx-version-min=14.4',
                    '-framework', 'AppKit', '-framework', 'UniformTypeIdentifiers',
                    str(source), '-o', str(executable)], check=True, timeout=60)
    with (
        (output / 'native-cocoa-icon-service.log').open('w') as log,
        subprocess.Popen([str(executable)], stdout=log, stderr=subprocess.STDOUT) as process,
    ):
        try:
            status = process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            try:
                subprocess.run(['sample', str(process.pid), '3', '-file',
                                str(output.resolve() / 'native-cocoa-icon-service-stack.txt')],
                               stdout=log, stderr=subprocess.STDOUT, timeout=20, check=False)
            finally:
                process.kill()  # Only this failed prerequisite child, never OS services.
                process.wait(timeout=20)
            if allow_runner_mitigation:
                # Image-specific, independently reproduced without Qt. Never apply
                # this to a user's Mac or silently substitute an offscreen GUI.
                mitigate_hosted_icon_service(output)
                qualify_icon_service(output / 'after-runner-mitigation')
                return
            raise RuntimeError('Native Cocoa IconServices timed out without Python/Qt; SDK replay not started') from None
    text = (output / 'native-cocoa-icon-service.log').read_text()
    print(text, flush=True)
    assert status == 0 and 'Native Cocoa IconServices PASS' in text, (status, text)


def mitigate_hosted_icon_service(output: Path) -> None:
    assert platform.machine() == 'x86_64'
    assert os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
    assert subprocess.check_output(['sw_vers', '-productVersion'], text=True).strip() == '26.6.1'
    label = f'gui/{os.getuid()}/com.apple.iconservices.iconservicesagent'
    results = []
    for command in [['launchctl', 'bootout', label], ['launchctl', 'disable', label]]:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        results.append({'command': command, 'returncode': result.returncode,
                        'stdout': result.stdout, 'stderr': result.stderr})
    # bootout may report Bad request for the already-crashed agent.
    # Disabling must succeed; a fresh native API probe must still pass.
    assert results[-1]['returncode'] == 0, results
    (output / 'runner-iconservices-mitigation.json').write_text(json.dumps({
        'source': 'https://github.com/actions/runner-images/issues/14751',
        'scope': 'Ephemeral hosted Intel26.6.1 VM only; native generic icons. No application/package patch or security verification change.',
        'commands': results}, indent=2))


def main() -> None:
    assert sys.platform == 'darwin' and platform.machine() == 'x86_64'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    output = Path('macos-x64-pilot-evidence')
    output.mkdir(exist_ok=True)
    qualify_icon_service(output)
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
