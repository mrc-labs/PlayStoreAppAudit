"""Restore the exact qualified pre-Qt diagnostic prefix, never a candidate."""
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
from extract_qt_pilot_evidence import ARTIFACT, DIGEST, SOURCE

REPO = Path(__file__).resolve().parents[2]
QT_ARTIFACT = 14126645491
QT_SOURCE = '367486bea017f81426e4cc80e2bacfeac0dcf441'
QT_DIGEST = '1a6b377a3923dfe313a3bfb86c7c9e32d6291f7e34a77b116186c04cea7ee8d3'
QT_SDK_DIGEST = '4acaf82c9e7dd1f52f5d307c4f2f2e23180ef3aaf3ea9269540e9b5f86158451'
SDK_DIGEST = 'b8f55c348888b2f42728a4f4ee953b63fa002035a6209bc54c8171b65463a6f5'


def unchanged_inputs(archive: zipfile.ZipFile, *, with_qt: bool = False) -> None:
    if with_qt:
        for name in ('qt_data_refresh_sources.json', 'qt_cldr49_sources.json'):
            if json.loads(archive.read(name)) != json.loads((REPO / '.github/scripts' / name).read_text()):
                raise ValueError('Changed compiled Qt source contract: ' + name)
    for name in ('native_runtime_pilot_sources.json', 'linux_x64_native_delta_sources.json',
                 'qt_text_provider_sources.json', 'qt_cbor_provider_sources.json',
                 'qt_http_security_sources.json'):
        if json.loads(archive.read(name)) != json.loads((REPO / '.github/scripts' / name).read_text()):
            raise ValueError('Changed pre-Qt source contract: ' + name)
    for name in ('source_build_requirements.txt', 'source_build_constraints.txt'):
        if archive.read('build-dependencies/' + name).replace(b'\r\n', b'\n') != (
                REPO / '.github/scripts' / name).read_bytes().replace(b'\r\n', b'\n'):
            raise ValueError('Changed source-build contract: ' + name)


def restore(data: bytes, output: Path, runner_temp: Path, *, with_qt: bool = False) -> dict:
    digest, sdk_digest, source_sha = (QT_DIGEST, QT_SDK_DIGEST, QT_SOURCE) if with_qt else (DIGEST, SDK_DIGEST, SOURCE)
    label = 'qt-sdk' if with_qt else 'pre-qt-sdk'
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Changed original integrated diagnostic ZIP')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        unchanged_inputs(archive, with_qt=with_qt)
        receipt = json.loads(archive.read(label + '-provenance.json'))
        assert receipt['source_sha'] == source_sha and receipt['archive_sha256'] == sdk_digest
        if with_qt:
            assert receipt['capture_stage'] == 'qtbase-and-qtsvg-installed'
        prefix = Path(receipt['original_prefix'])
        # Preserve absolute install names/rpaths. Never overwrite an existing tree.
        expected = runner_temp.resolve() / 'native-runtime-pilot-43587421820-1/prefix'
        if prefix != expected or prefix.parent.exists():
            raise ValueError('Unsafe or occupied original diagnostic SDK prefix')
        raw = archive.read(label + '.tar.gz')
        if hashlib.sha256(raw).hexdigest() != sdk_digest:
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
        assert (prefix / 'qt').exists() == with_qt, 'Unexpected diagnostic SDK framework membership'
        if with_qt:
            reused = output / 'reused-qt'
            reused.mkdir()
            for name in ['qtbase-CMakeCache.txt', 'qtbase-config.summary', 'reused-pre-qt-sdk.json']:
                (reused / name).write_bytes(archive.read(name))
        for name in ('cpython-config.log', 'openssl-configdata.pm'):
            (output / name).write_bytes(archive.read(name))
        (output / ('original-qt-sdk-provenance.json' if with_qt else 'original-pre-qt-sdk-provenance.json')).write_bytes(
            archive.read(label + '-provenance.json'))
    proof = {'compiled_source_sha': source_sha, 'original_artifact': QT_ARTIFACT if with_qt else ARTIFACT,
             'original_zip_sha256': digest, 'sdk_sha256': sdk_digest, 'compiled_qt_reused': with_qt,
             'prefix': str(prefix), 'verified_files': len(actual),
             'runtime_compiled_source_sha': SOURCE,
             'scope': 'Diagnostic SDK reuse only; compiled Qt is reused when explicitly selected, binding/runtime checks remain required. Not a candidate.'}
    (output / 'reused-pre-qt-sdk.json').write_text(json.dumps(proof, indent=2) + '\n')
    (output / 'reused-prefix.txt').write_text(str(prefix))
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qt', action='store_true', help='Reuse the exact compiled Qt SDK; no runtime acceptance claim')
    args = parser.parse_args()
    artifact, source, digest, run, size = (QT_ARTIFACT, QT_SOURCE, QT_DIGEST, 43623545058, 529280327) if args.qt else (
        ARTIFACT, SOURCE, DIGEST, 43587421820, 867663500)
    metadata, data = fetch_artifact(artifact)
    assert metadata['workflow_run']['head_sha'] == source
    assert metadata['workflow_run']['id'] == run and not metadata['expired']
    assert metadata['digest'] == 'sha256:' + digest and metadata['size_in_bytes'] == len(data) == size
    print(json.dumps(restore(data, Path('pilot-evidence'), Path(os.environ['RUNNER_TEMP']), with_qt=args.qt), indent=2))


if __name__ == '__main__':
    main()
