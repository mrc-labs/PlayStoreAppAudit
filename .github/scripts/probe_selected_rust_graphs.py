"""Resolve only the current selected Rust integrations, excluding dev edges."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tomllib
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



def maintained_paste(root: Path, output: Path) -> dict:
    path = REPO / '.github/scripts/ruff_maintained_paste_sources.json'
    spec = json.loads(path.read_text())
    shutil.copy2(path, output)
    # The original checked parent lock supplies the original crate checksum.
    original = tomllib.loads((root / 'Cargo.lock').read_text())
    package = next(p for p in original['package'] if p['name'] == 'libcst')
    assert package['version'] == '1.9.0' and package['checksum'] == spec['libcst']['sha256']
    vendor = root / 'psaa-vendor'
    vendor.mkdir()
    for key in ['libcst', 'pastey']:
        item = spec[key]
        with urllib.request.urlopen(item['url'], timeout=90) as response:
            assert response.geturl().startswith('https:')
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == item['sha256']
        archive = output / 'sources' / item['name']
        archive.write_bytes(data)
        with tarfile.open(archive) as bundle:
            bundle.extractall(vendor, filter='data')
    manifest = vendor / 'libcst-1.9.0/Cargo.toml'
    original_manifest = manifest.read_bytes()
    assert hashlib.sha256(original_manifest).hexdigest() == spec['libcst']['manifest_original_sha256']
    new = original_manifest.replace(b'[dependencies.paste]\nversion = "1.0.15"',
                                    b'[dependencies.paste]\nversion = "=0.2.3"\npackage = "pastey"')
    assert hashlib.sha256(new).hexdigest() == spec['libcst']['manifest_patched_sha256']
    manifest.write_bytes(new)
    parent = root / 'Cargo.toml'
    before = parent.read_bytes()
    assert 'patch' not in tomllib.loads(before.decode())
    after = before + b'\n[patch.crates-io]\nlibcst = { path = "psaa-vendor/libcst-1.9.0" }\n'
    parent.write_bytes(after)
    patch = ''.join(difflib.unified_diff(original_manifest.decode().splitlines(True), new.decode().splitlines(True),
                                        'a/libcst/Cargo.toml', 'b/libcst/Cargo.toml'))
    patch += ''.join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
                                         'a/ruff/Cargo.toml', 'b/ruff/Cargo.toml'))
    (output / 'maintained-paste.patch').write_text(patch, encoding='utf-8')
    return {'source': spec, 'parent_original_sha256': hashlib.sha256(before).hexdigest(),
            'parent_patched_sha256': hashlib.sha256(after).hexdigest(),
            'scope': 'Source configuration candidate; actual supported native consumer qualification required before adoption'}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--update-compatible', action='store_true', help='Resolve candidate versions within unchanged upstream manifests; never install them')
    parser.add_argument('--check-candidate', action='store_true', help='Compile-check candidate APIs on this native host only; no binary adoption')
    parser.add_argument('--check-package', choices=['ruff', 'cryptography-rust'], help='Repeat only this affected native API check')
    parser.add_argument('--maintained-paste', action='store_true', help='Qualify the minimal maintained macro dependency configuration for Ruff only')
    parser.add_argument('--only-package', choices=['ruff', 'cryptography-rust'])
    args = parser.parse_args()
    if args.maintained_paste and (not args.update_compatible or args.only_package != 'ruff'):
        parser.error('--maintained-paste requires --update-compatible --only-package ruff')
    if args.check_package and not args.check_candidate:
        parser.error('--check-package requires --check-candidate')
    if args.check_candidate and not args.update_compatible:
        parser.error('--check-candidate requires --update-compatible')
    assert not args.work.exists()
    args.work.mkdir(parents=True)
    (args.output / 'sources').mkdir(parents=True)
    spec_path = REPO / '.github/scripts/selected_rust_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, args.output)
    results = []
    adaptation = None
    selected_sources = [item for item in spec['sources'] if not args.only_package or item['package'] == args.only_package]
    for item in selected_sources:
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
        if args.maintained_paste:
            adaptation = maintained_paste(root, args.output)
        lock = root / 'Cargo.lock'
        original_lock = lock.read_bytes()
        if args.update_compatible:
            candidate = subprocess.run(['cargo', 'update', '--package', item['package'], '--recursive'],
                                       cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=600)
            (args.output / (item['package'] + '-update.log')).write_text(candidate.stdout + candidate.stderr, encoding='utf-8')
            if candidate.returncode:
                print(candidate.stderr[-3000:], flush=True)
                candidate.check_returncode()
            (args.output / (item['package'] + '-original.Cargo.lock')).write_bytes(original_lock)
            (args.output / (item['package'] + '-candidate.Cargo.lock')).write_bytes(lock.read_bytes())
            patch = ''.join(difflib.unified_diff(original_lock.decode().splitlines(True),
                                                lock.read_text().splitlines(True), 'a/Cargo.lock', 'b/Cargo.lock'))
            (args.output / (item['package'] + '-lock.patch')).write_text(patch, encoding='utf-8')
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
            if args.maintained_paste:
                assert not any(p['name'] == 'paste' for p in packages)
                assert {'name': 'pastey', 'version': '0.2.3'} in packages
                assert 'psaa-vendor/libcst-1.9.0' in result.stdout.replace('\\', '/')
            results.append({'package': item['package'], 'target': target,
                            'source_sha256': item['sha256'], 'lock_sha256': digest,
                            'selected': packages, 'edges': 'normal,build; dev excluded'})
            print(label, len(packages), 'selected normal/build packages', flush=True)
        if args.check_candidate and (not args.check_package or item['package'] == args.check_package):
            environment = {**os.environ, 'CARGO_BUILD_JOBS': '2', 'PYO3_PYTHON': __import__('sys').executable}
            command = ['cargo', 'check', '--locked', '--package', item['package']]
            checked = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                                     text=True, encoding='utf-8', timeout=1200)
            (args.output / (item['package'] + '-candidate-check.log')).write_text(
                checked.stdout + checked.stderr, encoding='utf-8')
            if checked.returncode:
                print(checked.stderr[-4000:], flush=True)
                checked.check_returncode()
            assert hashlib.sha256(lock.read_bytes()).hexdigest() == digest
            print(item['package'], 'PASS native candidate API compile check; not runtime/ABI/adoption acceptance', flush=True)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'scope': spec['scope'], 'graphs': results,
              'candidate_update_only': args.update_compatible, 'maintained_macro_candidate': adaptation, 'native_candidate_api_check': args.check_candidate, 'native_checked_packages': ([args.check_package] if args.check_package else [item['package'] for item in selected_sources]) if args.check_candidate else [],
              'check_scope': 'Native Ubuntu24.04 x64 compiler API only; OpenSSL host provider is used only for a crypto package check. No target ABI/runtime/provider/package acceptance or changed pins.',
              'result': 'PASS selected source graph' + (' and native API compile checks' if args.check_candidate else '') + '; candidate updates still require native regression/compatibility acceptance before adoption'}
    (args.output / 'selected-rust-graphs.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
