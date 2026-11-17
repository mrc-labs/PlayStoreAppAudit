from __future__ import annotations

import hashlib
import json
from pathlib import Path

import provision_nuitka_scons as provision
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_controlled_compiler_has_labelled_stable_sources_and_reviewed_patch_hashes():
    manifest = json.loads((ROOT / '.github/scripts/nuitka_scons_sources.json').read_text())
    assert manifest['distribution_version'] == '4.3.5+psaa.scons4111'
    assert [s['version'] for s in manifest['sources']] == ['4.3.5', '4.11.1']
    for item in manifest['sources']:
        assert item['url'].startswith('https://files.pythonhosted.org/') and len(item['sha256']) == 64
        assert item['authority'].startswith('https://pypi.org/pypi/')
    for key in ['nuitka_patch', 'scons_patch']:
        patch = manifest[key]
        assert hashlib.sha256((ROOT / patch['path']).read_bytes()).hexdigest() == patch['sha256']
        assert all(h['base_sha256'] != h['patched_sha256'] for h in patch['files'].values())
    source = (ROOT / '.github/scripts/provision_nuitka_scons.py').read_text()
    assert '--no-index' in source and '--no-deps' in source and '--no-build-isolation' in source
    assert '--experimental' not in source and 'force-system-scons' not in source


@pytest.mark.parametrize('changed', ['patch', 'source'])
def test_changed_source_or_patch_aborts_before_git_or_build(tmp_path, monkeypatch, changed):
    patch_file = tmp_path / 'reviewed.patch'
    patch_file.write_bytes(b'patch fixture')
    (tmp_path / 'source.py').write_bytes(b'original fixture')
    patch = {'path': 'reviewed.patch', 'sha256': hashlib.sha256(patch_file.read_bytes()).hexdigest(),
             'files': {'source.py': {'base_sha256': hashlib.sha256(b'original fixture').hexdigest(), 'patched_sha256': '0' * 64}}}
    if changed == 'patch':
        patch_file.write_bytes(b'changed patch')
    else:
        (tmp_path / 'source.py').write_bytes(b'changed source')
    calls = []
    monkeypatch.setattr(provision, 'REPO', tmp_path)
    monkeypatch.setattr(provision.subprocess, 'run', lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match='Unexpected'):
        provision.apply_source_patch(tmp_path, patch)
    assert not calls
