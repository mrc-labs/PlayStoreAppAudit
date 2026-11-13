"""Isolated QtCore/Network Schannel consumer; no Python/PySide or release rebuild."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import zipfile
from importlib.metadata import version
from pathlib import Path, PurePosixPath

from build_windows_runtime_pilot import native_loader_preflight, patch_source, run
from inspect_pe import read_pe_machine
from probe_qt_ca_security import fetch_inputs
from verify_native_runtime_pilot import certificate_material, default_trust_handshake, tls_server
from verify_windows_runtime_pilot import pe_versions, validate_imports, validate_qtcore_imports

REPO = Path(__file__).resolve().parents[2]
NINJA_WHEEL = {
    'name': 'ninja-1.13.2-py3-none-win_amd64.whl',
    'url': 'https://files.pythonhosted.org/packages/3f/dd/3766b5f4d32e8a9b97d195496b0b01fbbe2e1a41669dab0cd6492a6ce199/ninja-1.13.2-py3-none-win_amd64.whl',
    'sha256': '1293f4078278b70d0ee4b6cc8f3a9e030656c9b2f59909970343c4fe76070118',
    'authority': 'https://pypi.org/pypi/ninja/1.13.2/json',
    'binary_sha256': 'a7f084e8ee37bff0872aa8bd3d17cc19632d2a37734f6c242dd3dee22d77c0b4',
    'native_version': '1.13.2.git.kitware.jobserver-pipe-1',
}


def qualify_ninja_identity(tool: dict, distribution_version: str) -> None:
    """The stable Python wheel includes the documented Kitware jobserver variant."""
    if (distribution_version != '1.13.2' or tool['returncode'] != 0
            or tool['version'].strip() != NINJA_WHEEL['native_version']
            or tool['sha256'] != NINJA_WHEEL['binary_sha256']):
        raise ValueError('Unqualified native Ninja distribution/version/bytes: ' + repr(tool))


def source_contract() -> tuple[dict, dict]:
    windows = json.loads((REPO / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    qt = next(item for item in windows['sources'] if item['name'] == 'qtbase-everywhere-src-6.12.0.tar.xz')
    guard = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text())['qt_ca_patch']
    if qt['sha256'] != 'a951bd163c7b80fc6b8c88d7668fb56abf91c152373e13c10666763238131307':
        raise ValueError('Changed qualified Qt original')
    if hashlib.sha256((REPO / guard['path']).read_bytes()).hexdigest() != guard['sha256']:
        raise ValueError('Changed qualified Qt guard')
    return qt, guard


def verified_download(item: dict, target: Path) -> None:
    with urllib.request.urlopen(item['url'], context=ssl.create_default_context(), timeout=180) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Source HTTPS downgrade rejected')
        with target.open('wb') as stream:
            shutil.copyfileobj(response, stream)
    with target.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
            raise ValueError('Changed official source: ' + item['name'])


def extract_chains(inputs: Path) -> None:
    target = inputs / 'chains'
    target.mkdir()
    with zipfile.ZipFile(inputs / 'chains.zip') as archive:
        for name in archive.namelist():
            path = PurePosixPath(name.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in name:
                raise ValueError('Unsafe public chain archive path')
        archive.extractall(target)


def checked_image(path: Path, output: Path) -> dict:
    assert read_pe_machine(path) == 0x8664, path
    versions = pe_versions(path)
    assert versions['os'] <= (10, 0) and versions['subsystem'] <= (10, 0), (path, versions)
    imports = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
    validate_imports(imports)
    if path.name == 'Qt6Core.dll':
        validate_qtcore_imports(imports)
    if re.search(r'lib(?:ssl|crypto)', imports, re.I):
        raise ValueError('Schannel-only diagnostic imported OpenSSL')
    destination = output / 'native-binaries'
    destination.mkdir(exist_ok=True)
    shutil.copy2(path, destination / path.name)
    (output / (path.name + '-imports.txt')).write_text(imports, encoding='utf-8')
    return {'name': path.name, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'machine': 'AMD64', 'versions': versions, 'imports': imports}


def validate_loaded_origins(result: dict, prefix: Path, executable: Path) -> None:
    modules = [Path(name).resolve() for name in result['loaded_modules']]
    names = {p.name.lower() for p in modules}
    assert {'qt6core.dll', 'qt6network.dll', 'qschannelbackend.dll', 'schannel.dll', 'crypt32.dll',
            'vcruntime140.dll', 'msvcp140.dll'} <= names, names
    validate_imports('\n'.join(names))
    assert not any(re.search(r'lib(?:ssl|crypto)|libclang', name) for name in names)
    for path in modules:
        if path.name.lower().startswith('qt6') or path.name.lower() == 'qschannelbackend.dll':
            assert path.is_relative_to(prefix.resolve()), ('Foreign Qt library', path)
    assert executable.resolve() in modules


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--prerequisites-only', action='store_true')
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert re.fullmatch('[0-9a-f]{40}', head) and head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert sys.platform == 'win32' and platform.machine().upper() == 'AMD64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'x64'
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh private work root required'
    work.mkdir()
    output = REPO / 'windows-pilot-evidence'
    output.mkdir(exist_ok=True)
    qt, guard = source_contract()
    tools = {}
    for name, flags in [('cl', ['/?']), ('link', ['/?']), ('cmake', ['--version']), ('ninja', ['--version'])]:
        path = Path(shutil.which(name) or '')
        assert path.is_file() and read_pe_machine(path) == 0x8664, name
        process = subprocess.run([str(path), *flags], capture_output=True, text=True)
        tools[name] = {'path': str(path), 'version': process.stdout + process.stderr,
                       'returncode': process.returncode,
                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (output / 'qt-ca-tools-discovery.json').write_text(json.dumps({
        'source_sha': head, 'tools': tools, 'PATH': os.environ['PATH'],
        'scope': 'Actual native tool selection before version guards or component downloads',
    }, indent=2), encoding='utf-8')
    print('Native tools before version guards:', json.dumps(tools), flush=True)
    assert '19.44.' in tools['cl']['version'], tools['cl']
    assert tools['cmake']['returncode'] == 0 and '4.4.4' in tools['cmake']['version'], tools['cmake']
    qualify_ninja_identity(tools['ninja'], version('ninja'))
    ninja_original = output / NINJA_WHEEL['name']
    verified_download(NINJA_WHEEL, ninja_original)
    with zipfile.ZipFile(ninja_original) as wheel:
        original = wheel.read('ninja-1.13.2.data/scripts/ninja.exe')
        assert hashlib.sha256(original).hexdigest() == tools['ninja']['sha256']
        tool_legal = output / 'ninja-original-licenses'
        tool_legal.mkdir()
        licenses = [name for name in wheel.namelist() if '.dist-info/licenses/' in name and not name.endswith('/')]
        assert licenses, 'Original Ninja wheel licenses absent'
        for index, name in enumerate(licenses):
            (tool_legal / (str(index) + '-' + Path(name).name)).write_bytes(wheel.read(name))
    (output / 'ninja-original-provenance.json').write_text(json.dumps(NINJA_WHEEL, indent=2), encoding='utf-8')
    defaults = default_trust_handshake()
    windows_roots = sorted(hashlib.sha256(cert).hexdigest() for cert, encoding, trust in ssl.enum_certificates('ROOT')
                           if encoding == 'x509_asn')
    assert windows_roots
    native_loader_preflight(work, output)
    (output / 'qt-ca-prerequisites.json').write_text(json.dumps({
        'source_sha': head, 'python': platform.python_version(), 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'),
        'machine': platform.machine(), 'tools': tools, 'sdk': os.environ.get('WINDOWSSDKVERSION'),
        'vc_tools': os.environ.get('VCTOOLSVERSION'), 'bootstrap_python_default_trust': defaults,
        'windows_ROOT_fingerprints': windows_roots, 'qt': qt, 'guard': guard,
        'scope': 'Native compiler/loader/OS trust prerequisites only; bootstrap Python is not the controlled runtime',
    }, indent=2), encoding='utf-8')
    if args.prerequisites_only:
        print('PASS native prerequisites; no Qt source download or rebuild.', flush=True)
        return
    # Gate stable parent status before selecting a modified source integration.
    with urllib.request.urlopen('https://pypi.org/pypi/PySide6-Essentials/json', timeout=60) as response:
        parent = json.load(response)
    assert parent['info']['version'] == '6.12.0', 'New stable parent requires review before rebuild'
    (output / 'parent-release.json').write_text(json.dumps({'version': parent['info']['version'],
        'source': 'https://pypi.org/pypi/PySide6-Essentials/json'}, indent=2), encoding='utf-8')
    sources = output / 'sources'
    sources.mkdir()
    archive = sources / qt['name']
    verified_download(qt, archive)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / qt['directory']
    patch_source(source, {'path': guard['path'], 'sha256': guard['sha256'], 'files': {
        guard['file']: {'base_sha256': guard['base_sha256'], 'patched_sha256': guard['patched_sha256']}}}, output)
    shutil.copy2(source / guard['file'], output / 'qsslcertificate-project.cpp')
    (output / 'qt-ca-patch-provenance.json').write_text(json.dumps({**guard,
        'identity': 'Project-modified Qt6.12.0; not an unchanged official binary',
        'scope': 'Native Windows x64 QtCore/Network Schannel diagnostic only'}, indent=2), encoding='utf-8')
    legal = output / 'legal'
    legal.mkdir()
    shutil.copytree(source / 'LICENSES', legal / 'Qt6.12.0-LICENSES')
    shutil.copy2(source / 'licenseRule.json', legal / 'licenseRule.json')
    fetch_inputs(output)
    inputs = output / 'inputs'
    extract_chains(inputs)
    build, prefix = work / 'qt-build', work / 'qt'
    build.mkdir()
    run(['cmd', '/d', '/c', source / 'configure.bat', '-prefix', prefix, '-release', '-opensource',
         '-confirm-license', '-nomake', 'tests', '-nomake', 'examples', '-no-gui', '-no-widgets',
         '-no-openssl', '-no-dbus', '-no-feature-sql', '-no-feature-xml', '-no-feature-testlib', '--',
         '-DQT_FEATURE_schannel=ON', '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=build,
        log=output / 'qt-configure.log')
    run(['cmake', '--build', build, '--parallel', '2'], log=output / 'qt-build.log')
    run(['cmake', '--install', build], log=output / 'qt-install.log')
    for name in ('CMakeCache.txt', 'config.summary'):
        shutil.copy2(build / name, output / name)
    consumer_source = work / 'consumer'
    consumer_source.mkdir()
    consumer_cpp = REPO / '.github/scripts/windows_qt_ca_consumer.cpp'
    shutil.copy2(consumer_cpp, consumer_source / consumer_cpp.name)
    shutil.copy2(consumer_cpp, output / consumer_cpp.name)
    (consumer_source / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.21)\n'
        'project(WindowsQtCaConsumer LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\n'
        'find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Network)\n'
        'add_executable(qt_ca_consumer windows_qt_ca_consumer.cpp)\n'
        'target_link_libraries(qt_ca_consumer PRIVATE Qt6::Core Qt6::Network)\n', encoding='utf-8')
    consumer_build = work / 'consumer-build'
    run(['cmake', '-S', consumer_source, '-B', consumer_build, '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], log=output / 'consumer-configure.log')
    run(['cmake', '--build', consumer_build], log=output / 'consumer-build.log')
    executable = consumer_build / 'qt_ca_consumer.exe'
    selected = [executable, prefix / 'bin/Qt6Core.dll', prefix / 'bin/Qt6Network.dll',
                prefix / 'plugins/tls/qschannelbackend.dll']
    images = [checked_image(path, output) for path in selected]
    directives = subprocess.check_output(['dumpbin', '/nologo', '/directives',
        str(consumer_build / 'CMakeFiles/qt_ca_consumer.dir/windows_qt_ca_consumer.cpp.obj')], text=True)
    assert re.search(r'DEFAULTLIB:"?MSVCRT', directives, re.I) and not re.search(r'DEFAULTLIB:"?LIBCMT', directives, re.I)
    (output / 'consumer-crt.txt').write_text(directives, encoding='utf-8')
    os.environ['PATH'] = str(prefix / 'bin') + os.pathsep + os.environ['PATH']
    os.environ['QT_PLUGIN_PATH'] = str(prefix / 'plugins')
    for variable in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'QT_SSL_BACKEND'):
        os.environ.pop(variable, None)
    def exercise(label: str, *arguments: str) -> dict:
        process = subprocess.run([str(executable), *arguments], capture_output=True, text=True)
        (output / (label + '.log')).write_text(process.stdout + process.stderr, encoding='utf-8')
        if process.returncode:
            raise RuntimeError(f'Native consumer {label} failed: {process.stdout}\n{process.stderr}')
        result = json.loads(process.stdout)
        validate_loaded_origins(result, prefix, executable)
        (output / (label + '.json')).write_text(json.dumps(result, indent=2), encoding='utf-8')
        return result
    policy = exercise('qt-ca-policy', 'policy', str(inputs))
    default = exercise('qt-default-trust', 'default')
    fixtures = output / 'isolated-certificates'
    fixtures.mkdir()
    paths = certificate_material(fixtures)
    rows = []
    for label, protocol, hostname, trusted, leaf, error in [
        ('tls12', 'tls12', 'localhost', True, 'valid', 'positive'),
        ('tls13', 'tls13', 'localhost', True, 'valid', 'positive'),
        ('hostname', 'negative', 'wrong.invalid', True, 'valid', 'hostname'),
        ('untrusted', 'negative', 'localhost', False, 'valid', 'untrusted'),
        ('expired', 'negative', 'localhost', True, 'expired', 'expired'),
    ]:
        with tls_server(paths, leaf) as port:
            rows.append(exercise('qt-' + label, 'fixture', str(paths['ca']) if trusted else 'untrusted',
                                 str(port), hostname, protocol, str(error)))
    incidents = []
    for index, path in enumerate(sorted((inputs / 'chains').rglob('*.pem'))):
        incidents.append(exercise('qt-incident-' + str(index), 'incident', str(path)))
    assert len(incidents) == 16
    result = {'source_sha': head, 'identity': 'Project-modified Qt6.12.0 / native Schannel, not OpenSSL',
        'input_policy': policy, 'incident_tls': incidents, 'ordinary_default_trust': default, 'tls_fixture_cases': rows,
        'images': images,
        'scope': 'QtCore/Network native x64 diagnostic only; no controlled CPython/PySide/GUI/full package acceptance',
        'remaining': 'Full source-stack dual-provider qualification and finite R01-R17 obligations remain required'}
    (output / 'qt-ca-results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    assert all(row['result'] == 'PASS' for row in incidents), 'Native incident TLS gate failed/inconclusive; retained per-case JSON identifies cause'
    print('PASS native Schannel guard/default trust/TLS positive-negative/AMD64/MD diagnostic.', flush=True)


if __name__ == '__main__':
    main()
