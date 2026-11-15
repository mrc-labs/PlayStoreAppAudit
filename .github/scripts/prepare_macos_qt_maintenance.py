"""Apply the already-qualified common Qt delta and native Mac text providers."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import lzma
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from probe_qt_text_providers import checked_source
from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--arch', choices=['arm64', 'x86_64'], required=True)
    parser.add_argument('--source-only', action='store_true', help='Cheap guarded source transforms only; no native qualification')
    args = parser.parse_args()
    assert args.source_only or sys.platform == 'darwin'
    work, output = args.work.resolve(), args.evidence.resolve()
    prefix, qt = work / 'prefix', work / 'src/qtbase-everywhere-src-6.12.0'
    sources = output / 'sources'
    text = json.loads((REPO / '.github/scripts/qt_text_provider_sources.json').read_text())
    cbor = json.loads((REPO / '.github/scripts/qt_cbor_provider_sources.json').read_text())
    data = json.loads((REPO / '.github/scripts/qt_data_refresh_sources.json').read_text())
    cldr = json.loads((REPO / '.github/scripts/qt_cldr49_sources.json').read_text())
    selected = [row for row in text['sources'] if row['directory'].startswith(('harfbuzz-', 'md4c-'))]
    selected += [row for row in text['meson'] if row['name'].endswith('.tar.gz')]
    assert len(selected) == 3
    selected += [cbor['source'], *data['sources'], *cldr['sources']]

    def stage(row: dict) -> None:
        archive = sources / row['name']
        if archive.exists():
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == row['sha256']
        else:
            archive = checked_source(row, sources)
        if row in selected[:3]:
            with tarfile.open(archive) as bundle:
                bundle.extractall(work / 'src', filter='data')
            root = work / 'src' / row.get('directory', row['name'].removesuffix('.tar.gz'))
            legal = output / 'legal' / root.name
            legal.mkdir(parents=True, exist_ok=True)
            for path in root.iterdir():
                if path.is_file() and path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
                    shutil.copy2(path, legal)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(stage, selected))
    for name in ['qt_text_provider_sources.json', 'qt_cbor_provider_sources.json',
                 'qt_data_refresh_sources.json', 'qt_cldr49_sources.json', 'qt_cldr49_generated_cache.json', 'provider_ca_security_sources.json']:
        shutil.copy2(REPO / '.github/scripts' / name, output)

    def run(command: list, name: str, *, cwd: Path = REPO, env: dict | None = None) -> str:
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, capture_output=True, text=True)
        combined = result.stdout + result.stderr
        (output / (name + '.log')).write_text(combined, encoding='utf-8')
        if result.returncode:
            print(combined[-5000:], flush=True)
        result.check_returncode()
        return result.stdout

    commands = [
        ['apply_qt_cbor_upgrade.py', '--archive', sources / cbor['source']['name']],
        ['apply_qt_http_limits.py', 'apply'],
        ['apply_qt_data_refresh.py', '--archives', sources],
        ['apply_qt_cldr49.py', '--archives', sources, '--reuse-generated'],
        ['apply_qt_ca_guard.py'],
    ]
    for command in commands:
        run([sys.executable, REPO / '.github/scripts' / command[0], *command[1:],
             '--source', qt, '--evidence', output], command[0].removesuffix('.py'))
    for key in ['qt_public_markdown_header', 'qt_private_markdown_header']:
        row = text[key]
        assert hashlib.sha256((qt / row['file']).read_bytes()).hexdigest() == row['sha256']
    assert hashlib.sha256((work / 'src/md4c-0.6.0/src/md4c.h').read_bytes()).hexdigest() == text['md4c_header_sha256']
    apply_source_patch(qt, text['qt_md4c_patch'])
    shutil.copy2(REPO / text['qt_md4c_patch']['path'], output)
    (output / 'qt-md4c-patch-provenance.json').write_text(json.dumps(text['qt_md4c_patch'], indent=2) + '\n')
    for name, digest in text['qt_wrapper_hashes'].items():
        assert hashlib.sha256((qt / name).read_bytes()).hexdigest() == digest
    fonts = []
    for name in ['Roboto-Regular.gsub.fi.ttf', 'Roboto-Regular.nogsub.fi.ttf']:
        matches = list((work / 'src/harfbuzz-15.1.0').rglob(name))
        assert len(matches) == 1 and hashlib.sha256(matches[0].read_bytes()).hexdigest() == text['fonts'][name]
        fonts.append(matches[0])
    cache = json.loads((REPO / '.github/scripts/qt_cldr49_generated_cache.json').read_text())['runtime_fixture']
    fixture_path = (REPO / cache['path']).resolve()
    assert fixture_path.is_relative_to((REPO / '.github/sources').resolve())
    raw = fixture_path.read_bytes()
    assert len(raw) == cache['bytes'] and hashlib.sha256(raw).hexdigest() == cache['sha256']
    shutil.copy2(fixture_path, sources)
    generated = json.loads((REPO / '.github/scripts/qt_cldr49_generated_cache.json').read_text())
    shutil.copy2(REPO / generated['archive'], sources)
    xml = lzma.decompress(raw)
    assert hashlib.sha256(xml).hexdigest() == cache['xml_sha256']
    (output / 'qt-cldr49-runtime-input.xml').write_bytes(xml)
    if args.source_only:
        print('PASS guarded common Qt source transforms only; no native compiler/provider acceptance', flush=True)
        return
    # Mac Qt needs neither GLib nor the GLib-only upstream test/CLI drivers.
    # The unchanged native shaping/Markdown consumer below exercises the actual
    # new libraries; actual QtGui/font/dialect integration follows in the pilot.
    meson = work / 'src/meson-1.12.1/meson.py'
    run([sys.executable, meson, 'setup', work / 'harfbuzz-build', work / 'src/harfbuzz-15.1.0',
         '--prefix=' + str(prefix), '--libdir=lib', '--buildtype=release', '--wrap-mode=nofallback',
         '-Dauto_features=disabled', '-Dglib=disabled', '-Dtests=disabled', '-Dutilities=disabled',
         '-Dsubset=enabled', '-Draster=disabled', '-Dvector=disabled', '-Dgpu=disabled',
         '-Dbenchmark=disabled', '-Dexperimental_api=false'], 'harfbuzz-configure')
    run([sys.executable, meson, 'compile', '-C', work / 'harfbuzz-build', '-j', '2'], 'harfbuzz-build')
    run([sys.executable, meson, 'install', '-C', work / 'harfbuzz-build', '--no-rebuild'], 'harfbuzz-install')
    native = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
              '-DCMAKE_INSTALL_LIBDIR=lib', '-DCMAKE_OSX_ARCHITECTURES=' + args.arch,
              '-DCMAKE_OSX_DEPLOYMENT_TARGET=14.4', '-DCMAKE_OSX_SYSROOT=' + os.environ['SDKROOT'],
              '-DCMAKE_INSTALL_NAME_DIR=@rpath', '-DCMAKE_INSTALL_RPATH=' + str(prefix / 'lib'),
              '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local']
    run(['cmake', '-S', work / 'src/md4c-0.6.0', '-B', work / 'md4c-build', *native,
         '-DBUILD_SHARED_LIBS=ON'], 'md4c-configure')
    run(['cmake', '--build', work / 'md4c-build', '--parallel', '2'], 'md4c-build')
    run(['cmake', '--install', work / 'md4c-build'], 'md4c-install')
    # Compile the same source consumer used by the qualified Linux prerequisite.
    consumer = work / 'mac-text-consumer'
    consumer.mkdir()
    shutil.copy2(REPO / '.github/scripts/qt_text_consumer.cpp', consumer)
    (consumer / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.21)
project(MacNativeText LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(harfbuzz CONFIG REQUIRED PATHS "${PRIVATE_PREFIX}" NO_DEFAULT_PATH)
find_package(md4c CONFIG REQUIRED PATHS "${PRIVATE_PREFIX}" NO_DEFAULT_PATH)
list(PREPEND CMAKE_MODULE_PATH "${QT_SOURCE}/cmake")
find_package(WrapSystemHarfbuzz 2.6.0 REQUIRED)
find_package(WrapSystemMd4c REQUIRED)
add_executable(qt_text_consumer qt_text_consumer.cpp)
target_link_libraries(qt_text_consumer PRIVATE WrapSystemHarfbuzz::WrapSystemHarfbuzz WrapSystemMd4c::WrapSystemMd4c)
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/selected-libraries.txt" CONTENT "$<TARGET_FILE:harfbuzz::harfbuzz>\\n$<TARGET_FILE:md4c::md4c>\\n")
''')
    run(['cmake', '-S', consumer, '-B', consumer / 'build', *native,
         '-DQT_SOURCE=' + str(qt), '-DPRIVATE_PREFIX=' + str(prefix), '-DCMAKE_PREFIX_PATH=' + str(prefix)], 'text-wrapper-configure')
    run(['cmake', '--build', consumer / 'build', '--parallel', '2'], 'text-wrapper-build')
    execution = run([consumer / 'build/qt_text_consumer', *fonts], 'native-text-consumer',
                    env={**os.environ, 'DYLD_PRINT_LIBRARIES': '1'})
    assert execution.startswith('PASS HarfBuzz15.1.0 OpenType')
    selected_libraries = (consumer / 'build/selected-libraries.txt').read_text().splitlines()
    assert len(selected_libraries) == 2
    trace = (output / 'native-text-consumer.log').read_text()
    for name in selected_libraries:
        path = Path(name).resolve()
        assert path.is_relative_to(prefix.resolve()) and path.is_file(), path
        assert str(path) in trace or name in trace, ('Provider absent from dyld trace', name)
    security = json.loads((REPO / '.github/scripts/provider_ca_security_sources.json').read_text())
    directory = output / 'provider-security-inputs'
    directory.mkdir()
    for row in security['sources']:
        checked_source(row, directory)
    (output / 'macos-qt-maintenance-source.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'arch': args.arch, 'framework_deployment': '14.4',
        'source_inputs': selected, 'native_text_consumer': execution.splitlines()[0],
        'scope': 'Common guarded Qt source delta and actual native text prerequisite; full framework/provider/GUI/CA acceptance follows'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
