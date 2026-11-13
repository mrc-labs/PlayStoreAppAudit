from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import apply_qt_ca_guard as qt_guard
import probe_qt_ca_security as ca_probe
import pytest
from verify_linux_x64_native_delta import STEMS, SUITES, executed_native_suites, provider_paths


@pytest.mark.parametrize('labels', [[], ['CertificateBlacklisted'], ['NoSslSupport']])
def test_unsupported_manual_verifier_never_claims_chain_acceptance_or_security_rejection(labels: list[str]) -> None:
    result = ca_probe.manual_chain_outcome(labels, supported=False)
    assert result['accepted'] is None and result['trust_rejected'] is None
    assert not result['manual_verification_supported']


@pytest.mark.parametrize('labels,accepted,rejected', [
    ([], True, False), (['CertificateBlacklisted'], False, True), (['HostNameMismatch'], False, False),
])
def test_supported_manual_verifier_preserves_actual_acceptance_and_rejection_reasons(labels, accepted, rejected) -> None:
    result = ca_probe.manual_chain_outcome(labels, supported=True)
    assert result['accepted'] is accepted and result['trust_rejected'] is rejected


@pytest.mark.parametrize('labels,expected', [
    ([], False), (['NoSslSupport'], False), (['CertificateSignatureFailed'], False),
    (['CertificateUntrusted'], True), (['CertificateBlacklisted'], True),
    (['UnableToGetLocalIssuerCertificate'], True),
    (['CertificateUntrusted', 'HostNameMismatch'], False),
    (['CertificateUntrusted', 'CertificateExpired'], False),
    (['CertificateRevoked', 'CertificateNotYetValid'], False),
])
def test_ca_rejection_requires_trust_policy_not_an_unrelated_failure(labels: list[str], expected: bool) -> None:
    assert ca_probe.trust_rejected(labels) is expected


@pytest.mark.parametrize('failure', ['missing', 'foreign', 'ambiguous'])
def test_provider_selection_rejects_system_fallback_or_multiple_images(tmp_path: Path, failure: str) -> None:
    prefix = tmp_path / 'private'
    paths = {prefix / 'lib' / (stem + '.9') for stem in STEMS.values()}
    if failure in {'missing', 'foreign'}:
        paths.remove(prefix / 'lib/libffi.so.9')
    if failure == 'foreign':
        paths.add(tmp_path / 'system/libffi.so.9')
    if failure == 'ambiguous':
        paths.add(prefix / 'lib/libffi.so.8')
    with pytest.raises(ValueError, match='libffi'):
        provider_paths(paths, prefix)


def test_private_provider_selection_has_exactly_one_native_image_per_component(tmp_path: Path) -> None:
    expected = {name: (tmp_path / 'lib' / (stem + '.9')).resolve() for name, stem in STEMS.items()}
    assert provider_paths(set(expected.values()), tmp_path) == expected


@pytest.mark.parametrize('failure', ['skipped', 'notrun', 'failure', 'error', 'absent'])
def test_native_regressions_require_every_affected_module_executed(tmp_path: Path, failure: str) -> None:
    root = ET.Element('testsuite')
    for name in SUITES:
        if name == 'test_ctypes' and failure == 'absent':
            continue
        case = ET.SubElement(root, 'testcase', name=name + '.NativeCase.test_call')
        if name == 'test_ctypes':
            if failure == 'notrun':
                case.set('status', 'notrun')
            else:
                ET.SubElement(case, failure)
    path = tmp_path / 'native.xml'
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError):
        executed_native_suites(path)


def test_native_regressions_accept_cpython_name_only_junit(tmp_path: Path) -> None:
    root = ET.Element('testsuite')
    for name in SUITES:
        ET.SubElement(root, 'testcase', name=name + ('.CNativeCase.test_call' if name == 'test_decimal' else '.NativeCase.test_call'))
    path = tmp_path / 'native.xml'
    ET.ElementTree(root).write(path)
    assert executed_native_suites(path) == {**dict.fromkeys(SUITES, 1), 'test_decimal_C': 1}


def test_python_only_decimal_does_not_qualify_the_native_provider(tmp_path: Path) -> None:
    root = ET.Element('testsuite')
    for name in SUITES:
        ET.SubElement(root, 'testcase', name=name + '.PythonOnly.test_call')
    path = tmp_path / 'native.xml'
    ET.ElementTree(root).write(path)
    with pytest.raises(ValueError):
        executed_native_suites(path)


@pytest.mark.parametrize('downgrade', [False, True])
def test_unverified_ca_fixtures_never_reach_the_certificate_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, downgrade: bool
) -> None:
    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    (scripts / 'provider_ca_security_sources.json').write_text(json.dumps({'sources': [
        {'name': 'chain.json', 'url': 'https://fixture.invalid/chain', 'sha256': '0' * 64}]}))
    output = tmp_path / 'evidence'
    output.mkdir()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def geturl(self):
            return ('http' if downgrade else 'https') + '://fixture.invalid/chain'

        def read(self):
            return b'changed untrusted fixture'

    monkeypatch.setattr(ca_probe, 'REPO', tmp_path)
    monkeypatch.setattr(ca_probe.urllib.request, 'urlopen', lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match='downgrade|Changed reviewed'):
        ca_probe.fetch_inputs(output)
    assert not list((output / 'inputs').iterdir())


@pytest.mark.parametrize('altered', ['patch', 'source'])
def test_qt_guard_refuses_changed_patch_or_original_before_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, altered: str
) -> None:
    import hashlib

    scripts = tmp_path / '.github/scripts'
    scripts.mkdir(parents=True)
    patch = tmp_path / 'guard.patch'
    patch.write_bytes(b'reviewed patch')
    source = tmp_path / 'qt'
    source.mkdir()
    target = source / 'certificate.cpp'
    target.write_bytes(b'original source')
    (scripts / 'linux_x64_native_delta_sources.json').write_text(json.dumps({'qt_ca_patch': {
        'path': 'guard.patch', 'file': 'certificate.cpp',
        'sha256': hashlib.sha256(patch.read_bytes()).hexdigest(),
        'base_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}}))
    (patch if altered == 'patch' else target).write_bytes(b'changed')
    monkeypatch.setattr(qt_guard, 'REPO', tmp_path)
    monkeypatch.setattr(qt_guard.subprocess, 'run', lambda *a, **kw: pytest.fail('Unreviewed source reached patch'))
    with pytest.raises(ValueError, match='Changed reviewed|Unexpected original'):
        qt_guard.apply_guard(source, tmp_path / 'evidence')
