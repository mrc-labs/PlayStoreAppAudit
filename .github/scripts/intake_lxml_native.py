"""Reuse only the six exact source-qualified parser wheels in controlled pilots."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path

from probe_lxml_native import installed_results
from qualified_original_archive import read_original

REPO = Path(__file__).resolve().parents[2]


def contract(target: str) -> tuple[dict, dict, dict]:
    index = json.loads((REPO / '.github/scripts/lxml_qualified_wheel_sources.json').read_text())
    spec = json.loads((REPO / '.github/scripts/lxml_native_sources.json').read_text())
    if hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != index['source_contract_canonical_sha256']:
        raise ValueError('Changed parser source/build contract requires new native qualification')
    return index, spec, next(item for item in index['targets'] if item['target'] == target)


def verify_zip(data: bytes, expected: dict) -> tuple[str, bytes]:
    if len(data) != expected['zip_bytes'] or hashlib.sha256(data).hexdigest() != expected['zip_sha256']:
        raise ValueError('Changed qualified parser ZIP')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        report = json.loads(archive.read('lxml-native-results.json'))
        assert report['source_sha'] == expected['source_sha']
        assert report['compiled_source_sha'] == expected['compiled_source_sha']
        names = [name for name in archive.namelist() if name.startswith('wheels/lxml-6.1.3-') and name.endswith('.whl')]
        assert len(names) == 1
        wheel = archive.read(names[0])
    if hashlib.sha256(wheel).hexdigest() != expected['wheel_sha256']:
        raise ValueError('Changed qualified parser wheel')
    with zipfile.ZipFile(io.BytesIO(wheel)) as archive:
        native = {Path(name).name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                  if name.endswith(('.pyd', '.so'))}
        assert native == expected['native_image_sha256'], 'Changed qualified native parser modules'
    return Path(names[0]).name, wheel


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--qualify', action='store_true', help='Install/run the exact retained wheel on the actual controlled interpreter')
    args = parser.parse_args()
    index, spec, expected = contract(args.target)
    output = args.output_dir.resolve()
    source = output / 'original-qualified-lxml.zip'
    if not args.qualify:
        data, storage = read_original(expected['artifact'], expected['run'], expected['source_sha'],
                                      expected['zip_sha256'], expected['zip_bytes'])
        verify_zip(data, expected)
        output.mkdir(parents=True)
        source.write_bytes(data)
        (output / 'intake-provenance.json').write_text(json.dumps({
            'intake_source_sha': os.environ['GITHUB_SHA'], 'qualified_native': expected,
            'archive_storage': storage,
            'identity': index['identity'], 'scope': 'Original source/legal/wheel/native bytes retained in exact original ZIP; no rebuild or relabeling'}, indent=2) + '\n')
        return
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert not sysconfig.get_config_var('Py_DEBUG')
    system, arch = args.target.split('-')
    assert sys.platform == {'windows': 'win32', 'linux': 'linux', 'macos': 'darwin'}[system]
    assert platform.machine().lower() in ({'arm64', 'aarch64'} if arch == 'arm64' else {'amd64', 'x86_64'})
    name, wheel = verify_zip(source.read_bytes(), expected)
    wheel_path = output / name
    wheel_path.write_bytes(wheel)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', '--force-reinstall', str(wheel_path)], check=True)
    qualification = output / 'controlled-runtime'
    qualification.mkdir()
    deployment = ('11.0' if arch == 'arm64' else '10.15') if system == 'macos' else None
    installed_results(spec, qualification, arch, deployment, 'Original qualified compiler retained in source ZIP',
                      wheel_path, {}, os.environ['GITHUB_SHA'], expected['compiled_source_sha'], expected)


if __name__ == '__main__':
    main()
