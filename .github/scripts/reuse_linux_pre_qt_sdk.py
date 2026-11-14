"""Restore the exact qualified pre-Qt diagnostic prefix, never a candidate."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact
from extract_qt_pilot_evidence import ARTIFACT, DIGEST, SOURCE

REPO = Path(__file__).resolve().parents[2]
SDK_DIGEST = 'b8f55c348888b2f42728a4f4ee953b63fa002035a6209bc54c8171b65463a6f5'


def unchanged_inputs(archive: zipfile.ZipFile) -> None:
    for name in ('native_runtime_pilot_sources.json', 'linux_x64_native_delta_sources.json',
                 'qt_text_provider_sources.json', 'qt_cbor_provider_sources.json',
                 'qt_http_security_sources.json'):
        if json.loads(archive.read(name)) != json.loads((REPO / '.github/scripts' / name).read_text()):
            raise ValueError('Changed pre-Qt source contract: ' + name)
    for name in ('source_build_requirements.txt', 'source_build_constraints.txt'):
        if archive.read('build-dependencies/' + name).replace(b'\r\n', b'\n') != (
                REPO / '.github/scripts' / name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Changed source-build contract: ' + name)


def restore(data: bytes, output: Path, runner_temp: Path) -> dict:
    if hashlib.sha256(data).hexdigest() != DIGEST:
        raise ValueError('Changed original integrated diagnostic ZIP')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        unchanged_inputs(archive)
        receipt = json.loads(archive.read('pre-qt-sdk-provenance.json'))
        assert receipt['source_sha'] == SOURCE and receipt['archive_sha256'] == SDK_DIGEST
        prefix = Path(receipt['original_prefix'])
        # Preserve absolute install names/rpaths. Never overwrite an existing tree.
        expected = runner_temp.resolve() / 'native-runtime-pilot-43587421820-1/prefix'
        if prefix != expected or prefix.parent.exists():
            raise ValueError('Unsafe or occupied original diagnostic SDK prefix')
        raw = archive.read('pre-qt-sdk.tar.gz')
        if hashlib.sha256(raw).hexdigest() != SDK_DIGEST:
            raise ValueError('Changed pre-Qt SDK bytes')
        with tarfile.open(fileobj=io.BytesIO(raw)) as sdk:
            for member in sdk.getmembers():
                if not member.name.startswith('prefix/') and member.name != 'prefix':
                    raise ValueError('Unexpected SDK archive root')
            prefix.parent.mkdir(parents=True)
            sdk.extractall(prefix.parent, filter='data')
        actual = {}
        for path in prefix.rglob('*'):
            relative = path.relative_to(prefix).as_posix()
            if path.is_symlink():
                if not path.resolve().is_relative_to(prefix):
                    raise ValueError('SDK link escapes prefix')
                actual[relative] = {'symlink': os.readlink(path)}
            elif path.is_file():
                actual[relative] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if actual != receipt['files']:
            raise ValueError('Restored SDK differs from original file receipt')
        assert not (prefix / 'qt').exists(), 'Expected pre-Qt SDK, not an old framework'
        for name in ('cpython-config.log', 'openssl-configdata.pm'):
            (output / name).write_bytes(archive.read(name))
        (output / 'original-pre-qt-sdk-provenance.json').write_bytes(
            archive.read('pre-qt-sdk-provenance.json'))
    proof = {'compiled_source_sha': SOURCE, 'original_artifact': ARTIFACT,
             'original_zip_sha256': DIGEST, 'sdk_sha256': SDK_DIGEST,
             'prefix': str(prefix), 'verified_files': len(actual),
             'scope': 'Unchanged diagnostic Python/OpenSSL/native providers only; Qt and bindings rebuilt. Not a candidate.'}
    (output / 'reused-pre-qt-sdk.json').write_text(json.dumps(proof, indent=2) + '\n')
    (output / 'reused-prefix.txt').write_text(str(prefix))
    return proof


def main() -> None:
    metadata, data = fetch_artifact(ARTIFACT)
    assert metadata['workflow_run']['head_sha'] == SOURCE
    assert metadata['workflow_run']['id'] == 43587421820 and not metadata['expired']
    assert metadata['digest'] == 'sha256:' + DIGEST and metadata['size_in_bytes'] == len(data) == 867663500
    print(json.dumps(restore(data, Path('pilot-evidence'), Path(os.environ['RUNNER_TEMP'])), indent=2))


if __name__ == '__main__':
    main()
