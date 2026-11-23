"""Resume only codec consumer tests from two exact native compiled artifacts."""
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
import tarfile
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact
from inspect_pe import read_pe_machine
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]
SOURCE = '732371e4b840385708f6d07b048111178a1cd48d'
INPUTS = {
    'x64': (14154246998, 28603875, 'aa43aeed9ebd1d62a9d286e66c9a92bcbea042134ee8e2a79d71ae3747163438'),
    'arm64': (14153164731, 28560316, '5d832d9e27256ed051606c25b02ea059041d0e4e740be7e910aad15d91b5d9ae'),
}


def restore(data: bytes, arch: str, output: Path) -> dict:
    artifact, size, digest = INPUTS[arch]
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Changed original native codec ZIP')
    spec = json.loads((REPO / '.github/scripts/windows_codec_provider_sources.json').read_text())
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if json.loads(archive.read('windows_codec_provider_sources.json')) != spec:
            raise ValueError('Changed compiled codec source contract')
        for row in spec['sources']:
            assert hashlib.sha256(archive.read('sources/' + row['name'])).hexdigest() == row['sha256']
        modules = output / 'native-codecs'
        assert not modules.exists()
        modules.mkdir(parents=True)
        images = []
        for name in ['zlib.pyd', '_lzma.pyd', 'liblzma.dll']:
            content = archive.read(name)
            path = modules / name
            path.write_bytes(content)
            assert read_pe_machine(path) == (0xAA64 if arch == 'arm64' else 0x8664)
            versions = pe_versions(path)
            assert all(version <= (10, 0) for version in versions.values())
            images.append({'name': name, 'sha256': hashlib.sha256(content).hexdigest(), 'versions': versions})
        # Native /MD/import/ctest guards ran before these bytes were retained in
        # the original jobs. They are not recompiled or relabeled by this job.
        for name in archive.namelist():
            if name.endswith('/') or name in ['zlib.pyd', '_lzma.pyd', 'liblzma.dll']:
                continue
            target = output / ('original-consumer-failure.log' if name == 'codec-upstream-tests.log' else name)
            if not target.resolve().is_relative_to(output.resolve()):
                raise ValueError('Unsafe original codec evidence path')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
        python = next(row for row in spec['sources'] if row['name'].startswith('Python-'))
        source = output / 'test-source'
        with tarfile.open(output / 'sources' / python['name']) as bundle:
            bundle.extractall(source, filter='data')
    proof = {'compiled_source_sha': SOURCE, 'original_run': 43695553011,
             'original_artifact': artifact, 'original_zip_sha256': digest, 'images': images,
             'compiler': '14.52.37025 native /MD, original source-build job',
             'scope': 'Exact original native codec bytes and upstream C tests; only corrected Python consumer reruns'}
    (output / 'original-codec-provenance.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    arch = os.environ['EXPECTED_ARCH']
    assert sys.platform == 'win32' and platform.python_version() == '3.14.10'
    assert platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    artifact, size, digest = INPUTS[arch]
    metadata, data = fetch_artifact(artifact)
    assert metadata['workflow_run']['head_sha'] == SOURCE
    assert metadata['workflow_run']['id'] == 43695553011 and not metadata['expired']
    assert metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['size_in_bytes'] == size and metadata['digest'] == 'sha256:' + digest
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    output = args.output_dir.resolve()
    proof = restore(data, arch, output)
    subprocess.run([sys.executable, '-I', str(REPO / '.github/scripts/windows_codec_consumer.py'),
                    '--modules', str(output / 'native-codecs'),
                    '--stdlib', str(output / 'test-source/Python-3.14.10/Lib'),
                    '--lzma-dll', 'liblzma.dll', '--output', str(output / 'windows-codec-consumers.json')], check=True)
    print(json.dumps(proof, indent=2))


if __name__ == '__main__':
    main()
