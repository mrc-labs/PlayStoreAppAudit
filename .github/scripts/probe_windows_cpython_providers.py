"""Qualify controlled CPython/current stdlib providers, before any Qt rebuild."""
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
import zipfile
from pathlib import Path

from apply_windows_cpython_providers import apply
from build_windows_runtime_pilot import fetch, patch_source, run
from download_diagnostic_artifact import fetch_artifact
from inspect_pe import read_pe_machine
from probe_windows_arm64_ctypes import FFI_ARTIFACT, FFI_LIBRARY_SHA256, FFI_SOURCE, FFI_ZIP_SHA256
from probe_windows_arm64_ctypes import restore_ffi as restore_arm_ffi
from probe_windows_x64_ffi_consumers import restore_ffi as restore_x64_ffi
from retain_macos_runtime_sdk import retain
from verify_native_runtime_pilot import certificate_material, default_trust_handshake
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]


def qualify(work: Path) -> None:
    assert sys.platform == 'win32' and platform.python_version() == '3.14.10'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    assert platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == arch
    compiler = Path(shutil.which('cl')).resolve()
    assert read_pe_machine(compiler) == machine and compiler.parents[3].name.startswith('14.52.')
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work, output = work.resolve(), REPO / 'toolchain-delta-evidence'
    assert not work.exists()
    toolsets = list(Path(os.environ['VSINSTALLDIR']).glob('MSBuild/Microsoft/VC/*/Platforms/' + ('ARM64' if arch == 'arm64' else 'x64') + '/PlatformToolsets/v145/Toolset.props'))
    context = {'compiler': str(compiler), 'machine': machine, 'sdk': os.environ.get('WINDOWSSDKVERSION'),
               'vs_install': os.environ['VSINSTALLDIR'], 'v145_matches': list(map(str, toolsets)),
               'available_toolsets': list(map(str, Path(os.environ['VSINSTALLDIR']).glob('MSBuild/Microsoft/VC/*/Platforms/' + ('ARM64' if arch == 'arm64' else 'x64') + '/PlatformToolsets/*/Toolset.props')))}
    (output / 'native-cpython-msbuild-context.json').write_text(json.dumps(context, indent=2) + '\n')
    print(json.dumps(context), flush=True)
    assert len(toolsets) == 1, 'Qualify current stable MSBuild v145 before OpenSSL/Python compilation'
    if arch == 'arm64':
        assembler = Path(shutil.which('clang-cl') or '').resolve()
        assert assembler.is_file() and read_pe_machine(assembler) == machine, 'Native ARM64 OpenSSL assembler required'
        version = subprocess.check_output([assembler, '--version'], text=True)
        (output / 'openssl-assembler-prerequisite.txt').write_text(str(assembler) + '\n' + version)
        assert 'clang version 23.1.5' in version, 'Qualify current supported standalone assembler before expensive builds'
    work.mkdir()
    sources, legal = output / 'sources', output / 'legal'
    sources.mkdir()
    legal.mkdir()
    base = json.loads((REPO / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    arm = json.loads((REPO / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text())
    codec = json.loads((REPO / '.github/scripts/windows_codec_provider_sources.json').read_text())
    native = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
    ffi = ({'artifact': FFI_ARTIFACT, 'run': 43538466498, 'source_sha': FFI_SOURCE,
            'zip_sha256': FFI_ZIP_SHA256, 'library_sha256': FFI_LIBRARY_SHA256} if arch == 'arm64'
           else json.loads((REPO / '.github/scripts/windows_x64_ffi_consumer_sources.json').read_text())['ffi'])
    metadata, data = fetch_artifact(ffi['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_sha'] == ffi['source_sha']
    assert metadata['workflow_run']['id'] == ffi['run'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['digest'] == 'sha256:' + ffi['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    (output / 'original-ffi-sdk.zip').write_bytes(data)
    ffi_root = work / 'ffi-sdk'
    if arch == 'arm64':
        restore_arm_ffi(data, ffi_root)
        ffi_library, ffi_include = ffi_root / 'ffi.lib', ffi_root
    else:
        restore_x64_ffi(data, ffi_root, ffi)
        ffi_library, ffi_include = ffi_root / 'lib/libffi.lib', ffi_root / 'include'
    externals = [item for item in base['cpython_externals'] if item['destination'].startswith(('bzip2-', 'zstd-'))]
    assert len(externals) == 2
    selected = [*base['sources'][:2], *codec['sources'][1:], arm['host_perl_source'], *externals]
    selected += [row for row in native['sources'] if row['directory'].startswith(('sqlite-', 'mpdecimal-'))]
    if arch == 'x64':
        selected += [base['nasm'], base['nasm_source']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        archives = list(pool.map(lambda item: fetch(item, sources), selected))
    external_root = work / 'externals'
    external_root.mkdir()
    for item, archive in zip(selected, archives, strict=True):
        if archive.suffix == '.zip':
            with zipfile.ZipFile(archive) as bundle:
                assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in bundle.namelist())
                bundle.extractall(work / 'nasm')
            continue
        if item.get('source_only'):
            continue
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
        directory = work / item['directory']
        if item in externals:
            directory = directory.rename(external_root / item['destination'])
        destination = legal / directory.name
        destination.mkdir(exist_ok=True)
        for path in directory.iterdir():
            if path.is_file() and path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'COPYRIGHT', 'NOTICE', 'AUTHORS')):
                shutil.copy2(path, destination)
    notice = fetch(native['sqlite_legal_notice'], legal)
    assert notice.is_file()
    if arch == 'x64':
        nasm = next((work / 'nasm').rglob('nasm.exe'))
        assert read_pe_machine(nasm) == machine
        os.environ['PATH'] = str(nasm.parent) + os.pathsep + os.environ['PATH']
        run([nasm, '-v'], log=output / 'nasm-version.log')
    perl_source = work / 'perl-5.44.0'
    make = ['nmake', '-f', 'Makefile', 'CCTYPE=MSVC143', 'WIN64=define',
            'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\')]
    run(make, cwd=perl_source / 'win32', log=output / 'perl-build.log')
    perl = perl_source / 'perl.exe'
    assert read_pe_machine(perl) == machine
    os.environ['PERL5LIB'] = str(perl_source / 'lib')
    os.environ['PATH'] = str(perl.parent) + os.pathsep + os.environ['PATH']
    run([perl, '-MConfig', '-e', 'die unless $Config{version} eq "5.44.0"; print "$^V $Config{archname}\\n"'], log=output / 'perl-native.log')
    run([*make, 'test', 'TEST_FILES=op/arith2.t op/pack.t'], cwd=perl_source / 'win32', log=output / 'perl-tests.log')
    assert 'Result: PASS' in (output / 'perl-tests.log').read_text(encoding='utf-8', errors='replace')
    prefix = work / 'prefix'
    providers = prefix / 'providers'
    common = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
              '-DCMAKE_INSTALL_PREFIX=' + str(providers), '-DBUILD_TESTING=OFF']
    for source, label, extra in [
        ('xz-5.8.4', 'xz', ['-DBUILD_SHARED_LIBS=ON']),
        ('zlib-ng-2.3.3', 'zlib-ng', ['-DBUILD_SHARED_LIBS=OFF', '-DZLIB_COMPAT=ON', '-DWITH_GTEST=OFF',
                                   '-DWITH_BENCHMARKS=OFF', '-DWITH_NATIVE_INSTRUCTIONS=OFF', '-DWITH_RUNTIME_CPU_DETECTION=ON'])]:
        build = work / (label + '-build')
        run(['cmake', '-S', work / source, '-B', build, *common, *extra], log=output / (label + '-configure.log'))
        shutil.copy2(build / 'CMakeCache.txt', output / (label + '-CMakeCache.txt'))
        run(['cmake', '--build', build, '--parallel', '2'], log=output / (label + '-build.log'))
        run(['cmake', '--install', build], log=output / (label + '-install.log'))
    zlib = list((providers / 'lib').glob('*zlib*.lib'))
    lzma = list((providers / 'lib').glob('*lzma*.lib'))
    lzma_dll = list((providers / 'bin').glob('*lzma*.dll'))
    assert len(zlib) == len(lzma) == len(lzma_dll) == 1
    assert read_pe_machine(lzma_dll[0]) == machine
    python_source = work / 'Python-3.14.10'
    for key in ['cpython_patch', 'windows_patch']:
        patch_source(python_source, base[key], output)
    for name, digest in base['security_files'].items():
        assert hashlib.sha256((python_source / name).read_bytes()).hexdigest() == digest
    apply(python_source, output)
    ssl_source, ssl_prefix = work / 'openssl-4.0.3', prefix / 'openssl'
    target = arm['openssl_target'] if arch == 'arm64' else 'VC-WIN64A'
    run([perl, 'Configure', target, 'shared', 'no-uplink', 'no-makedepend', 'no-docs',
         '--prefix=' + str(ssl_prefix), '--libdir=lib', 'CFLAGS=/MD'], cwd=ssl_source, log=output / 'openssl-configure.log')
    run(['nmake'], cwd=ssl_source, log=output / 'openssl-build.log')
    run(['nmake', 'test', 'TESTS=test_evp test_x509 test_verify test_ssl_new'], cwd=ssl_source, log=output / 'openssl-tests.log')
    run(['nmake', 'install_sw'], cwd=ssl_source, log=output / 'openssl-install.log')
    variant = arm if arch == 'arm64' else base
    for name in variant['openssl_dlls']:
        assert read_pe_machine(ssl_source / name) == machine
    build = python_source / 'PCbuild' / ('arm64' if arch == 'arm64' else 'amd64')
    properties = {'Configuration': 'Release', 'Platform': 'ARM64' if arch == 'arm64' else 'x64',
                  'PreferredToolArchitecture': 'ARM64' if arch == 'arm64' else 'x64', 'PlatformToolset': 'v145',
                  'VCToolsVersion': os.environ['VCTOOLSVERSION'].rstrip('\\'),
                  'WindowsTargetPlatformVersion': os.environ['WINDOWSSDKVERSION'].rstrip('\\'),
                  'IncludeTkinter': 'false', 'IncludeSSL': 'true', 'IncludeTests': 'true', 'UseJIT': 'false', 'DisableGil': 'false',
                  'IncludeExternals': 'true', 'PSAAControlledProviders': 'true', 'ExternalsDir': str(external_root) + '\\',
                  'opensslOutDir': str(ssl_source) + '\\', 'opensslIncludeDir': str(ssl_prefix / 'include'),
                  'sqlite3Dir': str(work / 'sqlite-autoconf-3540100') + '\\', 'mpdecimalDir': str(work / 'mpdecimal-4.0.1') + '\\',
                  'PSAAFFILibrary': str(ffi_library), 'PSAAFFIIncludeDir': str(ffi_include),
                  'PSAACodecIncludeDir': str(providers / 'include'), 'PSAAZlibLibrary': str(zlib[0]),
                  'PSAALzmaImportLibrary': str(lzma[0]), 'PSAALzmaRuntime': str(lzma_dll[0])}
    run(['msbuild', python_source / 'PCbuild/pcbuild.proj', '/m:2', *['/p:' + k + '=' + v for k, v in properties.items()]], log=output / 'cpython-build.log')
    python = build / 'python.exe'
    assert read_pe_machine(python) == machine
    images = []
    for path in sorted(build.iterdir()):
        if path.suffix.lower() not in {'.exe', '.dll', '.pyd'}:
            continue
        assert read_pe_machine(path) == machine, path
        versions = pe_versions(path)
        assert all(v <= (10, 0) for v in versions.values()), (path, versions)
        images.append({'name': path.name, 'machine': machine, 'versions': versions,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for name in ['python314.dll', '_ctypes.pyd', '_ssl.pyd', '_hashlib.pyd', '_decimal.pyd', '_sqlite3.pyd', '_lzma.pyd']:
        imports = subprocess.check_output(['dumpbin', '/dependents', build / name], text=True)
        assert not any(line.strip().lower().startswith('libffi') for line in imports.splitlines())
        assert any(term in imports.upper() for term in ['VCRUNTIME140', 'API-MS-WIN-CRT-', 'UCRTBASE.DLL'])
        (output / (name + '-imports.txt')).write_text(imports)
    run([python, '-c', 'import ssl,_decimal,sqlite3,zlib,lzma,ctypes,_ctypes,sysconfig; '
         'assert ssl.OPENSSL_VERSION.startswith("OpenSSL 4.0.3 "); '
         'assert not sysconfig.get_config_var("Py_GIL_DISABLED"); '
         'assert sqlite3.sqlite_version=="3.54.1" and _decimal.__libmpdec_version__=="4.0.1"; '
         'assert zlib.__spec__.origin=="built-in" and "zlib-ng" in zlib.ZLIB_RUNTIME_VERSION; '
         'd=ctypes.WinDLL(_ctypes.__file__);d.ffi_get_version.restype=ctypes.c_char_p;assert d.ffi_get_version()==b"3.8.0"; '
         'assert lzma.decompress(lzma.compress(b"native"))==b"native"; '
         'print("PASS actual controlled Python/providers/GIL; zlib remains builtin")'], log=output / 'actual-provider-versions.log')
    variadic_source, variadic_dll = work / 'variadic.c', work / 'variadic.dll'
    variadic_source.write_text('#include <stdarg.h>\n#include <string.h>\n'
        '__declspec(dllexport) double psaa_variadic(int base, ...) {\n'
        'va_list a;va_start(a,base);const char *s=va_arg(a,const char*);int n=va_arg(a,int);'
        'double d=va_arg(a,double);va_end(a);return base+strlen(s)+n+d;}\n')
    run([compiler, '/nologo', '/MD', '/LD', '/std:c17', variadic_source, '/Fe:' + str(variadic_dll)],
        cwd=work, log=output / 'variadic-build.log')
    assert read_pe_machine(variadic_dll) == machine
    run([python, '-c', 'import ctypes,sys;d=ctypes.CDLL(sys.argv[1]);f=d.psaa_variadic;'
         'f.argtypes=[ctypes.c_int];f.restype=ctypes.c_double;'
         'r=f(7,ctypes.c_char_p(b"ffi"),ctypes.c_int(13),ctypes.c_double(4.5));'
         'assert r==27.5,r;print("PASS actual controlled ctypes mixed variadic",r)', variadic_dll], log=output / 'ctypes-mixed-variadic.log')
    for file in [variadic_source, variadic_dll]:
        shutil.copy2(file, output)
    suites = ['test_ssl', 'test_hashlib', 'test_hmac', 'test_zlib', 'test_lzma', 'test_ctypes', 'test_decimal', 'test_sqlite3']
    run([python, '-m', 'test', '-j2', '--junit-xml', output / 'cpython-regressions.xml', *suites], cwd=python_source, log=output / 'cpython-regressions.log')
    run([python, '-m', 'unittest', '-v', 'test.test_tarfile.TestExtractionFilters.test_link_at_destination'], cwd=python_source, log=output / 'tarfile-security-regression.log')
    certs = output / 'certs'
    certs.mkdir()
    paths = certificate_material(certs)
    (output / 'tls-fixtures.json').write_text(json.dumps({k: str(v) for k, v in paths.items()}))
    code = ('import sys,json,pathlib;sys.path.insert(0,sys.argv[1]); '
            'from verify_native_runtime_pilot import default_trust_handshake,python_tls_checks,executed_cpython_security; '
            'out=pathlib.Path(sys.argv[2]);paths={k:pathlib.Path(v) for k,v in json.loads((out/"tls-fixtures.json").read_text()).items()}; '
            'r=dict(default_trust=default_trust_handshake(),tls=python_tls_checks(paths),security=executed_cpython_security(out/"cpython-regressions.xml",out/"tarfile-security-regression.log")); '
            '(out/"controlled-python-tls.json").write_text(json.dumps(r,indent=2));print("PASS actual default Windows trust/TLS1.2/1.3/negative/security execution")')
    run([python, '-c', code, REPO / '.github/scripts', output], log=output / 'controlled-python-tls.log')
    runtime = prefix / 'python'
    run([python, python_source / 'PC/layout', '-s', python_source, '-b', build, '--copy', runtime,
         '--include-dev', '--include-venv', '--include-stable', '--include-tests'], log=output / 'cpython-layout.log')
    report = {'source_sha': os.environ['GITHUB_SHA'], 'arch': arch, 'compiler': str(compiler), 'properties': properties,
              'images': images, 'ctypes_mixed_variadic': 27.5,
              'ffi_input': ffi, 'sources': selected, 'bootstrap_default_trust': default_trust_handshake(),
              'scope': 'Project-modified native CPython/current stdlib providers only; no Qt/crypto/GUI/CLI/package acceptance', 'result': 'PASS'}
    (runtime / 'PROJECT_MODIFIED_RUNTIME.json').write_text(json.dumps(report, indent=2) + '\n')
    (output / 'windows-cpython-providers.json').write_text(json.dumps(report, indent=2) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    work = args.work_root.resolve()
    output = REPO / 'toolchain-delta-evidence'
    existing = work.exists()
    try:
        qualify(work)
    finally:
        if not existing and output.is_dir() and work.is_dir():
            retain(work, output, 0 if (output / 'windows-cpython-providers.json').exists() else 1,
                   sdk_name='windows-cpython-sdk')


if __name__ == '__main__':
    main()
