"""Apply the opt-in source-build routing for qualified Windows providers."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from provision_nuitka_scons import apply_source_patch

REPO = Path(__file__).resolve().parents[2]


def apply(source: Path, evidence: Path) -> dict:
    spec_path = REPO / '.github/scripts/windows_cpython_provider_config_sources.json'
    spec = json.loads(spec_path.read_text())
    evidence.mkdir(parents=True, exist_ok=True)
    for name, expected in spec['patch']['files'].items():
        path = source / name
        raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected['original_sha256'], name
        original = evidence / 'original-windows-build-config' / name
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(raw)
        normalized = raw.replace(b'\r\n', b'\n')
        assert hashlib.sha256(normalized).hexdigest() == expected['base_sha256']
        path.write_bytes(normalized)
    apply_source_patch(source, spec['patch'])
    for name in spec['patch']['files']:
        ET.fromstring((source / name).read_bytes())
    shutil.copy2(REPO / spec['patch']['path'], evidence)
    shutil.copy2(spec_path, evidence)
    result = {'identity': 'Project-controlled opt-in PCbuild configuration; unchanged CPython C sources',
              'contract': spec, 'scope': 'Patch/XML/source guards only; no native build, producer or package acceptance'}
    (evidence / 'windows-cpython-provider-config.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    apply(args.source.resolve(), args.evidence.resolve())
    print('PASS guarded opt-in PCbuild source configuration only; native qualification pending')


if __name__ == '__main__':
    main()
