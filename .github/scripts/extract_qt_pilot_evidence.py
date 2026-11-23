"""Verify/slice one retained Qt integration ZIP without rebuilding or executing it."""
from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact

ARTIFACT = 14111694314
SOURCE = 'f2bdb0443a3c659fa464dd253fdd4c1bd829a91f'
DIGEST = '5639ca8f9e3f37b8ec9f64c6766dc2e2596bbc50af60e6a4f63c418e7dbeb20e'


def main() -> None:
    metadata, data = fetch_artifact(ARTIFACT)
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    assert metadata['id'] == ARTIFACT and not metadata['expired']
    assert metadata['workflow_run']['head_sha'] == SOURCE and metadata['workflow_run']['id'] == 43587421820
    assert len(data) == metadata['size_in_bytes'] == 867663500
    assert metadata['digest'] == 'sha256:' + DIGEST and hashlib.sha256(data).hexdigest() == DIGEST
    output = Path('retained-qt-evidence')
    output.mkdir()
    skipped = {}
    images = {}
    with zipfile.ZipFile(io.BytesIO(data)) as original, zipfile.ZipFile(
            output / 'qt-integration-evidence.zip', 'w', compression=zipfile.ZIP_DEFLATED) as target:
        for name in original.namelist():
            if name.endswith('/'):
                continue
            payload = original.read(name)
            if name in {'pre-qt-sdk.tar.gz', 'qt-sdk.tar.gz', 'original-python-14098850639.zip'}:
                skipped[name] = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            else:
                target.writestr(name, payload)
        report = json.loads(original.read('pilot-results.json'))
        assert report['source_sha'] == SOURCE
        receipt = json.loads(original.read('qt-sdk-provenance.json'))
        assert receipt['source_sha'] == SOURCE
        assert skipped['qt-sdk.tar.gz']['sha256'] == receipt['archive_sha256']
        desired = {item['path'].split('/prefix/', 1)[1]: item for item in report['loaded_changed_images']
                   if '/prefix/' in item['path']}
        with tarfile.open(fileobj=io.BytesIO(original.read('qt-sdk.tar.gz')), mode='r|gz') as sdk:
            for member in sdk:
                relative = member.name.removeprefix('prefix/')
                if relative not in desired or not member.isfile():
                    continue
                payload = sdk.extractfile(member).read()
                digest = hashlib.sha256(payload).hexdigest()
                assert digest == desired[relative]['sha256'] == receipt['files'][relative]['sha256']
                target.writestr('sdk-native-binaries/' + relative, payload)
                images[relative] = digest
        assert set(images) == set(desired), 'A retained SDK image was not recovered'
        assert skipped['original-python-14098850639.zip']['sha256'] == 'd33de909db30a6f56ff438ec57f08091c72e486ffbb0b68b257de6f7c883579a'
        proof = {'extract_source_sha': os.environ['GITHUB_SHA'], 'compiled_source_sha': SOURCE,
                 'original_artifact': metadata, 'original_zip_sha256': DIGEST,
                 'omitted_large_blobs': skipped, 'retained_sdk_images': images,
                 'unretained_binding_images': [item for item in report['loaded_changed_images'] if '/prefix/' not in item['path']],
                 'scope': 'Read-only byte verification/slice; no execution, rebuild, candidate or relabeling. Binding images absent from the original retained SDK remain CI-observed hashes only.',
                 'result': 'PASS original ZIP/hash and recovered SDK image bytes'}
        target.writestr('extraction-provenance.json', json.dumps(proof, indent=2) + '\n')
    print('PASS retained Qt evidence ZIP', (output / 'qt-integration-evidence.zip').stat().st_size,
          'recovered images', len(images), flush=True)


if __name__ == '__main__':
    main()
