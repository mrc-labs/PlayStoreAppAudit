from __future__ import annotations

import hashlib
import io
import zipfile

import pytest
import reuse_linux_arm64_pilot as reuse


def test_changed_noble_sdk_zip_stops_before_restore(tmp_path):
    with pytest.raises(ValueError, match='Changed original Noble ARM64 diagnostic ZIP'):
        reuse.restore(b'unreviewed SDK', tmp_path, tmp_path)
    assert not list(tmp_path.iterdir())


def test_changed_compiled_arm64_input_stops_before_restore(tmp_path, monkeypatch):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    (scripts / 'native_runtime_pilot_sources.json').write_text('{"changed": true}')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('native_runtime_pilot_sources.json', '{"original": true}')
    raw = buffer.getvalue()
    monkeypatch.setattr(reuse, 'DIGEST', hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(reuse, 'REPO', tmp_path)
    with pytest.raises(ValueError, match='Changed compiled ARM64 contract'):
        reuse.restore(raw, tmp_path / 'evidence', tmp_path)
    assert not (tmp_path / 'evidence').exists()
