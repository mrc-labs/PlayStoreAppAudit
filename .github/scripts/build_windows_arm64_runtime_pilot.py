"""Controlled ARM64 source profile; host prerequisites gate every expensive rebuild."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import (
    REPO,
    fetch,
    patch_source,
    pyside_packaging_preflight,
    register_private_dll_directories,
    run,
)
from inspect_pe import read_pe_machine
from probe_windows_arm64_runtime import require_arm64
from verify_native_runtime_pilot import executed_upstream_suites


def unpack(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter='data')


def host_tools(work: Path, arm: dict, base: dict, evidence: Path) -> dict[str, Path]:
    sources = evidence / 'sources'
    sources.mkdir(exist_ok=True)
    # The image extractor only unpacks the hash-verified native 26.05 host tool.
    installer = fetch(arm['host_extractor'], work)
    image_seven = shutil.which('7z')
    assert image_seven
    run([image_seven, 'x', '-y', '-o' + str(work / '7zip'), installer], log=evidence / 'extractor-bootstrap.log')
    seven = next(path for path in (work / '7zip').rglob('7z.exe') if read_pe_machine(path) == 0xAA64)
    require_arm64(seven)
    run([seven], log=evidence / '7zip-version.log')
    # Build the current stable Perl using the unchanged upstream ARM64 Makefile.
    perl_archive = fetch(arm['host_perl_source'], sources)
    unpack(perl_archive, work)
    perl_source = work / 'perl-5.44.0'
    tests = ['op/arith2.t', 'op/pack.t']
    assert all((perl_source / 't' / name).is_file() for name in tests), 'Check upstream test layout before compiling'
    run(['nmake', '-f', 'Makefile', 'CCTYPE=MSVC143', 'WIN64=define',
         'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\')], cwd=perl_source / 'win32', log=evidence / 'perl-build.log')
    perl = perl_source / 'perl.exe'
    require_arm64(perl)
    os.environ['PERL5LIB'] = str(perl_source / 'lib')
    run([perl, '-MConfig', '-e', 'die unless $Config{version} eq "5.44.0"; die unless $Config{archname} =~ /arm64/; use File::Spec; use File::Temp; use Digest::SHA; print "$^V $Config{archname}\\n"'], cwd=perl_source, log=evidence / 'perl-native-probe.log')
    # Targeted upstream core tests for the modules used by source generators.
    run(['nmake', '-f', 'Makefile', 'test', 'CCTYPE=MSVC143', 'WIN64=define',
         'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\'), 'TEST_FILES=' + ' '.join(tests)],
        cwd=perl_source / 'win32', log=evidence / 'perl-regressions.log')
    result = (evidence / 'perl-regressions.log').read_text(encoding='utf-8', errors='replace')
    counts = re.search(r'Files=(\d+), Tests=(\d+)', result)
    assert counts and int(counts[1]) == 2 and int(counts[2]) > 0 and 'Result: PASS' in result, 'Two executed upstream host-tool suites required'
    os.environ['PATH'] = str(perl.parent) + os.pathsep + os.environ['PATH']
    assert Path(shutil.which('perl') or '').resolve() == perl.resolve()
    # Only Qt's bootstrap MOC is compiled; native wheel uic/rcc already passed.
    qt_item = next(item for item in base['sources'] if item['directory'] == 'qtbase-everywhere-src-6.12.0')
    qt_archive = fetch(qt_item, sources)
    unpack(qt_archive, work)
    qt_source = work / qt_item['directory']
    build = work / 'qt-host-tools-build'
    build.mkdir()
    run(['cmd', '/d', '/c', qt_source / 'configure.bat', '-prefix', work / 'host-qt', '-release',
         '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples', '--',
         '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=build, log=evidence / 'qt-host-tools-configure.log')
    run(['cmake', '--build', build, '--target', 'moc', '--parallel', '2'], log=evidence / 'qt-host-tools-build.log')
    generators = {}
    for name in ('moc',):
        tool = build / 'bin' / (name + '.exe')
        require_arm64(tool)
        run([tool, '--version'], log=evidence / (name + '-source-version.log'))
        generators[name] = tool
    header = work / 'native_moc_probe.h'
    header.write_text('#include <QObject>\nclass NativeMocProbe : public QObject { Q_OBJECT\nQ_SIGNALS: void ready();\n};\n', encoding='utf-8')
    output = work / 'moc_native_probe.cpp'
    run([generators['moc'], '-I' + str(build / 'include'), '-I' + str(build / 'include/QtCore'),
         '-I' + str(qt_source / 'src/corelib'), header, '-o', output], log=evidence / 'moc-generation.log')
    assert 'NativeMocProbe' in output.read_text(encoding='utf-8') and 'qt_metacall' in output.read_text(encoding='utf-8')
    imports = subprocess.check_output(['dumpbin', '/dependents', str(generators['moc'])], text=True)
    assert 'Qt6Core.dll' not in imports and 'libssl-' not in imports and 'libcrypto-' not in imports, 'Bootstrap MOC must not use a runtime TLS/Qt provider'
    (evidence / 'moc-host-imports.txt').write_text(imports, encoding='utf-8')
    report = {'source_sha':os.environ['GITHUB_SHA'], 'scope':'native host tools only; no controlled runtime build',
        'perl':'5.44.0 native ARM64, official unmodified source; replaces EOL image 5.32.1 AMD64',
        'generators':'MOC 6.12.0 native ARM64 built from exact accepted Qt source; native wheel uic/rcc/Shiboken proved separately',
        'moc_generated_cpp_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'binaries':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [seven, perl, *generators.values()]},
        'result':'PASS'}
    (evidence / 'host-tools-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    return {'seven':seven, 'perl':perl, 'qt_source':qt_source}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--host-tools-only', action='store_true')
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64'
    require_arm64(Path(sys.executable))
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh host-tool root required'
    work.mkdir()
    evidence = REPO / 'windows-arm64-pilot-evidence'
    arm = json.loads((REPO / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text(encoding='utf-8'))
    base = json.loads((REPO / '.github/scripts' / arm['base_manifest']).read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == arm['base_manifest_canonical_sha256']
    host = host_tools(work, arm, base, evidence)
    if not args.host_tools_only:
        build_stack(work, arm, base, evidence, host)


def stack_sources(arm: dict, base: dict) -> list[dict]:
    """Use the accepted archives with an explicit host-parser architecture override."""
    items = [item for item in base['sources'] if item['directory'] != 'libclang']
    items += [arm['host_libclang'], *base['cpython_externals'], base['extractor_source']]
    return items


def build_stack(work: Path, arm: dict, base: dict, evidence: Path, host: dict[str, Path]) -> None:
    sources = evidence / 'sources'
    items = stack_sources(arm, base)

    def source_archive(item: dict) -> Path:
        folder = work if item['name'].endswith('.7z') else sources
        archive = folder / item['name']
        if archive.is_file():
            with archive.open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256']
            return archive
        return fetch(item, folder)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        archives = list(pool.map(source_archive, items))
    externals = work / 'externals'
    externals.mkdir()
    source_only = work / 'source-attributions'
    source_only.mkdir()
    for item, archive in zip(items, archives, strict=True):
        if item is base['extractor_source']:
            continue
        if item.get('source_only'):
            unpack(archive, source_only)
            continue
        if archive.suffix == '.7z':
            run([host['seven'], 'x', '-y', '-o' + str(work), archive], log=evidence / 'libclang-extract.log')
        elif not (work / item['directory']).exists():
            unpack(archive, work)
        if item in base['cpython_externals']:
            (work / item['directory']).rename(externals / item['destination'])
    python_source = work / 'Python-3.14.9'
    for key in ('cpython_patch', 'windows_patch'):
        patch_source(python_source, base[key], evidence)
    pyside = work / 'pyside-setup-everywhere-src-6.12.0'
    patch_source(pyside, base['pyside_windows_patch'], evidence)
    pyside_packaging_preflight(pyside, evidence)
    for path in (REPO / '.github/scripts/windows_arm64_runtime_pilot_sources.json', REPO / '.github/scripts/windows_runtime_pilot_sources.json'):
        shutil.copy2(path, evidence / path.name)
    legal = evidence / 'legal'
    legal.mkdir()
    directories = [work / item['directory'] for item in items if 'directory' in item and item not in base['cpython_externals']]
    directories += list(externals.iterdir()) + list(source_only.iterdir()) + [work / 'perl-5.44.0', work / '7zip']
    for directory in directories:
        if not directory.is_dir():
            continue
        target = legal / directory.name
        target.mkdir(exist_ok=True)
        for candidate in directory.iterdir():
            if candidate.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'ARTISTIC')):
                if candidate.is_dir():
                    shutil.copytree(candidate, target / candidate.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(candidate, target / candidate.name)
    parser_dll = work / 'libclang/bin/libclang.dll'
    require_arm64(parser_dll)
    assert (work / 'libclang/lib/cmake/clang/ClangConfig.cmake').is_file()
    run([sys.executable, '-I', '-c', 'import ctypes,os,sys; h=os.add_dll_directory(os.path.dirname(sys.argv[1])); d=ctypes.WinDLL(sys.argv[1]); assert d.clang_getClangVersion; print("Native ARM64 parser SDK load PASS")', parser_dll], log=evidence / 'libclang-loader-preflight.log')
    prefix = work / 'prefix'
    prefix.mkdir()
    ssl_source = work / 'openssl-4.0.3'
    ssl_prefix = prefix / 'openssl'
    run([host['perl'], 'Configure', arm['openssl_target'], 'shared', 'no-uplink', 'no-makedepend', 'no-docs', '--prefix=' + str(ssl_prefix), '--libdir=lib', 'CFLAGS=/MD'], cwd=ssl_source, log=evidence / 'openssl-configure.log')
    makefile = (ssl_source / 'makefile').read_text(encoding='utf-8')
    assert 'CFLAGS=/MD' in makefile
    # Exercise current Perl + the real OpenSSL ARM64 perlasm/clang-cl recipe first.
    target = re.search(r'^([^\r\n :]*aesv8-armx\.obj)\s*:', makefile, re.MULTILINE)
    assert target, 'Find the upstream ARM64 AES assembly target before full compilation'
    run(['nmake', target[1]], cwd=ssl_source, log=evidence / 'openssl-perlasm-preflight.log')
    assembly = ssl_source / target[1].replace('\\', '/')
    headers = subprocess.check_output(['dumpbin', '/headers', str(assembly)], text=True)
    assert 'AA64 machine' in headers and '8664 machine' not in headers
    (evidence / 'openssl-perlasm-headers.txt').write_text(headers, encoding='utf-8')
    run(['nmake'], cwd=ssl_source, log=evidence / 'openssl-build.log')
    run(['nmake', 'test', 'TESTS=test_evp test_x509 test_verify test_ssl_new'], cwd=ssl_source, log=evidence / 'openssl-regressions.log')
    run(['nmake', 'install_sw'], cwd=ssl_source, log=evidence / 'openssl-install.log')
    for name in arm['openssl_dlls']:
        require_arm64(ssl_source / name)
    for name in arm['openssl_import_libraries']:
        assert (ssl_source / name).is_file()
    shutil.copy2(ssl_source / 'configdata.pm', evidence / 'openssl-configdata.pm')
    build = python_source / 'PCbuild/arm64'
    run(['msbuild', python_source / 'PCbuild/pcbuild.proj', '/m:2', '/p:Configuration=Release', '/p:Platform=ARM64', '/p:PreferredToolArchitecture=ARM64',
         '/p:PlatformToolset=v143', '/p:VCToolsVersion=' + os.environ['VCTOOLSVERSION'],
         '/p:WindowsTargetPlatformVersion=' + os.environ['WINDOWSSDKVERSION'].rstrip('\\'),
         '/p:IncludeTkinter=false', '/p:IncludeSSL=true', '/p:IncludeTests=true', '/p:UseJIT=false', '/p:DisableGil=false',
         '/p:ExternalsDir=' + str(externals) + '\\', '/p:opensslOutDir=' + str(ssl_source) + '\\', '/p:opensslIncludeDir=' + str(ssl_prefix / 'include')], log=evidence / 'cpython-build.log')
    py = build / 'python.exe'
    require_arm64(py)
    run([py, '-c', 'import ssl,sysconfig; assert ssl.OPENSSL_VERSION.startswith("OpenSSL 4.0.3 "); assert not sysconfig.get_config_var("Py_GIL_DISABLED"); print(ssl.OPENSSL_VERSION)'])
    run([py, '-c', "import ssl,sys; from pathlib import Path; root=Path(sys.argv[1]); c=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); c.load_cert_chain(root/'keycert.pem'); t=ssl.create_default_context(cafile=str(root/'pycacert.pem')); assert t.verify_mode==ssl.CERT_REQUIRED and t.check_hostname; print('ARM64 PEM I/O PASS')", python_source / 'Lib/test/certdata'])
    run([py, '-m', 'test', '-j2', '--junit-xml', evidence / 'cpython-regressions.xml', 'test_ssl', 'test_hashlib', 'test_hmac'], cwd=python_source, log=evidence / 'cpython-regressions.log')
    executed_upstream_suites(evidence / 'cpython-regressions.xml')
    runtime = prefix / 'python'
    run([py, python_source / 'PC/layout', '-s', python_source, '-b', build, '--copy', runtime, '--include-dev', '--include-venv', '--include-stable', '--include-tests'], log=evidence / 'cpython-layout.log')
    shutil.copy2(evidence / 'windows_arm64_runtime_pilot_sources.json', runtime / 'PROJECT_MODIFIED_RUNTIME.json')
    shutil.copy2(evidence / 'windows_runtime_pilot_sources.json', runtime / 'windows_runtime_pilot_sources.json')
    py = runtime / 'python.exe'
    run([py, '-m', 'ensurepip'])
    run([py, '-m', 'venv', work / 'venv'])
    py = work / 'venv/Scripts/python.exe'
    require_arm64(py)
    for variable in ('PYTHONHOME', 'PYTHON_ROOT_DIR', 'PYTHON2_ROOT_DIR', 'PYTHON3_ROOT_DIR'):
        os.environ.pop(variable, None)
    os.environ.update(PYTHON_ROOT_DIR=str(runtime), PYTHON3_ROOT_DIR=str(runtime), CMAKE_PREFIX_PATH=os.pathsep.join(map(str, [prefix, ssl_prefix, prefix / 'qt'])))
    directories = [prefix / 'qt/bin', prefix / 'bin', ssl_prefix / 'bin']
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    os.environ['PATH'] = os.pathsep.join(map(str, [py.parent, *directories])) + os.pathsep + os.environ['PATH']
    register_private_dll_directories(py, directories, evidence)
    run([py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([py, '-m', 'pip', 'install', 'setuptools==84.2.1', 'wheel==0.48.0', 'cmake==4.4.4', 'ninja==1.13.2', 'packaging==26.3', '--report', evidence / 'build-tools-install.json'])
    crypto_source(work, prefix, sources, evidence, arm, base, host, py)
    os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = '2'
    common = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL']
    for directory, label, extra in [('zlib-1.3.2', 'zlib', ['-DZLIB_BUILD_TESTING=ON']), ('libpng-1.6.59', 'libpng', ['-DPNG_TESTS=ON', '-DPNG_SHARED=ON', '-DPNG_STATIC=OFF']), ('pcre2-10.49', 'pcre2', ['-DBUILD_SHARED_LIBS=ON', '-DPCRE2_BUILD_PCRE2_16=ON', '-DPCRE2_SUPPORT_JIT=ON', '-DPCRE2_BUILD_TESTS=ON'])]:
        folder = work / (label + '-build')
        run(['cmake', '-S', work / directory, '-B', folder, *common, '-DCMAKE_PREFIX_PATH=' + str(prefix), *extra], log=evidence / (label + '-configure.log'))
        run(['cmake', '--build', folder], log=evidence / (label + '-build.log'))
        run(['ctest', '--test-dir', folder, '--output-on-failure'], log=evidence / (label + '-regressions.log'))
        run(['cmake', '--install', folder], log=evidence / (label + '-install.log'))
    dependency = work / 'qt-dependency-probe'
    dependency.mkdir()
    (dependency / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.25)\nproject(Arm64QtDependencies LANGUAGES C)\n'
        f'list(PREPEND CMAKE_MODULE_PATH "{(host["qt_source"] / "cmake").as_posix()}")\n'
        'set(QT_USE_BUNDLED_BundledZLIB OFF)\nfind_package(WrapZLIB REQUIRED)\n'
        'if(NOT TARGET WrapZLIB::WrapZLIB)\nmessage(FATAL_ERROR "Missing source zlib target")\nendif()\n', encoding='utf-8')
    run(['cmake', '-S', dependency, '-B', dependency / 'build', *common, '-DCMAKE_PREFIX_PATH=' + str(prefix)], log=evidence / 'qt-dependency-preflight.log')
    qt_build = work / 'qt-build'
    qt_build.mkdir()
    run(['cmd', '/d', '/c', host['qt_source'] / 'configure.bat', '-prefix', prefix / 'qt', '-release', '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples',
         '-openssl-linked', '-system-libpng', '-system-pcre', '-system-zlib', '-no-feature-openssl-runtime', '--',
         '-DOPENSSL_ROOT_DIR=' + str(ssl_prefix), '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=qt_build, log=evidence / 'qtbase-configure.log')
    run(['cmake', '--build', qt_build, '--parallel', '2'], log=evidence / 'qtbase-build.log')
    run(['cmake', '--install', qt_build], log=evidence / 'qtbase-install.log')
    for name in ('CMakeCache.txt', 'config.summary'):
        shutil.copy2(qt_build / name, evidence / ('qtbase-' + name))
    for name in ('moc.exe', 'rcc.exe', 'uic.exe'):
        require_arm64(prefix / 'qt/bin' / name)
    svg = work / 'svg-build'
    svg.mkdir()
    run(['cmd', '/d', '/c', prefix / 'qt/bin/qt-configure-module.bat', work / 'qtsvg-everywhere-src-6.12.0', '--', '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=svg, log=evidence / 'qtsvg-configure.log')
    run(['cmake', '--build', svg, '--parallel', '2'], log=evidence / 'qtsvg-build.log')
    run(['cmake', '--install', svg], log=evidence / 'qtsvg-install.log')
    run([py, '-I', '-c', 'import ctypes,sys; d=ctypes.WinDLL(sys.argv[1]); print("Controlled ARM64 QtCore secure-load PASS",d._name)', prefix / 'qt/bin/Qt6Core.dll'], log=evidence / 'qtcore-loader-preflight.log')
    os.environ['LLVM_INSTALL_DIR'] = str(work / 'libclang')
    run([py, 'setup.py', 'install', '--ignore-git', '--qtpaths=' + str(prefix / 'qt/bin/qtpaths6.exe'), '--parallel=2', '--limited-api=yes', '--module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test', '--no-qt-tools'], cwd=pyside, log=evidence / 'pyside-build.log')
    requirements = evidence / 'runtime-requirements.txt'
    requirements.write_text('\n'.join(line for line in (REPO / 'requirements.txt').read_text(encoding='utf-8').splitlines() if not line.startswith('PySide6-Essentials==')) + '\n', encoding='utf-8')
    run([py, '-m', 'pip', 'install', '-r', requirements, 'pytest==9.1.1', '--report', evidence / 'runtime-install.json'])
    run([py, '-m', 'pip', 'check'])
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'PYTHONHOME', 'QT_QPA_PLATFORM', 'LLVM_INSTALL_DIR'):
        os.environ.pop(name, None)
    os.environ.update(PILOT_PREFIX=str(prefix), PILOT_WORK=str(work), PILOT_EVIDENCE=str(evidence), QT_PLUGIN_PATH=str(prefix / 'qt/plugins'), APPDATA=str(work / 'profile/roaming'), LOCALAPPDATA=str(work / 'profile/local'))
    run([py, REPO / '.github/scripts/verify_windows_arm64_runtime_pilot.py', '--output-dir', evidence])
    run([py, REPO / 'main.py', 'cli', 'audit', '--help'], log=evidence / 'cli-smoke.txt')
    run([py, '-m', 'pytest', 'tests/test_cli_headless.py', '-q'], log=evidence / 'project-cli-regressions.log')
    run([py, '-m', 'compileall', '-q', 'playstore_app_audit'])
    print('Native ARM64 controlled runtime-framework pilot PASS; no final application candidate.', flush=True)


def crypto_source(work: Path, prefix: Path, sources: Path, evidence: Path, arm: dict, base: dict, host: dict[str, Path], py: Path) -> None:
    """Repeat the proven independent static-OpenSSL/dynamic-CRT integration."""
    root = work / 'crypto-source'
    root.mkdir()
    archive = sources / 'openssl-4.0.3.tar.gz'
    unpack(archive, root)
    source = root / 'openssl-4.0.3'
    installed = prefix / 'crypto-openssl'
    crypto_evidence = evidence / 'openssl-cryptography'
    crypto_evidence.mkdir()
    arguments = [arm['openssl_target'], 'no-shared', 'no-module', 'no-tests', 'no-docs', 'no-makedepend', '--prefix=' + str(installed), '--libdir=lib', '--openssldir=C:/Program Files/Common Files/SSL', 'CFLAGS=/MD']
    run([host['perl'], 'Configure', *arguments], cwd=source, log=crypto_evidence / 'configure.log')
    assert 'CFLAGS=/MD' in (source / 'makefile').read_text(encoding='utf-8')
    run(['nmake'], cwd=source, log=crypto_evidence / 'build.log')
    run(['nmake', 'install_sw'], cwd=source, log=crypto_evidence / 'install.log')
    assert not list(installed.rglob('*.dll')), 'cryptography OpenSSL must remain static'
    for name in ('libcrypto', 'libssl'):
        library = installed / 'lib' / (name + '.lib')
        headers = subprocess.check_output(['dumpbin', '/headers', str(library)], text=True)
        assert 'AA64 machine' in headers and '8664 machine' not in headers
        directives = subprocess.check_output(['dumpbin', '/directives', str(library)], text=True)
        assert 'LIBCMT' not in directives and 'MT_StaticRelease' not in directives
        (crypto_evidence / (name + '-headers.txt')).write_text(headers, encoding='utf-8')
        (crypto_evidence / (name + '-directives.txt')).write_text(directives, encoding='utf-8')
    shutil.copy2(archive, crypto_evidence / archive.name)
    shutil.copy2(source / 'LICENSE.txt', crypto_evidence / 'LICENSE.txt')
    provenance = {'version':'4.0.3', 'source_url':base['sources'][1]['url'], 'source_sha256':base['sources'][1]['sha256'],
        'source_sha256_url':base['sources'][1]['authority'], 'target':arm['openssl_target'], 'linkage':'static', 'crt':'dynamic',
        'compiler':shutil.which('cl'), 'assembler':shutil.which('clang-cl'), 'configure':arguments,
        'source_sha':os.environ['GITHUB_SHA'], 'run_id':os.environ['GITHUB_RUN_ID']}
    (crypto_evidence / 'source-provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    run(['rustup', 'toolchain', 'install', '1.99.1', '--profile', 'minimal'], log=crypto_evidence / 'rust-install.log')
    os.environ.update(RUSTUP_TOOLCHAIN='1.99.1', OPENSSL_DIR=str(installed), OPENSSL_INCLUDE_DIR=str(installed / 'include'), OPENSSL_LIB_DIR=str(installed / 'lib'),
        OPENSSL_STATIC='1', OPENSSL_NO_VENDOR='1', PIP_NO_BINARY='cryptography', PIP_NO_CACHE_DIR='1',
        CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER=shutil.which('link') or '')
    rust = subprocess.check_output(['rustc', '-vV'], text=True)
    assert 'host: aarch64-pc-windows-msvc' in rust and 'release: 1.99.1' in rust
    for tool in ('rustc', 'cargo'):
        require_arm64(Path(subprocess.check_output(['rustup', 'which', tool], text=True).strip()))
    (crypto_evidence / 'rust.txt').write_text(rust, encoding='utf-8')
    original = arm['cryptography_source']
    fetch(original, sources)
    run([py, '-m', 'pip', 'install', '--no-binary=cryptography', '--no-cache-dir',
         original['url'] + '#sha256=' + original['sha256'], '--report', crypto_evidence / 'cryptography-install.json'])
    run([py, REPO / '.github/scripts/verify_windows_arm64_crypto.py', '--evidence-dir', crypto_evidence], log=crypto_evidence / 'cryptography-check.log')
    for name in ('OPENSSL_DIR', 'OPENSSL_INCLUDE_DIR', 'OPENSSL_LIB_DIR', 'OPENSSL_STATIC', 'OPENSSL_NO_VENDOR', 'PIP_NO_BINARY', 'PIP_NO_CACHE_DIR', 'CARGO_TARGET_AARCH64_PC_WINDOWS_MSVC_LINKER'):
        os.environ.pop(name, None)


if __name__ == '__main__':
    main()
