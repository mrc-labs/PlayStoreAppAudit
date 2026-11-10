"""Probe the official libffi MSVC ARM64 project; never adopt a runtime library."""
from __future__ import annotations

import argparse
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
import urllib.request
from pathlib import Path

from inspect_pe import read_pe_machine

URL = 'https://github.com/libffi/libffi/releases/download/v3.8.0/libffi-3.8.0.tar.gz'
SHA256 = '7da3e2d9a171eb0a038f592ecad3ff2bb2550f3496d87b3b29ad0cf4430c0db4'


def fetch_source(work: Path, evidence: Path) -> Path:
    archive = evidence / 'libffi-3.8.0.tar.gz'
    with urllib.request.urlopen(URL, timeout=90) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Source HTTPS downgrade rejected')
        data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Unexpected official libffi source digest')
    archive.write_bytes(data)
    with tarfile.open(archive) as source:
        source.extractall(work, filter='data')
    return work / 'libffi-3.8.0'


def run(command: list[str], log: Path, cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        print((result.stdout + result.stderr)[-14000:], flush=True)
    result.check_returncode()
    return result.stdout + result.stderr


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64', 'Native Windows ARM64 Python required'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED'), 'Exact stable3.14.10/GIL bootstrap required'
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'arm64', 'MSVC host and target must both be ARM64'
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh source workspace required'
    work.mkdir(parents=True)
    evidence = Path('windows-arm64-pilot-evidence/libffi-prerequisites').resolve()
    evidence.mkdir(parents=True)
    report = {'source_sha': head, 'scope': 'Official MSVC project feasibility only; no CPython/cffi or runtime adoption',
              'libffi_source': URL, 'libffi_sha256': SHA256, 'vendor_patches': [], 'result': 'BLOCKED',
              'source_authority': 'https://api.github.com/repos/libffi/libffi/releases/tags/v3.8.0'}
    try:
        report['gate'] = 'native compiler and assembler host architecture'
        compiler = Path(shutil.which('cl.exe') or '')
        assembler = Path(shutil.which('armasm64.exe') or '')
        compiler_machine = read_pe_machine(compiler)
        assembler_machine = read_pe_machine(assembler)
        assert compiler_machine == 0xAA64, f'Non-native compiler host: {compiler} machine={compiler_machine}'
        assert assembler_machine == 0xAA64, f'Non-native assembler host: {assembler} machine={assembler_machine}'
        report.update(compiler=str(compiler), assembler=str(assembler), host_target='native ARM64/ARM64',
                      compiler_machine=compiler_machine, assembler_machine=assembler_machine,
                      toolset=os.environ['VCTOOLSVERSION'], sdk=os.environ['WINDOWSSDKVERSION'])
        report['gate'] = 'official source digest/extraction/provenance'
        source = fetch_source(work, evidence)
        project = source / 'msvc_build/aarch64/Ffi_staticLib.vcxproj'
        report['official_project_sha256'] = hashlib.sha256(project.read_bytes()).hexdigest()
        report['official_header_sha256'] = hashlib.sha256((source / 'msvc_build/aarch64/aarch64_include/ffi.h').read_bytes()).hexdigest()
        shutil.copy2(source / 'LICENSE', evidence / 'libffi-LICENSE')
        build = work / 'build'
        build.mkdir()
        msbuild = Path(os.environ['PILOT_VS_PATH']) / 'MSBuild/Current/Bin/arm64/MSBuild.exe'
        assert msbuild.is_file(), f'Native ARM64 MSBuild missing: {msbuild}'
        report['gate'] = 'official MSVC project, supported toolset/SDK property overrides; no source patches'
        run([str(msbuild), str(project), '/t:Build', '/m:2', '/v:normal', '/p:Configuration=Release',
             '/p:Platform=ARM64', '/p:PlatformToolset=' + os.environ['PILOT_MSVC_TOOLSET'], '/p:PreferredToolArchitecture=ARM64',
             '/p:VCToolsVersion=' + os.environ['VCTOOLSVERSION'].rstrip('\\/'),
             '/p:WindowsTargetPlatformVersion=' + os.environ['WINDOWSSDKVERSION'].rstrip('\\/'),
             '/p:OutDir=' + str(build) + os.sep, '/p:IntDir=' + str(build / 'obj') + os.sep],
            evidence / 'msbuild.log', project.parent)
        libraries = list(build.glob('*.lib'))
        assert len(libraries) == 1, libraries
        report['gate'] = 'library target architecture and CRT provenance'
        headers = run(['dumpbin.exe', '/headers', str(libraries[0])], evidence / 'coff-headers.txt', work)
        machines = re.findall(r'\b([0-9A-Fa-f]{3,4}) machine \(', headers)
        assert machines and {m.upper() for m in machines} == {'AA64'}, f'Unexpected library COFF architectures: {machines}'
        directives = run(['dumpbin.exe', '/directives', str(libraries[0])], evidence / 'crt-directives.txt', work)
        normalized = directives.upper().replace('"', '')
        assert '/DEFAULTLIB:MSVCRT' in normalized and '/DEFAULTLIB:LIBCMT' not in normalized, 'Dynamic release CRT provenance failed'
        report.update(result='PASS official native project and dynamic CRT; consumer/ABI execution remains required',
                      library_machines=machines, library_sha256=hashlib.sha256(libraries[0].read_bytes()).hexdigest())
        shutil.copy2(libraries[0], evidence)
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (evidence / 'libffi-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
