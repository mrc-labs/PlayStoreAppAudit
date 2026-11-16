"""Finish only the necessary Windows Qt/security integration on qualified CPython."""
from __future__ import annotations

import argparse
import hashlib
import io
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

from build_windows_runtime_pilot import (
    fetch,
    patch_source,
    pyside_packaging_preflight,
    register_private_dll_directories,
    run,
)
from download_diagnostic_artifact import fetch_artifact
from inspect_pe import read_pe_machine
from retain_macos_runtime_sdk import retain
from reuse_windows_x64_provider_sdk import contract, restore

ROOT = Path(__file__).resolve().parents[2]


def native_extractor(root: Path, arch: str, machine: int) -> Path:
    # The official x64 Extra archive provides 7za; ARM64 installer provides 7z.
    name = '7z.exe' if arch == 'arm64' else '7za.exe'
    matches = [path for path in root.rglob(name) if read_pe_machine(path) == machine]
    assert len(matches) == 1, ('Exactly one official native extractor required', arch, list(root.rglob('7z*.exe')))
    return matches[0]


def settings() -> tuple[str, int, Path, Path]:
    arch = os.environ['EXPECTED_ARCH']
    assert arch in {'x64', 'arm64'} and sys.platform == 'win32'
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    assert read_pe_machine(Path(sys.executable)) == machine
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == arch
    compiler = Path(shutil.which('cl')).resolve()
    assert read_pe_machine(compiler) == machine and compiler.parents[3].name.startswith('14.52.')
    powershell = subprocess.check_output(['pwsh', '-NoProfile', '-Command',
        '[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()'], text=True).strip()
    assert powershell == ('Arm64' if arch == 'arm64' else 'X64'), 'Native Windows chain-engine host required before rebuild'
    work = Path(os.environ['RUNNER_TEMP']).resolve() / contract(arch, runtime=True)['work_name']
    return arch, machine, work, compiler


def cffi_wheel(arch: str, output: Path) -> Path:
    spec = contract(arch, runtime=True)['cffi']
    metadata, raw = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['id'] == spec['run']
    assert metadata['workflow_run']['head_sha'] == spec['source_sha'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(raw) == spec['zip_bytes'] and hashlib.sha256(raw).hexdigest() == spec['zip_sha256']
    (output / 'original-cffi.zip').write_bytes(raw)
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        data = bundle.read(spec['wheel'])
    assert hashlib.sha256(data).hexdigest() == spec['wheel_sha256']
    wheel = output / Path(spec['wheel']).name
    wheel.write_bytes(data)
    return wheel


def environment(work: Path) -> Path:
    prefix = work / 'prefix'
    python = work / 'venv/Scripts/python.exe'
    for name in ['PYTHONHOME', 'PYTHON_ROOT_DIR', 'PYTHON2_ROOT_DIR', 'PYTHON3_ROOT_DIR', 'LLVM_INSTALL_DIR', 'QT_QPA_PLATFORM']:
        os.environ.pop(name, None)
    os.environ.update(PYTHON_ROOT_DIR=str(prefix / 'python'), PYTHON3_ROOT_DIR=str(prefix / 'python'),
                      CMAKE_PREFIX_PATH=os.pathsep.join(map(str, [prefix, prefix / 'qt', prefix / 'openssl'])),
                      CMAKE_BUILD_PARALLEL_LEVEL='2')
    os.environ['PATH'] = os.pathsep.join(map(str, [python.parent, prefix / 'qt/bin', prefix / 'bin', prefix / 'openssl/bin'])) + os.pathsep + os.environ['PATH']
    return python


def prepare(arch: str, machine: int, work: Path, compiler: Path, output: Path) -> None:
    assert not work.exists(), 'Preserve unexpected existing native work'
    work.mkdir()
    context = {'compiler': str(compiler), 'machine': machine, 'sdk': os.environ['WINDOWSSDKVERSION']}
    restore(work, output, [], context, runtime=True)
    prefix, src = work / 'prefix', work / 'src'
    src.mkdir()
    sources, legal = output / 'sources', output / 'legal'
    sources.mkdir()
    legal.mkdir()
    base = json.loads((ROOT / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    arm = json.loads((ROOT / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text())
    native = json.loads((ROOT / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
    selected = [r for r in base['sources'] if r['directory'].startswith(('libpng-', 'pcre2-', 'qtbase-', 'qtsvg-', 'pyside-'))]
    selected += [next(r for r in native['sources'] if r['directory'] == 'zlib-1.4')]
    parser = arm['host_libclang'] if arch == 'arm64' else next(r for r in base['sources'] if r['directory'] == 'libclang')
    extractor = arm['host_extractor'] if arch == 'arm64' else base['extractor']
    for item in selected:
        archive = fetch(item, sources)
        with tarfile.open(archive) as bundle:
            bundle.extractall(src, filter='data')
        directory = src / item['directory']
        for path in directory.iterdir():
            if path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                destination = legal / directory.name / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir():
                    shutil.copytree(path, destination)
                else:
                    shutil.copy2(path, destination)
    pyside = src / 'pyside-setup-everywhere-src-6.12.0'
    patch_source(pyside, base['pyside_windows_patch'], output)
    pyside_packaging_preflight(pyside, output)
    for script in ['apply_qt_http_limits.py', 'apply_qt_ca_guard.py']:
        extra = ['apply'] if script == 'apply_qt_http_limits.py' else []
        run([sys.executable, ROOT / '.github/scripts' / script, *extra,
             '--source', src / 'qtbase-everywhere-src-6.12.0', '--evidence', output], log=output / (script + '.log'))
    tool = fetch(extractor, sources)
    run([shutil.which('7z'), 'x', '-y', '-o' + str(work / '7zip'), tool], log=output / 'extractor-bootstrap.log')
    seven = native_extractor(work / '7zip', arch, machine)
    parser_archive = fetch(parser, sources)
    run([seven, 'x', '-y', '-o' + str(src), parser_archive], log=output / 'parser-extraction.log')
    parser_dlls = list((src / 'libclang').rglob('libclang.dll'))
    assert len(parser_dlls) == 1 and read_pe_machine(parser_dlls[0]) == machine
    parser_probe = work / 'native-parser.cpp'
    parser_probe.write_text('#include <clang-c/Index.h>\n#include <stdio.h>\n'
        'int main(int n,char**v){auto i=clang_createIndex(0,0);const char*a[]={"-xc++"};'
        'auto t=clang_parseTranslationUnit(i,v[1],a,1,nullptr,0,0);if(!t||clang_getNumDiagnostics(t))return 2;'
        'auto s=clang_getClangVersion();puts(clang_getCString(s));clang_disposeString(s);'
        'clang_disposeTranslationUnit(t);clang_disposeIndex(i);}\n')
    header = work / 'native-parser.h'
    header.write_text('int native_parser_probe(void);\n')
    executable = work / 'native-parser.exe'
    run([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/I' + str(src / 'libclang/include'), parser_probe,
         '/link', '/LIBPATH:' + str(src / 'libclang/lib'), 'libclang.lib', '/OUT:' + str(executable)],
        cwd=work, log=output / 'native-parser-build.log')
    assert read_pe_machine(executable) == machine
    saved_path = os.environ['PATH']
    try:
        os.environ['PATH'] = str(parser_dlls[0].parent) + os.pathsep + saved_path
        run([executable, header], log=output / 'native-parser-execution.log')
    finally:
        os.environ['PATH'] = saved_path
    assert '22.1.8' in (output / 'native-parser-execution.log').read_text()
    run([prefix / 'python/python.exe', '-m', 'venv', work / 'venv'], log=output / 'venv.log')
    python = environment(work)
    directories = [prefix / 'qt/bin', prefix / 'bin', prefix / 'openssl/bin']
    for path in directories:
        path.mkdir(parents=True, exist_ok=True)
    register_private_dll_directories(python, directories, output)
    run([python, ROOT / '.github/scripts/bootstrap_pip.py'], log=output / 'private-pip.log')
    wheel = cffi_wheel(arch, output)
    run([sys.executable, ROOT / '.github/scripts/intake_lxml_native.py', '--target', 'windows-' + arch,
         '--output-dir', output / 'lxml-qualified'], log=output / 'lxml-intake.log')
    # Fetch authenticated retained inputs before removing tokens from build children.
    for name in ['GH_TOKEN', 'GITHUB_TOKEN']:
        os.environ.pop(name, None)
    run([python, '-m', 'pip', 'install', '--no-index', '--no-deps', wheel], log=output / 'cffi-intake.log')
    run([python, '-m', 'pip', 'install', '-r', ROOT / '.github/scripts/source_build_requirements.txt',
         '-c', ROOT / '.github/scripts/source_build_constraints.txt', 'cmake==4.4.4', 'ninja==1.13.2', 'pycparser==3.12'], log=output / 'build-tools.log')
    if arch == 'arm64':
        from build_windows_arm64_runtime_pilot import crypto_source, unpack
        from probe_windows_cpython_providers import native_arm64_assembler

        native_arm64_assembler(output)
        perl = arm['host_perl_source']
        unpack(fetch(perl, sources), work)
        perl_root = work / perl['directory']
        run(['nmake', '-f', 'Makefile', 'CCTYPE=MSVC143', 'WIN64=define',
             'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\')], cwd=perl_root / 'win32', log=output / 'perl-build.log')
        assert read_pe_machine(perl_root / 'perl.exe') == machine
        os.environ.update(PERL5LIB=str(perl_root / 'lib'))
        os.environ['PATH'] = str(perl_root) + os.pathsep + os.environ['PATH']
        run([perl_root / 'perl.exe', '-MConfig', '-e',
             'die unless $Config{version} eq "5.44.0" && $Config{archname}=~/arm64/; print "$^V $Config{archname}\\n"'],
            cwd=perl_root, log=output / 'perl-native.log')
        run(['rustup', 'toolchain', 'install', '1.100.0', '--profile', 'minimal'], log=output / 'rust-install.log')
        original_ssl = output / 'original-runtime/sources/openssl-4.0.3.tar.gz'
        shutil.copy2(original_ssl, sources)
        crypto_source(work, prefix, sources, output, arm, base, {'perl': perl_root / 'perl.exe'}, python)
    else:
        run([python, '-m', 'pip', 'install', '--only-binary=cryptography', 'cryptography==50.0.2', '--report', output / 'crypto-install.json'], log=output / 'crypto-intake.log')
    run([python, '-c', 'import ssl,sys,sysconfig,ctypes,cffi,_cffi_backend;from cryptography.hazmat.backends.openssl.backend import backend;'
         'assert ssl.OPENSSL_VERSION.startswith("OpenSSL 4.0.3 ");assert backend.openssl_version_text().startswith("OpenSSL 4.0.3 ");'
         'assert not sysconfig.get_config_var("Py_GIL_DISABLED");'
         'd=ctypes.CDLL(_cffi_backend.__file__);d.ffi_get_version.restype=ctypes.c_char_p;assert d.ffi_get_version()==b"3.8.0";'
         'f=cffi.FFI();cb=f.callback("int(int)",lambda x:x+4);assert cb(6)==10;'
         'f.cdef("struct value {int n; double d;};");v=f.new("struct value *",{"n":7,"d":4.5});assert v.n+v.d==11.5;'
         'print("PASS private Python/independent crypto OpenSSL4/GIL and actual CFFI3.8 callback/structure")'], log=output / 'provider-intake.log')
    state = {'source_sha': os.environ['GITHUB_SHA'], 'arch': arch, 'compiler': str(compiler),
             'original_cpython': contract(arch, runtime=True), 'framework_sources': selected,
             'parser': parser, 'parser_dll': str(parser_dlls[0]), 'pyside_patch': base['pyside_windows_patch'],
             'scope': 'Necessary OpenSSL/PNG/HTTP/CA fixes; other Qt vendor internals unchanged under official-distribution necessity policy'}
    (output / 'windows-framework-inputs.json').write_text(json.dumps(state, indent=2) + '\n')


def build_qt(work: Path, compiler: Path, output: Path) -> None:
    environment(work)
    jobs = str(min(3, os.process_cpu_count() or 2))
    prefix, src = work / 'prefix', work / 'src'
    common = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
              '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL', '-DCMAKE_C_COMPILER=' + str(compiler),
              '-DCMAKE_CXX_COMPILER=' + str(compiler), '-DCMAKE_PREFIX_PATH=' + str(prefix)]
    for directory, label, extra in [
        ('zlib-1.4', 'zlib', ['-DZLIB_BUILD_TESTING=ON']),
        ('libpng-1.6.59', 'libpng', ['-DPNG_TESTS=ON', '-DPNG_SHARED=ON', '-DPNG_STATIC=OFF']),
        ('pcre2-10.49', 'pcre2', ['-DBUILD_SHARED_LIBS=ON', '-DPCRE2_BUILD_PCRE2_16=ON', '-DPCRE2_SUPPORT_JIT=ON', '-DPCRE2_BUILD_TESTS=ON'])]:
        build = work / (label + '-framework-build')
        run(['cmake', '-S', src / directory, '-B', build, *common, *extra], log=output / (label + '-configure.log'))
        run(['cmake', '--build', build, '--parallel', jobs], log=output / (label + '-build.log'))
        run(['ctest', '--test-dir', build, '--output-on-failure'], log=output / (label + '-regressions.log'))
        run(['cmake', '--install', build], log=output / (label + '-install.log'))
    build = work / 'qt-current-build'
    build.mkdir()
    run(['cmd', '/d', '/c', src / 'qtbase-everywhere-src-6.12.0/configure.bat',
         '-prefix', prefix / 'qt', '-release', '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples',
         '-openssl-linked', '-system-libpng', '-system-pcre', '-system-zlib', '-no-feature-openssl-runtime', '--',
         '-DOPENSSL_ROOT_DIR=' + str(prefix / 'openssl'), '-DCMAKE_PREFIX_PATH=' + str(prefix),
         '-DCMAKE_C_COMPILER=' + str(compiler), '-DCMAKE_CXX_COMPILER=' + str(compiler),
         '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL', '-DQT_FEATURE_vulkan=OFF', '-DQT_FEATURE_schannel=ON'],
        cwd=build, log=output / 'qtbase-configure.log')
    run(['cmake', '--build', build, '--parallel', jobs], log=output / 'qtbase-build.log')
    run(['cmake', '--install', build], log=output / 'qtbase-install.log')
    for name in ['CMakeCache.txt', 'config.summary']:
        shutil.copy2(build / name, output / ('qtbase-' + name))
    svg = work / 'svg-current-build'
    svg.mkdir()
    run(['cmd', '/d', '/c', prefix / 'qt/bin/qt-configure-module.bat', src / 'qtsvg-everywhere-src-6.12.0', '--',
         '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=svg, log=output / 'qtsvg-configure.log')
    run(['cmake', '--build', svg, '--parallel', jobs], log=output / 'qtsvg-build.log')
    run(['cmake', '--install', svg], log=output / 'qtsvg-install.log')
    arch = os.environ['EXPECTED_ARCH']
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    for name in ['moc.exe', 'rcc.exe', 'uic.exe', 'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Network.dll']:
        assert read_pe_machine(prefix / 'qt/bin' / name) == machine
    for path in prefix.rglob('*'):
        if path.suffix.lower() in {'.exe', '.dll', '.pyd'} and path.is_file():
            with path.open('rb') as stream:
                if stream.read(2) == b'MZ':
                    assert read_pe_machine(path) == machine, path
    (output / 'windows-framework-qt.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'arch': arch, 'qt_compile_jobs': int(jobs),
        'result': 'PASS installed native Qt6.12/security/PNG/PCRE and same-source generators; bindings/consumers follow'}) + '\n')


def native_security(work: Path, output: Path, compiler: Path) -> None:
    from probe_windows_qt_ca_guard import (
        checked_image,
        exercise_schannel_consumer,
        extract_chains,
        verified_download,
    )

    prefix = work / 'prefix'
    inputs = output / 'provider-security-inputs'
    inputs.mkdir()
    spec = json.loads((ROOT / '.github/scripts/provider_ca_security_sources.json').read_text())
    for row in spec['sources']:
        verified_download(row, inputs / row['name'])
    extract_chains(inputs)
    folder = work / 'native-security-consumer'
    folder.mkdir()
    shutil.copy2(ROOT / '.github/scripts/windows_qt_ca_consumer.cpp', folder)
    shutil.copy2(ROOT / '.github/scripts/qt_http_public_limits.cpp', folder)
    (folder / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\nproject(CurrentNativeSecurity LANGUAGES CXX)\n'
        'set(CMAKE_CXX_STANDARD 17)\nfind_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Network)\n'
        'add_executable(qt_ca_consumer windows_qt_ca_consumer.cpp)\ntarget_link_libraries(qt_ca_consumer PRIVATE Qt6::Core Qt6::Network)\n'
        'add_executable(http_public qt_http_public_limits.cpp)\ntarget_link_libraries(http_public PRIVATE Qt6::Core Qt6::Network)\n')
    run(['cmake', '-S', folder, '-B', folder / 'build', '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_PREFIX_PATH=' + str(prefix / 'qt'), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
         '-DCMAKE_CXX_COMPILER=' + str(compiler)], log=output / 'native-security-configure.log')
    run(['cmake', '--build', folder / 'build'], log=output / 'native-security-build.log')
    run([folder / 'build/http_public.exe'], log=output / 'public-http-regressions.log')
    executable = folder / 'build/qt_ca_consumer.exe'
    machine = 0xAA64 if os.environ['EXPECTED_ARCH'] == 'arm64' else 0x8664
    native_output = output / 'native-schannel'
    native_output.mkdir()
    images = [checked_image(path, native_output, machine=machine, openssl_prefix=prefix / 'openssl') for path in
              [executable, prefix / 'qt/bin/Qt6Core.dll', prefix / 'qt/bin/Qt6Network.dll', prefix / 'qt/plugins/tls/qschannelbackend.dll']]
    exercise_schannel_consumer(executable, prefix / 'qt', native_output, inputs, os.environ['GITHUB_SHA'], images,
                              compiled_source=os.environ['GITHUB_SHA'], native_rollover=True, openssl_prefix=prefix / 'openssl')


def bindings_and_consumers(arch: str, machine: int, work: Path, output: Path) -> None:
    python = environment(work)
    prefix, src = work / 'prefix', work / 'src'
    state = json.loads((output / 'windows-framework-inputs.json').read_text())
    assert (output / 'windows-framework-qt.json').is_file()
    os.environ['LLVM_INSTALL_DIR'] = str(src / 'libclang')
    run([python, '-I', '-c', 'import ctypes,sys;ctypes.WinDLL(sys.argv[1]);print("PASS controlled QtCore secure load")',
         prefix / 'qt/bin/Qt6Core.dll'], log=output / 'qtcore-loader-preflight.log')
    os.environ['PYTHONVERBOSE'] = '1'
    run([python, 'setup.py', 'install', '--ignore-git', '--qtpaths=' + str(prefix / 'qt/bin/qtpaths6.exe'),
         '--parallel=2', '--limited-api=yes', '--module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test', '--no-qt-tools'],
        cwd=src / 'pyside-setup-everywhere-src-6.12.0', log=output / 'pyside-build.log')
    os.environ.pop('PYTHONVERBOSE')
    run([python, ROOT / '.github/scripts/probe_setuptools_build.py', '--consumer', 'pyside',
         '--consumer-log', output / 'pyside-build.log', '--output-dir', output / 'build-dependencies'])
    run([python, ROOT / '.github/scripts/intake_lxml_native.py', '--target', 'windows-' + arch,
         '--output-dir', output / 'lxml-qualified', '--qualify'], log=output / 'lxml-runtime.log')
    requirements = output / 'runtime-requirements.txt'
    requirements.write_text('\n'.join(line for line in (ROOT / 'requirements.txt').read_text().splitlines()
                                     if not line.startswith('PySide6-Essentials==')) + '\n')
    run([python, '-m', 'pip', 'install', '-r', requirements, 'pytest==9.2.0', '--report', output / 'runtime-install.json'])
    run([python, '-m', 'pip', 'check'])
    for name in ['SSL_CERT_FILE', 'SSL_CERT_DIR', 'PYTHONHOME', 'QT_QPA_PLATFORM', 'LLVM_INSTALL_DIR']:
        os.environ.pop(name, None)
    os.environ.update(PILOT_PREFIX=str(prefix), PILOT_WORK=str(work), PILOT_EVIDENCE=str(output),
                      QT_PLUGIN_PATH=str(prefix / 'qt/plugins'), APPDATA=str(work / 'profile/roaming'), LOCALAPPDATA=str(work / 'profile/local'))
    for name in ['cpython-regressions.xml', 'tarfile-security-regression.log']:
        shutil.copy2(output / 'original-runtime' / name, output / name)
    verifier = 'verify_windows_arm64_runtime_pilot.py' if arch == 'arm64' else 'verify_windows_runtime_pilot.py'
    run([python, ROOT / '.github/scripts' / verifier, '--output-dir', output], log=output / 'framework-consumers.log')
    native_security(work, output, Path(state['compiler']))
    run([python, '-c', 'import sys,pathlib;sys.path.insert(0,sys.argv[1]);from PySide6.QtWidgets import QApplication;'
         'from PySide6.QtNetwork import QSslSocket;from verify_macos_maintenance import qt_incident_security;'
         'app=QApplication([]);assert app.platformName()=="windows";assert QSslSocket.setActiveBackend("openssl");'
         'qt_incident_security(pathlib.Path(sys.argv[2]),"openssl")', ROOT / '.github/scripts', output], log=output / 'qt-openssl-incident.log')
    run([python, ROOT / 'main.py', 'cli', 'audit', '--help'], log=output / 'cli-smoke.txt')
    run([python, '-m', 'pytest', 'tests/test_cli_headless.py', '-q'], log=output / 'project-cli-regressions.log')
    run([python, '-m', 'compileall', '-q', ROOT / 'playstore_app_audit'])
    (output / 'windows-current-framework.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'arch': arch, 'machine': hex(machine), 'inputs': state,
        'result': 'PASS current native Python/Qt/bindings/dual-provider/TLS/PNG/GUI/CLI; no final application candidate'}) + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['prepare', 'qt', 'bindings'], required=True)
    args = parser.parse_args()
    arch, machine, work, compiler = settings()
    output = ROOT / 'toolchain-delta-evidence'
    complete = False
    try:
        if args.stage == 'prepare':
            prepare(arch, machine, work, compiler, output)
        else:
            state = json.loads((output / 'windows-framework-inputs.json').read_text())
            assert state['source_sha'] == os.environ['GITHUB_SHA'] and state['arch'] == arch and state['compiler'] == str(compiler)
            if args.stage == 'qt':
                build_qt(work, compiler, output)
            else:
                bindings_and_consumers(arch, machine, work, output)
                complete = True
    finally:
        if work.is_dir():
            retain(work, output, 0 if complete else 1, sdk_name='windows-framework-sdk')


if __name__ == '__main__':
    main()
