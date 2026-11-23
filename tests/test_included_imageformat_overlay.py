from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile

import complete_qt_imageformats as modules
import download_diagnostic_artifact
import pytest


@pytest.mark.parametrize('mode', ['included', 'changed', 'add-only'])
def test_closed_sdk_modules_are_verified_without_overwrite(tmp_path, monkeypatch, mode):
    work, output = tmp_path / 'sdk', tmp_path / 'reports'
    output.mkdir()
    relative = 'prefix/qt/plugins/imageformats/plugin.fixture'
    target = work / relative
    target.parent.mkdir(parents=True)
    target.write_bytes(b'changed' if mode == 'changed' else b'qualified module')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as archive:
        info = tarfile.TarInfo(relative)
        info.size = len(b'qualified module')
        archive.addfile(info, io.BytesIO(b'qualified module'))
    raw_overlay = payload.getvalue()
    source = b'original source fixture'
    monkeypatch.setattr(modules, 'SOURCE', {'name': 'original.tar.xz', 'sha256': hashlib.sha256(source).hexdigest()})
    provenance = {'source_sha': 'a' * 40, 'source': modules.SOURCE,
                  'installed_module': {'original_work_root': str(work), 'sha256': hashlib.sha256(raw_overlay).hexdigest(),
                                       'paths': {relative: {'bytes': 16, 'sha256': hashlib.sha256(b'qualified module').hexdigest()}}}}
    raw_provenance = json.dumps(provenance).encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('imageformats/module-provenance.json', raw_provenance)
        archive.writestr('imageformats/installed-module.tar.zst', raw_overlay)
        archive.writestr('sources/original.tar.xz', source)
    data = stream.getvalue()
    spec = {'artifact': 1, 'run': 2, 'source_sha': 'a' * 40, 'zip_bytes': len(data),
            'zip_sha256': hashlib.sha256(data).hexdigest(), 'provenance_sha256': hashlib.sha256(raw_provenance).hexdigest(),
            'overlay_sha256': hashlib.sha256(raw_overlay).hexdigest(), 'already_in_sdk': mode != 'add-only'}
    metadata = {'expired': False, 'workflow_run': {'head_sha': 'a' * 40, 'id': 2, 'head_repository_id': 1334403620}}
    monkeypatch.setattr(download_diagnostic_artifact, 'fetch_artifact', lambda _: (metadata, data))
    before = target.read_bytes()
    if mode == 'included':
        modules.restore_qualified_overlay(work, output, spec)
        assert (output / 'imageformats/overlay-intake.json').exists()
    else:
        with pytest.raises(AssertionError):
            modules.restore_qualified_overlay(work, output, spec)
    assert target.read_bytes() == before
