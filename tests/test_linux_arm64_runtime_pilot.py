from __future__ import annotations

import hashlib
import json
from pathlib import Path

import probe_linux_arm64_runtime as probe
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_linux_generator_paths_use_qt_reported_libexec(tmp_path: Path) -> None:
    info = {name:str(tmp_path / name) for name in ('cmake', 'ninja', 'libexec', 'generator')}
    paths = probe.generator_paths(info)
    assert paths[2:4] == [tmp_path / 'libexec/uic', tmp_path / 'libexec/rcc']
    assert paths[-1] == tmp_path / 'generator/shiboken6'


@pytest.mark.parametrize('glibc,glibcxx,allowed', [('2.38','3.4.32',True), ('2.39','3.4.32',False), ('2.38','3.4.33',False)])
def test_arm64_application_abi_cannot_inherit_host_or_x64_limits(tmp_path: Path, monkeypatch, glibc, glibcxx, allowed) -> None:
    path = tmp_path / 'probe'
    path.write_bytes(b'\x7fELFactual target probe')
    version = f'Version needs section\n Name: GLIBC_{glibc}\n Name: GLIBCXX_{glibcxx}\n'
    monkeypatch.setattr(probe, 'readelf', lambda _, option:' Machine: AArch64\n' if option == '--file-header' else version)
    if allowed:
        assert probe.elf(path, target=True)['machine'] == 'AArch64'
    else:
        with pytest.raises(AssertionError):
            probe.elf(path, target=True)
    # Host tools may require Noble's libc; this never changes the app ceiling.
    assert probe.elf(path, target=False)['role'].startswith('native build-host')


def test_arm64_probe_rejects_an_emulated_host_or_target(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / 'compiler'
    path.write_bytes(b'\x7fELF')
    monkeypatch.setattr(probe, 'readelf', lambda *args:' Machine: Advanced Micro Devices X86-64\n')
    with pytest.raises(AssertionError, match='Non-native ELF'):
        probe.elf(path, target=False)


def test_arm64_contract_keeps_source_hashes_but_selects_native_host_assets() -> None:
    arm, base = probe.contract()
    assert arm['base_manifest_canonical_sha256'] == hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert arm['machine'] == 'AArch64' and arm['os'] == '24.04'
    assert (arm['glibc_max'], arm['glibcxx_max']) == ('2.38','3.4.32')
    assert arm['openssl_target'] == 'linux-aarch64'
    assert 'arm64.7z' in arm['host_libclang']['name']
    assert 'linux-arm64' in arm['host_extractor']['name']
    assert all('aarch64.whl' in item['name'] for item in arm['probe_wheels'])
    assert 'win32' not in arm['host_perl_source']['native_makefile']


def test_current_security_python_override_keeps_the_reviewed_patch_bytes() -> None:
    arm, base = probe.contract()
    selected = probe.runtime_sources(arm, base)
    assert selected[0] == arm['cpython_source'] and selected[1:] == base['sources'][1:7]
    assert selected[0]['directory'] == 'Python-3.14.10'
    assert base['sources'][0]['directory'] == 'Python-3.14.9'
    assert arm['cpython_patch']['sha256'] == base['cpython_patch']['sha256']
    assert hashlib.sha256((ROOT / arm['cpython_patch']['path']).read_bytes()).hexdigest() == arm['cpython_patch']['sha256']
    assert 'Modules/_ssl/distrusted_spki.h' in arm['security_files']
    assert 'Lib/tarfile.py' in arm['security_files']


@pytest.mark.parametrize('outcome', ['', '<skipped/>', '<error/>', '<failure/>'])
def test_security_regression_requires_actual_unskipped_execution(tmp_path: Path, outcome: str) -> None:
    from verify_linux_arm64_runtime_pilot import require_security_case

    path = tmp_path / 'results.xml'
    path.write_text(f'<testsuite><testcase name="test.test_ssl.MemoryBIOTests.test_distrusted_spki">{outcome}</testcase></testsuite>')
    if not outcome:
        require_security_case(path)
    else:
        with pytest.raises(AssertionError, match='compromised-SPKI'):
            require_security_case(path)


def test_security_regression_cannot_accept_an_absent_case(tmp_path: Path) -> None:
    from verify_linux_arm64_runtime_pilot import require_security_case

    path = tmp_path / 'results.xml'
    path.write_text('<testsuite><testcase name="test_other"/></testsuite>')
    with pytest.raises(AssertionError, match='compromised-SPKI'):
        require_security_case(path)


def test_security_case_marked_notrun_is_rejected_even_without_skip_element(tmp_path: Path) -> None:
    from verify_linux_arm64_runtime_pilot import require_security_case

    path = tmp_path / 'results.xml'
    path.write_text('<testsuite><testcase name="test_distrusted_spki" status="notrun"/></testsuite>')
    with pytest.raises(AssertionError, match='compromised-SPKI'):
        require_security_case(path)


def test_arm64_diagnostic_does_not_select_x64_sysroot_or_other_jobs() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text(encoding='utf-8')
    prior, job = workflow.split('\n  linux-arm64-runtime-pilot:', 1)
    assert 'runs-on: ubuntu-24.04-arm' in job and 'matrix:' not in job
    assert 'test "$EXPECTED_SHA" = "${{ github.sha }}"' in job
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in job
    assert prior.count("(!inputs.linux_arm64_pilot || inputs.linux_arm64_pilot == 'off')") == 4
    assert 'provision_pilot_cxx_sdk' not in job and 'prepare_linux_x64_sysroot' not in job
    assert 'ubuntu-26' not in job
