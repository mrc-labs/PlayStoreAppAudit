from __future__ import annotations

import io
import json
import zipfile

import pytest
import reuse_linux_pre_qt_sdk as reuse


def test_changed_sdk_zip_fails_before_restore_or_execution(tmp_path):
    with pytest.raises(ValueError, match='Changed original integrated diagnostic ZIP'):
        reuse.restore(b'changed ZIP', tmp_path / 'evidence', tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('changed', ['native_runtime_pilot_sources.json', 'source_build_constraints.txt', 'qt_data_refresh_sources.json', 'qt_cldr49_sources.json'])
def test_changed_pre_qt_build_input_requires_new_qualification(tmp_path, monkeypatch, changed):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    names = ['native_runtime_pilot_sources.json', 'linux_x64_native_delta_sources.json',
             'qt_text_provider_sources.json', 'qt_cbor_provider_sources.json', 'qt_http_security_sources.json',
             'source_build_requirements.txt', 'source_build_constraints.txt', 'qt_data_refresh_sources.json', 'qt_cldr49_sources.json']
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, 'w') as archive:
        for name in names:
            payload = json.dumps({'original': True}).encode() if name.endswith('.json') else b'package==1.0\n'
            (scripts / name).write_bytes(payload)
            archive.writestr(name if name.endswith('.json') else 'build-dependencies/' + name, payload)
    (scripts / changed).write_text('{}' if changed.endswith('.json') else 'package==2.0\n')
    monkeypatch.setattr(reuse, 'REPO', tmp_path)
    with zipfile.ZipFile(raw) as archive, pytest.raises(ValueError, match='Changed .*contract'):
        reuse.unchanged_inputs(archive, with_qt=changed.startswith(('qt_data_', 'qt_cldr')))


def test_changed_matched_binding_zip_is_rejected_before_restore(tmp_path):
    with pytest.raises(ValueError, match='Changed original matched binding ZIP'):
        reuse.restore_bindings(b'unreviewed bindings', tmp_path)
    assert not list(tmp_path.iterdir())
