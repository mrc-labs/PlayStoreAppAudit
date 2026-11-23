"""Qualify existing native external ADB discovery without rebuilding or bundling it."""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact
from inspect_linux_abi import readelf, required_versions
from probe_adb_linux_arm64 import within_floor

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    assert sys.platform == 'linux' and platform.machine() == 'aarch64'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '24.04'
    spec = json.loads((ROOT / '.github/scripts/adb_linux_arm64_external_inputs.json').read_text())
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    work = Path(os.environ['RUNNER_TEMP']) / f'external-adb-{os.environ["GITHUB_RUN_ID"]}-{os.environ["GITHUB_RUN_ATTEMPT"]}'
    assert not work.exists()
    work.mkdir()
    output = ROOT / 'adb-diagnostic-evidence'
    output.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        source = json.loads(original.read('adb_linux_arm64_sources.json'))
        assert hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == spec['source_contract_canonical_sha256']
        for member, relative, digest in [('adb', 'libexec/adb', spec['adb_sha256']),
                (spec['libusb_member'], 'lib/libusb-1.0.so.0', spec['libusb_sha256'])]:
            raw = original.read(member)
            assert hashlib.sha256(raw).hexdigest() == digest
            assert raw[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', raw, 18)[0] == 183
            target = work / relative
            target.parent.mkdir()
            target.write_bytes(raw)
            target.chmod(0o755)
            within_floor(required_versions(readelf(target, '--version-info')))
    wrapper = work / 'bin/adb'
    wrapper.parent.mkdir()
    wrapper.write_text('#!/bin/sh\nset -eu\nroot=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\n'
                       'export LD_LIBRARY_PATH="$root/lib"\n'
                       'printf "%s\\n" "$*" >> "$PSAA_ADB_TRACE"\n'
                       'exec "$root/libexec/adb" "$@"\n')
    wrapper.chmod(0o755)
    profile = work / 'profile'
    profile.mkdir()
    trace = output / 'private-client-commands.log'
    os.environ.update(HOME=str(profile), ANDROID_USER_HOME=str(profile), ADB_SERVER_PORT='15037',
        ADB_SERVER_SOCKET='tcp:localhost:15037', ADB_MDNS_AUTO_CONNECT='0', PSAA_ADB_TRACE=str(trace),
        XDG_CONFIG_HOME=str(profile / 'config'), XDG_DATA_HOME=str(profile / 'data'), XDG_CACHE_HOME=str(profile / 'cache'),
        PATH=str(wrapper.parent) + os.pathsep + os.environ['PATH'])
    loader_environment = {**os.environ, 'LD_LIBRARY_PATH': str(work / 'lib')}
    linkage = subprocess.check_output(['ldd', str(work / 'libexec/adb')], env=loader_environment, text=True)
    assert 'not found' not in linkage and str(work / 'lib/libusb-1.0.so.0') in linkage
    (output / 'relocated-linkage.txt').write_text(linkage)
    sys.path.insert(0, str(ROOT))
    from playstore_app_audit.devices.adb import find_adb, is_authorised, run_adb

    selected = find_adb()
    assert selected == str(wrapper), selected
    version = run_adb(selected, 'version').stdout
    assert '37.0.0' in version
    try:
        devices = run_adb(selected, '-P', '15037', 'devices', '-l').stdout
        assert devices.strip() == 'List of devices attached' and not is_authorised(selected)
        before = trace.stat().st_size
        cli = subprocess.run([sys.executable, str(ROOT / 'main.py'), 'cli', 'audit', 'phone',
                              '--country', 'us', '--language', 'en'], capture_output=True, text=True, timeout=60)
        (output / 'cli-no-device.stdout').write_text(cli.stdout)
        (output / 'cli-no-device.stderr').write_text(cli.stderr)
        assert cli.returncode == 3 and 'No final output was written' in cli.stderr
        commands = trace.read_bytes()[before:].decode().splitlines()
        assert 'version' in commands and any('devices' in command for command in commands), commands
    finally:
        run_adb(selected, '-P', '15037', 'kill-server')  # This task's private port only.
    (output / 'external-adb-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'original': spec, 'selected': selected,
        'version': version, 'wrapper': wrapper.read_text(), 'relocated_private_libusb': spec['libusb_sha256'],
        'read_only_discovery': devices, 'cli_no_device_exit': cli.returncode,
        'scope': 'Native Noble external PATH route only; no ADB in application, automatic download, OS trust change, physical-device or final-package acceptance.'}, indent=2))


if __name__ == '__main__':
    main()
