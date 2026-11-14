from __future__ import annotations

import json
from pathlib import Path

import pytest
from probe_qt_text_providers import (
    checked_source,
    upstream_harfbuzz_results,
    validate_abi,
    validate_loaded_paths,
)


@pytest.mark.parametrize('machine,versions', [
    ('AArch64', ['GLIBC_2.35']),
    ('Advanced Micro Devices X86-64', ['GLIBC_2.36']),
    ('Advanced Micro Devices X86-64', ['GLIBCXX_3.4.30']),
])
def test_text_provider_prerequisite_preserves_the_existing_x64_floor(machine, versions):
    with pytest.raises(ValueError, match='x64|ABI'):
        validate_abi('Machine: ' + machine, versions)


def test_text_provider_abi_compares_numeric_needs_not_lexical_versions():
    assert validate_abi('Machine: Advanced Micro Devices X86-64', ['GLIBC_2.9', 'GLIBC_2.35', 'GLIBCXX_3.4.29']) == {
        'GLIBC_': 'GLIBC_2.35', 'GLIBCXX_': 'GLIBCXX_3.4.29'}


@pytest.mark.parametrize('failure', ['foreign', 'sdk', 'missing'])
def test_actual_text_consumer_rejects_fallback_or_link_sdk_runtime(tmp_path, failure):
    prefix, sdk = tmp_path / 'prefix', tmp_path / 'link-sdk'
    paths = [prefix / 'lib/libharfbuzz.so.0', prefix / 'lib/libmd4c.so.0', tmp_path / 'system/libstdc++.so.6']
    if failure == 'foreign':
        paths[0] = tmp_path / 'system/libharfbuzz.so.0'
    elif failure == 'sdk':
        paths[-1] = sdk / 'libstdc++.so.6'
    else:
        paths.pop(0)
    with pytest.raises(ValueError, match='fallback|runtime|Both actual'):
        validate_loaded_paths('\n'.join('address r-xp 0 0 0 ' + path.as_posix() for path in paths), prefix, sdk)


def test_actual_text_consumer_records_private_providers(tmp_path):
    prefix, sdk = tmp_path / 'prefix', tmp_path / 'sdk'
    paths = [prefix / 'lib/libharfbuzz.so.0', prefix / 'lib/libmd4c.so.0']
    assert validate_loaded_paths('\n'.join('address r-xp 0 0 0 ' + path.as_posix() for path in paths), prefix, sdk) == sorted(map(str, paths))


@pytest.mark.parametrize('failure', ['failed', 'skipped-required', 'empty'])
def test_upstream_security_shaping_tests_must_really_execute(failure):
    rows = [{'name': name, 'result': 'OK'} for name in ['test-font', 'test-map', 'test-shape', 'test-ot-nullable-output']]
    if failure == 'failed':
        rows.append({'name': 'malformed-font', 'result': 'FAIL'})
    elif failure == 'skipped-required':
        rows[-1]['result'] = 'SKIP'
    else:
        rows.clear()
    with pytest.raises(ValueError, match='failure|missing'):
        upstream_harfbuzz_results('\n'.join(map(json.dumps, rows)))


def test_upstream_results_preserve_optional_skip_counts():
    rows = [{'name': name, 'result': 'OK'} for name in ['test-font', 'test-map', 'test-shape', 'test-ot-nullable-output']]
    rows.append({'name': 'optional', 'result': 'SKIP'})
    assert upstream_harfbuzz_results('\n'.join(map(json.dumps, rows))) == {'OK': 4, 'SKIP': 1, 'EXPECTEDFAIL': 0}


@pytest.mark.parametrize('failure', ['scheme', 'downgrade', 'hash'])
def test_changed_source_stops_before_writing_or_executing(tmp_path, monkeypatch, failure):
    import probe_qt_text_providers as probe

    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def geturl(self): return 'http://bad.invalid/source' if failure == 'downgrade' else 'https://example.com/source'
        def read(self): return b'changed original source'

    monkeypatch.setattr(probe.urllib.request, 'urlopen', lambda *a, **k: Response())
    item = {'url': ('http' if failure == 'scheme' else 'https') + '://example.com/source', 'name': 'source.tar.gz', 'sha256': '0' * 64}
    with pytest.raises(ValueError, match='HTTPS|digest'):
        checked_source(item, tmp_path)
    assert not list(tmp_path.iterdir())


def test_text_preflight_cannot_dispatch_the_full_stack():
    workflow = (Path(__file__).resolve().parents[1] / '.github/workflows/ui-style-audit.yml').read_text()
    job = workflow.split('\n  runtime-pilot:', 1)[1].split('\n  windows-runtime-pilot:', 1)[0]
    assert "test '${{ inputs.runtime_pilot }}' = false" in job
    assert "test '${{ inputs.trust_diagnostics_only }}' = false" in job
    condition = job.split('Build and exercise one controlled native stack\n        if: ', 1)[1].splitlines()[0]
    assert '!inputs.trust_diagnostics_only' in condition
    for profile in ['qt-text-prerequisites', 'qt-http-limits']:
        assert "inputs.linux_arm64_pilot != '" + profile + "'" in condition
