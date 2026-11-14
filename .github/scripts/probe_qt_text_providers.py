"""One Jammy x64 source/link prerequisite for Qt text providers; no Qt rebuild."""
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
from importlib.metadata import version
from pathlib import Path

from inspect_linux_abi import readelf, required_versions, version_floor

REPO = Path(__file__).resolve().parents[2]


def reviewed_md4c_flags(qt: Path, md4c: Path, output: Path) -> Path:
    """Generate a tiny prerequisite from actual guarded Qt declarations and patched expression."""
    spec = json.loads((REPO / '.github/scripts/qt_text_provider_sources.json').read_text(encoding='utf-8'))
    for key in ['qt_public_markdown_header', 'qt_private_markdown_header']:
        item = spec[key]
        if hashlib.sha256((qt / item['file']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Changed original Qt Markdown declarations')
    if hashlib.sha256((md4c / 'src/md4c.h').read_bytes()).hexdigest() != spec['md4c_header_sha256']:
        raise ValueError('Changed original MD4C interface')
    patch = spec['qt_md4c_patch']
    for name, guard in patch['files'].items():
        if hashlib.sha256((qt / name).read_bytes()).hexdigest() != guard['patched_sha256']:
            raise ValueError('Reviewed Qt flag adaptation not applied')
    public = (qt / spec['qt_public_markdown_header']['file']).read_text(encoding='utf-8')
    private = (qt / spec['qt_private_markdown_header']['file']).read_text(encoding='utf-8')
    importer = (qt / 'src/gui/text/qtextmarkdownimporter.cpp').read_text(encoding='utf-8')
    dialect = re.search(r'MarkdownDialectGitHub\s*=\s*([^\n,]+)', public)[1].strip()
    front_matter = re.search(r'FeatureFrontMatter\s*=\s*(0x[0-9a-fA-F]+)', private)[1]
    expression = re.search(r'^\s+(unsigned\(m_features\)[^\n]+),$', importer, re.MULTILINE)[1]
    if not re.fullmatch(r'(?:0x[0-9a-fA-F]+|\s|\|)+', dialect):
        raise ValueError('Unreviewed Qt public dialect expression')
    output.mkdir(parents=True, exist_ok=True)
    header = output / 'qt-md4c-reviewed-flags.h'
    header.write_text(f'constexpr unsigned qtDialectGitHub = {dialect};\n'
                      f'constexpr unsigned FeatureFrontMatter = {front_matter};\n'
                      f'static unsigned qtProviderFlags(unsigned m_features) {{ return {expression}; }}\n', encoding='utf-8')
    shutil.copy2(REPO / '.github/scripts/qt_md4c_flags_consumer.cpp', output)
    return header


def checked_source(item: dict, directory: Path) -> Path:
    """Only the closed HTTPS/hash contract may provide build inputs."""
    if not item['url'].startswith('https://'):
        raise ValueError('Source HTTPS required')
    with urllib.request.urlopen(item['url'], timeout=180) as response:
        if not response.geturl().startswith('https://'):
            raise ValueError('Source HTTPS downgrade')
        data = response.read()
    if hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError('Changed official source digest: ' + item['name'])
    path = directory / item['name']
    path.write_bytes(data)
    return path


def validate_abi(header: str, versions: list[str]) -> dict:
    if not re.search(r'Machine:\s+Advanced Micro Devices X86-64', header):
        raise ValueError('Native x64 ELF required')
    result = {}
    for key, ceiling in [('GLIBC_', (2, 35)), ('GLIBCXX_', (3, 4, 29))]:
        selected = version_floor(versions, key)
        if selected and tuple(map(int, selected.removeprefix(key).split('.'))) > ceiling:
            raise ValueError('Raised text-provider ABI: ' + selected)
        result[key] = selected
    return result


def validate_loaded_paths(text: str, prefix: Path, sdk: Path) -> list[str]:
    paths = {Path(line.split()[-1]).resolve() for line in text.splitlines()
             if line.strip() and Path(line.split()[-1]).is_absolute()}
    if any(path.is_relative_to(sdk) for path in paths):
        raise ValueError('Link-only GNU SDK loaded at runtime')
    selected = [path for path in paths if path.name.startswith(('libharfbuzz', 'libmd4c'))]
    if not all(any(path.name.startswith(name) for path in selected) for name in ['libharfbuzz', 'libmd4c']):
        raise ValueError('Both actual provider libraries must load')
    if any(not path.is_relative_to(prefix) for path in selected):
        raise ValueError('Foreign text-provider fallback')
    return sorted(map(str, selected))


def upstream_harfbuzz_results(text: str) -> dict:
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    if not rows or any(row['result'] not in {'OK', 'SKIP', 'EXPECTEDFAIL'} for row in rows):
        raise ValueError('HarfBuzz upstream failure/empty suite')
    for name in ['test-font', 'test-map', 'test-shape', 'test-ot-nullable-output']:
        if not any(name in row['name'] and row['result'] == 'OK' for row in rows):
            raise ValueError('Required actual HarfBuzz regression missing: ' + name)
    return {result: sum(row['result'] == result for row in rows) for result in ['OK', 'SKIP', 'EXPECTEDFAIL']}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert sys.platform == 'linux' and platform.machine() == 'x86_64'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '22.04'
    assert platform.python_version() == '3.14.10' and sys.version_info.releaselevel == 'final'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED') and version('pip') == '26.3'
    work, output = args.work_root.resolve(), args.output_dir.resolve()
    assert not work.exists(), 'Fresh bounded source workspace required'
    work.mkdir(parents=True)
    output.mkdir(parents=True, exist_ok=True)
    spec_path = REPO / '.github/scripts/qt_text_provider_sources.json'
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    shutil.copy2(spec_path, output)
    report = {'source_sha': head, 'scope': spec['scope'], 'limits': spec['limits'], 'result': 'BLOCKED'}

    def run(command: list, name: str, *, cwd: Path = work, env: dict | None = None) -> str:
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
        (output / name).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            print((result.stdout + result.stderr)[-14000:], flush=True)
        result.check_returncode()
        return result.stdout

    try:
        # These cheap gates run before downloading/extracting any vendor source.
        report['gate'] = 'native compiler, GLib test driver, link SDK and bootstrap tools'
        for tool in ['gcc', 'g++', 'pkg-config', 'readelf']:
            run([tool, '--version'], tool.replace('+', 'x') + '-version.txt')
        assert run(['gcc', '-dumpmachine'], 'compiler-target.txt').strip() == 'x86_64-linux-gnu'
        report['glib_os_test_driver'] = run(['pkg-config', '--modversion', 'glib-2.0'], 'glib-version.txt').strip()
        sdk = json.loads((output / 'cxx-sdk-qualified.json').read_text())
        assert sdk['source_sha'] == head and sdk['compatible'] and not sdk['runtime_sdk_loaded']
        assert '-L' + sdk['link_directory'] in os.environ['LDFLAGS'].split()
        for name in ['cmake', 'ninja']:
            assert version(name) == spec['versions'][name]
            run([name, '--version'], name + '-version.txt')
        report['gate'] = 'stable parent/provider recheck before vendor downloads'
        authorities = {
            'qt': 'https://pypi.org/pypi/PySide6-Essentials/json',
            'harfbuzz': 'https://api.github.com/repos/harfbuzz/harfbuzz/releases/latest',
            'md4c': 'https://api.github.com/repos/mity/md4c/tags?per_page=100',
        }
        metadata = {}
        for name, url in authorities.items():
            with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'PlayStoreAppAudit-component-preflight'}), timeout=45) as response:
                metadata[name] = json.load(response)
        actual = {'qt': metadata['qt']['info']['version'], 'harfbuzz': metadata['harfbuzz']['tag_name']}
        assert not metadata['harfbuzz']['prerelease'] and not metadata['harfbuzz']['draft']
        stable_tags = [tuple(map(int, match.groups())) for tag in metadata['md4c']
                       if (match := re.fullmatch(r'(?:v|release-)(\d+)\.(\d+)\.(\d+)', tag['name']))]
        actual['md4c'] = '.'.join(map(str, max(stable_tags)))
        assert all(actual[name] == spec['versions'][name] for name in authorities), actual
        report['stable_parent_provider_recheck'] = actual
        report['gate'] = 'original HTTPS/hash source and Meson inputs'
        sources, tree = output / 'sources', work / 'src'
        sources.mkdir()
        tree.mkdir()
        for item in [*spec['sources'], *spec['meson']]:
            path = checked_source(item, sources)
            if item['name'].endswith(('.tar.gz', '.tar.xz')):
                with tarfile.open(path) as archive:
                    archive.extractall(tree, filter='data')
        wheel = next(sources.glob('meson-*.whl'))
        run([sys.executable, '-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps', str(wheel)], 'meson-offline-install.log')
        assert version('meson') == spec['versions']['meson']
        run([sys.executable, '-m', 'mesonbuild.mesonmain', '--version'], 'meson-version.txt')
        hb, md, qt = [tree / item['directory'] for item in spec['sources']]
        for name, digest in spec['qt_wrapper_hashes'].items():
            assert hashlib.sha256((qt / name).read_bytes()).hexdigest() == digest
        legal = output / 'legal'
        for source in [hb, md, qt, tree / 'meson-1.12.1']:
            destination = legal / source.name
            destination.mkdir(parents=True)
            for path in source.iterdir():
                if path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')) or path.name == 'licenseRule.json':
                    if path.is_dir():
                        shutil.copytree(path, destination / path.name)
                    else:
                        shutil.copy2(path, destination / path.name)
        shutil.copy2(md / 'test/LICENSE.md', legal / 'md4c-0.6.0/test-LICENSE.md')
        prefix = work / 'prefix'
        meson = [sys.executable, '-m', 'mesonbuild.mesonmain']
        report['gate'] = 'primary Meson HarfBuzz and upstream API/shaping regressions'
        hb_build = work / 'harfbuzz-build'
        run([*meson, 'setup', hb_build, hb, '--prefix=' + str(prefix), '--libdir=lib', '--buildtype=release',
             '--wrap-mode=nofallback', '-Dauto_features=disabled', '-Dglib=enabled', '-Dtests=enabled',
             '-Dutilities=enabled', '-Dsubset=enabled', '-Draster=disabled', '-Dvector=disabled', '-Dgpu=disabled',
             '-Dbenchmark=disabled', '-Dexperimental_api=false', '-Db_ndebug=false'], 'harfbuzz-configure.log')
        run([*meson, 'compile', '-C', hb_build, '-j', '2'], 'harfbuzz-build.log')
        run([*meson, 'test', '-C', hb_build, '--no-rebuild', '--print-errorlogs', '--num-processes', '2'], 'harfbuzz-tests.log')
        shutil.copy2(hb_build / 'meson-logs/testlog.json', output / 'harfbuzz-testlog.json')
        report['harfbuzz_upstream'] = upstream_harfbuzz_results((output / 'harfbuzz-testlog.json').read_text())
        run([*meson, 'install', '-C', hb_build, '--no-rebuild'], 'harfbuzz-install.log')
        report['gate'] = 'official MD4C CMake build and unmodified CommonMark/regression suites'
        md_build = work / 'md4c-build'
        run(['cmake', '-S', md, '-B', md_build, '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
             '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_INSTALL_LIBDIR=lib', '-DBUILD_SHARED_LIBS=ON'], 'md4c-configure.log')
        run(['cmake', '--build', md_build, '--parallel', '2'], 'md4c-build.log')
        run(['cmake', '--install', md_build], 'md4c-install.log')
        report['md4c_upstream'] = {}
        for suite in ['spec', 'regressions']:
            text = run([sys.executable, md / 'test/run-testsuite.py', '--program', prefix / 'bin/md2html',
                        '--spec', md / ('test/' + suite + '.txt')], 'md4c-' + suite + '.log',
                       env={**os.environ, 'LD_LIBRARY_PATH': str(prefix / 'lib')})
            counts = re.search(r'(\d+) passed, (\d+) failed, (\d+) errored, (\d+) skipped', text)
            assert counts and int(counts[1]) > 0 and all(int(counts[n]) == 0 for n in [2, 3, 4]), text
            report['md4c_upstream'][suite] = int(counts[1])
        report['gate'] = 'original Qt system wrappers and actual native text consumer'
        # Qt's wrapper also supports pkg-config (including newer HarfBuzz majors).
        # The supported private prefix must participate in both discovery routes.
        os.environ['PKG_CONFIG_PATH'] = str(prefix / 'lib/pkgconfig') + os.pathsep + os.environ.get('PKG_CONFIG_PATH', '')
        for name in ['harfbuzz', 'md4c']:
            assert run(['pkg-config', '--modversion', name], name + '-pkgconfig-version.txt').strip() == spec['versions'][name]
        consumer = work / 'consumer'
        consumer.mkdir()
        shutil.copy2(REPO / '.github/scripts/qt_text_consumer.cpp', consumer)
        shutil.copy2(consumer / 'qt_text_consumer.cpp', output)
        (consumer / 'CMakeLists.txt').write_text('''cmake_minimum_required(VERSION 3.21)
project(ControlledTextProviders LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
find_package(harfbuzz CONFIG REQUIRED PATHS "${PRIVATE_PREFIX}" NO_DEFAULT_PATH)
find_package(md4c CONFIG REQUIRED PATHS "${PRIVATE_PREFIX}" NO_DEFAULT_PATH)
list(PREPEND CMAKE_MODULE_PATH "${QT_SOURCE}/cmake")
find_package(WrapSystemHarfbuzz 2.6.0 REQUIRED)
find_package(WrapSystemMd4c REQUIRED)
add_executable(qt_text_consumer qt_text_consumer.cpp)
target_link_libraries(qt_text_consumer PRIVATE WrapSystemHarfbuzz::WrapSystemHarfbuzz WrapSystemMd4c::WrapSystemMd4c)
set_target_properties(qt_text_consumer PROPERTIES BUILD_RPATH "${PRIVATE_PREFIX}/lib")
file(GENERATE OUTPUT "${CMAKE_BINARY_DIR}/selected-libraries.txt" CONTENT "$<TARGET_FILE:harfbuzz::harfbuzz>\\n$<TARGET_FILE:md4c::md4c>\\n")
''', encoding='utf-8')
        build = work / 'consumer-build'
        run(['cmake', '-S', consumer, '-B', build, '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
             '-DPRIVATE_PREFIX=' + str(prefix), '-DQT_SOURCE=' + str(qt),
             '-DCMAKE_PREFIX_PATH=' + str(prefix),
             '-DCMAKE_FIND_USE_PACKAGE_REGISTRY=OFF', '-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY=OFF'], 'qt-wrapper-configure.log')
        run(['cmake', '--build', build, '--parallel', '2'], 'qt-wrapper-build.log')
        selections = (build / 'selected-libraries.txt').read_text().splitlines()
        assert len(selections) == 2 and all(Path(name).resolve().is_relative_to(prefix) for name in selections)
        fonts = []
        for name, digest in spec['fonts'].items():
            font = hb / 'test/api/fonts' / name
            assert hashlib.sha256(font.read_bytes()).hexdigest() == digest
            shutil.copy2(font, output)
            fonts.append(font)
        maps = run([build / 'qt_text_consumer', *fonts], 'consumer-execution.log')
        assert maps.startswith('PASS HarfBuzz15.1.0 OpenType')
        report['loaded_providers'] = validate_loaded_paths(maps, prefix, Path(sdk['sdk_root']))
        report['elf_images'] = []
        binaries = output / 'native-binaries'
        binaries.mkdir()
        for image in [build / 'qt_text_consumer', *map(Path, selections)]:
            image = image.resolve()
            versions = required_versions(readelf(image, '--version-info'))
            abi = validate_abi(readelf(image, '--file-header'), versions)
            data = image.read_bytes()
            shutil.copy2(image, binaries / image.name)
            report['elf_images'].append({'name': image.name, 'sha256': hashlib.sha256(data).hexdigest(), 'abi': abi,
                                         'dynamic': readelf(image, '--dynamic')})
        for name, path in [('consumer-CMakeLists.txt', consumer / 'CMakeLists.txt'), ('consumer-CMakeCache.txt', build / 'CMakeCache.txt')]:
            shutil.copy2(path, output / name)
        report['result'] = 'PASS native text-provider prerequisite; actual rebuilt Qt/PySide/GUI remains REQUIRED'
    finally:
        (output / 'qt-text-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
