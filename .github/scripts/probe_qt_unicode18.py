"""Run Qt's documented Unicode generator against stable 18 data and retained QtCore.

This is a generator prerequisite, never runtime/table adoption or conformance acceptance.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact
from probe_qt_http_limits import COMPILED_ARTIFACT, verified_sdk
from probe_qt_text_providers import checked_source

REPO = Path(__file__).resolve().parents[2]
DATA = [
    {'name': 'UCD18.zip', 'url': 'https://www.unicode.org/Public/18.0.0/ucd/UCD.zip',
     'sha256': '7b3e555514060b92290d154f53655c5eb0fa62b16eb04c03434ff72d1a66a0d8'},
    {'name': 'IdnaMappingTable.txt', 'url': 'https://www.unicode.org/Public/18.0.0/idna/IdnaMappingTable.txt',
     'sha256': 'a03b1eb38032268c696406a83f0972d6a815acd2c8d4151d42ec0fda70ffced1'},
]


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
    candidate = work / 'candidate'
    with zipfile.ZipFile(io.BytesIO(raw)) as original:
        base = json.loads(original.read('native_runtime_pilot_sources.json'))
        item = next(item for item in base['sources'] if item['name'].startswith('qtbase-'))
        qt_source = item
        data = original.read('sources/' + item['name'])
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            for member in archive:
                relative = member.name.split('/', 1)[-1]
                if not member.isfile() or not (relative.startswith('util/unicode/') or
                                               relative == 'src/corelib/text/qchar.h'):
                    continue
                path = candidate / relative
                assert path.resolve().is_relative_to(candidate)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.extractfile(member).read())
    sources = output / 'unicode18-sources'
    sources.mkdir()
    for item in DATA:
        checked_source(item, sources)
    tool = candidate / 'util/unicode'
    with zipfile.ZipFile(sources / 'UCD18.zip') as ucd:
        assert '18.0.0' in ucd.read('ReadMe.txt').decode()
        for path in (tool / 'data').glob('*.txt'):
            if path.name.startswith('ReadMe'):
                continue
            if path.name == 'IdnaMappingTable.txt':
                shutil.copy2(sources / path.name, path)
                continue
            matches = [name for name in ucd.namelist() if Path(name).name == path.name]
            assert len(matches) == 1, path.name
            path.write_bytes(ucd.read(matches[0]))
    header = candidate / 'src/corelib/text/qchar.h'
    main_cpp = tool / 'main.cpp'
    originals = {path: path.read_text(encoding='utf-8') for path in (header, main_cpp)}
    changed = originals[header].replace('        ScriptCount',
        '        // Project Unicode 18 generator candidate; append to preserve values.\n'
        '        Script_Jurchen,\n        Script_ProtoCuneiform,\n        Script_Seal,\n\n        ScriptCount')
    changed = changed.replace('        Unicode_17_0,', '        Unicode_17_0,\n        Unicode_18_0,')
    assert changed != originals[header]
    header.write_text(changed, encoding='utf-8')
    changed = originals[main_cpp].replace('#define DATA_VERSION_S "17.0"', '#define DATA_VERSION_S "18.0"')
    changed = changed.replace('#define DATA_VERSION_STR "QChar::Unicode_17_0"', '#define DATA_VERSION_STR "QChar::Unicode_18_0"')
    changed = changed.replace('        { QChar::Unicode_17_0,',
                              '        { QChar::Unicode_18_0,   "18.0" },\n        { QChar::Unicode_17_0,')
    changed = changed.replace('        // unhandled\n',
        '        { QChar::Script_Jurchen, "Jurchen" },\n'
        '        { QChar::Script_ProtoCuneiform, "Proto_Cuneiform" },\n'
        '        { QChar::Script_Seal, "Seal" },\n\n        // unhandled\n')
    main_cpp.write_text(changed, encoding='utf-8')
    patch = ''.join(''.join(difflib.unified_diff(old.splitlines(True), path.read_text(encoding='utf-8').splitlines(True),
                    fromfile='a/' + path.relative_to(candidate).as_posix(),
                    tofile='b/' + path.relative_to(candidate).as_posix())) for path, old in originals.items())
    (output / 'unicode18-generator-candidate.patch').write_text(patch, encoding='utf-8')
    (tool / 'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\n'
        'project(Unicode18Prerequisite LANGUAGES CXX)\n'
        'find_package(Qt6 6.12.0 EXACT REQUIRED COMPONENTS Core CorePrivate)\n'
        'add_executable(unicode main.cpp)\ntarget_link_libraries(unicode PRIVATE Qt6::Core Qt6::CorePrivate)\n'
        'target_compile_features(unicode PRIVATE cxx_std_17)\n'
        f'target_compile_options(unicode PRIVATE -include "{header.as_posix()}")\n', encoding='utf-8')
    env = {**os.environ, 'LD_LIBRARY_PATH': f'{prefix}/qt/lib:{prefix}/lib'}
    for command, label in [(['cmake', '-S', tool, '-B', work / 'out', '-GNinja',
                            '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_PREFIX_PATH=' + str(prefix / 'qt')], 'configure'),
                           (['cmake', '--build', work / 'out', '--parallel', '2'], 'build'),
                           ([work / 'out/unicode'], 'generate')]:
        result = subprocess.run(list(map(str, command)), cwd=tool, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / ('unicode18-' + label + '.log')).write_text(result.stdout, encoding='utf-8')
        print(label, result.returncode, result.stdout[-5000:], flush=True)
        result.check_returncode()
    generated = candidate / 'src/corelib/text'
    results = {}
    for path in generated.glob('qunicodetables*'):
        shutil.copy2(path, output)
        results[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert {'qunicodetables.cpp', 'qunicodetables_p.h'} <= results.keys()
    (output / 'unicode18-prerequisite.json').write_text(json.dumps({
        'source_sha': head, 'original_sdk': metadata, 'qt_original_sha256': qt_source['sha256'],
        'stable_data': DATA, 'generated': results,
        'candidate_patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
        'result': 'PASS generator prerequisite only; runtime, HarfBuzz maps, conformance and six-target adoption remain required',
    }, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
