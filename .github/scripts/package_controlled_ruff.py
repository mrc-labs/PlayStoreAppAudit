"""Package the qualified modified Ruff through its upstream Maturin backend."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import venv
import zipfile
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]


def prepare(root: Path, output: Path) -> Path:
    output = output.resolve()
    spec_path = REPO / '.github/scripts/ruff_packaging_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, output)
    apply_source_patch(root, spec['metadata_patch'])
    shutil.copy2(REPO / spec['metadata_patch']['path'], output)
    arch = 'arm64' if platform.machine().lower() in {'arm64', 'aarch64'} else 'x64'
    target = {'win32': 'windows', 'darwin': 'macos', 'linux': 'linux'}[sys.platform] + '-' + arch
    files = []
    for item in [spec['source'], spec['wheels'][target]]:
        with urllib.request.urlopen(item['url'], timeout=120) as response:
            assert response.geturl().startswith('https:')
            raw = response.read()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        path = output / 'sources' / item['name']
        path.write_bytes(raw)
        files.append(path)
    environment = output.parent / 'ruff-packaging-environment'
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([python, REPO / '.github/scripts/bootstrap_pip.py'], check=True)
    subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--no-deps', files[1]], check=True)
    actual = subprocess.check_output([python, '-m', 'maturin', '--version'], text=True).strip()
    assert actual == 'maturin ' + spec['version'], actual
    return python


def package(root: Path, output: Path, python: Path) -> dict:
    root, output = root.resolve(), output.resolve()
    spec = json.loads((REPO / '.github/scripts/ruff_packaging_sources.json').read_text())
    wheels = output / 'wheels'
    wheels.mkdir()
    command = [python, '-m', 'maturin', 'build', '--locked', '--release', '--out', wheels]
    # Honest native-host tool wheels; no application/portable manylinux claim,
    # no auditwheel substitution or copied system C++/OS libraries.
    if sys.platform == 'linux':
        command += ['--compatibility', 'linux']
    environment = {**os.environ, 'CARGO_BUILD_JOBS': '2'}
    if os.name == 'nt':
        environment['RUSTFLAGS'] = '-C target-feature=-crt-static'
    if sys.platform == 'darwin':
        environment['MACOSX_DEPLOYMENT_TARGET'] = '11.0' if platform.machine() == 'arm64' else '10.15'
    with (output / 'ruff-wheel-build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, cwd=root, env=environment, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print((output / 'ruff-wheel-build.log').read_text(encoding='utf-8')[-5000:], flush=True)
    result.check_returncode()
    built = list(wheels.glob('ruff-*.whl'))
    assert len(built) == 1 and ('ruff-' + spec['distribution_version'] + '-') in built[0].name
    with zipfile.ZipFile(built[0]) as archive:
        names = [n for n in archive.namelist() if Path(n).name in {'ruff', 'ruff.exe'} and not n.endswith('/')]
        assert len(names) == 1
        binary = archive.read(names[0])
        binary_sha = hashlib.sha256(binary).hexdigest()
        assert any('LICENSE' in n.upper() for n in archive.namelist())
    subprocess.run([python, '-m', 'pip', 'install', '--no-index', '--no-deps', built[0]], check=True)
    actual = subprocess.check_output([python, '-c', 'from importlib.metadata import version; print(version("ruff"))'], text=True).strip()
    assert actual == spec['distribution_version']
    assert subprocess.check_output([python, '-m', 'ruff', '--version'], text=True).startswith('ruff 0.17.5')
    scripts = python.parent
    binary_path = scripts / ('ruff.exe' if os.name == 'nt' else 'ruff')
    assert hashlib.sha256(binary_path.read_bytes()).hexdigest() == binary_sha
    if os.name == 'nt':
        from inspect_pe import read_pe_machine
        assert read_pe_machine(binary_path) == (0xAA64 if platform.machine().lower() == 'arm64' else 0x8664)
    elif sys.platform == 'darwin':
        assert subprocess.check_output(['lipo', '-archs', binary_path], text=True).split() == [platform.machine()]
    else:
        assert binary[:6] == b'\x7fELF\x02\x01'
        assert int.from_bytes(binary[18:20], 'little') == (183 if platform.machine() == 'aarch64' else 62)
    from probe_selected_rust_graphs import ruff_codemod_consumer
    consumer = output / 'wheel-consumer'
    consumer.mkdir()
    ruff_codemod_consumer(binary_path, consumer)
    subprocess.run([python, '-m', 'ruff', 'check', '--no-cache', 'playstore_app_audit', 'tests', 'main.py'], cwd=REPO, check=True)
    report = {'distribution': actual, 'wheel': built[0].name, 'wheel_sha256': hashlib.sha256(built[0].read_bytes()).hexdigest(),
              'native_binary_sha256': binary_sha, 'backend': 'maturin ' + spec['version'], 'metadata_patch': spec['metadata_patch'],
              'checks': ['exact installed binary bytes/native architecture', 'upstream Python wrapper', 'actual codemods/executed semantics', 'repository lint'],
              'scope': 'Project-modified native developer-tool wheel only; no application/package/producer acceptance', 'result': 'PASS'}
    (output / 'ruff-wheel-results.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
