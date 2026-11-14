"""Resolve only the current selected Rust integrations, excluding dev edges."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def selected_packages(tree: str) -> list[dict[str, str]]:
    selected = set()
    for line in tree.splitlines():
        match = re.match(r'^(\S+) v([^\s]+)(?:\s|$)', line)
        if match:
            selected.add(match.groups())
    if not selected:
        raise ValueError('Empty selected Rust dependency graph')
    return [{'name': name, 'version': version} for name, version in sorted(selected)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.work.exists()
    args.work.mkdir(parents=True)
    (args.output / 'sources').mkdir(parents=True)
    spec_path = REPO / '.github/scripts/selected_rust_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, args.output)
    results = []
    for item in spec['sources']:
        with urllib.request.urlopen(item['authority'], timeout=90) as response:
            metadata = json.load(response)
        source = next(row for row in metadata['urls'] if row['packagetype'] == 'sdist')
        assert source['filename'] == item['name'] and source['digests']['sha256'] == item['sha256']
        with urllib.request.urlopen(source['url'], timeout=120) as response:
            raw = response.read()
        assert hashlib.sha256(raw).hexdigest() == item['sha256']
        archive_path = args.output / 'sources' / item['name']
        archive_path.write_bytes(raw)
        with tarfile.open(archive_path) as archive:
            archive.extractall(args.work, filter='data')
        root = args.work / item['name'].removesuffix('.tar.gz')
        if completion := item.get('workspace_completion'):
            originals = {name: (root / name).read_bytes() for name in ['Cargo.toml', 'Cargo.lock']}
            assert hashlib.sha256(originals['Cargo.lock']).hexdigest() == completion['cargo_lock_sha256']
            assert hashlib.sha256(originals['Cargo.toml']).hexdigest() == completion['cargo_manifest_sha256']
            with urllib.request.urlopen(completion['url'], timeout=120) as response:
                assert response.geturl().startswith('https:')
                full = response.read()
            assert hashlib.sha256(full).hexdigest() == completion['sha256']
            complete_path = args.output / 'sources' / (item['name'].removesuffix('.tar.gz') + '-upstream.tar.gz')
            complete_path.write_bytes(full)
            with tarfile.open(complete_path) as archive:
                for name, original in originals.items():
                    assert archive.extractfile(root.name + '/' + name).read() == original
                archive.extractall(args.work, filter='data')
        lock = root / 'Cargo.lock'
        digest = hashlib.sha256(lock.read_bytes()).hexdigest()
        for target in spec['targets']:
            command = ['cargo', 'tree', '--locked', '--package', item['package'], '--target', target,
                       '--edges', 'normal,build', '--prefix', 'none', '--format', '{p}']
            result = subprocess.run(command, cwd=root, text=True, encoding='utf-8',
                                    capture_output=True, timeout=600)
            label = item['package'] + '-' + target
            (args.output / (label + '.txt')).write_text(result.stdout, encoding='utf-8')
            (args.output / (label + '-cargo.log')).write_text(result.stderr, encoding='utf-8')
            if result.returncode:
                print(result.stderr[-3000:], flush=True)
                result.check_returncode()
            assert hashlib.sha256(lock.read_bytes()).hexdigest() == digest, 'Locked graph changed'
            packages = selected_packages(result.stdout)
            results.append({'package': item['package'], 'target': target,
                            'source_sha256': item['sha256'], 'lock_sha256': digest,
                            'selected': packages, 'edges': 'normal,build; dev excluded'})
            print(label, len(packages), 'selected normal/build packages', flush=True)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'scope': spec['scope'], 'graphs': results,
              'result': 'PASS locked selection only; selected component freshness/advisory decisions remain separate'}
    (args.output / 'selected-rust-graphs.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
