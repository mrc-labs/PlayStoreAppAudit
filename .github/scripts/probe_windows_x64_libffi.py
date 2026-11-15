"""Qualify the official stable libffi MSVC port before runtime adoption."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import fetch
from inspect_pe import read_pe_machine
from probe_libffi_arm64 import exercise_library
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]


def run(command: list, *, log: Path, cwd: Path = REPO, env: dict | None = None) -> str:
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                            capture_output=True, text=True)
    text = result.stdout + result.stderr
    log.write_text(text, encoding='utf-8')
    if result.returncode:
        print(text[-5000:], flush=True)
    result.check_returncode()
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert os.name == 'nt' and platform.machine().lower() == 'amd64'
    assert os.environ['EXPECTED_ARCH'] == 'x64'
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'x64'
    compiler = Path(shutil.which('cl')).resolve()
    assert read_pe_machine(compiler) == 0x8664 and compiler.parents[3].name.startswith('14.52.')
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    output = REPO / 'toolchain-delta-evidence'
    spec_path = REPO / '.github/scripts/windows_x64_libffi_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, output)
    (output / 'sources').mkdir()
    archive = fetch(spec['sources'][0], output / 'sources')
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / spec['sources'][0]['directory']
    for name, digest in spec['guarded_files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest
    assert json.loads((source / 'ports/libffi/vcpkg.json').read_text())['version'] == '3.8.0'
    # Official static-md triplet, with only release builds selected to avoid
    # compiling unused debug copies. The native selected compiler is inherited.
    triplets = work / 'triplets'
    triplets.mkdir()
    triplet = triplets / 'x64-windows-static-md.cmake'
    original = source / 'triplets' / triplet.name
    assert original.is_file()
    # Stable vcpkg's automatic VS discovery rejects the actual new18.12 host.
    # Its documented external-toolchain interface uses the already-validated
    # native DevShell compiler instead, without selecting an older toolset.
    chainload = work / 'native-msvc.cmake'
    chainload.write_text('set(CMAKE_SYSTEM_NAME Windows)\n'
                        f'set(CMAKE_C_COMPILER "{compiler.as_posix()}")\n'
                        f'set(CMAKE_CXX_COMPILER "{compiler.as_posix()}")\n'
                        f'set(CMAKE_ASM_MASM_COMPILER "{(compiler.parent / "ml64.exe").as_posix()}")\n'
                        'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreadedDLL)\n')
    triplet.write_bytes(original.read_bytes() + ('\nset(VCPKG_BUILD_TYPE release)\n'
                        'set(VCPKG_LOAD_VCVARS_ENV OFF)\n'
                        # make/autoconf needs flags as well as the CMake
                        # runtime property; otherwise direct cl defaults to /MT.
                        'set(VCPKG_C_FLAGS "/MD")\n'
                        'set(VCPKG_CXX_FLAGS "/MD")\n'
                        f'set(VCPKG_CHAINLOAD_TOOLCHAIN_FILE "{chainload.as_posix()}")\n'
                        'set(VCPKG_ENV_PASSTHROUGH PATH INCLUDE LIB LIBPATH WindowsSdkDir WindowsSDKVersion VCToolsInstallDir)\n').encode())
    shutil.copy2(original, output / 'original-triplet.cmake')
    shutil.copy2(triplet, output)
    shutil.copy2(chainload, output)
    environment = {**os.environ, 'VCPKG_DISABLE_METRICS': '1', 'VCPKG_BINARY_SOURCES': 'clear',
                   'VCPKG_MAX_CONCURRENCY': '2'}
    preflight = work / 'compiler-preflight'
    preflight.mkdir()
    (preflight / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\n'
        'project(NativeFFIToolchain LANGUAGES C CXX ASM_MASM)\nadd_executable(native_compiler main.c)\n')
    (preflight / 'main.c').write_text('#include <stdint.h>\nint main(void) { return sizeof(void *) != 8; }\n')
    run(['cmake', '-S', preflight, '-B', preflight / 'build', '-GNinja',
         '-DCMAKE_TOOLCHAIN_FILE=' + str(chainload)], env=environment, log=output / 'compiler-preflight-configure.log')
    run(['cmake', '--build', preflight / 'build'], env=environment, log=output / 'compiler-preflight-build.log')
    executable = preflight / 'build/native_compiler.exe'
    assert read_pe_machine(executable) == 0x8664
    run([executable], log=output / 'compiler-preflight-execute.log')
    run(['cmd', '/d', '/c', source / 'bootstrap-vcpkg.bat', '-disableMetrics'], cwd=source,
        env=environment, log=output / 'vcpkg-bootstrap.log')
    tool = source / 'vcpkg.exe'
    assert read_pe_machine(tool) == 0x8664
    install = work / 'installed'
    try:
        run([tool, 'install', 'libffi:x64-windows-static-md', '--host-triplet=x64-windows-static-md',
             '--overlay-triplets=' + str(triplets), '--x-install-root=' + str(install),
             '--disable-metrics'], cwd=source, env=environment, log=output / 'vcpkg-libffi.log')
    finally:
        # Preserve detailed configure/compiler failures before another attempt.
        for path in (source / 'buildtrees/libffi').glob('*.log'):
            shutil.copy2(path, output / ('libffi-' + path.name))
    prefix = install / spec['target']
    libraries = list((prefix / 'lib').glob('*.lib'))
    assert len(libraries) == 1, libraries
    library = libraries[0]
    headers = run(['dumpbin', '/headers', library], log=output / 'ffi-library-headers.txt')
    machines = set(re.findall(r'([0-9A-Fa-f]+) machine \(', headers))
    assert machines == {'8664'}, machines
    directives = run(['dumpbin', '/directives', library], log=output / 'ffi-library-crt.txt').upper().replace('"', '')
    assert '/DEFAULTLIB:MSVCRT' in directives and '/DEFAULTLIB:LIBCMT' not in directives
    original_source = source / 'downloads/libffi-3.8.0.tar.gz'
    assert hashlib.sha256(original_source.read_bytes()).hexdigest() == spec['libffi_source_sha256']
    shutil.copy2(original_source, output / 'sources')
    shutil.copytree(source / 'ports/libffi', output / 'official-libffi-port')
    shutil.copytree(prefix, output / 'libffi-sdk')
    shutil.copy2(source / 'LICENSE.txt', output / 'vcpkg-LICENSE.txt')
    consumer = exercise_library(source, work, library, compiler, output, machine=0x8664, include=prefix / 'include')
    versions = pe_versions(work / 'ffi_consumer.exe')
    assert max(versions.values()) <= (10, 0), versions
    report = {'source_sha': os.environ['GITHUB_SHA'], 'sources': spec, 'compiler': str(compiler),
              'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
              'vcpkg_sha256': hashlib.sha256(tool.read_bytes()).hexdigest(), 'crt': '/MD',
              'consumer': consumer, 'pe_versions': versions, 'result': 'PASS native static libffi prerequisite; CPython/cffi/crypto adoption remains required'}
    (output / 'windows-x64-libffi.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
