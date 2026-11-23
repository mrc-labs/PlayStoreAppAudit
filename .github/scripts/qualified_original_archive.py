"""Read an unchanged historical input from its original or explicit recovery store."""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact

INDEX = Path(__file__).with_name('retained_original_archives.json')


def read_original(artifact: int, run: int, source: str, digest: str,
                  size: int | None = None) -> tuple[bytes, dict]:
    selected = json.loads(INDEX.read_text(encoding='utf-8')).get(str(artifact))
    original = {'artifact': artifact, 'run': run, 'source_sha': source, 'sha256': digest}
    if selected and selected.get('recovered'):
        assert selected['original'] == {**original, 'bytes': selected['original']['bytes']}
        stored = selected['recovered']
        metadata, container = fetch_artifact(stored['artifact'])
        assert metadata['id'] == stored['artifact'] and not metadata['expired']
        assert metadata['workflow_run']['id'] == stored['run']
        assert metadata['workflow_run']['head_sha'] == stored['source_sha']
        assert metadata['workflow_run']['head_repository_id'] == 1334403620
        assert len(container) == metadata['size_in_bytes'] == stored['bytes']
        assert metadata['digest'] == 'sha256:' + stored['sha256']
        assert hashlib.sha256(container).hexdigest() == stored['sha256']
        with zipfile.ZipFile(io.BytesIO(container)) as archive:
            receipt = json.loads(archive.read('RECOVERY.json'))
            assert receipt['original'] == selected['original']
            assert receipt['recovery_source_sha'] == stored['source_sha']
            assert receipt['recovery_run'] == stored['run']
            assert archive.getinfo('original-input.zip').file_size == selected['original']['bytes']
            data = archive.read('original-input.zip')
        assert len(data) == selected['original']['bytes']
        kind = 'Byte-identical retained original; original GitHub container deleted'
    else:
        metadata, data = fetch_artifact(artifact)
        assert metadata['id'] == artifact and not metadata['expired']
        assert metadata['workflow_run']['id'] == run
        assert metadata['workflow_run']['head_sha'] == source
        assert metadata['workflow_run']['head_repository_id'] == 1334403620
        assert metadata['digest'] == 'sha256:' + digest
        assert len(data) == metadata['size_in_bytes']
        kind = 'Original GitHub Actions container'
    assert hashlib.sha256(data).hexdigest() == digest
    assert size is None or len(data) == size
    return data, {'identity': kind, 'original': {**original, 'bytes': len(data)},
                  'storage_metadata': metadata}
