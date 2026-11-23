"""Resume only the exact Noble ARM64 diagnostic SDK after consumer-test fixes."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact

REPO = Path(__file__).resolve().parents[2]
SOURCE = '1ba799e7fecafe1a0675495294670c316c8457ba'
ARTIFACT = 14143608998
DIGEST = 'd58103215ca9a07fc9e3c4c0e3ed057bf67096f62c67a4ee004afcb316744e5f'
SDK_DIGEST = '7a8e9cd5c65d5aedb5d0bb2dcc20f5346bf7b1233e9714bd45d8cb853987951b'


def restore(data: bytes, output: Path, runner_temp: Path) -> dict:
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError('Changed original Noble ARM64 diagnostic ZIP')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = ['native_runtime_pilot_sources.json', 'linux_arm64_runtime_pilot_sources.json',
                 'linux_arm64_maintenance_sources.json', 'linux_x64_native_delta_sources.json',
                 'qt_text_provider_sources.json', 'qt_cbor_provider_sources.json',
                 'qt_http_security_sources.json', 'qt_data_refresh_sources.json',
                 'qt_cldr49_sources.json', 'provider_ca_security_sources.json']
        for name in names:
            if json.loads(archive.read(name)) != json.loads((REPO / '.github/scripts' / name).read_text()):
                raise ValueError('Changed compiled ARM64 contract: ' + name)
        for name in ['source_build_requirements.txt', 'source_build_constraints.txt']:
            if archive.read('build-dependencies/' + name).replace(b'\r\n', b'\n') != (
                    REPO / '.github/scripts' / name).read_bytes().replace(b'\r\n', b'\n'):
                raise ValueError('Changed ARM64 source build requirements')
        receipt = json.loads(archive.read('qt-sdk-provenance.json'))
        assert receipt['source_sha'] == SOURCE and receipt['archive_sha256'] == SDK_DIGEST
        assert receipt['capture_stage'] == 'qtbase-and-qtsvg-installed'
        prefix = runner_temp.resolve() / 'linux-arm64-pilot-43667240760-1/prefix'
        if Path(receipt['original_prefix']) != prefix or prefix.parent.exists():
            raise ValueError('Unsafe or occupied original ARM64 SDK prefix')
        raw = archive.read('qt-sdk.tar.gz')
        if hashlib.sha256(raw).hexdigest() != SDK_DIGEST:
            raise ValueError('Changed ARM64 SDK bytes')
        with tarfile.open(fileobj=io.BytesIO(raw)) as sdk:
            if any(member.name != 'prefix' and not member.name.startswith('prefix/') for member in sdk.getmembers()):
                raise ValueError('Unexpected ARM64 SDK archive root')
            prefix.parent.mkdir(parents=True)
            sdk.extractall(prefix.parent, filter='data')
        actual = {}
        for path in prefix.rglob('*'):
            if path.is_symlink():
                if not path.resolve().is_relative_to(prefix):
                    raise ValueError('ARM64 SDK link escapes prefix')
                actual[path.relative_to(prefix).as_posix()] = {'symlink': os.readlink(path)}
            elif path.is_file():
                actual[path.relative_to(prefix).as_posix()] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if actual != receipt['files']:
            raise ValueError('Restored ARM64 SDK file mismatch')
        binding = json.loads(archive.read('pyside-binding-sdk-provenance.json'))
        assert all(binding[key] == SOURCE for key in ['source_sha', 'qt_compiled_source_sha', 'python_compiled_source_sha'])
        selected = {name.removeprefix('pyside-binding-sdk/'): name for name in archive.namelist()
                    if name.startswith('pyside-binding-sdk/') and not name.endswith('/')}
        assert selected.keys() == binding['files'].keys()
        for relative, name in selected.items():
            content = archive.read(name)
            assert binding['files'][relative] == {'sha256': hashlib.sha256(content).hexdigest()}
        # Retain original source/legal/build reports with their actual source identity.
        # Do not duplicate the two huge SDK archives or relabel their receipts.
        for name in archive.namelist():
            if name.endswith('/') or name in ['pre-qt-sdk.tar.gz', 'qt-sdk.tar.gz']:
                continue
            if name.startswith('python-native-binaries/'):
                continue
            target = output / name
            if not target.resolve().is_relative_to(output.resolve()):
                raise ValueError('Unsafe original evidence member')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    proof = {'compiled_source_sha': SOURCE, 'original_artifact': ARTIFACT,
             'original_zip_sha256': DIGEST, 'sdk_sha256': SDK_DIGEST,
             'prefix': str(prefix), 'verified_sdk_files': len(actual), 'verified_binding_files': len(selected),
             'scope': 'Unchanged diagnostic runtime/Qt/binding bytes; affected consumers rerun. Not final package acceptance.'}
    (output / 'reused-arm64-sdk.json').write_text(json.dumps(proof, indent=2) + '\n')
    (output / 'reused-prefix.txt').write_text(str(prefix))
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    metadata, data = fetch_artifact(ARTIFACT)
    assert metadata['workflow_run']['head_sha'] == SOURCE
    assert metadata['workflow_run']['id'] == 43667240760 and not metadata['expired']
    assert metadata['digest'] == 'sha256:' + DIGEST
    assert metadata['size_in_bytes'] == len(data) == 615903336
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(json.dumps(restore(data, args.output_dir, Path(os.environ['RUNNER_TEMP'])), indent=2))


if __name__ == '__main__':
    main()
