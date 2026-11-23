from __future__ import annotations

import hashlib

import probe_qt_text_providers as providers
import pytest


@pytest.mark.parametrize('corrupt', [False, True])
def test_declared_publisher_snapshot_is_exact_and_never_network_fallback(tmp_path, monkeypatch, corrupt):
    source = tmp_path / '.github/sources/list.dat'
    source.parent.mkdir(parents=True)
    original = b'// Original publisher notice\nexample\n'
    source.write_bytes(original + (b'changed' if corrupt else b''))
    item = {'name': 'public_suffix_list.dat', 'url': 'https://publicsuffix.org/list/public_suffix_list.dat',
            'sha256': hashlib.sha256(original).hexdigest(), 'retained_source': '.github/sources/list.dat'}
    monkeypatch.setattr(providers, 'REPO', tmp_path)
    monkeypatch.setattr(providers.urllib.request, 'urlopen', lambda *a, **k: pytest.fail('Unexpected network fallback'))
    if corrupt:
        with pytest.raises(ValueError, match='Changed official source digest'):
            providers.checked_source(item, tmp_path)
        assert not (tmp_path / item['name']).exists()
    else:
        assert providers.checked_source(item, tmp_path).read_bytes() == original


def test_retained_source_cannot_escape_the_declared_source_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, 'REPO', tmp_path)
    with pytest.raises(ValueError, match='escapes repository source directory'):
        providers.checked_source({'name': 'list.dat', 'url': 'https://publicsuffix.org/list/public_suffix_list.dat',
                                  'retained_source': '../other-project/list.dat'}, tmp_path)
