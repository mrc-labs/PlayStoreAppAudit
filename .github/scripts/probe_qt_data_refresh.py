"""Qualify only current Qt data/private-header consumers using a retained SDK."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from apply_qt_data_refresh import apply_refresh
from download_diagnostic_artifact import fetch_artifact
from probe_qt_http_limits import COMPILED_ARTIFACT, verified_sdk
from probe_qt_text_providers import checked_source
from verify_linux_x64_native_delta import elf_record

REPO = Path(__file__).resolve().parents[2]


def psl_fixtures(path: Path, target: Path) -> int:
    """Derive independent exact/exception/wildcard/section expectations from PSL text."""
    rules: dict[str, int] = {}
    section = 0
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('//'):
            if 'BEGIN ICANN DOMAINS' in line:
                section = 4
            elif 'BEGIN PRIVATE DOMAINS' in line:
                section = 8
            elif 'END ICANN DOMAINS' in line or 'END PRIVATE DOMAINS' in line:
                section = 0
            continue
        if not section:
            raise ValueError('PSL rule outside an explicit section')
        if line.startswith('!'):
            flags, line = section | 1, line[1:]
        elif line.startswith('*.'):
            flags, line = section | 2, line[2:]
        else:
            flags = section
        for name in {line, line.encode('idna').decode('ascii')}:
            if name in rules and rules[name] != flags:
                raise ValueError('Ambiguous PSL fixture: ' + name)
            rules[name] = flags
    target.write_bytes(''.join(str(value) + '\t' + name + '\n' for name, value in sorted(rules.items())).encode())
    return len(rules)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA']
    work, output = args.work_root.resolve(), args.output_dir.resolve()
    assert not work.exists()
    work.mkdir()
    metadata, raw = fetch_artifact(COMPILED_ARTIFACT)
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    sdk, receipt = verified_sdk(metadata, raw)
    with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
        archive.extractall(work, filter='data')
    prefix = work / 'prefix'
    for name, record in receipt['files'].items():
        path = prefix / name
        assert path.resolve().is_relative_to(prefix)
        if 'symlink' in record:
            assert path.is_symlink() and os.readlink(path) == record['symlink']
        else:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    source = work / 'qtbase'
    with zipfile.ZipFile(io.BytesIO(raw)) as original:
        base = json.loads(original.read('native_runtime_pilot_sources.json'))
        qt = next(item for item in base['sources'] if item['name'].startswith('qtbase-'))
        data = original.read('sources/' + qt['name'])
        assert hashlib.sha256(data).hexdigest() == qt['sha256']
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                name = member.name.split('/', 1)[-1]
                if not member.isfile() or not (name.startswith(('src/3rdparty/libpsl/', 'src/3rdparty/D3D12MemoryAllocator/'))
                     or name in {'src/corelib/global/qexpected_p.h', 'src/corelib/global/qt_attribution.json'}):
                    continue
                path = source / name
                assert path.resolve().is_relative_to(source)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
    spec = json.loads((REPO / '.github/scripts/qt_data_refresh_sources.json').read_text(encoding='utf-8'))
    archives = output / 'qt-data-sources'
    archives.mkdir()
    for item in spec['sources']:
        checked_source(item, archives)
    provenance = apply_refresh(source, archives, output)
    fixtures = output / 'psl-fixtures.txt'
    rules = psl_fixtures(archives / 'public_suffix_list.dat', fixtures)
    consumer = work / 'consumer'
    consumer.mkdir()
    for name in ['qt_expected_data_consumer.cpp', 'qt_psl_data_consumer.cpp']:
        shutil.copy2(REPO / '.github/scripts' / name, consumer)
        shutil.copy2(REPO / '.github/scripts' / name, output)
    (consumer / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\n'
        'project(QtDataPrerequisite LANGUAGES CXX)\n'
        'find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core CorePrivate)\n'
        'add_executable(expected qt_expected_data_consumer.cpp)\n'
        'add_executable(expected_no_exceptions qt_expected_data_consumer.cpp)\n'
        'foreach(target expected expected_no_exceptions)\n'
        '  target_link_libraries(${target} PRIVATE Qt6::Core Qt6::CorePrivate)\n'
        '  target_compile_features(${target} PRIVATE cxx_std_17)\n'
        f'  target_include_directories(${{target}} PRIVATE "{source}/src/corelib/global")\n'
        'endforeach()\n'
        'target_compile_definitions(expected_no_exceptions PRIVATE QT_NO_EXCEPTIONS)\n'
        'target_compile_options(expected_no_exceptions PRIVATE -fno-exceptions)\n'
        'add_executable(psl qt_psl_data_consumer.cpp)\n'
        'target_compile_features(psl PRIVATE cxx_std_17)\n'
        f'target_include_directories(psl PRIVATE "{source}/src/3rdparty/libpsl" "{source}/src/3rdparty/libpsl/src")\n',
        encoding='utf-8')
    env = {**os.environ, 'LD_LIBRARY_PATH': f'{prefix}/qt/lib:{prefix}/lib'}
    commands = [(['cmake', '-S', consumer, '-B', work / 'out', '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
                  '-DCMAKE_PREFIX_PATH=' + str(prefix / 'qt')], 'configure', 0),
                (['cmake', '--build', work / 'out', '--parallel', '2'], 'build', 0),
                ([work / 'out/psl', fixtures], 'psl-execute', 0),
                ([work / 'out/expected'], 'expected-execute', 0),
                ([work / 'out/expected_no_exceptions'], 'expected-no-exceptions', 0),
                ([work / 'out/expected_no_exceptions', '--bad-access'], 'expected-terminate', 86)]
    for command, label, expected in commands:
        result = subprocess.run(list(map(str, command)), env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / ('qt-data-' + label + '.log')).write_text(result.stdout, encoding='utf-8')
        print(label, result.returncode, result.stdout[-5000:], flush=True)
        if result.returncode != expected:
            raise RuntimeError('Qt data prerequisite failed: ' + label)
    images = [elf_record(work / 'out' / name, output) for name in ['psl', 'expected', 'expected_no_exceptions']]
    result = {'source_sha': head, 'original_sdk': metadata, 'qt_original_sha256': qt['sha256'],
              'source_provenance': provenance, 'psl_rules': rules, 'images': images,
              'expected': 'Value/error/map/and_then/move-only/void/exception PASS; no-exception bad access terminates with exact test handler86',
              'result': 'PASS changed source consumers only; no Qt/Python rebuild or final framework/package acceptance'}
    (output / 'qt-data-prerequisite.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
