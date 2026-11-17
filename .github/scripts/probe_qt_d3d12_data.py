"""Qualify stable D3D12MA with native MSVC/current existing SDK and dynamic CRT."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from inspect_pe import read_pe_machine
from probe_qt_text_providers import checked_source
from verify_windows_runtime_pilot import pe_versions, validate_imports

REPO = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    arch = os.environ['EXPECTED_ARCH']
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    assert os.environ['VSCMD_ARG_HOST_ARCH'].lower() == os.environ['VSCMD_ARG_TGT_ARCH'].lower() == arch
    assert os.environ['VCTOOLSVERSION'].rstrip('\\/').startswith('14.52.')
    compiler = shutil.which('cl')
    assert compiler and read_pe_machine(Path(compiler)) == machine
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    output = Path('toolchain-delta-evidence').resolve()
    sources = output / 'sources'
    sources.mkdir()
    manifest = REPO / '.github/scripts/qt_data_refresh_sources.json'
    spec = json.loads(manifest.read_text(encoding='utf-8'))
    item = next(item for item in spec['sources'] if item['name'].startswith('D3D12MemoryAllocator-'))
    archive = checked_source(item, sources)
    with tarfile.open(archive) as original:
        for name, selected in spec['d3d12_files'].items():
            data = original.extractfile(item['directory'] + '/' + selected['upstream']).read()
            assert hashlib.sha256(data).hexdigest() == selected['selected_sha256']
            (work / Path(name).name).write_bytes(data)
    shutil.copy2(work / 'LICENSE.txt', output / 'D3D12MA-LICENSE.txt')
    shutil.copy2(REPO / '.github/scripts/qt_d3d12_data_consumer.cpp', output)
    binary = work / 'd3d12-data-consumer.exe'
    commands = [([compiler, '/nologo', '/std:c++17', '/EHsc', '/MD', '/D_WIN32_WINNT=0x0A00', '/DWINVER=0x0A00',
                  '/I' + str(work), REPO / '.github/scripts/qt_d3d12_data_consumer.cpp', work / 'D3D12MemAlloc.cpp',
                  '/Fe:' + str(binary), '/link', 'd3d12.lib', 'dxgi.lib', 'dxguid.lib'], 'compile'),
                ([binary], 'execute'), (['dumpbin', '/nologo', '/dependents', binary], 'imports'),
                (['dumpbin', '/nologo', '/directives', work / 'D3D12MemAlloc.obj'], 'crt')]
    logs = {}
    for command, label in commands:
        result = subprocess.run(list(map(str, command)), cwd=work, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / ('d3d12-' + label + '.log')).write_text(result.stdout, encoding='utf-8')
        print(label, result.returncode, result.stdout[-5000:], flush=True)
        result.check_returncode()
        logs[label] = result.stdout
    assert read_pe_machine(binary) == machine
    validate_imports(logs['imports'])
    assert re.search(r'/DEFAULTLIB:"?MSVCRT', logs['crt'], re.I)
    assert not re.search(r'/DEFAULTLIB:"?LIBCMT', logs['crt'], re.I)
    versions = pe_versions(binary)
    assert all(value <= (10, 0) for value in versions.values())
    assert logs['execute'].startswith('PASS D3D12MA3.3 native virtual allocation/')
    shutil.copy2(binary, output)
    shutil.copy2(manifest, output)
    report = {'source_sha': head, 'source': item, 'machine': machine, 'compiler': compiler,
              'toolset': os.environ['VCTOOLSVERSION'], 'sdk': os.environ['WINDOWSSDKVERSION'],
              'consumer_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'pe_versions': versions,
              'crt': 'MD dynamic verified in native source object', 'imports': logs['imports'],
              'result': 'PASS native source/virtual allocation/alignment/free/PE/CRT; no GPU, preview Agility SDK or Qt/package adoption'}
    (output / 'd3d12-native-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
