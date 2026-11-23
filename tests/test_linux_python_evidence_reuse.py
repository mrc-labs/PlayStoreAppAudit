from __future__ import annotations

import io
import json
import zipfile

import pytest
import reuse_linux_python_evidence as reuse


@pytest.mark.parametrize('changed', ['', 'python', 'requirements', 'constraints', 'providers', 'text', 'meson'])
def test_upstream_suite_reuse_requires_unchanged_actual_inputs(tmp_path, monkeypatch, changed):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    records = {'native_runtime_pilot_sources.json': {'sources': ['Python', 'png', 'pcre'], 'security': 'guarded'},
               'linux_x64_native_delta_sources.json': {'sources': ['zlib', 'ffi']},
               'qt_text_provider_sources.json': {'sources': ['HB', 'MD4C'], 'meson': ['matching-tool']}}
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, 'w') as archive:
        for name, value in records.items():
            data = json.dumps(value)
            archive.writestr(name, data)
            (scripts / name).write_text(data, encoding='utf-8')
        for name in ['source_build_requirements.txt', 'source_build_constraints.txt']:
            archive.writestr('build-dependencies/' + name, 'qualified\n')
            (scripts / name).write_text('qualified\n', encoding='utf-8')
    if changed == 'python':
        (scripts / 'native_runtime_pilot_sources.json').write_text('{"sources": ["new-Python"]}', encoding='utf-8')
    elif changed in {'requirements', 'constraints'}:
        (scripts / f'source_build_{changed}.txt').write_text('different\n', encoding='utf-8')
    elif changed in {'providers', 'text', 'meson'}:
        name = 'linux_x64_native_delta_sources.json' if changed == 'providers' else 'qt_text_provider_sources.json'
        value = records[name]
        value['meson' if changed == 'meson' else 'sources'] = ['changed']
        (scripts / name).write_text(json.dumps(value), encoding='utf-8')
    monkeypatch.setattr(reuse, 'REPO', tmp_path)
    with zipfile.ZipFile(payload) as archive:
        if changed:
            with pytest.raises(ValueError, match='require'):
                reuse.unchanged_inputs(archive)
        else:
            reuse.unchanged_inputs(archive)
