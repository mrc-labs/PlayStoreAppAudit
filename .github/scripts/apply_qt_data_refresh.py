"""Apply the closed Qt expected/PSL/D3D12 source selections, preserving Qt glue."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]


def apply_refresh(source: Path, archives: Path, evidence: Path, *, windows: bool = False) -> dict:
    manifest = REPO / '.github/scripts/qt_data_refresh_sources.json'
    spec = json.loads(manifest.read_text(encoding='utf-8'))
    def digest(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    for item in spec['sources']:
        if digest(archives / item['name']) != item['sha256']:
            raise ValueError('Changed official Qt data source: ' + item['name'])
    for name, expected_hash in spec['qt_attribution_hashes'].items():
        if digest(source / name) != expected_hash:
            raise ValueError('Unexpected original Qt attribution: ' + name)
    lookup = spec['libpsl_lookup']
    if digest(source / lookup['file']) != lookup['sha256']:
        raise ValueError('Unexpected Qt/libpsl lookup implementation')
    generator = source / 'src/3rdparty/libpsl/src/psl-make-dafsa'
    data = source / 'src/3rdparty/libpsl/psl_data.cpp'
    if (digest(generator) != spec['psl_generator']['qt_original_generator_sha256'] or
            digest(data) != spec['psl_generator']['qt_original_data_sha256']):
        raise ValueError('Unexpected original Qt PSL input')
    if windows:
        for name, item in spec['d3d12_files'].items():
            if digest(source / name) != item['base_sha256']:
                raise ValueError('Unexpected Qt D3D12 source: ' + name)
    evidence.mkdir(parents=True, exist_ok=True)
    legal = evidence / 'legal/qt-data-refresh'
    for name in ['expected-1.3.1.tar.gz', 'libpsl-0.23.3.tar.gz', 'D3D12MemoryAllocator-3.3.0.tar.gz']:
        item = next(item for item in spec['sources'] if item['name'] == name)
        with tarfile.open(archives / name) as original:
            for member in original:
                relative = member.name.split('/', 1)[-1]
                if (member.isfile() and (Path(relative).name.upper().startswith(('COPYING', 'LICENSE', 'LICENCE'))
                                       or relative == 'include/tl/expected.hpp')):
                    target = legal / item['directory'] / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(original.extractfile(member).read())
    with tarfile.open(archives / 'expected-1.3.1.tar.gz') as original:
        header = original.extractfile('expected-1.3.1/include/tl/expected.hpp').read()
        if hashlib.sha256(header).hexdigest() != spec['expected_patch']['upstream_current_header_sha256']:
            raise ValueError('Changed upstream expected header')
    apply_source_patch(source, spec['expected_patch'])
    with tarfile.open(archives / 'libpsl-0.23.3.tar.gz') as original:
        current = original.extractfile('libpsl-0.23.3/src/lookup_string_in_fixed_set.c').read()
        if current != (source / lookup['file']).read_bytes():
            raise ValueError('Qt lookup differs from current supported libpsl')
        current = original.extractfile('libpsl-0.23.3/src/psl-make-dafsa').read()
    if hashlib.sha256(current).hexdigest() != spec['psl_generator']['original_sha256']:
        raise ValueError('Changed original PSL generator')
    old = b"text += b'static const unsigned char kDafsa['"
    if current.count(old) != 1:
        raise ValueError('Unexpected Qt constexpr generation interface')
    current = current.replace(old, b"text += b'static constexpr unsigned char kDafsa['")
    if hashlib.sha256(current).hexdigest() != spec['psl_generator']['patched_sha256']:
        raise ValueError('Changed Qt PSL generator adaptation')
    generator.write_bytes(current)
    subprocess.run([sys.executable, str(generator), str(archives / 'public_suffix_list.dat'), str(data)], check=True)
    if digest(data) != spec['psl_generator']['generated_sha256']:
        raise ValueError('Non-reproducible Qt PSL generation')
    if windows:
        with tarfile.open(archives / 'D3D12MemoryAllocator-3.3.0.tar.gz') as original:
            for name, item in spec['d3d12_files'].items():
                current = original.extractfile('D3D12MemoryAllocator-3.3.0/' + item['upstream']).read()
                if hashlib.sha256(current).hexdigest() != item['selected_sha256']:
                    raise ValueError('Changed current D3D12 source: ' + name)
                (source / name).write_bytes(current)
    # Attribution describes the controlled selections, not an unchanged upstream Qt.
    expected = source / 'src/corelib/global/qt_attribution.json'
    item = json.loads(expected.read_text(encoding='utf-8'))
    item.update(Version='1.3.1', DownloadLocation='https://github.com/TartanLlama/expected/tree/v1.3.1',
                Comment='Project-adapted stable1.3.1 changes; Qt namespace/configuration preserved')
    expected.write_text(json.dumps(item, indent=2) + '\n', encoding='utf-8')
    attribution = source / 'src/3rdparty/libpsl/qt_attribution.json'
    items = json.loads(attribution.read_text(encoding='utf-8'), strict=False)
    for item in items:
        if item['Id'] == 'psl-data':
            item.update(Version=spec['versions']['psl'], PURL='pkg:generic/psl-data@71c235dd3f888dd4ecd066817050a7482da710e5')
        elif item['Id'] == 'libpsl':
            item.update(Version='0.23.3', Comment='Current byte-identical lookup; stable generator with Qt constexpr output')
    attribution.write_text(json.dumps(items, indent=2) + '\n', encoding='utf-8')
    if windows:
        attribution = source / 'src/3rdparty/D3D12MemoryAllocator/qt_attribution.json'
        items = json.loads(attribution.read_text(encoding='utf-8'), strict=False)
        for item in items:
            item['Version'] = 'v3.3.0'
        attribution.write_text(json.dumps(items, indent=2) + '\n', encoding='utf-8')
    shutil.copy2(manifest, evidence)
    shutil.copy2(REPO / spec['expected_patch']['path'], evidence)
    selected = ['src/corelib/global/qexpected_p.h', 'src/corelib/global/qt_attribution.json',
                lookup['file'], 'src/3rdparty/libpsl/src/psl-make-dafsa',
                'src/3rdparty/libpsl/psl_data.cpp', 'src/3rdparty/libpsl/qt_attribution.json']
    if windows:
        selected.extend([*spec['d3d12_files'], 'src/3rdparty/D3D12MemoryAllocator/qt_attribution.json'])
    selected_hashes = {}
    for name in selected:
        target = evidence / 'qt-data-selected' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
        selected_hashes[name] = digest(target)
    result = {'source_sha': os.environ.get('GITHUB_SHA'), 'selections': spec,
              'windows_d3d12_selected': windows,
              'selected_hashes': selected_hashes,
              'result': 'Source/patch/PSL generation verified; native consumers/framework/package acceptance still required'}
    (evidence / 'qt-data-source-provenance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--archives', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--windows', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_refresh(args.source, args.archives, args.evidence, windows=args.windows), indent=2))


if __name__ == '__main__':
    main()
