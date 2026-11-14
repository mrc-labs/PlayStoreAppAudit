"""One Jammy QtCore/Network HTTP security diagnostic; no Python/PySide rebuild."""
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

from apply_qt_ca_guard import apply_guard
from apply_qt_cbor_upgrade import apply_upgrade
from apply_qt_http_limits import apply_limits, test_limits
from probe_qt_text_providers import checked_source
from verify_linux_x64_native_delta import elf_record

REPO = Path(__file__).resolve().parents[2]


def loaded_images(lines: list[str], prefix: Path, sdk: Path) -> list[Path]:
    paths = {Path(line.split()[-1]).resolve() for line in lines}
    if any(path.is_relative_to(sdk) for path in paths):
        raise ValueError('Link-only GNU SDK loaded at runtime')
    paths = {path for path in paths if path.name.startswith(('libQt6', 'libssl.so', 'libcrypto.so', 'libqopensslbackend'))}
    if any(not path.is_relative_to(prefix) for path in paths):
        raise ValueError('Foreign Qt/OpenSSL or link SDK loaded')
    for stem in ['libQt6Core.so', 'libQt6Network.so', 'libssl.so.4', 'libcrypto.so.4', 'libqopensslbackend.so']:
        if not any(path.name.startswith(stem) for path in paths):
            raise ValueError('Expected private HTTP/TLS image missing: ' + stem)
    if any(path.name.startswith(('libssl.so.3', 'libcrypto.so.3')) for path in paths):
        raise ValueError('OpenSSL3 fallback')
    return sorted(paths)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA']
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '22.04'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    work, output = args.work_root.resolve(), args.output_dir.resolve()
    assert not work.exists()
    sdk = json.loads((output / 'cxx-sdk-qualified.json').read_text())
    trust = json.loads((output / 'system-trust-diagnostics.json').read_text())
    assert sdk['source_sha'] == trust['source_sha'] == head and sdk['compatible']
    assert sdk['thread_probe'] == 'PASS' and sdk['runtime_sdk_loaded'] is False
    assert trust['default_trust']['result'] == 'default-trust authenticated handshake PASS'
    with urllib.request.urlopen('https://pypi.org/pypi/PySide6-Essentials/json', timeout=60) as response:
        parent = json.load(response)['info']['version']
    assert parent == '6.12.0', 'New stable matched parent requires review before modified Qt build'
    (output / 'http-parent-release.json').write_text(json.dumps({'version': parent,
        'source': 'https://pypi.org/pypi/PySide6-Essentials/json'}, indent=2) + '\n')
    work.mkdir()
    sources = output / 'sources'
    sources.mkdir(exist_ok=True)
    manifests = {}
    for name in ['native_runtime_pilot_sources.json', 'linux_x64_native_delta_sources.json',
                 'qt_cbor_provider_sources.json', 'qt_http_security_sources.json']:
        path = REPO / '.github/scripts' / name
        manifests[name] = json.loads(path.read_text())
        shutil.copy2(path, output)
    base = manifests['native_runtime_pilot_sources.json']
    delta = manifests['linux_x64_native_delta_sources.json']
    cbor = manifests['qt_cbor_provider_sources.json']
    selected = [item for item in base['sources'] if item['name'].startswith(('qtbase-', 'openssl-'))]
    selected += [item for item in delta['sources'] if item['name'].startswith('zlib-')] + [cbor['source']]
    for item in selected:
        archive = checked_source(item, sources)
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
    qt = work / 'qtbase-everywhere-src-6.12.0'
    apply_upgrade(qt, sources / cbor['source']['name'], output)
    apply_limits(qt, output)
    apply_guard(qt, output)
    legal = output / 'legal'
    legal.mkdir(exist_ok=True)  # The qualified link-SDK preflight already retains legal material here.
    shutil.copytree(qt / 'LICENSES', legal / 'Qt6.12.0-LICENSES')
    shutil.copy2(qt / 'licenseRule.json', legal)
    shutil.copy2(work / 'openssl-4.0.3/LICENSE.txt', legal / 'OpenSSL-LICENSE.txt')
    shutil.copy2(work / 'zlib-1.4/README', legal / 'zlib-README')
    shutil.copy2(work / 'zlib-1.4/zlib.h', legal / 'zlib.h')
    shutil.copy2(work / cbor['source']['directory'] / 'LICENSE', legal / 'TinyCBOR-LICENSE')
    prefix = work / 'prefix'
    prefix.mkdir()
    env = {**os.environ, 'LD_LIBRARY_PATH': str(prefix / 'lib'),
           'PKG_CONFIG_PATH': str(prefix / 'lib/pkgconfig')}

    def run(command: list, name: str, cwd: Path = work) -> None:
        print('Qt HTTP diagnostic stage:', name, flush=True)
        with (output / (name + '.log')).open('w', encoding='utf-8') as log:
            result = subprocess.run(list(map(str, command)), cwd=cwd, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print('\n'.join((output / (name + '.log')).read_text(encoding='utf-8', errors='replace').splitlines()[-80:]), flush=True)
        result.check_returncode()

    run(['./configure', '--prefix=' + str(prefix)], 'zlib-configure', work / 'zlib-1.4')
    run(['make', '-j2'], 'zlib-build', work / 'zlib-1.4')
    run(['make', 'install'], 'zlib-install', work / 'zlib-1.4')
    openssldir = re.fullmatch(r'OPENSSLDIR: "(.+)"\s*', trust['commands']['openssl_directory']['stdout'])
    assert openssldir and Path(openssldir[1]).is_absolute()
    openssl = work / 'openssl-4.0.3'
    run(['./Configure', 'linux-x86_64', 'shared', '--prefix=' + str(prefix), '--libdir=lib',
         '--openssldir=' + openssldir[1]], 'openssl-configure', openssl)
    run(['make', '-j2'], 'openssl-build', openssl)
    run(['make', 'install_sw'], 'openssl-install', openssl)
    build = work / 'qt-build'
    build.mkdir()
    # Official private readStatus/readHeader tests require Q_AUTOTEST_EXPORT.
    # Export them in this diagnostic dependency build only; never a producer setting.
    run([qt / 'configure', '-prefix', prefix / 'qt', '-developer-build', '-release', '-no-warnings-are-errors',
         '-opensource', '-confirm-license',
         '-nomake', 'tests', '-nomake', 'examples', '-no-gui', '-no-widgets', '-no-dbus',
         '-no-feature-sql', '-no-feature-xml', '-system-zlib', '-openssl-linked',
         '-no-feature-openssl-runtime', '--', '-DOPENSSL_ROOT_DIR=' + str(prefix),
         '-DCMAKE_PREFIX_PATH=' + str(prefix), '-DCMAKE_INSTALL_RPATH=' + str(prefix / 'lib'),
         '-DQT_BUILD_DOC_SNIPPETS=OFF'],
        'qt-configure', build)
    cache = (build / 'CMakeCache.txt').read_text(encoding='utf-8')
    for feature, value in [('developer_build', 'ON'), ('testlib', 'ON'), ('gui', 'OFF'),
                           ('sql', 'OFF'), ('system_zlib', 'ON'), ('openssl_linked', 'ON'),
                           ('openssl_runtime', 'OFF')]:
        assert f'QT_FEATURE_{feature}:INTERNAL={value}' in cache, feature
    flags = next(line for line in cache.splitlines() if line.startswith('CMAKE_CXX_FLAGS:STRING='))
    assert '-L' + sdk['link_directory'] in flags, 'Qualified C++ link SDK was not selected'
    assert 'QT_BUILD_DOC_SNIPPETS:BOOL=OFF' in cache
    shutil.copy2(build / 'CMakeCache.txt', output / 'qtbase-CMakeCache.txt')
    run(['cmake', '--build', '.', '--parallel', '2'], 'qt-build', build)
    run(['cmake', '--install', '.'], 'qt-install', build)
    # Retain the compiled diagnostic SDK before harness configuration/execution.
    # A later harness-only fix can reuse these exact bytes instead of rebuilding.
    sdk_files = {}
    for path in sorted(prefix.rglob('*')):
        relative = path.relative_to(prefix).as_posix()
        if path.is_symlink():
            assert path.resolve().is_relative_to(prefix), 'Diagnostic SDK symlink escapes private prefix'
            sdk_files[relative] = {'symlink': os.readlink(path)}
        elif path.is_file():
            sdk_files[relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    sdk_archive = output / 'qt-http-sdk.tar.gz'
    with tarfile.open(sdk_archive, 'w:gz', compresslevel=1) as archive:
        archive.add(prefix, arcname='prefix')
    (output / 'qt-http-sdk-provenance.json').write_text(json.dumps({
        'source_sha': head, 'scope': 'Compiled private Core/Network diagnostic SDK only; tests/acceptance pending',
        'archive_sha256': hashlib.sha256(sdk_archive.read_bytes()).hexdigest(),
        'files': sdk_files, 'qt_configuration_sha256': hashlib.sha256(cache.encode()).hexdigest(),
    }, indent=2) + '\n', encoding='utf-8')
    os.environ['LD_LIBRARY_PATH'] = str(prefix / 'qt/lib') + ':' + str(prefix / 'lib')
    os.environ['QT_PLUGIN_PATH'] = str(prefix / 'qt/plugins')
    os.environ['PKG_CONFIG_PATH'] = env['PKG_CONFIG_PATH']
    regression = test_limits(qt, prefix / 'qt', work / 'http-tests', output)
    consumer = work / 'consumer'
    consumer.mkdir()
    cpp = REPO / '.github/scripts/qt_http_default_consumer.cpp'
    shutil.copy2(cpp, output)
    (consumer / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\n'
        'project(QtHttpDefault LANGUAGES CXX)\nfind_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core Network)\n'
        f'add_executable(qt_http_default "{cpp.as_posix()}")\n'
        'target_link_libraries(qt_http_default PRIVATE Qt6::Core Qt6::Network)\n')
    env.update(LD_LIBRARY_PATH=os.environ['LD_LIBRARY_PATH'], QT_PLUGIN_PATH=os.environ['QT_PLUGIN_PATH'])
    run(['cmake', '-S', consumer, '-B', consumer / 'out', '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_PREFIX_PATH=' + str(prefix / 'qt')], 'http-default-configure')
    run(['cmake', '--build', consumer / 'out', '--parallel', '2'], 'http-default-build')
    binary = consumer / 'out/qt_http_default'
    run([binary], 'http-default')
    result = json.loads((output / 'http-default.log').read_text())
    assert result['result'] == 'PASS default-trust authenticated HTTP/1 response'
    paths = loaded_images(result['loaded'], prefix, Path(sdk['link_directory']).resolve())
    result.update(source_sha=head, scope='Qt HTTP security only; no Python/PySide/GUI/cffi rebuild or final candidate',
                  upstream=regression, images=[elf_record(path, output) for path in [binary, *paths]],
                  consumer_sha256=hashlib.sha256(cpp.read_bytes()).hexdigest())
    (output / 'qt-http-native-results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
