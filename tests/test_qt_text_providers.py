from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from probe_qt_text_providers import (
    checked_source,
    reviewed_md4c_flags,
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
    for profile in ['qt-text-prerequisites', 'qt-http-limits', 'qt-md4c-flags', 'qt-cbor-sdk']:
        assert "inputs.linux_arm64_pilot != '" + profile + "'" in condition


def test_qt_markdown_public_dialect_keeps_front_matter_and_legacy_reference_links():
    # Existing official Qt behavior fixture; modified-source native adoption remains separate.
    from PySide6.QtWidgets import QApplication
    from verify_native_runtime_pilot import qt_markdown_flag_regressions

    app = QApplication.instance() or QApplication([])
    assert app
    assert qt_markdown_flag_regressions()['result'] == 'PASS fixed Qt Markdown dialect'


@pytest.mark.parametrize('changed', ['', 'public', 'private', 'provider', 'patched', 'expression'])
def test_md4c_early_probe_uses_only_guarded_actual_qt_flag_declarations(tmp_path, monkeypatch, changed):
    import probe_qt_text_providers as probe

    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    qt, md4c = tmp_path / 'qt', tmp_path / 'md4c'
    (qt / 'src/gui/text').mkdir(parents=True)
    (md4c / 'src').mkdir(parents=True)
    public, private = qt / 'public.h', qt / 'private.h'
    provider, patched = md4c / 'src/md4c.h', qt / 'src/gui/text/qtextmarkdownimporter.cpp'
    public.write_text('MarkdownDialectGitHub = 0x4 | 0x100000,\n')
    private.write_text('FeatureFrontMatter = 0x100000,\n')
    provider.write_bytes(b'original provider interface fixture')
    patched.write_text('        unsigned(m_features) & ~unsigned(FeatureFrontMatter),\n')
    if changed == 'expression':
        public.write_text('MarkdownDialectGitHub = 0x4 | unreviewed(),\n')
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    spec = {'qt_public_markdown_header': {'file': 'public.h', 'sha256': digest(public)},
            'qt_private_markdown_header': {'file': 'private.h', 'sha256': digest(private)},
            'md4c_header_sha256': digest(provider),
            'qt_md4c_patch': {'files': {'src/gui/text/qtextmarkdownimporter.cpp': {'patched_sha256': digest(patched)}}}}
    (scripts / 'qt_text_provider_sources.json').write_text(json.dumps(spec))
    (scripts / 'qt_md4c_flags_consumer.cpp').write_text('// consumer fixture\n')
    paths = {'public': public, 'private': private, 'provider': provider, 'patched': patched}
    if changed in paths:
        paths[changed].write_bytes(b'unreviewed source')
    monkeypatch.setattr(probe, 'REPO', tmp_path)
    output = tmp_path / 'output'
    if changed:
        with pytest.raises(ValueError, match='Changed|not applied|Unreviewed'):
            reviewed_md4c_flags(qt, md4c, output)
        assert not output.exists()
    else:
        header = reviewed_md4c_flags(qt, md4c, output).read_text()
        assert 'qtDialectGitHub = 0x4 | 0x100000;' in header
        assert 'return unsigned(m_features) & ~unsigned(FeatureFrontMatter);' in header
