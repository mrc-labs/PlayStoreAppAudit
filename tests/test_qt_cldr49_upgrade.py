from __future__ import annotations

import hashlib
import io
import json
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

import apply_qt_cldr49 as cldr
import pytest
from probe_qt_cldr49_runtime import locale_identifiers


def test_qualified_cldr_cache_preserves_exact_locale_and_language_code_identity():
    spec = json.loads((cldr.REPO / '.github/scripts/qt_cldr49_sources.json').read_text())
    cache, files = cldr.qualified_generated(spec)
    assert len(files) == 9 and cache['origin']['artifact_id'] == 14143608998
    header = files['src/corelib/text/qlocale_data_p.h'].decode()
    assert len(cldr.locale_keys(header)) == 714
    import re

    codes = re.search(cldr.CODE_ARRAY, header, re.S)
    assert codes and int(codes[1]) == 349
    assert hashlib.sha256(codes[0].encode()).hexdigest() == spec['retained_code_sha256']


@pytest.mark.parametrize('extra_member,content', [(True, b'original'), (False, b'changed')])
def test_qualified_cldr_cache_rejects_unreviewed_members_and_output(tmp_path, monkeypatch, extra_member, content):
    scripts, sources = tmp_path / '.github/scripts', tmp_path / '.github/sources'
    scripts.mkdir(parents=True)
    sources.mkdir()
    spec = {'generated_files': {'locale.h': hashlib.sha256(b'original').hexdigest()}}
    archive = sources / 'cache.tar.xz'
    with tarfile.open(archive, 'w:xz') as bundle:
        member = tarfile.TarInfo('locale.h')
        member.size = len(content)
        bundle.addfile(member, io.BytesIO(content))
        if extra_member:
            member = tarfile.TarInfo('../../unexpected.h')
            member.size = 1
            bundle.addfile(member, io.BytesIO(b'x'))
    cache = {'source_contract_canonical_sha256': hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
             'archive': '.github/sources/cache.tar.xz', 'bytes': archive.stat().st_size,
             'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()}
    (scripts / 'qt_cldr49_generated_cache.json').write_text(json.dumps(cache))
    monkeypatch.setattr(cldr, 'REPO', tmp_path)
    with pytest.raises(ValueError, match='Unexpected qualified|Changed qualified CLDR generated'):
        cldr.qualified_generated(spec)
    assert not (tmp_path / 'unexpected.h').exists()


def test_cldr_display_names_and_qt_zero_sentinels_are_distinct():
    root = ET.fromstring('<localeDatabase><languageList><naming id="0" code="  ">AnyLanguage</naming>'
                         '</languageList><scriptList><naming id="0" code="Zzzz">Unknown Script</naming>'
                         '</scriptList><territoryList><naming id="0" code="ZZ">Unknown Region</naming>'
                         '</territoryList></localeDatabase>')
    ids = locale_identifiers(root)
    assert ids['script']['AnyScript'] == ids['script']['Unknown Script'] == 0
    assert ids['territory']['AnyTerritory'] == ids['territory']['Unknown Region'] == 0
    with pytest.raises(KeyError):
        _ = ids['script']['unreviewed-script']


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


def test_pyside_territory_argument_uses_exposed_country_enum():
    from PySide6.QtCore import QLocale

    # PySide6 exposes Qt's territory enum under its compatibility name Country.
    locale = QLocale(QLocale.English, QLocale.AnyScript, QLocale.Country.UnitedStates)
    assert locale.territory() == QLocale.Country.UnitedStates


def test_short_locale_date_requires_explicit_fixture_century():
    from PySide6.QtCore import QDate, QLocale

    locale = QLocale('en_US')
    date = QDate(2026, 11, 14)
    rendered = locale.toString(date, QLocale.ShortFormat)
    assert locale.toDate(rendered, QLocale.ShortFormat).year() == 1926
    assert locale.toDate(rendered, QLocale.ShortFormat, 2000) == date
