"""Apply official Qt HTTP limits and execute their original native regression test."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]
TEST = 'tests/auto/network/access/qhttpnetworkreply/tst_qhttpnetworkreply.cpp'
HEADER_ROWS = {'empty', 'within-limit', 'within-limit-LFLF', 'at-limit',
               'over-limit-terminated', 'over-limit-unterminated', 'over-limit-unterminated-lines'}


def contract() -> dict:
    return json.loads((REPO / '.github/scripts/qt_http_security_sources.json').read_text(encoding='utf-8'))


def verify(source: Path, files: dict[str, str]) -> None:
    for name, digest in files.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Changed reviewed Qt HTTP source: ' + name)


def apply_limits(source: Path, evidence: Path) -> dict:
    spec = contract()
    # Check every original and both official patches before mutating vendor source.
    verify(source, spec['original_files'])
    for patch in spec['patches']:
        if hashlib.sha256((REPO / patch['path']).read_bytes()).hexdigest() != patch['sha256']:
            raise ValueError('Changed official Qt HTTP patch bytes')
    for patch in spec['patches']:
        apply_source_patch(source, patch)
    verify(source, spec['final_files'])
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / '.github/scripts/qt_http_security_sources.json', evidence)
    for patch in spec['patches']:
        shutil.copy2(REPO / patch['path'], evidence)
    for name in spec['final_files']:
        shutil.copy2(source / name, evidence / Path(name).name)
    result = {**spec, 'result': 'Official bytes/original/intermediate/post verified; native test pending'}
    (evidence / 'qt-http-patch-provenance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def executed_limits(path: Path) -> dict[str, int]:
    counts = dict.fromkeys(contract()['required_tests'], 0)
    executed = []
    for case in ET.parse(path).getroot().iter('testcase'):
        if any(case.find(tag) is not None for tag in ('failure', 'error')):
            raise ValueError('Original Qt HTTP regression failed')
        if case.find('skipped') is not None or case.get('status') == 'notrun':
            continue
        identity = case.get('name', '')
        name = identity.split('(', 1)[0]
        if name in counts:
            counts[name] += 1
            executed.append(identity.removesuffix('()'))
    expected = {'headerSizeLimit(' + row + ')' for row in HEADER_ROWS} | {'statusLineSizeLimit'}
    if set(executed) != expected or len(executed) != len(expected):
        raise ValueError('Original Qt HTTP limit cases did not all execute: ' + repr(counts))
    return counts


def test_limits(source: Path, prefix: Path, build: Path, evidence: Path) -> dict:
    spec = contract()
    verify(source, spec['final_files'])
    build.mkdir(parents=True, exist_ok=False)
    cmake = ('cmake_minimum_required(VERSION 3.22)\n'
             'project(QtHttpLimits LANGUAGES CXX)\n'
             'set(CMAKE_AUTOMOC ON)\n'
             'find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core CorePrivate Network NetworkPrivate Test)\n'
             f'add_executable(qt_http_limits "{(source / TEST).resolve().as_posix()}")\n'
             'target_link_libraries(qt_http_limits PRIVATE Qt6::CorePrivate Qt6::NetworkPrivate Qt6::Test)\n')
    (build / 'CMakeLists.txt').write_text(cmake, encoding='utf-8')
    evidence.mkdir(parents=True, exist_ok=True)
    commands = [
        ['cmake', '-S', str(build), '-B', str(build / 'out'), '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
         '-DCMAKE_PREFIX_PATH=' + str(prefix) + ';' + str(prefix.parent),
         '-DOPENSSL_ROOT_DIR=' + str(prefix.parent)],
        ['cmake', '--build', str(build / 'out'), '--parallel', '2'],
        [str(build / 'out/qt_http_limits'), '-o', str(evidence / 'qt-http-tests.xml') + ',junitxml',
         '-o', str(evidence / 'qt-http-tests.txt') + ',txt'],
    ]
    for number, command in enumerate(commands):
        with (evidence / f'qt-http-command-{number}.log').open('w', encoding='utf-8') as log:
            completed = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if completed.returncode:
            print('\n'.join((evidence / f'qt-http-command-{number}.log').read_text(encoding='utf-8', errors='replace').splitlines()[-80:]), flush=True)
        completed.check_returncode()
        if number == 0:
            cache = (build / 'out/CMakeCache.txt').read_text(encoding='utf-8')
            for component in ['Qt6', 'Qt6Core', 'Qt6CorePrivate', 'Qt6Network', 'Qt6NetworkPrivate', 'Qt6Test']:
                selected = next(line.split('=', 1)[1] for line in cache.splitlines()
                                if line.startswith(component + '_DIR:PATH='))
                if not Path(selected).resolve().is_relative_to(prefix.resolve()):
                    raise ValueError('Foreign Qt selected by HTTP regression: ' + selected)
    counts = executed_limits(evidence / 'qt-http-tests.xml')
    # This entry point is used only by the controlled Jammy x64 diagnostic.
    # Independently retain/inspect the test executable and actual Qt linkage.
    from verify_linux_x64_native_delta import elf_record

    binary = build / 'out/qt_http_limits'
    linkage = subprocess.check_output(['ldd', str(binary)], text=True)
    (evidence / 'qt-http-linkage.txt').write_text(linkage, encoding='utf-8')
    images = [elf_record(binary, evidence)]
    for stem in ['libQt6Core.so', 'libQt6Network.so', 'libQt6Test.so']:
        line = next(line for line in linkage.splitlines() if line.strip().startswith(stem))
        path = Path(line.split('=>', 1)[1].split()[0]).resolve()
        if not path.is_relative_to(prefix.resolve()):
            raise ValueError('Foreign Qt loaded by HTTP regression: ' + str(path))
        images.append(elf_record(path, evidence))
    result = {'cve': spec['cve'], 'executed': counts,
              'original_test_sha256': hashlib.sha256((source / TEST).read_bytes()).hexdigest(),
              'images': images,
              'result': 'Original upstream HTTP boundary/unterminated/cleared-fragment regressions PASS'}
    (evidence / 'qt-http-results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['apply', 'test'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--qt-prefix', type=Path)
    parser.add_argument('--build', type=Path)
    args = parser.parse_args()
    if args.mode == 'test':
        if not args.qt_prefix or not args.build:
            parser.error('test requires --qt-prefix and --build')
        result = test_limits(args.source.resolve(), args.qt_prefix.resolve(), args.build.resolve(), args.evidence.resolve())
    else:
        result = apply_limits(args.source.resolve(), args.evidence.resolve())
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
