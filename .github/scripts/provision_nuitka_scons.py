"""Build one labelled Nuitka4.3.5/SCons4.11.1 source integration for diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def verify_files(source: Path, patch: dict, field: str) -> None:
    for name, hashes in patch['files'].items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != hashes[field]:
            raise ValueError(f'Unexpected source/patch bytes: {name} ({field})')


def apply_source_patch(source: Path, patch: dict) -> None:
    path = REPO / patch['path']
    if hashlib.sha256(path.read_bytes()).hexdigest() != patch['sha256']:
        raise ValueError('Unexpected reviewed patch digest')
    verify_files(source, patch, 'base_sha256')
    environment = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(source.parent.resolve())}
    command = ['git', '-c', 'core.autocrlf=false', '-c', 'core.eol=lf', 'apply']
    subprocess.run([*command, '--check', str(path)], cwd=source, env=environment, check=True)
    subprocess.run([*command, str(path)], cwd=source, env=environment, check=True)
    verify_files(source, patch, 'patched_sha256')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', required=True, type=Path)
    parser.add_argument('--evidence-dir', required=True, type=Path)
    args = parser.parse_args()
    work, evidence = args.work_root.resolve(), args.evidence_dir.resolve()
    assert not work.exists(), 'Fresh source workspace required'
    work.mkdir(parents=True)
    sources = evidence / 'compiler-sources'
    sources.mkdir(parents=True, exist_ok=True)
    manifest_path = REPO / '.github/scripts/nuitka_scons_sources.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['distribution_version'] == '4.3.5+psaa.scons4111'
    for item in manifest['sources']:
        archive = sources / item['name']
        with urllib.request.urlopen(item['url'], timeout=120) as response, archive.open('wb') as target:
            shutil.copyfileobj(response, target)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('Unexpected official source digest: ' + item['name'])
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
    nuitka, scons = [work / item['directory'] for item in manifest['sources']]
    apply_source_patch(scons, manifest['scons_patch'])
    apply_source_patch(nuitka, manifest['nuitka_patch'])
    inline = nuitka / 'nuitka/build/inline_copy/lib/scons-4.11.1'
    assert not inline.exists()
    inline.mkdir()
    shutil.copytree(scons / 'SCons', inline / 'SCons')
    for path in scons.iterdir():
        if path.is_file() and path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
            shutil.copy2(path, inline / path.name)
    source_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    source_dirty = bool(subprocess.check_output(['git', 'status', '--porcelain', '--', '.github'], cwd=REPO, text=True).strip())
    marker = {'identity': 'project-modified stable-source compiler; not unchanged official Nuitka',
              'source_sha': source_sha, 'source_dirty': source_dirty,
              'manifest_canonical_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
              'distribution_version': manifest['distribution_version'],
              'scons': manifest['scons'], 'manifest': manifest,
              'limits': 'Diagnostic source tool integration; native/package acceptance recorded separately'}
    (nuitka / 'nuitka/PROJECT_MODIFIED_TOOLCHAIN.json').write_text(json.dumps(marker, indent=2), encoding='utf-8')
    for component, source in [('Nuitka', nuitka), ('SCons', scons)]:
        legal = evidence / 'compiler-legal' / component
        legal.mkdir(parents=True)
        for path in source.iterdir():
            if path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                if path.is_dir():
                    shutil.copytree(path, legal / path.name)
                else:
                    shutil.copy2(path, legal / path.name)
    for key in ['nuitka_patch', 'scons_patch']:
        shutil.copy2(REPO / manifest[key]['path'], sources)
    shutil.copy2(manifest_path, sources)
    wheels = evidence / 'compiler-wheels'
    wheels.mkdir()
    log = evidence / 'compiler-wheel-build.log'
    result = subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--verbose', '--no-deps', '--no-build-isolation',
                             '--no-cache-dir', '--wheel-dir', str(wheels), str(nuitka)],
                            env={**os.environ, 'PYTHONVERBOSE': '1', 'PYTHONUTF8': '1'},
                            text=True, encoding='utf-8', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(result.stdout, encoding='utf-8')
    if result.returncode:
        print(result.stdout[-16000:], flush=True)
    result.check_returncode()
    subprocess.run([sys.executable, str(REPO / '.github/scripts/probe_setuptools_build.py'),
                    '--consumer', 'nuitka', '--consumer-log', str(log),
                    '--output-dir', str(evidence / 'build-dependencies')], check=True)
    wheel = next(wheels.glob('nuitka-4.3.5+psaa.scons4111-*.whl'))
    with zipfile.ZipFile(wheel) as archive:
        assert json.loads(archive.read('nuitka/PROJECT_MODIFIED_TOOLCHAIN.json')) == marker
        names = archive.namelist()
        assert any('/lib/scons-4.11.1/SCons/__init__.py' in name for name in names)
        assert not any('/lib/scons-4.10.1/' in name for name in names), 'Old selected inline copy must not enter the new wheel'
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '--force-reinstall', str(wheel)], check=True)
    installed = json.loads(subprocess.check_output([sys.executable, '-c',
        "import importlib.metadata,json,pathlib,nuitka;from nuitka.build.SconsInterface import getInlineSconsVersion;"
        "print(json.dumps(dict(version=importlib.metadata.version('Nuitka'),scons=getInlineSconsVersion(),"
        "marker=json.loads(pathlib.Path(nuitka.__file__).with_name('PROJECT_MODIFIED_TOOLCHAIN.json').read_text()))))"], text=True))
    assert installed == {'version': manifest['distribution_version'], 'scons': 'scons-4.11.1', 'marker': marker}
    marker.update(wheel=wheel.name, wheel_sha256=hashlib.sha256(wheel.read_bytes()).hexdigest(), result='Controlled compiler wheel installed with verified source/patch identity; native execution still required')
    (evidence / 'compiler-source-provenance.json').write_text(json.dumps(marker, indent=2), encoding='utf-8')
    print(json.dumps(marker, indent=2), flush=True)


if __name__ == '__main__':
    main()
