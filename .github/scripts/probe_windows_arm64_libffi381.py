"""Qualify only official libffi3.8.1 static ARM64 /MD; no runtime adoption."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import fetch
from inspect_pe import read_pe_machine
from probe_libffi_arm64 import apply_libffi_patch, configure_headers, exercise_library, run

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'arm64'
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    compiler = Path(shutil.which('cl.exe')).resolve()
    assert read_pe_machine(compiler) == 0xAA64 and compiler.parents[3].name.startswith('14.52.')
    assembler = Path(shutil.which('armasm64.exe')).resolve()
    assert read_pe_machine(assembler) == 0xAA64
    output = ROOT / 'toolchain-delta-evidence'
    work = Path(os.environ['RUNNER_TEMP']) / ('libffi381-arm64-' + os.environ['GITHUB_RUN_ID'])
    assert not work.exists()
    work.mkdir()
    spec_path = ROOT / '.github/scripts/libffi381_arm64_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, output)
    sources = output / 'sources'
    sources.mkdir()
    archive = fetch({'name': 'libffi-3.8.1.tar.gz', 'url': spec['source_url'], 'sha256': spec['source_sha256']}, sources)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / 'libffi-3.8.1'
    shutil.copy2(source / 'LICENSE', output / 'libffi-LICENSE')
    configured = configure_headers(source, work, output, compiler, expected_version='3.8.1')
    for key in ['alignment_patch', 'msvc_project_patch']:
        apply_libffi_patch(source, output, spec[key])
    build = work / 'build'
    build.mkdir()
    msbuild = Path(os.environ['VSINSTALLDIR']) / 'MSBuild/Current/Bin/arm64/MSBuild.exe'
    assert read_pe_machine(msbuild) == 0xAA64
    project = source / 'msvc_build/aarch64/Ffi_staticLib.vcxproj'
    run([str(msbuild), str(project), '/t:Build', '/m:2', '/v:normal', '/p:Configuration=Release',
         '/p:Platform=ARM64', '/p:PlatformToolset=v145', '/p:PreferredToolArchitecture=ARM64',
         '/p:WholeProgramOptimization=false', '/p:VCToolsVersion=' + os.environ['VCTOOLSVERSION'].rstrip('\\/'),
         '/p:WindowsTargetPlatformVersion=' + os.environ['WINDOWSSDKVERSION'].rstrip('\\/'),
         '/p:OutDir=' + str(build) + os.sep, '/p:IntDir=' + str(build / 'obj') + os.sep],
        output / 'msbuild.log', project.parent)
    libraries = list(build.glob('*.lib'))
    assert len(libraries) == 1
    library = libraries[0]
    headers = run(['dumpbin.exe', '/headers', str(library)], output / 'coff-headers.txt', work)
    assert set(re.findall(r'\b([0-9A-Fa-f]{3,4}) machine \(', headers)) == {'AA64'}
    directives = run(['dumpbin.exe', '/directives', str(library)], output / 'crt-directives.txt', work).upper().replace('"', '')
    assert '/DEFAULTLIB:MSVCRT' in directives and '/DEFAULTLIB:LIBCMT' not in directives
    consumer = exercise_library(source, work, library, compiler, output, expected_version='3.8.1')
    sdk = output / 'libffi381-sdk'
    (sdk / 'include').mkdir(parents=True)
    (sdk / 'lib').mkdir()
    for name in ['ffi.h', 'fficonfig.h']:
        shutil.copy2(source / 'msvc_build/aarch64/aarch64_include' / name, sdk / 'include' / name)
    shutil.copy2(source / 'src/aarch64/ffitarget.h', sdk / 'include/ffitarget.h')
    shutil.copy2(library, sdk / 'lib/ffi.lib')
    shutil.copy2(source / 'LICENSE', sdk)
    (output / 'arm64-libffi381.json').write_text(json.dumps({'source_sha': os.environ['GITHUB_SHA'],
        'version': '3.8.1', 'source_sha256': spec['source_sha256'], 'configured': configured,
        'library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(), 'crt': '/MD',
        'machine': 'AA64', 'consumer': consumer,
        'scope': 'Static native FFI prerequisite only; ctypes/cffi/runtime adoption remains required'}, indent=2))


if __name__ == '__main__':
    main()
