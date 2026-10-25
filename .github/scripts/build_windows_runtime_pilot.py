"""Bounded Windows x64 source build. Never produces an application candidate."""
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
import urllib.request
import zipfile
from pathlib import Path

from inspect_pe import read_pe_machine
from verify_native_runtime_pilot import default_trust_handshake, executed_upstream_suites

REPO = Path(__file__).resolve().parents[2]


def run(command: list[str | Path], *, cwd: Path = REPO, log: Path | None = None) -> None:
    print('RUN', *map(str, command), flush=True)
    if log:
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run(list(map(str, command)), cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log.read_text(encoding='utf-8', errors='replace')[-16000:], flush=True)
            raise subprocess.CalledProcessError(result.returncode, command)
    else:
        subprocess.run(list(map(str, command)), cwd=cwd, check=True)


def fetch(item: dict, destination: Path) -> Path:
    target = destination / item['name']
    with urllib.request.urlopen(item['url'], timeout=180) as response, target.open('wb') as stream:
        shutil.copyfileobj(response, stream)
    with target.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256'], item['name']
    print('Official input verified:', item['name'], flush=True)
    return target


def patch_source(source: Path, patch: dict, evidence: Path) -> None:
    for name, hashes in patch['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['base_sha256'], name
        if 'normalized_sha256' in hashes:
            normalized = (source / name).read_bytes().replace(b'\r\n', b'\n')
            assert hashlib.sha256(normalized).hexdigest() == hashes['normalized_sha256']
            (source / name).write_bytes(normalized)
    path = REPO / patch['path']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == patch['sha256']
    # git apply works on the extracted official archive; no repository mutation.
    # Do not let a surrounding checkout redirect paths when testing an archive locally.
    environment = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(source.parent)}
    for arguments in (['--check'], []):
        subprocess.run(['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'apply', *arguments, str(path)], cwd=source, env=environment, check=True)
    for name, hashes in patch['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256'], name
    shutil.copy2(path, evidence / path.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    work = args.work_root.resolve()
    evidence = REPO / 'windows-pilot-evidence'
    evidence.mkdir(exist_ok=True)
    assert sys.platform == 'win32' and platform.machine().upper() == 'AMD64'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not work.exists(), 'Fresh isolated work root required'
    work.mkdir()
    # Cheap prerequisites and actual Windows default trust BEFORE component downloads.
    tools = {}
    for name, arguments in {'cl':['/?'], 'link':['/?'], 'msbuild':['-version'], 'perl':['-v']}.items():
        tool = shutil.which(name)
        assert tool, name
        if name in {'cl', 'link'}:
            assert read_pe_machine(Path(tool)) == 0x8664
        result = subprocess.run([tool, *arguments], capture_output=True, text=True)
        tools[name] = {'path':tool, 'version':result.stdout + result.stderr}
    assert '19.44.' in tools['cl']['version'], tools['cl']
    trust = default_trust_handshake()
    assert __import__('ssl').enum_certificates('ROOT'), 'Windows ROOT store unreadable'
    (evidence / 'prerequisites.json').write_text(json.dumps({'source_sha':os.environ['GITHUB_SHA'],
        'tools':tools, 'os':platform.platform(), 'windows':tuple(sys.getwindowsversion()),
        'image':os.environ.get('IMAGEVERSION'), 'trust':trust,
        'sdk':os.environ.get('WINDOWSSDKVERSION'), 'vc_tools':os.environ.get('VCTOOLSVERSION')}, indent=2))
    manifest = REPO / '.github/scripts/windows_runtime_pilot_sources.json'
    spec = json.loads(manifest.read_text())
    shutil.copy2(manifest, evidence / manifest.name)
    sources, legal = evidence / 'sources', evidence / 'legal'
    sources.mkdir()
    legal.mkdir()
    src, prefix = work / 'src', work / 'prefix'
    src.mkdir()
    prefix.mkdir()
    extractor = fetch(spec['extractor'], work)
    image_7zip = shutil.which('7z')
    assert image_7zip, 'Image extractor needed only for verified portable-tool bootstrap'
    run([image_7zip, 'x', '-y', f'-o{work / "7zip"}', extractor], log=evidence / 'extractor-bootstrap.log')
    seven = work / '7zip/x64/7za.exe'
    assert read_pe_machine(seven) == 0x8664
    run([seven], log=evidence / '7zip-version.log')
    nasm = fetch(spec['nasm'], work)
    with zipfile.ZipFile(nasm) as archive:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in archive.namelist())
        archive.extractall(work / 'nasm')
    nasm_exe = next((work / 'nasm').rglob('nasm.exe'))
    assert read_pe_machine(nasm_exe) == 0x8664
    os.environ['PATH'] = str(nasm_exe.parent) + os.pathsep + os.environ['PATH']
    run([nasm_exe, '-v'], log=evidence / 'nasm-version.log')
    items = [*spec['sources'], *spec['cpython_externals'], spec['extractor_source'], spec['nasm_source']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        downloaded = list(pool.map(lambda item: fetch(item, work if item['name'].endswith('.7z') else sources), items))
    externals = work / 'externals'
    externals.mkdir()
    for item, archive in zip(items, downloaded, strict=True):
        if item.get('source_only') or item in (spec['extractor_source'], spec['nasm_source']):
            continue
        if archive.suffix == '.7z':
            run([seven, 'x', '-y', f'-o{src}', archive], log=evidence / 'libclang-extract.log')
        else:
            with tarfile.open(archive) as bundle:
                bundle.extractall(src, filter='data')
        extracted = src / item['directory']
        if item in spec['cpython_externals']:
            extracted.rename(externals / item['destination'])
    python_source = src / 'Python-3.14.9'
    patch_source(python_source, spec['cpython_patch'], evidence)
    patch_source(python_source, spec['windows_patch'], evidence)
    for directory in [*src.iterdir(), *externals.iterdir()]:
        if not directory.is_dir():
            continue
        target = legal / directory.name
        target.mkdir()
        for candidate in directory.iterdir():
            if candidate.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
                if candidate.is_dir():
                    shutil.copytree(candidate, target / candidate.name)
                else:
                    shutil.copy2(candidate, target / candidate.name)
    for candidate in (work / '7zip').glob('*.txt'):
        shutil.copy2(candidate, legal / ('7zip-' + candidate.name))
    ssl_source, ssl_prefix = src / 'openssl-4.0.3', prefix / 'openssl'
    run(['perl', 'Configure', 'VC-WIN64A', 'shared', 'no-docs', '--prefix=' + str(ssl_prefix), '--libdir=lib', 'CFLAGS=/MD'], cwd=ssl_source, log=evidence / 'openssl-configure.log')
    assert 'CFLAGS=/MD' in (ssl_source / 'makefile').read_text(), 'Explicit shared CRT required'
    run(['nmake'], cwd=ssl_source, log=evidence / 'openssl-build.log')
    run(['nmake', 'test', 'TESTS=test_evp test_x509 test_verify test_ssl_new'], cwd=ssl_source, log=evidence / 'openssl-regressions.log')
    run(['nmake', 'install_sw'], cwd=ssl_source, log=evidence / 'openssl-install.log')
    for name in [*spec['openssl_dlls'], *spec['openssl_import_libraries']]:
        assert (ssl_source / name).is_file(), name
    shutil.copy2(ssl_source / 'configdata.pm', evidence / 'openssl-configdata.pm')
    build = python_source / 'PCbuild/amd64'
    run(['msbuild', python_source / 'PCbuild/pcbuild.proj', '/m:2', '/p:Configuration=Release', '/p:Platform=x64', '/p:PlatformToolset=v143', '/p:IncludeTkinter=false', '/p:IncludeSSL=true', '/p:IncludeTests=true', '/p:UseJIT=false', '/p:DisableGil=false', '/p:ExternalsDir=' + str(externals) + '\\', '/p:opensslOutDir=' + str(ssl_source) + '\\', '/p:opensslIncludeDir=' + str(ssl_prefix / 'include')], log=evidence / 'cpython-build.log')
    py = build / 'python.exe'
    run([py, '-c', "import _ssl,_hashlib,ssl,sysconfig; print(ssl.OPENSSL_VERSION); assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 '); assert not sysconfig.get_config_var('Py_GIL_DISABLED')"])
    run([py, '-m', 'test', '-j2', '--junit-xml', evidence / 'cpython-regressions.xml', 'test_ssl', 'test_hashlib', 'test_hmac'], cwd=python_source, log=evidence / 'cpython-regressions.log')
    executed_upstream_suites(evidence / 'cpython-regressions.xml')
    runtime = prefix / 'python'
    run([py, python_source / 'PC/layout', '-s', python_source, '-b', build, '--copy', runtime, '--include-dev', '--include-venv', '--include-stable', '--include-tests'], log=evidence / 'cpython-layout.log')
    py = runtime / 'python.exe'
    shutil.copy2(manifest, runtime / 'PROJECT_MODIFIED_RUNTIME.json')
    run([py, '-m', 'ensurepip'])
    run([py, '-m', 'venv', work / 'venv'])
    py = work / 'venv/Scripts/python.exe'
    os.environ['PATH'] = os.pathsep.join(map(str, [py.parent, prefix / 'qt/bin', prefix / 'bin', ssl_prefix / 'bin'])) + os.pathsep + os.environ['PATH']
    run([py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([py, '-m', 'pip', 'install', 'setuptools==84.2.1', 'wheel==0.48.0', 'cmake==4.4.4', 'ninja==1.13.2', 'packaging==26.3', '--report', evidence / 'build-tools-install.json'])
    os.environ['CMAKE_BUILD_PARALLEL_LEVEL'] = '2'
    common = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL']
    for directory, label, extra in [('zlib-1.3.2', 'zlib', ['-DZLIB_BUILD_TESTING=ON']), ('libpng-1.6.59', 'libpng', ['-DPNG_TESTS=ON','-DPNG_SHARED=ON','-DPNG_STATIC=OFF']), ('pcre2-10.49', 'pcre2', ['-DBUILD_SHARED_LIBS=ON','-DPCRE2_BUILD_PCRE2_16=ON','-DPCRE2_SUPPORT_JIT=ON','-DPCRE2_BUILD_TESTS=ON'])]:
        build_dir = work / (label + '-build')
        run(['cmake', '-S', src / directory, '-B', build_dir, *common, '-DCMAKE_PREFIX_PATH=' + str(prefix), *extra], log=evidence / (label + '-configure.log'))
        run(['cmake', '--build', build_dir], log=evidence / (label + '-build.log'))
        run(['ctest', '--test-dir', build_dir, '--output-on-failure'], log=evidence / (label + '-regressions.log'))
        run(['cmake', '--install', build_dir], log=evidence / (label + '-install.log'))
    qt_build = work / 'qt-build'
    qt_build.mkdir()
    run(['cmd', '/d', '/c', src / 'qtbase-everywhere-src-6.12.0/configure.bat', '-prefix', prefix / 'qt', '-release', '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples', '-openssl-linked', '-system-libpng', '-system-pcre', '-system-zlib', '-no-feature-openssl-runtime', '--', '-DOPENSSL_ROOT_DIR=' + str(ssl_prefix), '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=qt_build, log=evidence / 'qtbase-configure.log')
    run(['cmake', '--build', qt_build, '--parallel', '2'], log=evidence / 'qtbase-build.log')
    run(['cmake', '--install', qt_build], log=evidence / 'qtbase-install.log')
    shutil.copy2(qt_build / 'CMakeCache.txt', evidence / 'qtbase-CMakeCache.txt')
    shutil.copy2(qt_build / 'config.summary', evidence / 'qtbase-config.summary')
    svg_build = work / 'svg-build'
    svg_build.mkdir()
    run(['cmd', '/d', '/c', prefix / 'qt/bin/qt-configure-module.bat', src / 'qtsvg-everywhere-src-6.12.0'], cwd=svg_build, log=evidence / 'qtsvg-configure.log')
    run(['cmake', '--build', svg_build, '--parallel', '2'], log=evidence / 'qtsvg-build.log')
    run(['cmake', '--install', svg_build], log=evidence / 'qtsvg-install.log')
    os.environ['LLVM_INSTALL_DIR'] = str(src / 'libclang')
    run([py, 'setup.py', 'install', '--ignore-git', '--qtpaths=' + str(prefix / 'qt/bin/qtpaths6.exe'), '--parallel=2', '--limited-api=yes', '--module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test', '--no-qt-tools'], cwd=src / 'pyside-setup-everywhere-src-6.12.0', log=evidence / 'pyside-build.log')
    requirements = evidence / 'runtime-requirements.txt'
    requirements.write_text('\n'.join(x for x in (REPO / 'requirements.txt').read_text().splitlines() if not x.startswith('PySide6-Essentials==')) + '\n')
    run([py, '-m', 'pip', 'install', '-r', requirements, 'pytest==9.1.1', '--report', evidence / 'runtime-install.json'])
    run([py, '-m', 'pip', 'check'])
    for name in ('SSL_CERT_FILE','SSL_CERT_DIR','PYTHONHOME','QT_QPA_PLATFORM','LLVM_INSTALL_DIR'):
        os.environ.pop(name, None)
    os.environ.update(PILOT_PREFIX=str(prefix), PILOT_WORK=str(work), PILOT_EVIDENCE=str(evidence), QT_PLUGIN_PATH=str(prefix / 'qt/plugins'), APPDATA=str(work / 'profile/roaming'), LOCALAPPDATA=str(work / 'profile/local'))
    run([py, REPO / '.github/scripts/verify_windows_runtime_pilot.py', '--output-dir', evidence])
    run([py, REPO / 'main.py', 'cli', 'audit', '--help'], log=evidence / 'cli-smoke.txt')
    run([py, '-m', 'pytest', 'tests/test_cli_headless.py', '-q'], log=evidence / 'project-cli-regressions.log')
    run([py, '-m', 'compileall', '-q', 'playstore_app_audit'])
    print('Native Windows x64 source-stack pilot PASS; no application candidate produced.', flush=True)


if __name__ == '__main__':
    main()
