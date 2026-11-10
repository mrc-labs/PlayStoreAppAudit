"""Apply the hash-bound Qt6.12 compromised-key guard to the isolated x64 pilot."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def apply_guard(source: Path, evidence: Path) -> dict:
    spec = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text())['qt_ca_patch']
    patch = REPO / spec['path']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError('Changed reviewed Qt CA patch')
    target = source / spec['file']
    if hashlib.sha256(target.read_bytes()).hexdigest() != spec['base_sha256']:
        raise ValueError('Unexpected original Qt certificate source')
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch.resolve())], cwd=source, check=True)
    if hashlib.sha256(target.read_bytes()).hexdigest() != spec['patched_sha256']:
        raise ValueError('Unexpected patched Qt certificate source')
    evidence.mkdir(parents=True, exist_ok=True)
    shutil.copy2(patch, evidence / patch.name)
    shutil.copy2(target, evidence / 'qsslcertificate-project.cpp')
    result = {**spec, 'identity': 'Project-modified Qt6.12.0; not an unchanged official Qt binary',
              'scope': 'Common certificate blacklist; no OS trust mutation or TLS bypass'}
    (evidence / 'qt-ca-patch-provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(apply_guard(args.source, args.evidence), indent=2), flush=True)


if __name__ == '__main__':
    main()
