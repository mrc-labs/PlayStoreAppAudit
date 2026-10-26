"""Bounded Windows x64 source build. Never produces an application candidate."""
from __future__ import annotations

import argparse
import ast
import concurrent.futures
import functools
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
from types import SimpleNamespace

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


def register_private_dll_directories(py: Path, directories: list[Path], evidence: Path) -> None:
    """Initialize only this diagnostic venv using Python's secure DLL search API."""
    site = Path(subprocess.check_output([str(py), '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'], text=True).strip())
    paths = [str(path.resolve(strict=True)) for path in directories]
    module = site / '_playstore_pilot_dll_dirs.py'
    module.write_text('import os\nDIRECTORIES = ' + repr(paths) + '\n'
                      'HANDLES = [os.add_dll_directory(path) for path in DIRECTORIES]\n', encoding='utf-8')
    startup = site / 'playstore_pilot_dll_dirs.pth'
    startup.write_text('import _playstore_pilot_dll_dirs\n', encoding='utf-8')
    (evidence / 'private-dll-directories.json').write_text(json.dumps({
        'source_sha':os.environ['GITHUB_SHA'], 'python':str(py), 'directories':paths,
        'files':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (module, startup)},
        'scope':'isolated diagnostic venv only; no OS or application loader changes',
    }, indent=2))


def native_loader_preflight(work: Path, evidence: Path) -> None:
    """Reproduce PATH-only failure, then test explicit and venv-startup registration."""
    root = work / 'loader-preflight'
    dependency, extension = root / 'dependency', root / 'extension'
    dependency.mkdir(parents=True)
    extension.mkdir()
    helper = dependency / 'pilot_dependency.c'
    helper.write_text('__declspec(dllexport) int pilot_answer(void) { return 42; }\n')
    source = extension / 'pilot_loader.c'
    source.write_text('#include <Python.h>\n__declspec(dllimport) int pilot_answer(void);\n'
        'static PyObject *answer(PyObject *s, PyObject *a) { return PyLong_FromLong(pilot_answer()); }\n'
        'static PyMethodDef methods[] = {{"answer", answer, METH_NOARGS, NULL}, {NULL}};\n'
        'static struct PyModuleDef module = {PyModuleDef_HEAD_INIT, "pilot_loader", NULL, -1, methods};\n'
        'PyMODINIT_FUNC PyInit_pilot_loader(void) { return PyModule_Create(&module); }\n')
    run(['cl', '/nologo', '/LD', '/MD', helper, '/link', '/OUT:' + str(dependency / 'pilot_dependency.dll'),
         '/IMPLIB:' + str(dependency / 'pilot_dependency.lib')], cwd=dependency, log=evidence / 'loader-helper-build.log')
    run(['cl', '/nologo', '/LD', '/MD', '/I' + str(Path(sys.base_prefix) / 'include'), source,
         '/link', '/LIBPATH:' + str(Path(sys.base_prefix) / 'libs'), dependency / 'pilot_dependency.lib',
         '/OUT:' + str(extension / 'pilot_loader.pyd')], cwd=extension, log=evidence / 'loader-extension-build.log')
    assert read_pe_machine(extension / 'pilot_loader.pyd') == 0x8664
    environment = {**os.environ, 'PATH':str(dependency) + os.pathsep + os.environ['PATH']}
    code = 'import sys; sys.path.insert(0, sys.argv[1]); import pilot_loader; assert pilot_loader.answer() == 42; print("answer=42")'
    failed = subprocess.run([sys.executable, '-I', '-c', code, str(extension)], cwd=root, env=environment, capture_output=True, text=True)
    assert failed.returncode and 'DLL load failed while importing pilot_loader' in failed.stderr, failed
    explicit = subprocess.run([sys.executable, '-I', '-c',
        'import os; handle=os.add_dll_directory(' + repr(str(dependency)) + '); ' + code,
        str(extension)], cwd=root, env=environment, capture_output=True, text=True, check=True)
    venv = root / 'venv'
    run([sys.executable, '-m', 'venv', '--without-pip', venv])
    py = venv / 'Scripts/python.exe'
    register_private_dll_directories(py, [dependency], evidence)
    automatic = subprocess.run([str(py), '-I', '-c', code, str(extension)], cwd=root, env=environment, capture_output=True, text=True, check=True)
    (evidence / 'loader-preflight.json').write_text(json.dumps({
        'source_sha':os.environ['GITHUB_SHA'], 'machine':'AMD64', 'crt':'/MD',
        'path_only':{'returncode':failed.returncode, 'stderr':failed.stderr},
        'explicit_registration':explicit.stdout, 'venv_startup_registration':automatic.stdout,
        'inputs':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in (helper, source)},
    }, indent=2))
    print('Native secure DLL loader preflight PASS: PATH rejected; explicit and private venv registration accepted.', flush=True)


def pyside_packaging_preflight(source: Path, evidence: Path) -> None:
    """Exercise the actual hash-verified vendor packager without compiling Qt."""
    path = source / 'build_scripts/platforms/windows_desktop.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'copy_qt_artifacts')
    results = []
    for uitools, designer_available in [(False, False), (True, False), (True, True)]:
        copied = []
        clang_preparations = []

        def copydir(origin: str, *args: object, selected: list[str] = copied,
                    available: bool = designer_available, **kwargs: object) -> bool:
            selected.append(origin)
            if origin == '{install_dir}/plugins/designer' and not available:
                raise FileNotFoundError('required Designer plugin missing')
            return True

        modules = ['Core', 'Gui', 'Widgets', 'Network', 'Svg', 'SvgWidgets', 'Test']
        if uitools:
            modules.append('UiTools')
        build = SimpleNamespace(get_built_pyside_config=lambda _, selected=modules: {'built_modules':selected},
            qtinfo=SimpleNamespace(build_type='release'), build_classifiers=[],
            is_webengine_built=lambda _:False,
            prepare_standalone_clang=lambda selected=clang_preparations, **kwargs:selected.append(kwargs))
        namespace = {'functools':functools, 'platform':platform,
            'config':SimpleNamespace(is_internal_shiboken_generator_build=lambda:False),
            'PYSIDE_MULTIMEDIA_LIBS':[], 'PYSIDE':'pyside6', 'copydir':copydir,
            'copyfile':lambda *a, **k:None, 'download_qt_dependency_dlls':lambda *a:None,
            'filter_match':lambda *a:True}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
        try:
            namespace['copy_qt_artifacts'](build, 'package/PySide6', False, {})
        except FileNotFoundError:
            assert uitools and not designer_available, 'Unselected optional Designer was required'
            outcome = 'required missing plugin rejected'
        else:
            assert not uitools or designer_available, 'Required missing plugin was silently accepted'
            assert '{qt_plugins_dir}' in copied, 'TLS/platform plugin collection must remain enabled'
            assert ('{install_dir}/plugins/designer' in copied) == uitools
            assert clang_preparations == ([{'is_win':True}] if platform.machine() == 'ARM64' else [])
            outcome = 'selected plugins collected'
        results.append({'uitools':uitools, 'designer_available':designer_available,
            'clang_preparations':clang_preparations, 'result':outcome})
    (evidence / 'pyside-packaging-preflight.json').write_text(json.dumps({
        'source_sha':os.environ['GITHUB_SHA'], 'vendor_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'cases':results, 'scope':'actual vendor function; file-copy calls instrumented, no binaries fabricated'}, indent=2))
    print('PySide Windows module-subset packaging preflight PASS (3 cases).', flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--prerequisites-only', action='store_true')
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
    native_loader_preflight(work, evidence)
    # Exercise the native OS backend/verifier on this runner before costly sources/rebuilds.
    bootstrap = work / 'schannel-preflight'
    run([sys.executable, '-m', 'venv', bootstrap])
    bootstrap_py = bootstrap / 'Scripts/python.exe'
    run([bootstrap_py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([bootstrap_py, '-m', 'pip', 'install', 'PySide6-Essentials==6.12.0', 'cryptography==50.0.2', '--report', evidence / 'schannel-preflight-install.json'])
    run([bootstrap_py, REPO / '.github/scripts/verify_windows_runtime_pilot.py', '--bootstrap-schannel', '--output-dir', evidence / 'schannel-preflight'])
    if args.prerequisites_only:
        print('Windows prerequisite/loader diagnostics PASS; no component source downloads or rebuild.', flush=True)
        return
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
    pyside_source = src / 'pyside-setup-everywhere-src-6.12.0'
    patch_source(pyside_source, spec['pyside_windows_patch'], evidence)
    pyside_packaging_preflight(pyside_source, evidence)
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
    # CPython's Windows OpenSSL recipe uses no-uplink: all components share /MD.
    # Fresh one-shot builds can use OpenSSL's documented no-makedepend option.
    run(['perl', 'Configure', 'VC-WIN64A', 'shared', 'no-uplink', 'no-makedepend', 'no-docs', '--prefix=' + str(ssl_prefix), '--libdir=lib', 'CFLAGS=/MD'], cwd=ssl_source, log=evidence / 'openssl-configure.log')
    assert 'CFLAGS=/MD' in (ssl_source / 'makefile').read_text(), 'Explicit shared CRT required'
    run(['nmake'], cwd=ssl_source, log=evidence / 'openssl-build.log')
    run(['nmake', 'test', 'TESTS=test_evp test_x509 test_verify test_ssl_new'], cwd=ssl_source, log=evidence / 'openssl-regressions.log')
    run(['nmake', 'install_sw'], cwd=ssl_source, log=evidence / 'openssl-install.log')
    for name in [*spec['openssl_dlls'], *spec['openssl_import_libraries']]:
        assert (ssl_source / name).is_file(), name
    shutil.copy2(ssl_source / 'configdata.pm', evidence / 'openssl-configdata.pm')
    build = python_source / 'PCbuild/amd64'
    run(['msbuild', python_source / 'PCbuild/pcbuild.proj', '/m:2', '/p:Configuration=Release', '/p:Platform=x64', '/p:PlatformToolset=v143', '/p:VCToolsVersion=' + os.environ['VCTOOLSVERSION'], '/p:IncludeTkinter=false', '/p:IncludeSSL=true', '/p:IncludeTests=true', '/p:UseJIT=false', '/p:DisableGil=false', '/p:ExternalsDir=' + str(externals) + '\\', '/p:opensslOutDir=' + str(ssl_source) + '\\', '/p:opensslIncludeDir=' + str(ssl_prefix / 'include')], log=evidence / 'cpython-build.log')
    py = build / 'python.exe'
    run([py, '-c', "import _ssl,_hashlib,ssl,sysconfig; print(ssl.OPENSSL_VERSION); assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 '); assert not sysconfig.get_config_var('Py_GIL_DISABLED')"])
    # Imports alone did not detect the uplink ABI failure: exercise actual PEM file I/O.
    run([py, '-c', "import ssl,sys; from pathlib import Path; root=Path(sys.argv[1]); c=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); c.load_cert_chain(root/'keycert.pem'); t=ssl.create_default_context(cafile=str(root/'pycacert.pem')); assert t.verify_mode==ssl.CERT_REQUIRED and t.check_hostname; print('OpenSSL PEM file I/O and CRT integration PASS')", python_source / 'Lib/test/certdata'])
    run([py, '-m', 'test', '-j2', '--junit-xml', evidence / 'cpython-regressions.xml', 'test_ssl', 'test_hashlib', 'test_hmac'], cwd=python_source, log=evidence / 'cpython-regressions.log')
    executed_upstream_suites(evidence / 'cpython-regressions.xml')
    runtime = prefix / 'python'
    run([py, python_source / 'PC/layout', '-s', python_source, '-b', build, '--copy', runtime, '--include-dev', '--include-venv', '--include-stable', '--include-tests'], log=evidence / 'cpython-layout.log')
    py = runtime / 'python.exe'
    shutil.copy2(manifest, runtime / 'PROJECT_MODIFIED_RUNTIME.json')
    run([py, '-m', 'ensurepip'])
    run([py, '-m', 'venv', work / 'venv'])
    py = work / 'venv/Scripts/python.exe'
    # setup-python exports bootstrap roots; binding discovery must use the rebuilt runtime.
    for variable in ('PYTHONHOME', 'PYTHON_ROOT_DIR', 'PYTHON2_ROOT_DIR', 'PYTHON3_ROOT_DIR'):
        os.environ.pop(variable, None)
    os.environ['PYTHON_ROOT_DIR'] = str(runtime)
    os.environ['PYTHON3_ROOT_DIR'] = str(runtime)
    os.environ['CMAKE_PREFIX_PATH'] = os.pathsep.join(map(str, [prefix, ssl_prefix, prefix / 'qt']))
    os.environ['PATH'] = os.pathsep.join(map(str, [py.parent, prefix / 'qt/bin', prefix / 'bin', ssl_prefix / 'bin'])) + os.pathsep + os.environ['PATH']
    dll_directories = [prefix / 'qt/bin', prefix / 'bin', ssl_prefix / 'bin']
    for directory in dll_directories:
        directory.mkdir(parents=True, exist_ok=True)
    register_private_dll_directories(py, dll_directories, evidence)
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
    # QtSvg is a separate configure process: require its system zlib wrapper first.
    dependency_probe = work / 'qt-dependency-probe'
    dependency_probe.mkdir()
    (dependency_probe / 'CMakeLists.txt').write_text(
        'cmake_minimum_required(VERSION 3.21)\nproject(PilotQtDependencies LANGUAGES C)\n'
        f'list(PREPEND CMAKE_MODULE_PATH "{(src / "qtbase-everywhere-src-6.12.0/cmake").as_posix()}")\n'
        'set(QT_USE_BUNDLED_BundledZLIB OFF)\n'
        'find_package(WrapZLIB REQUIRED)\n'
        'if(NOT TARGET WrapZLIB::WrapZLIB)\nmessage(FATAL_ERROR "Missing Qt system zlib target")\nendif()\n')
    run(['cmake', '-S', dependency_probe, '-B', dependency_probe / 'build', *common,
         '-DCMAKE_PREFIX_PATH=' + str(prefix)], log=evidence / 'qt-dependency-preflight.log')
    qt_build = work / 'qt-build'
    qt_build.mkdir()
    run(['cmd', '/d', '/c', src / 'qtbase-everywhere-src-6.12.0/configure.bat', '-prefix', prefix / 'qt', '-release', '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples', '-openssl-linked', '-system-libpng', '-system-pcre', '-system-zlib', '-no-feature-openssl-runtime', '--', '-DOPENSSL_ROOT_DIR=' + str(ssl_prefix), '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=qt_build, log=evidence / 'qtbase-configure.log')
    run(['cmake', '--build', qt_build, '--parallel', '2'], log=evidence / 'qtbase-build.log')
    run(['cmake', '--install', qt_build], log=evidence / 'qtbase-install.log')
    shutil.copy2(qt_build / 'CMakeCache.txt', evidence / 'qtbase-CMakeCache.txt')
    shutil.copy2(qt_build / 'config.summary', evidence / 'qtbase-config.summary')
    svg_build = work / 'svg-build'
    svg_build.mkdir()
    run(['cmd', '/d', '/c', prefix / 'qt/bin/qt-configure-module.bat', src / 'qtsvg-everywhere-src-6.12.0', '--', '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=svg_build, log=evidence / 'qtsvg-configure.log')
    run(['cmake', '--build', svg_build, '--parallel', '2'], log=evidence / 'qtsvg-build.log')
    run(['cmake', '--install', svg_build], log=evidence / 'qtsvg-install.log')
    # Exercise the actual Qt dependency closure before compiling binding wrappers/stubs.
    run([py, '-I', '-c', 'import ctypes,sys; dll=ctypes.WinDLL(sys.argv[1]); print("Controlled QtCore secure-load PASS", dll._name)',
         prefix / 'qt/bin/Qt6Core.dll'], log=evidence / 'qtcore-loader-preflight.log')
    run(['dumpbin', '/dependents', prefix / 'qt/bin/Qt6Core.dll'], log=evidence / 'qtcore-dependents.log')
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
