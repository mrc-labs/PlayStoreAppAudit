"""Read-only verification of the exact Mac ARM pilot and its original bound SDK."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from download_diagnostic_artifact import fetch_artifact

ROOT = Path(__file__).resolve().parents[2]
PILOT = {'artifact': 14185067272, 'run': 43772341683,
         'source_sha': 'e4c810f352dccbf1f0db86fd61bd88b83847cb85', 'zip_bytes': 1621134105,
         'zip_sha256': 'b443772e473ab00e06f4f1bb754662a7aa4e63149ae7f3583069a3dc98702f7c'}


def verified(spec: dict) -> tuple[dict, bytes]:
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['id'] == spec['run']
    assert metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    return metadata, data


def verify_sdk(sdk: tarfile.TarFile, paths: dict, desired: dict, target: zipfile.ZipFile) -> tuple[set, dict]:
    seen, verified_files, recovered = set(), {}, {}
    by_digest = {}
    for name, row in desired.items():
        by_digest.setdefault(row['sha256'], []).append(name)
    for member in sdk:
        path = PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts and path.parts[0] in {'prefix', 'venv'}
        if member.isdir():
            continue
        assert member.name not in seen and member.name in paths
        expected = paths[member.name]
        seen.add(member.name)
        if member.issym():
            assert member.linkname == expected['link']
            continue
        size_digest = expected['bytes'], expected['sha256']
        if member.islnk():
            # Streaming tar cannot extract a prior hardlink body a second time.
            # Its exact target bytes have already been hashed; verify identity.
            assert member.linkname in verified_files
            assert verified_files[member.linkname] == size_digest
            verified_files[member.name] = size_digest
            continue
        assert member.isfile()
        raw = sdk.extractfile(member).read()
        assert (len(raw), hashlib.sha256(raw).hexdigest()) == size_digest
        verified_files[member.name] = size_digest
        for name in by_digest.get(size_digest[1], []):
            if name not in recovered:
                target.writestr('sdk-native-binaries/' + name, raw)
                recovered[name] = size_digest[1]
    assert seen == set(paths) and set(recovered) == set(desired)
    return seen, recovered


def main() -> None:
    output = ROOT / 'retained-qt-evidence'
    output.mkdir()
    target_path = output / 'macos-integration-evidence.zip'
    sdk_spec = json.loads((ROOT / '.github/scripts/macos_arm64_bound_sdk_sources.json').read_text())
    pilot_metadata, data = verified(PILOT)
    omitted, recovered, original_hashes = {}, {}, {}
    with zipfile.ZipFile(target_path, 'w', compression=zipfile.ZIP_DEFLATED) as target:
        with io.BytesIO(data) as buffer, zipfile.ZipFile(buffer) as original:
            report = json.loads(original.read('pilot-results.json'))
            assert report['source_sha'] == PILOT['source_sha'] and report['machine'] == 'arm64'
            rows = [*report['native']['changed'], *report['qt_securetransport']['changed_images']]
            for name in original.namelist():
                if name.endswith('/'):
                    continue
                assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                if name.startswith('sources/libclang-'):
                    with original.open(name) as stream:
                        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                    omitted[name] = {'bytes': original.getinfo(name).file_size, 'sha256': digest,
                                     'scope': 'Original host-parser archive verified, not copied into the small review slice'}
                else:
                    raw = original.read(name)
                    if name.startswith('sources/'):
                        original_hashes[name] = hashlib.sha256(raw).hexdigest()
                    assert not Path(name).name.endswith(('server-key.pem', 'ca-key.pem'))
                    target.writestr(name, raw)
        del data
        sdk_metadata, data = verified(sdk_spec)
        with io.BytesIO(data) as buffer, zipfile.ZipFile(buffer) as original:
            receipt = json.loads(original.read('macos-runtime-sdk.json'))
            assert receipt['source_sha'] == sdk_spec['source_sha'] and receipt['machine'] == 'arm64'
            assert not receipt['complete_pilot'], 'Do not relabel the failed original consumer'
            root = receipt['original_work_root'].rstrip('/') + '/'
            desired = {}
            for row in rows:
                assert row['path'].startswith(root)
                name = row['path'].removeprefix(root)
                assert name in receipt['paths'] and receipt['paths'][name]['sha256'] == row['sha256'], name
                desired[name] = row
            archive = original.read('macos-runtime-sdk.tar.zst')
            assert hashlib.sha256(archive).hexdigest() == receipt['archive_sha256']
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r|zst') as sdk:
                seen, recovered = verify_sdk(sdk, receipt['paths'], desired, target)
            target.writestr('original-bound-sdk-receipt.json', json.dumps(receipt, indent=2) + '\n')
        proof = {'verification_source_sha': os.environ['GITHUB_SHA'], 'pilot': pilot_metadata,
                 'original_sdk': sdk_metadata, 'verified_sdk_paths': len(seen), 'recovered_images': recovered,
                 'source_archive_hashes': original_hashes, 'omitted_host_archives': omitted,
                 'scope': 'Distinct read-only worker verifies both full original ZIP hashes, all indexed SDK bytes/links and all loaded changed image bytes. No execution/rebuild/candidate or independent review acceptance claimed.',
                 'result': 'PASS exact pilot/SDK/native/source/legal evidence bytes'}
        target.writestr('extraction-provenance.json', json.dumps(proof, indent=2) + '\n')
    print('PASS Mac evidence byte verification', target_path.stat().st_size, len(recovered), 'native images')


if __name__ == '__main__':
    main()
