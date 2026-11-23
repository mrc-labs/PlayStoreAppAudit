from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

import probe_macos_x64_runtime as probe
import pytest
import verify_macos_x64_runtime_pilot as verify

ROOT = Path(__file__).resolve().parents[1]


def raw_commands(minimum: str) -> str:
    return f"Load command 0\ncmd LC_BUILD_VERSION\nplatform 1\nminos {minimum}\nsdk 26.5\nLoad command 1\ncmd LC_LOAD_DYLIB\nname /usr/lib/libSystem.B.dylib (offset 24)"


@pytest.mark.parametrize('architectures,vendor,allowed', [
    ('x86_64', False, True), ('arm64', False, False),
    ('x86_64 arm64', False, False), ('x86_64 arm64', True, True),
    ('x86_64 arm64e', True, False),
])
def test_intel_native_slice_is_required_and_controlled_targets_are_thin(tmp_path, monkeypatch, architectures, vendor, allowed):
    image = tmp_path / 'image'
    image.write_bytes(b'native fixture')
    monkeypatch.setattr(probe, 'run', lambda argv: architectures if argv[0] == 'lipo' else raw_commands('14.4'))
    if allowed:
        assert probe.macho(image, target=True, allow_universal=vendor)['selected_slice'] == 'x86_64'
    else:
        with pytest.raises(AssertionError):
            probe.macho(image, target=True, allow_universal=vendor)


@pytest.mark.parametrize('minimum,allowed', [('10.15', True), ('14.4', True), ('26.0', True), ('26.1', False)])
def test_each_loaded_image_respects_the_existing_package_ceiling(tmp_path, monkeypatch, minimum, allowed):
    image = tmp_path / 'image'
    image.write_bytes(b'native fixture')
    monkeypatch.setattr(probe, 'run', lambda argv: 'x86_64' if argv[0] == 'lipo' else raw_commands(minimum))
    if allowed:
        assert probe.macho(image, target=True)['minimum_os'] == [minimum]
    else:
        with pytest.raises(AssertionError, match='Raised package floor'):
            probe.macho(image, target=True)
    assert probe.macho(image, target=False)['role'].startswith('native host')


def test_intel_contract_preserves_the_qualified_sources_and_separates_deployment():
    intel, base = probe.contract()
    arm = json.loads((ROOT / '.github/scripts/macos_arm64_runtime_pilot_sources.json').read_text())
    assert intel['base_manifest_canonical_sha256'] == arm['base_manifest_canonical_sha256']
    for key in ('zlib_source', 'xz_source', 'zstd_source', 'certifi_source', 'certifi_wheel', 'cryptography_source', 'host_libclang', 'host_perl_source'):
        if key == 'host_libclang':
            assert intel[key]['sha256'] == arm[key]['sha256']
        else:
            assert {k: v for k, v in intel[key].items() if k != 'scope'} == {k: v for k, v in arm[key].items() if k != 'scope'}
    assert base['sources'][0]['directory'] == 'Python-3.14.10'
    assert (intel['python_deployment'], intel['framework_deployment'], intel['accepted_package_maximum']) == ('10.15', '14.4', '26.0')
    assert intel['openssl_target'] == 'darwin64-x86_64-cc'
    helper = (ROOT / '.github/scripts/provision_macos_intel_crypto.sh').read_text()
    assert intel['host_rustup']['url'] in helper and intel['host_rustup']['sha256'] in helper
    assert intel['rust_std_source']['sha256'] and intel['rustup_source']['sha256']


@pytest.mark.parametrize('failure', ['', 'head', 'wheel', 'module', 'dynamic'])
def test_runtime_cryptography_must_match_retained_source_wheel_and_static_provider(tmp_path, monkeypatch, failure):
    monkeypatch.setenv('GITHUB_SHA', 'a' * 40)
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    wheel = wheels / 'cryptography-50.0.2-cp314-macosx.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('cryptography/hazmat/bindings/_rust.abi3.so', b'native fixture')
    image = tmp_path / '_rust.abi3.so'
    image.write_bytes(b'changed' if failure == 'module' else b'native fixture')
    report = {'source_sha': 'b' * 40 if failure == 'head' else os.environ['GITHUB_SHA'], 'wheel': wheel.name, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest()}
    if failure == 'wheel':
        report['wheel_sha256'] = '0' * 64
    (tmp_path / 'cryptography-source-provenance.json').write_text(json.dumps(report))
    monkeypatch.setattr(verify, 'macho', lambda *args, **kwargs: {'dependencies': ['/usr/lib/libSystem.B.dylib'] + (['@rpath/libssl.4.dylib'] if failure == 'dynamic' else [])})
    if failure:
        with pytest.raises(AssertionError):
            verify.source_wheel_provenance(tmp_path, image)
    else:
        assert verify.source_wheel_provenance(tmp_path, image)['runtime_module_matches_retained_wheel']


def test_dispatch_is_bounded_to_native_intel_and_full_build_is_explicit():
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    job = workflow.split('  macos-x64-runtime-pilot:', 1)[1]
    assert 'runs-on: macos-26-intel' in job
    assert "== 'macos-x64-prerequisites'" in job and "== 'macos-x64-full'" in job
    assert "if: ${{ inputs.linux_arm64_pilot == 'macos-x64-full' }}" in job
    assert 'test "$EXPECTED_SHA" = "${{ github.sha }}"' in job
    assert 'test "$RUNNER_ARCH" = X64' in job
    arm_job = workflow.split('  macos-arm64-runtime-pilot:', 1)[1].split('  macos-x64-runtime-pilot:', 1)[0]
    assert 'macos-x64' not in arm_job
    commands = job
    builder = (ROOT / '.github/scripts/build_macos_x64_runtime_pilot.sh').read_text()
    assert 'darwin64-x86_64-cc no-shared' in builder
    assert 'OPENSSL_STATIC=1 OPENSSL_NO_VENDOR=1' in builder
    assert 'rustc -vV | grep' in builder
    assert 'codesign --sign' not in commands + builder
