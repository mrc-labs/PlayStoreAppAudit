from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import apply_qt_http_limits as limits
import probe_qt_http_limits as probe
import pytest


@pytest.mark.parametrize('changed', ['original', 'second-patch'])
def test_unreviewed_source_or_second_patch_stops_before_first_mutation(tmp_path, monkeypatch, changed):
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    source = tmp_path / 'source'
    source.mkdir()
    original = source / 'parser.cpp'
    original.write_bytes(b'original source')
    patches = []
    for number in range(2):
        patch = tmp_path / f'{number}.patch'
        patch.write_bytes(str(number).encode())
        patches.append({'path': patch.name, 'sha256': hashlib.sha256(patch.read_bytes()).hexdigest()})
    spec = {'original_files': {'parser.cpp': hashlib.sha256(original.read_bytes()).hexdigest()}, 'patches': patches}
    (scripts / 'qt_http_security_sources.json').write_text(json.dumps(spec))
    if changed == 'original':
        original.write_bytes(b'unknown source')
    else:
        (tmp_path / '1.patch').write_bytes(b'unknown patch')
    calls = []
    monkeypatch.setattr(limits, 'REPO', tmp_path)
    monkeypatch.setattr(limits, 'apply_source_patch', lambda *a: calls.append(a))
    with pytest.raises(ValueError, match='Changed'):
        limits.apply_limits(source, tmp_path / 'evidence')
    assert calls == [] and not (tmp_path / 'evidence').exists()


@pytest.mark.parametrize('invalid', ['', 'missing', 'skipped', 'notrun', 'failure', 'error', 'duplicate', 'replaced-row'])
def test_acceptance_requires_all_actual_upstream_cases(tmp_path, invalid):
    suite = ET.Element('testsuite')
    names = ['headerSizeLimit(' + name + ')' for name in (
        'empty', 'within-limit', 'within-limit-LFLF', 'at-limit',
        'over-limit-terminated', 'over-limit-unterminated', 'over-limit-unterminated-lines')]
    names.append('statusLineSizeLimit')
    if invalid == 'missing':
        names.pop()
    if invalid == 'duplicate':
        names.append('statusLineSizeLimit')
    if invalid == 'replaced-row':
        names[0] = names[1]
    for name in names:
        case = ET.SubElement(suite, 'testcase', name=name)
        if name == names[0] and invalid in {'skipped', 'failure', 'error'}:
            ET.SubElement(case, invalid)
        if name == names[0] and invalid == 'notrun':
            case.set('status', 'notrun')
    path = tmp_path / 'actual-upstream.xml'
    ET.ElementTree(suite).write(path)
    if invalid:
        with pytest.raises(ValueError, match='did not all execute|failed'):
            limits.executed_limits(path)
    else:
        assert limits.executed_limits(path) == {'headerSizeLimit': 7, 'statusLineSizeLimit': 1}


def test_official_patch_bytes_and_dependency_order_are_preserved():
    root = Path(__file__).resolve().parents[1]
    spec = limits.contract()
    first, second = spec['patches']
    assert first['official_url'].endswith('0002.diff') and second['official_url'].endswith('0001.diff')
    for patch in spec['patches']:
        assert hashlib.sha256((root / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    for name, hashes in second['files'].items():
        assert first['files'][name]['patched_sha256'] == hashes['base_sha256']
        assert hashes['patched_sha256'] == spec['final_files'][name]


@pytest.mark.parametrize('bad', ['', 'foreign', 'openssl3', 'sdk', 'missing-backend'])
def test_native_http_smoke_requires_private_openssl4_and_no_link_sdk(tmp_path, bad):
    prefix, sdk = tmp_path / 'private', tmp_path / 'link-sdk'
    names = ['libQt6Core.so.6.12.0', 'libQt6Network.so.6.12.0', 'libssl.so.4',
             'libcrypto.so.4', 'libqopensslbackend.so']
    paths = [prefix / 'lib' / name for name in names]
    if bad == 'foreign':
        paths[0] = tmp_path / 'foreign/libQt6Core.so.6.12.0'
    if bad == 'openssl3':
        paths.append(prefix / 'lib/libssl.so.3')
    if bad == 'sdk':
        paths.append(sdk / 'libstdc++.so.6')
    if bad == 'missing-backend':
        paths.pop()
    lines = ['address permissions offset device inode ' + str(path) for path in paths]
    if bad:
        with pytest.raises(ValueError):
            probe.loaded_images(lines, prefix, sdk)
    else:
        assert set(probe.loaded_images(lines, prefix, sdk)) == set(paths)
