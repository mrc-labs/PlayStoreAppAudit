from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
import qualified_original_archive as originals


@pytest.mark.parametrize('fault', [None, 'container', 'payload', 'source', 'repo', 'receipt', 'original'])
def test_recovered_bytes_keep_original_and_storage_identities_distinct(tmp_path, monkeypatch, fault):
    payload = b'unchanged original ZIP fixture'
    digest = hashlib.sha256(payload).hexdigest()
    original = {'artifact': 1, 'run': 2, 'source_sha': 'a' * 40, 'sha256': digest, 'bytes': len(payload)}
    receipt = {'original': original, 'recovery_source_sha': 'b' * 40, 'recovery_run': 4}
    if fault == 'receipt':
        receipt = {**receipt, 'recovery_run': 99}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('original-input.zip', b'changed' if fault == 'payload' else payload)
        archive.writestr('RECOVERY.json', json.dumps(receipt))
    container = stream.getvalue()
    container_sha = hashlib.sha256(container).hexdigest()
    storage = {'artifact': 3, 'run': 4, 'source_sha': 'b' * 40, 'sha256': container_sha, 'bytes': len(container)}
    index = tmp_path / 'index.json'
    index.write_text(json.dumps({'1': {'original': original, 'recovered': storage}}))
    monkeypatch.setattr(originals, 'INDEX', index)
    metadata = {'id': 3, 'expired': False, 'size_in_bytes': len(container), 'digest': 'sha256:' + container_sha,
                'workflow_run': {'id': 4, 'head_sha': 'x' * 40 if fault == 'source' else 'b' * 40,
                                 'head_repository_id': 99 if fault == 'repo' else 1334403620}}
    monkeypatch.setattr(originals, 'fetch_artifact', lambda _: (metadata, container + b'tampered' if fault == 'container' else container))
    if fault:
        with pytest.raises(AssertionError):
            originals.read_original(1, 2, 'x' * 40 if fault == 'original' else 'a' * 40, digest, len(payload))
    else:
        data, provenance = originals.read_original(1, 2, 'a' * 40, digest, len(payload))
        assert data == payload and provenance['original'] == original
        assert provenance['storage_metadata']['id'] == 3
        assert provenance['storage_metadata']['workflow_run']['head_sha'] == 'b' * 40
