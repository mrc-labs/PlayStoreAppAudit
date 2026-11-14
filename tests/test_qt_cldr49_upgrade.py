from __future__ import annotations

import hashlib
import json
from pathlib import Path

import apply_qt_cldr49 as cldr
import pytest


def test_changed_original_locale_source_stops_before_generator_or_patch(tmp_path, monkeypatch):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    spec = {'original_files': {'qlocale_data_p.h': hashlib.sha256(b'original').hexdigest()}}
    (scripts / 'qt_cldr49_sources.json').write_text(json.dumps(spec))
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'qlocale_data_p.h').write_bytes(b'unreviewed data')
    calls = []
    monkeypatch.setattr(cldr, 'REPO', tmp_path)
    monkeypatch.setattr(cldr, 'apply_source_patch', lambda *args: calls.append(args))
    with pytest.raises(ValueError, match='Changed original Qt locale source'):
        cldr.apply_cldr49(source, tmp_path / 'archives', tmp_path / 'evidence')
    assert not calls and not (tmp_path / 'evidence').exists()


def test_locale_coverage_uses_full_language_script_territory_identity():
    header = 'constexpr QLocaleData locale_data[] = {\n { 126, 66, 48, 99 },\n {126, 4, 48, 88},\n};'
    assert cldr.locale_keys(header) == {(126, 66, 48), (126, 4, 48)}
    with pytest.raises(ValueError, match='Missing Qt locale data table'):
        cldr.locale_keys('unrecognized source layout')


def test_closed_cldr_recipe_keeps_complete_registry_out_of_build_inputs():
    repo = Path(__file__).resolve().parents[1]
    spec = json.loads((repo / '.github/scripts/qt_cldr49_sources.json').read_text())
    assert {item['name'] for item in spec['sources']} == {'cldr-common-49.zip', 'cldr-exemplars-delta-49.zip'}
    for patch in spec['patches']:
        assert hashlib.sha256((repo / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    assert spec['baseline_locale_keys'] == 711 and spec['generated_locale_keys'] == 714
    assert spec['retained_code_records'] == 349
