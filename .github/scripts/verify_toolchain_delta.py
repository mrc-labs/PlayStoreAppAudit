"""Bounded native pip/dev/compiler check; no application or release build."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
from importlib.metadata import version
from pathlib import Path

from inspect_pe import read_pe_machine


def run(args: list, output: Path) -> str:
    result = subprocess.run(list(map(str, args)), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output.write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        print(result.stdout[-12000:], flush=True)
    result.check_returncode()
    return result.stdout


def main() -> None:
    output = Path('toolchain-delta-evidence')
    output.mkdir(exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert platform.python_version() == '3.14.10' and sys.version_info.releaselevel == 'final'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    expected = os.environ['EXPECTED_ARCH']
    machine = platform.machine().lower()
    assert machine in ({'arm64', 'aarch64'} if expected == 'arm64' else {'amd64', 'x86_64'})
    if sys.platform == 'darwin':
        assert os.environ['DEVELOPER_DIR'] == '/Applications/Xcode_26.6.app/Contents/Developer'
        xcode = run(['xcodebuild', '-version'], output / 'xcode.txt')
        assert xcode.splitlines()[0] == 'Xcode 26.6'
    selected = {name: version(name) for name in ['pip', 'Nuitka', 'pytest', 'ruff', 'mypy']}
    assert selected == {'pip': '26.3', 'Nuitka': '4.3.4', 'pytest': '9.2.0', 'ruff': '0.17.3', 'mypy': '2.4.1'}
    import pip._vendor.urllib3
    from nuitka.build.SconsInterface import getInlineSconsVersion

    assert pip._vendor.urllib3.__version__ == '2.8.0'
    scons = getInlineSconsVersion()
    # Record the actual unresolved integration; never claim the parent fixes it.
    assert scons == 'scons-4.10.1'
    run([sys.executable, '-m', 'nuitka', '--version'], output / 'nuitka-version.txt')
    source = output / 'probe_toolchain.py'
    source.write_text('def result(value: int) -> int:\n    return sum(i * i for i in range(value))\n', encoding='utf-8')
    run([sys.executable, '-m', 'ruff', 'check', source], output / 'ruff.log')
    run([sys.executable, '-m', 'mypy', '--no-incremental', source], output / 'mypy.log')
    invalid = output / 'invalid_types.py'
    invalid.write_text('amount: int = "incorrect"\n', encoding='utf-8')
    rejected = subprocess.run([sys.executable, '-m', 'mypy', '--no-incremental', str(invalid)], text=True, capture_output=True)
    (output / 'mypy-negative.log').write_text(rejected.stdout + rejected.stderr, encoding='utf-8')
    assert rejected.returncode == 1 and '[assignment]' in rejected.stdout
    binary = output / 'compiled'
    run([sys.executable, '-m', 'nuitka', '--module', '--output-dir=' + str(binary),
         '--report=' + str(output / 'nuitka-report.xml'), '--jobs=2', '--assume-yes-for-downloads', source], output / 'compiler.log')
    modules = [p for p in binary.iterdir() if p.suffix in ('.pyd', '.so')]
    assert len(modules) == 1, modules
    module = modules[0]
    run([sys.executable, '-c', "import sys;sys.path.insert(0,sys.argv[1]);import probe_toolchain;assert probe_toolchain.result(7)==91;print('Native compiled module roundtrip PASS')", binary.resolve()], output / 'execution.log')
    test = output / 'test_native_module.py'
    test.write_text('import probe_toolchain\n\ndef test_compiled_result():\n    assert probe_toolchain.result(7) == 91\n', encoding='utf-8')
    run([sys.executable, '-c', "import sys;sys.path.insert(0,sys.argv[1]);import pytest;raise SystemExit(pytest.main([sys.argv[2],'-q','-p','no:cacheprovider']))", binary.resolve(), test.resolve()], output / 'pytest.log')
    if sys.platform == 'win32':
        architecture = read_pe_machine(module)
        assert architecture == (0xAA64 if expected == 'arm64' else 0x8664)
    elif sys.platform == 'darwin':
        architecture = run(['lipo', '-archs', module], output / 'architecture.txt').strip()
        assert architecture == ('arm64' if expected == 'arm64' else 'x86_64')
        run(['otool', '-l', module], output / 'macho-load-commands.txt')
    else:
        architecture = run(['readelf', '-h', module], output / 'architecture.txt')
        assert ('AArch64' if expected == 'arm64' else 'X86-64') in architecture
        run(['readelf', '--version-info', module], output / 'elf-version-needs.txt')
    run([sys.executable, '-m', 'pip', 'check'], output / 'pip-check.txt')
    report = {'source_sha': head, 'scope': 'Native host tool qualification only; not controlled runtime/framework, package ABI or release acceptance', 'machine': machine, 'python': sys.version, 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'), 'selected': selected, 'pip_vendor_urllib3': pip._vendor.urllib3.__version__, 'actual_scons': scons, 'scons_gate': 'R15 remains blocked; no experimental override', 'native_module': str(module), 'native_module_sha256': hashlib.sha256(module.read_bytes()).hexdigest(), 'architecture': architecture, 'result': 'PASS native bootstrap/install/compiler/module; R15 and final package gates remain open'}
    (output / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
