"""Rebuild four exact official Action sources with their closed compatible locks."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import fetch
from provision_nuitka_scons import apply_source_patch

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    node = Path(os.environ['PSAA_NODE']).resolve()
    assert subprocess.check_output([node, '--version'], text=True).startswith('v24.')
    npm = Path(shutil.which('npm')).resolve()
    assert npm.name.endswith('.js'), 'Use official npm CLI through the actual Node24 executable'
    work, output = args.work.resolve(), ROOT / 'controlled-actions-evidence'
    assert not work.exists()
    work.mkdir()
    output.mkdir(exist_ok=True)
    sources = output / 'sources'
    sources.mkdir()
    spec = json.loads((ROOT / '.github/scripts/controlled_actions_sources.json').read_text())
    environment = {**os.environ, 'PATH': str(node.parent) + os.pathsep + os.environ['PATH']}
    for key in ['GH_TOKEN', 'GITHUB_TOKEN', 'NPM_TOKEN', 'NODE_AUTH_TOKEN']:
        environment.pop(key, None)
    results = []
    for item in spec['actions']:
        archive = fetch(item['source'], sources)
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
        source = work / item['directory']
        assert hashlib.sha256((source / 'package.json').read_bytes()).hexdigest() == item['package_json_sha256']
        original_code = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (source / 'src').rglob('*') if p.is_file()}
        original_dist = work / (item['name'] + '-original-official-dist')
        (source / 'dist').rename(original_dist)
        lock = ROOT / item['lock']['path']
        assert hashlib.sha256(lock.read_bytes()).hexdigest() == item['lock']['sha256']
        shutil.copy2(lock, source / 'package-lock.json')
        if 'test_only_patch' in item:
            apply_source_patch(source, item['test_only_patch'])
            shutil.copy2(ROOT / item['test_only_patch']['path'], output)
        commands = [[node, npm, 'ci', '--ignore-scripts', '--no-audit', '--no-fund']]
        for command in spec['commands'][item['name']]:
            if command[0] == 'build':
                commands.append([node, npm, 'run', 'build'])
            else:
                commands.append([node, source / 'node_modules/@vercel/ncc/dist/ncc/cli.js',
                                 'build', command[1], '-o', command[2], '--license', 'licenses.txt'])
        commands.append([node, npm, 'test', '--', '--runInBand'])
        for number, command in enumerate(commands):
            log = output / f'{item["name"]}-{number}.log'
            with log.open('w', encoding='utf-8') as stream:
                result = subprocess.run(command, cwd=source, env=environment, stdout=stream, stderr=subprocess.STDOUT)
            if result.returncode:
                print(log.read_text(encoding='utf-8', errors='replace')[-12000:], flush=True)
            result.check_returncode()
        assert original_code == {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (source / 'src').rglob('*') if p.is_file()}
        assert hashlib.sha256((source / 'package-lock.json').read_bytes()).hexdigest() == item['lock']['sha256']
        target = output / 'actions' / item['name']
        target.mkdir(parents=True)
        shutil.copytree(source / 'dist', target / 'dist')
        if item['name'] == 'checkout':
            shutil.copy2(original_dist / 'problem-matcher.json', target / 'dist/problem-matcher.json')
        shutil.copy2(source / 'LICENSE', target)
        metadata = (source / 'action.yml').read_text()
        metadata = 'name: PSAA controlled ' + item['name'] + '\n' + '\n'.join(metadata.splitlines()[1:]) + '\n'
        assert 'node24' in metadata
        (target / 'action.yml').write_text(metadata)
        shutil.copy2(lock, target / 'controlled.package-lock.json')
        assert list((target / 'dist').rglob('licenses.txt')), 'Retain bundled dependency license notices'
        files = {p.relative_to(target).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
                 for p in target.rglob('*') if p.is_file()}
        results.append({'action': item['name'], 'original': item, 'files': files,
                        'result': 'Original production source unchanged; closed dependencies/build/upstream tests PASS'})
    shutil.copy2(ROOT / '.github/scripts/controlled_actions_sources.json', output)
    (output / 'controlled-actions-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'node': subprocess.check_output([node, '--version'], text=True).strip(),
        'npm': subprocess.check_output([node, npm, '--version'], text=True).strip(), 'actions': results,
        'scope': 'Project-modified Action bundles; native Node24 behavior and producer adoption still required'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
