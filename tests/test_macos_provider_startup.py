from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(('arch', 'cpu', 'deployment'), [('arm64', 'arm64', '11.0'), ('x64', 'x86_64', '10.15')])
def test_provider_startup_expands_clean_arch_flags_before_any_download(tmp_path, arch, cpu, deployment):
    bash = shutil.which('bash') if os.name != 'nt' else 'C:/Program Files/Git/bin/bash.exe'
    assert bash and Path(bash).is_file()
    source = (Path(__file__).resolve().parents[1] / '.github/scripts/probe_macos_native_providers.sh').read_text()
    assert source.count('mkdir -p "$work/src"') == 1
    startup = source.split('mkdir -p "$work/src"', 1)[0]
    fixtures = r'''uname() { if [ "$1" = -s ]; then echo Darwin; elif [ "$EXPECTED_ARCH" = arm64 ]; then echo arm64; else echo x86_64; fi; }
xcodebuild() { printf 'Xcode 26.6\nBuild version 26G111\n'; }
xcrun() { printf '/native/%s\n' "$2"; }
sysctl() { echo 0; }
'''
    environment = {key: value for key, value in os.environ.items() if key not in {'CFLAGS', 'CXXFLAGS'}}
    environment['EXPECTED_ARCH'] = arch
    result = subprocess.run([bash, '--noprofile', '--norc', '-c', fixtures + startup +
                             '\nprintf "%s\n" "$CFLAGS" "$CXXFLAGS" "$MACOSX_DEPLOYMENT_TARGET"',
                             'startup-fixture', str(tmp_path / 'uncreated-work')],
                            env=environment, text=True, capture_output=True, check=True)
    assert result.stdout.splitlines() == [f'-arch {cpu} -mmacosx-version-min={deployment}'] * 2 + [deployment]
    assert not (tmp_path / 'uncreated-work').exists()
