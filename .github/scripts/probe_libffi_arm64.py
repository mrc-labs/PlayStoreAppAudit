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
REPO = Path(__file__).resolve().parents[2]


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


def run(command: list[str], log: Path, cwd: Path, environment: dict[str, str] | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        print((result.stdout + result.stderr)[-14000:], flush=True)
    result.check_returncode()
    return result.stdout + result.stderr


def apply_libffi_patch(source: Path, evidence: Path, spec: dict) -> None:
    patch = REPO / spec['path']
    target = source / spec['source_file']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError('Changed reviewed libffi patch')
    if hashlib.sha256(target.read_bytes()).hexdigest() != spec['original_sha256']:
        raise ValueError('Changed original libffi source')
    if 'normalized_sha256' in spec:
        normalized = target.read_bytes().replace(b'\r\n', b'\n')
        if hashlib.sha256(normalized).hexdigest() != spec['normalized_sha256']:
            raise ValueError('Unexpected normalized libffi project')
        target.write_bytes(normalized)
    command = ['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'apply']
    environment = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(source.parent.resolve())}
    run([*command, '--check', str(patch)], evidence / (patch.stem + '-check.log'), source, environment)
    run([*command, str(patch)], evidence / (patch.stem + '-apply.log'), source, environment)
    if hashlib.sha256(target.read_bytes()).hexdigest() != spec['patched_sha256']:
        raise ValueError('Unexpected post-patch libffi source')
    shutil.copy2(patch, evidence)
    shutil.copy2(REPO / '.github/scripts/libffi_arm64_probe_sources.json', evidence)


def configure_headers(source: Path, work: Path, evidence: Path, compiler: Path) -> dict:
    """Generate matching upstream headers instead of editing stale declarations."""
    bash = Path(os.environ['PROGRAMFILES']) / 'Git/bin/bash.exe'
    assert bash.is_file(), f'Git Bash missing: {bash}'
    configured = work / 'configured'
    configured.mkdir()
    script = r'''set -euo pipefail
src=$(cygpath -u "$1")
build=$(cygpath -u "$2")
native_bin=$(cygpath -u "$3")
export PATH="$native_bin:$PATH"
cd "$build"
"$src/configure" --build=aarch64-w64-mingw32 --host=aarch64-w64-mingw32 \
  --disable-shared --enable-static --disable-dependency-tracking \
  CC="$src/msvcc.sh -marm64" CXX="$src/msvcc.sh -marm64" LD=link \
  CPP="cl -nologo -EP" CXXCPP="cl -nologo -EP" CPPFLAGS="-DFFI_BUILDING_DLL"
'''
    try:
        run([str(bash), '--noprofile', '--norc', '-c', script, 'libffi-headers',
             str(source), str(configured), str(compiler.parent)], evidence / 'configure.log', configured)
    finally:
        if (configured / 'config.log').is_file():
            shutil.copy2(configured / 'config.log', evidence)
    generated = {'ffi.h': configured / 'include/ffi.h', 'fficonfig.h': configured / 'fficonfig.h'}
    assert re.search(r'FFI_VERSION_STRING\s+"3\.8\.0"', generated['ffi.h'].read_text()), 'Wrong/unconfigured libffi header version'
    hashes = {}
    for name, path in generated.items():
        destination = source / 'msvc_build/aarch64/aarch64_include' / name
        shutil.copy2(destination, evidence / ('original-' + name))
        shutil.copy2(path, evidence / ('configured-' + name))
        hashes[name] = {'original_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                        'configured_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        shutil.copy2(path, destination)
    return {'bash': str(bash), 'bash_host_machine': read_pe_machine(bash), 'compiler': 'MSVC -marm64 wrapper, native ARM64',
            'abi_triple': 'aarch64-w64-mingw32 identifies Windows ABI; no GNU target compiler', 'headers': hashes}


def exercise_library(source: Path, work: Path, library: Path, compiler: Path, evidence: Path) -> dict:
    client = work / 'ffi_consumer.c'
    client.write_text(r'''#include <ffi.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static int64_t add(int64_t a, int64_t b) { return a + b; }
static void callback(ffi_cif *cif, void *result, void **args, void *data) {
    (void)cif;
    *(int64_t *)result = *(int64_t *)args[0] + *(int64_t *)args[1] + *(int64_t *)data;
}
typedef struct __declspec(align(16)) { uint64_t q[4]; } Big;
static uint64_t stacked(Big a, Big b, Big c, Big d, Big e,
                        Big f, Big g, Big h, Big i, Big j) {
    Big all[] = {a,b,c,d,e,f,g,h,i,j};
    uint64_t sum = 0;
    for (int x=0; x<10; x++) for (int y=0; y<4; y++) sum += all[x].q[y];
    volatile Big *local = &a;
    local->q[0] = 0;
    return sum;
}
int main(void) {
    setvbuf(stdout, NULL, _IONBF, 0);
    puts("stage: version API");
    ffi_cif cif;
    ffi_type *types[] = { &ffi_type_sint64, &ffi_type_sint64 };
    int64_t a = 11, b = 31, result = 0, extra = 3;
    void *args[] = { &a, &b }, *code = NULL;
    if (strcmp(ffi_get_version(), "3.8.0") || ffi_get_version_number() != 30800) return 1;
    puts("stage: scalar CIF");
    if (ffi_prep_cif(&cif, FFI_DEFAULT_ABI, 2, &ffi_type_sint64, types) != FFI_OK) return 2;
    puts("stage: scalar ffi_call");
    ffi_call(&cif, FFI_FN(add), &result, args);
    if (result != 42) return 3;
    puts("stage: closure allocation");
    ffi_closure *closure = ffi_closure_alloc(sizeof(ffi_closure), &code);
    puts("stage: closure preparation");
    if (!closure || ffi_prep_closure_loc(closure, &cif, callback, &extra, code) != FFI_OK) return 4;
    int64_t (*call)(int64_t, int64_t) = (int64_t (*)(int64_t, int64_t))code;
    puts("stage: closure invocation");
    if (call(a, b) != 45) return 5;
    puts("stage: closure free");
    ffi_closure_free(closure);
    Big big[10];
    ffi_type *elements[] = { &ffi_type_uint64, &ffi_type_uint64,
                             &ffi_type_uint64, &ffi_type_uint64, NULL };
    ffi_type aggregate = {sizeof(Big), __alignof(Big), FFI_TYPE_STRUCT, elements};
    ffi_type *big_types[10];
    void *big_args[10];
    uint64_t expected=0, total=0;
    for (int x=0; x<10; x++) {
        for (int y=0; y<4; y++) { big[x].q[y]=(uint64_t)(100*x+y+1); expected+=big[x].q[y]; }
        big_types[x]=&aggregate; big_args[x]=&big[x];
    }
    printf("stage: aligned struct CIF size=%zu alignment=%u\n", sizeof(Big), __alignof(Big));
    if (ffi_prep_cif(&cif, FFI_DEFAULT_ABI, 10, &ffi_type_uint64, big_types) != FFI_OK) return 6;
    puts("stage: aligned struct ffi_call");
    ffi_call(&cif, FFI_FN(stacked), &total, big_args);
    if (total!=expected || big[0].q[0]!=1) return 7;
    printf("libffi %s native version/call/closure/aligned-stack-structs PASS\n", ffi_get_version());
    return 0;
}
''', encoding='utf-8')
    shutil.copy2(client, evidence)
    executable = work / 'ffi_consumer.exe'
    run([str(compiler), '/nologo', '/MD', '/Zi', '/std:c17', '/DFFI_BUILDING_DLL',
         '/I' + str(source / 'msvc_build/aarch64/aarch64_include'), '/I' + str(source / 'src/aarch64'),
         str(client), str(library), '/Fe:' + str(executable)], evidence / 'consumer-build.log', work)
    assert read_pe_machine(executable) == 0xAA64, 'Consumer executable must be native ARM64'
    shutil.copy2(executable, evidence)
    try:
        output = run([str(executable)], evidence / 'consumer.log', work)
    except subprocess.CalledProcessError:
        debugger = Path(os.environ['PROGRAMFILES(X86)']) / 'Windows Kits/10/Debuggers/arm64/cdb.exe'
        if debugger.is_file():
            debugger_machine = read_pe_machine(debugger)
            (evidence / 'consumer-debugger.json').write_text(json.dumps({
                'path': str(debugger), 'machine': debugger_machine,
                'sha256': hashlib.sha256(debugger.read_bytes()).hexdigest(),
                'scope': 'Optional installed SDK diagnostic only; no compiler or runtime adoption',
            }, indent=2), encoding='utf-8')
            if debugger_machine != 0xAA64:
                raise
            try:
                trace = subprocess.run([str(debugger), '-c', 'g;.ecxr;kv;q', str(executable)],
                                       cwd=work, capture_output=True, text=True, timeout=40)
                (evidence / 'consumer-native-debug.log').write_text(trace.stdout + trace.stderr, encoding='utf-8')
            except subprocess.TimeoutExpired:
                (evidence / 'consumer-native-debug.log').write_text('Native debugger deadline reached', encoding='utf-8')
        raise
    assert 'libffi 3.8.0 native version/call/closure/aligned-stack-structs PASS' in output
    return {'machine': 0xAA64, 'sha256': hashlib.sha256(executable.read_bytes()).hexdigest(), 'executed': output.strip()}


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
        report['gate'] = 'upstream configure/MSVC wrapper header generation'
        report['project_configuration'] = configure_headers(source, work, evidence, compiler)
        patches = json.loads((REPO / '.github/scripts/libffi_arm64_probe_sources.json').read_text())
        report['gate'] = 'reviewed unsigned alignment/project source-list compatibility patches'
        for key in ['alignment_patch', 'msvc_project_patch']:
            apply_libffi_patch(source, evidence, patches[key])
            report['vendor_patches'].append(patches[key])
        build = work / 'build'
        build.mkdir()
        msbuild = Path(os.environ['PILOT_VS_PATH']) / 'MSBuild/Current/Bin/arm64/MSBuild.exe'
        assert msbuild.is_file(), f'Native ARM64 MSBuild missing: {msbuild}'
        report['gate'] = 'MSVC project with upstream-generated headers and equivalent unsigned mask; SDL preserved'
        run([str(msbuild), str(project), '/t:Build', '/m:2', '/v:normal', '/p:Configuration=Release',
             '/p:Platform=ARM64', '/p:PlatformToolset=' + os.environ['PILOT_MSVC_TOOLSET'], '/p:PreferredToolArchitecture=ARM64',
             '/p:WholeProgramOptimization=false',
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
        report.update(library_machines=machines, library_sha256=hashlib.sha256(libraries[0].read_bytes()).hexdigest())
        shutil.copy2(libraries[0], evidence)
        report['gate'] = 'native version/call/closure consumer execution'
        report['consumer'] = exercise_library(source, work, libraries[0], compiler, evidence)
        report.update(result='PASS controlled project/header configuration, native call/closure and dynamic CRT; CPython/cffi acceptance remains required',
                      library_machines=machines, library_sha256=hashlib.sha256(libraries[0].read_bytes()).hexdigest())
    except Exception as error:
        report['failure'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (evidence / 'libffi-probe.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
