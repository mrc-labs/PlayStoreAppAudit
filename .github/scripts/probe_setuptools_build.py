"""Qualify the source PEP517 dependency contract; no controlled producer-profile adoption."""
from __future__ import annotations

import argparse
import email
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib
import urllib.request
import zipfile
from importlib.metadata import version
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
IMPORTS = {'setuptools': 'setuptools/', 'packaging': 'packaging/',
           'more_itertools': 'more_itertools/', 'jaraco.text': 'jaraco/text/',
           'jaraco.functools': 'jaraco/functools/', 'jaraco.context': 'jaraco/context/'}


def candidate_metadata(original: str, spec: dict) -> str:
    """Source metadata may use the exact already-qualified candidate."""
    project = tomllib.loads(original)
    selected = project['build-system']['requires']
    if selected == spec['requirements']:
        return original
    if selected != ['setuptools==84.2.1', 'wheel==0.48.0']:
        raise ValueError('Unreviewed project build requirements')
    candidate = original.replace('requires = ["setuptools==84.2.1", "wheel==0.48.0"]', 'requires = ' + json.dumps(spec['requirements']), 1)
    parsed = tomllib.loads(candidate)
    assert parsed['build-system']['requires'] == spec['requirements'] and parsed['project'] == project['project']
    return candidate


def isolated_imports(trace: str) -> dict[str, str]:
    """Global installs and fallback copies cannot qualify the PEP517 worker."""
    found = {}
    for line in trace.splitlines():
        normalized = re.sub('/+', '/', line.replace('\\', '/')).lower()
        if 'code object from' not in normalized or 'pip-build-env-' not in normalized:
            continue
        if '/setuptools/_vendor/' in normalized:
            raise ValueError('Active setuptools fallback path: ' + line.strip())
        for name, fragment in IMPORTS.items():
            if '/_vendor/' + fragment in normalized:
                raise ValueError('Active setuptools fallback: ' + name)
            if '/site-packages/' + fragment in normalized:
                found.setdefault(name, line.strip())
    if set(found) != set(IMPORTS):
        raise ValueError('Missing actual isolated backend imports: ' + str(set(IMPORTS) - set(found)))
    return found


def selected_versions(trace: str, spec: dict) -> dict[str, str]:
    found = {}
    for line in trace.splitlines():
        if 'Successfully installed ' not in line:
            continue
        for entry in line.partition('Successfully installed ')[2].split():
            name, separator, selected = entry.rpartition('-')
            if not separator:
                raise ValueError('Unexpected dependency install record: ' + entry)
            name = re.sub(r'[-_.]+', '-', name).lower()
            if name not in spec['packages'] or selected != spec['packages'][name]['version']:
                raise ValueError('Unexpected build dependency/version: ' + entry)
            found[name] = selected
    required = {re.sub(r'[-_.]+', '-', item.split('==')[0]).lower() for item in spec['requirements']}
    if not required <= found.keys():
        raise ValueError('Required build distributions were not actually installed')
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert platform.machine().lower() in ({'arm64', 'aarch64'} if os.environ['EXPECTED_ARCH'] == 'arm64' else {'amd64', 'x86_64'})
    assert version('pip') == '26.3'
    args.work_root.mkdir(parents=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    work, output = args.work_root.resolve(), args.output_dir.resolve()
    spec_path = REPO / '.github/scripts/setuptools_build_probe_sources.json'
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    shutil.copy2(spec_path, output / spec_path.name)
    source = work / 'source'
    source.mkdir()
    files = subprocess.check_output(['git', 'ls-files', '-z', '--', 'playstore_app_audit', 'pyproject.toml', 'README.md', 'LICENSE']).decode().split('\0')
    hashes = {}
    for name in filter(None, files):
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / name, target)
        hashes[name] = hashlib.sha256(target.read_bytes()).hexdigest()
    original = (source / 'pyproject.toml').read_text(encoding='utf-8')
    project = tomllib.loads(original)
    candidate = candidate_metadata(original, spec)
    (source / 'pyproject.toml').write_text(candidate, encoding='utf-8')
    (output / 'candidate-pyproject.toml').write_text(candidate, encoding='utf-8')
    constraints = output / 'build-constraints.txt'
    constraints.write_text('\n'.join(spec['build_constraints']) + '\n', encoding='utf-8')
    sources = output / 'sources'
    sources.mkdir()
    for item in spec['packages'].values():
        item = item['source']
        with urllib.request.urlopen(item['url'], timeout=90) as response:
            assert response.geturl().startswith('https://'), 'Source HTTPS downgrade'
            data = response.read()
        assert hashlib.sha256(data).hexdigest() == item['sha256'], item['name']
        (sources / item['name']).write_bytes(data)
    temporary = work / 'temp'
    temporary.mkdir()
    wheels = output / 'wheels'
    wheels.mkdir()
    env = {**os.environ, 'PYTHONVERBOSE': '1', 'PYTHONUTF8': '1', 'TMPDIR': str(temporary),
           'TEMP': str(temporary), 'TMP': str(temporary), 'PIP_DISABLE_PIP_VERSION_CHECK': '1'}
    command = [sys.executable, '-m', 'pip', '--isolated', 'wheel', '--no-deps', '--verbose',
               '--only-binary=:all:', '--build-constraint', str(constraints), '--wheel-dir', str(wheels), str(source)]
    result = subprocess.run(command, env=env, capture_output=True)
    trace_bytes = result.stdout + result.stderr
    (output / 'pep517-import-trace.log').write_bytes(trace_bytes)
    trace = trace_bytes.decode('utf-8', errors='replace')
    if result.returncode:
        print(trace[-8000:], flush=True)
    result.check_returncode()
    imports = isolated_imports(trace)
    selected = selected_versions(trace, spec)
    artifacts = list(wheels.glob('*.whl'))
    assert len(artifacts) == 1 and artifacts[0].name.endswith('-py3-none-any.whl')
    with zipfile.ZipFile(artifacts[0]) as archive:
        metadata = email.message_from_bytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
        def normalize(value: str) -> str:
            return value.lower().replace('_', '-')
        assert {normalize(v) for v in metadata.get_all('Requires-Dist')} == {normalize(v) for v in project['project']['dependencies']}
        assert metadata['Version'] == project['project']['version'] == '2.4.0'
        assert metadata['License-Expression'] == 'GPL-3.0-only'
        for name in archive.namelist():
            assert name.startswith('playstore_app_audit/') or name.startswith('playstore_app_audit-2.4.0.dist-info/'), name
            if name.startswith('playstore_app_audit/'):
                assert hashlib.sha256(archive.read(name)).hexdigest() == hashes[name], name
    report = {'source_sha': head, 'scope': __doc__, 'python': platform.python_version(), 'architecture': platform.machine(),
              'candidate_build_requires': spec['requirements'], 'actually_installed': selected, 'actual_isolated_imports': imports,
              'source_file_hashes': hashes, 'wheel': artifacts[0].name, 'wheel_sha256': hashlib.sha256(artifacts[0].read_bytes()).hexdigest(),
              'wheel_contents': 'Project package bytes/runtime requirements unchanged; build-only dependencies excluded',
              'executed_setuptools_fallbacks': [],
              'result': 'PASS isolated diagnostic source-wheel test; no controlled producer-profile adoption'}
    (output / 'setuptools-build-results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'source_file_hashes'}, indent=2), flush=True)


if __name__ == '__main__':
    main()
