from __future__ import annotations

import hashlib
import json
from pathlib import Path

import apply_qt_cbor_upgrade as cbor
import pytest
from verify_native_runtime_pilot import qt_cbor_regressions


@pytest.mark.parametrize('changed', ['archive', 'qt-glue'])
def test_changed_original_or_qt_glue_stops_before_vendor_patch(tmp_path, monkeypatch, changed):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    archive = tmp_path / 'original.tar.gz'
    archive.write_bytes(b'original source fixture')
    source = tmp_path / 'source'
    source.mkdir()
    glue = source / 'tinycbor-version.h'
    glue.write_bytes(b'Qt-owned zero version sentinel')
    spec = {'source': {'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
            'qt_owned_unchanged': {'tinycbor-version.h': hashlib.sha256(glue.read_bytes()).hexdigest()}}
    (scripts / 'qt_cbor_provider_sources.json').write_text(json.dumps(spec))
    if changed == 'archive':
        archive.write_bytes(b'unreviewed source')
    else:
        glue.write_bytes(b'unreviewed Qt glue')
    calls = []
    monkeypatch.setattr(cbor, 'REPO', tmp_path)
    monkeypatch.setattr(cbor, 'apply_source_patch', lambda *a: calls.append(a))
    with pytest.raises(ValueError, match='original|Qt-owned'):
        cbor.apply_upgrade(source, archive, tmp_path / 'evidence')
    assert calls == [] and not (tmp_path / 'evidence').exists()


def test_qt_cbor_partial_values_still_require_explicit_parser_errors():
    # Local fixture/API regression; updated TinyCBOR is qualified by the rebuilt native pilot.
    result = qt_cbor_regressions()
    assert result['qiodevice_read_write'] == 'PASS'
    assert {case['input']: case['error'] for case in result['negative']} == {
        '1b00': 'EndOfFile', 'bf6161': 'EndOfFile', 'ff': 'UnexpectedBreak', '8201': 'EndOfFile'}


def test_tinycbor_source_patch_preserves_qt_export_and_version_adapters():
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / '.github/scripts/qt_cbor_provider_sources.json').read_text())
    assert hashlib.sha256((root / spec['patch']['path']).read_bytes()).hexdigest() == spec['patch']['sha256']
    assert not set(spec['patch']['files']).intersection(spec['qt_owned_unchanged'])
    assert len(spec['upstream_selected_files']) == 13
