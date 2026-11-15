"""Qualify source codecs with original native same-patch CPython C wrappers."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import fetch, run
from inspect_pe import read_pe_machine
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.python_version() == '3.14.10'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    assert platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == arch
    compiler = Path(shutil.which('cl') or '').resolve(strict=True)
    assert compiler.is_file() and read_pe_machine(compiler) == machine
    toolset = compiler.parents[3].name
    assert toolset.startswith('14.52.'), compiler
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    output = REPO / 'toolchain-delta-evidence'
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    sources = output / 'sources'
    sources.mkdir()
    spec_path = REPO / '.github/scripts/windows_codec_provider_sources.json'
    spec = json.loads(spec_path.read_text())
    assert [row['name'] for row in spec['sources']] == ['Python-3.14.10.tar.xz', 'xz-5.8.4.tar.xz', 'zlib-ng-2.3.3.tar.gz']
    shutil.copy2(spec_path, output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(lambda row: fetch(row, sources), spec['sources']))
    for row, archive in zip(spec['sources'], archives, strict=True):
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
        legal = output / 'legal' / row['directory']
        legal.mkdir(parents=True)
        for path in (work / row['directory']).iterdir():
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT', 'NOTICE', 'AUTHORS')):
                shutil.copy2(path, legal / path.name)
    prefix = work / 'prefix'
    for directory, name, extra in [
        ('xz-5.8.4', 'xz', ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=ON']),
        ('zlib-ng-2.3.3', 'zlib-ng', ['-DBUILD_SHARED_LIBS=OFF', '-DZLIB_COMPAT=ON',
         '-DBUILD_TESTING=ON', '-DWITH_GTEST=OFF', '-DWITH_BENCHMARKS=OFF',
         '-DWITH_NATIVE_INSTRUCTIONS=OFF', '-DWITH_RUNTIME_CPU_DETECTION=ON'])]:
        build = work / (name + '-build')
        run(['cmake', '-S', work / directory, '-B', build, '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
             '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
             *extra], log=output / (name + '-configure.log'))
        shutil.copy2(build / 'CMakeCache.txt', output / (name + '-CMakeCache.txt'))
        run(['cmake', '--build', build, '--parallel', '2'], log=output / (name + '-build.log'))
        run(['ctest', '--test-dir', build, '--output-on-failure', '--no-tests=error'], log=output / (name + '-tests.log'))
        run(['cmake', '--install', build], log=output / (name + '-install.log'))
    python_source = work / 'Python-3.14.10'
    modules = work / 'native-codecs'
    modules.mkdir()
    includes = ['/I' + str(python_source / 'PC'), '/I' + str(python_source / 'Include'),
                '/I' + str(python_source / 'Include/internal'), '/I' + str(prefix / 'include')]
    python_lib = Path(sys.base_prefix) / 'libs/python314.lib'
    libraries = list((prefix / 'lib').glob('*.lib'))
    zlib = [p for p in libraries if 'zlib' in p.name.lower()]
    lzma = [p for p in libraries if 'lzma' in p.name.lower()]
    assert len(zlib) == len(lzma) == 1, libraries
    for module, source, library in [('zlib', 'zlibmodule.c', zlib[0]), ('_lzma', '_lzmamodule.c', lzma[0])]:
        run([compiler, '/nologo', '/MD', '/O2', '/LD', '/DPy_BUILD_CORE_MODULE',
             '/D_CRT_SECURE_NO_WARNINGS', *includes, python_source / 'Modules' / source,
             '/link', python_lib, library, '/OUT:' + str(modules / (module + '.pyd'))],
            cwd=modules, log=output / (module + '-wrapper-build.log'))
    for dll in (prefix / 'bin').glob('*.dll'):
        shutil.copy2(dll, modules / dll.name)
    images = []
    for path in modules.iterdir():
        if path.suffix.lower() not in {'.dll', '.pyd'}:
            continue
        assert read_pe_machine(path) == machine
        versions = pe_versions(path)
        assert all(v <= (10, 0) for v in versions.values())
        imports = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
        assert 'VCRUNTIME' in imports.upper()
        if path.name == 'zlib.pyd':
            assert not any(name in imports.lower() for name in ['zlib1.dll', 'zlib.dll', 'zlib-ng.dll'])
        shutil.copy2(path, output / path.name)
        images.append({'name': path.name, 'machine': machine, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'versions': versions, 'imports': imports})
    lzma_dlls = [p.name for p in modules.glob('*.dll') if 'lzma' in p.name.lower()]
    assert len(lzma_dlls) == 1
    run([sys.executable, '-I', REPO / '.github/scripts/windows_codec_consumer.py',
         '--modules', modules, '--stdlib', python_source / 'Lib', '--lzma-dll', lzma_dlls[0],
         '--output', output / 'windows-codec-consumers.json'], log=output / 'codec-upstream-tests.log')
    (output / 'windows-codec-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'sources': spec['sources'], 'architecture': arch,
        'compiler': toolset, 'crt': '/MD', 'images': images, 'patches': [],
        'scope': spec['scope'], 'linkage': spec['linkage'], 'result': 'PASS'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
