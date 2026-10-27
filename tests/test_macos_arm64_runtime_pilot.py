from __future__ import annotations

import json
from pathlib import Path

import probe_macos_arm64_runtime as probe
import pytest

ROOT = Path(__file__).resolve().parents[1]


def commands(minimum: str, *, legacy: bool = False) -> str:
    deployment = f'cmd LC_VERSION_MIN_MACOSX\nversion {minimum}' if legacy else f'cmd LC_BUILD_VERSION\nplatform 1\nminos {minimum}'
    return f'''Load command 0
 {deployment}
 sdk 26.6
Load command 1
 cmd LC_RPATH
 path @loader_path/../lib (offset 12)
Load command 2
 cmd LC_ID_DYLIB
 name @rpath/libprobe.dylib (offset 24)
Load command 3
 cmd LC_LOAD_DYLIB
 name /usr/lib/libSystem.B.dylib (offset 24)
'''


@pytest.mark.parametrize('legacy', [False, True])
def test_macho_deployment_and_load_commands_are_measured_per_image(legacy: bool) -> None:
    row = probe.load_commands(commands('14.4', legacy=legacy))
    assert row == {'minimum_os': ['14.4'], 'sdk': ['26.6'], 'rpaths': ['@loader_path/../lib'], 'install_names': ['@rpath/libprobe.dylib'], 'dependencies': ['/usr/lib/libSystem.B.dylib']}


def test_missing_deployment_metadata_cannot_be_a_compatibility_pass() -> None:
    with pytest.raises(AssertionError, match='Missing Mach-O'):
        probe.load_commands('Load command 0\ncmd LC_RPATH\npath @rpath (offset 12)')


def test_raw_macho_measurement_is_retained_for_independent_review(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / 'image'
    path.write_bytes(b'Mach-O fixture')
    raw = commands('14.4')
    monkeypatch.setattr(probe, 'run', lambda argv: 'arm64' if argv[0] == 'lipo' else raw)
    evidence = tmp_path / 'evidence'
    row = probe.macho(path, target=True, output=evidence)
    assert (evidence / ('image-' + row['sha256'][:12] + '-otool.txt')).read_text() == raw


def test_ios_metadata_cannot_pass_as_macos() -> None:
    with pytest.raises(AssertionError, match='Non-macOS'):
        probe.load_commands(commands('14.4').replace('platform 1', 'platform 2'))


@pytest.mark.parametrize('minimum,allowed', [('11.0', True), ('14.4', True), ('15.0', True), ('15.1', False), ('26.0', False)])
def test_main_executable_minimum_cannot_hide_a_new_library_floor(tmp_path: Path, monkeypatch, minimum: str, allowed: bool) -> None:
    path = tmp_path / 'image'
    path.write_bytes(b'actual measured Mach-O fixture')
    monkeypatch.setattr(probe, 'run', lambda argv: 'arm64' if argv[0] == 'lipo' else commands(minimum))
    if allowed:
        assert probe.macho(path, target=True)['minimum_os'] == [minimum]
    else:
        with pytest.raises(AssertionError, match='Raised package floor'):
            probe.macho(path, target=True)
    # A parser host tool may have a newer floor; it is never an app baseline.
    assert probe.macho(path, target=False)['role'].startswith('native host')


@pytest.mark.parametrize('architectures,allow_vendor,allowed', [('x86_64', False, False), ('arm64 x86_64', False, False), ('arm64 x86_64', True, True), ('arm64e', True, False)])
def test_controlled_target_is_native_and_vendor_universal_slice_is_explicit(tmp_path: Path, monkeypatch, architectures: str, allow_vendor: bool, allowed: bool) -> None:
    path = tmp_path / 'image'
    path.write_bytes(b'Mach-O fixture')
    monkeypatch.setattr(probe, 'run', lambda argv: architectures if argv[0] == 'lipo' else commands('14.4'))
    if allowed:
        assert probe.macho(path, target=True, allow_universal=allow_vendor)['selected_slice'] == 'arm64'
    else:
        with pytest.raises(AssertionError):
            probe.macho(path, target=True, allow_universal=allow_vendor)


def test_mac_contract_reuses_qualified_sources_without_changing_prior_profiles() -> None:
    arm, base = probe.contract()
    windows = json.loads((ROOT / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    assert base['sources'][0]['directory'] == 'Python-3.14.10'
    assert arm['zlib_source'] == windows['sources'][-1]
    assert arm['python_deployment'] == '11.0'
    assert arm['framework_deployment'] == '14.4'
    assert arm['accepted_package_maximum'] == '15.0'
    assert all('universal2.whl' in wheel['name'] for wheel in arm['probe_wheels'])
    assert arm['xz_source']['directory'] == 'xz-5.8.4' and arm['zstd_source']['directory'] == 'zstd-1.5.7'


@pytest.mark.parametrize('second', ['<testcase name="test.test_zstd.test_roundtrip"/>', '<testcase name="test.test_zstd.test_roundtrip"><skipped/></testcase>', '<testcase name="test.test_zstd.test_roundtrip" status="notrun"/>', ''])
def test_new_codec_integrations_cannot_pass_with_an_absent_or_skipped_suite(tmp_path: Path, second: str) -> None:
    from verify_macos_arm64_runtime_pilot import executed_codec_suites

    path = tmp_path / 'codecs.xml'
    path.write_text('<testsuite><testcase name="test.test_lzma.test_roundtrip"/>' + second + '</testsuite>')
    if second == '<testcase name="test.test_zstd.test_roundtrip"/>':
        assert executed_codec_suites(path) == {'test_lzma': 1, 'test_zstd': 1}
    else:
        with pytest.raises(AssertionError, match='actually execute'):
            executed_codec_suites(path)


@pytest.mark.parametrize('relative,allowed', [('prefix/lib/libssl.4.dylib', True), ('venv/lib/native.so', True), ('host-tools/lib/libwrong.dylib', False), ('src/libclang/lib/libclang.dylib', False)])
def test_runtime_cannot_import_a_host_or_build_tree_provider(tmp_path: Path, relative: str, allowed: bool) -> None:
    from verify_macos_arm64_runtime_pilot import allowed_origin

    assert allowed_origin(tmp_path / relative, tmp_path / 'prefix', tmp_path / 'venv') == allowed


def test_unused_sdk_driver_aliases_are_excluded_without_disabling_link_validation() -> None:
    arm, _ = probe.contract()
    arguments = probe.clang_extraction(Path('7zz'), Path('sdk.7z'), Path('src'), arm['host_libclang'])
    assert {arg for arg in arguments if isinstance(arg, str) and arg.startswith('-x!')} == {
        '-x!libclang/bin/clang++', '-x!libclang/bin/clang-cl', '-x!libclang/bin/clang-cpp'}
    assert not any(isinstance(arg, str) and arg.startswith(('-snl', '-spf')) for arg in arguments)


def test_perl_absolute_compiler_keeps_the_selected_sdk_through_build_and_tests(tmp_path: Path, monkeypatch) -> None:
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[:2] == ['xcrun', '--find']:
            return '/Xcode/usr/bin/clang\n'
        if argv[:2] == ['xcrun', '--sdk']:
            return '/Xcode/SDKs/MacOSX.sdk\n'
        if argv == ['make', 'test_harness']:
            return 'Files=2, Tests=14735\nResult: PASS\n'
        return 'version=5.44.0\n'

    monkeypatch.setattr(probe, 'fetch', lambda *args: tmp_path / 'source.tar.gz')
    monkeypatch.setattr(probe, 'unpack', lambda *args: None)
    monkeypatch.setattr(probe, 'macho', lambda *args, **kwargs: {'selected_slice': 'arm64'})
    monkeypatch.setattr(probe, 'run', run)
    report = probe.source_perl(tmp_path, tmp_path, {'host_perl_source': {}})
    configure = next(argv for argv, _ in calls if argv[:2] == ['sh', 'Configure'])
    assert '-Dccflags=-isysroot /Xcode/SDKs/MacOSX.sdk -arch arm64' in configure
    assert '-Dldflags=-isysroot /Xcode/SDKs/MacOSX.sdk -arch arm64' in configure
    for argv, kwargs in calls:
        if argv[0] in ('sh', 'make'):
            assert kwargs['env']['SDKROOT'] == report['sdk'] == '/Xcode/SDKs/MacOSX.sdk'


def test_diagnostic_route_preserves_ten_inputs_and_does_not_dispatch_intel_or_linux() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    assert workflow.count('        type: ') == 10
    linux, mac = workflow.split('\n  macos-arm64-runtime-pilot:', 1)
    assert "inputs.linux_arm64_pilot == 'prerequisites' || inputs.linux_arm64_pilot == 'full'" in linux
    assert 'runs-on: macos-26\n' in mac and 'matrix:' not in mac and 'macos-26-intel' not in mac
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in mac
    assert "test '${{ inputs.component_audit }}' = false" in mac
    assert 'build-macos.yml' not in mac and 'notarytool' not in mac and 'DEVELOPER_ID' not in mac
    assert mac.index('Qualify native SDK, sources, trust and parser') < mac.index('Build and exercise the gated')
    assert "if: ${{ inputs.linux_arm64_pilot == 'macos-full' }}" in mac


def test_darwin_build_tests_use_upstreams_case_insensitive_executable_name() -> None:
    recipe = (ROOT / '.github/scripts/build_macos_arm64_runtime_pilot.sh').read_text()
    assert 'test -f ./python.exe && test -x ./python.exe' in recipe
    assert './python -' not in recipe
    assert recipe.count('./python.exe -') == 4
