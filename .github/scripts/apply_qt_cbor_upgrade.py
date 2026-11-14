"""Apply the selected TinyCBOR7.1 source update while preserving Qt-owned glue."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]


def apply_upgrade(source: Path, archive: Path, evidence: Path) -> dict:
    manifest = REPO / '.github/scripts/qt_cbor_provider_sources.json'
    spec = json.loads(manifest.read_text(encoding='utf-8'))
    if hashlib.sha256(archive.read_bytes()).hexdigest() != spec['source']['sha256']:
        raise ValueError('Changed original TinyCBOR7.1 archive')
    for name, digest in spec['qt_owned_unchanged'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Unexpected Qt-owned CBOR integration: ' + name)
    with tarfile.open(archive) as original:
        for name, digest in spec['upstream_selected_files'].items():
            data = original.extractfile(spec['source']['directory'] + '/' + name).read()
            if hashlib.sha256(data).hexdigest() != digest:
                raise ValueError('Changed selected upstream TinyCBOR file: ' + name)
    apply_source_patch(source, spec['patch'])
    for name, digest in spec['upstream_selected_files'].items():
        if hashlib.sha256((source / 'src/3rdparty/tinycbor' / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Qt selected copy differs from official TinyCBOR7.1: ' + name)
    for name, digest in spec['qt_owned_unchanged'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Qt-owned CBOR glue was modified: ' + name)
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, evidence)
    shutil.copy2(REPO / spec['patch']['path'], evidence)
    shutil.copytree(source / 'src/3rdparty/tinycbor', evidence / 'qt-tinycbor-selected')
    result = {**spec, 'identity': 'Project-modified Qt6.12.0 with selected TinyCBOR7.1 source',
              'result': 'Source/original/patch/post and unchanged Qt glue verified; native Qt tests still required'}
    (evidence / 'qt-cbor-patch-provenance.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply_upgrade(args.source, args.archive, args.evidence), indent=2), flush=True)


if __name__ == '__main__':
    main()
