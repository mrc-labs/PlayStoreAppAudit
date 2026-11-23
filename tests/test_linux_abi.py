from __future__ import annotations

import json
import sys
from pathlib import Path

import inspect_linux_abi as abi
import pytest
from download_linux_compat_python import select_distribution


def test_version_needs_exclude_newer_exported_definitions() -> None:
    output = """Version definition section '.gnu.version_d' contains 1 entry:
  Name: GLIBCXX_3.4.99
Version needs section '.gnu.version_r' contains 3 entries:
  Name: GLIBC_2.9  Flags: none
  Name: GLIBC_2.35  Flags: none
  Name: GLIBCXX_3.4.29  Flags: none
"""
    names = abi.required_versions(output)
    assert "GLIBCXX_3.4.99" not in names
    assert abi.version_floor(names, "GLIBC_") == "GLIBC_2.35"
    assert abi.version_floor(names, "GLIBCXX_") == "GLIBCXX_3.4.29"
    assert abi.required_versions("Version definition section\nName: GLIBC_2.39") == []
    assert abi.version_floor(["GLIBC_PRIVATE", "GLIBC_ABI_DT_RELR"], "GLIBC_") is None


def test_wrong_architecture_in_nested_plugin_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    plugin = tmp_path / "plugins" / "platforms" / "libqxcb.so"
    plugin.parent.mkdir(parents=True)
    plugin.write_bytes(b"\x7fELF" + b"fake")
    monkeypatch.setattr(abi, "readelf", lambda *_: "  Machine: AArch64\n")
    with pytest.raises(RuntimeError, match="Wrong packaged architecture"):
        abi.inspect_package(tmp_path, "x64")


def test_empty_package_fails(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="Required packaged ELF missing"):
        abi.inspect_package(tmp_path, "x64")


def test_linux_migration_requires_real_old_runtime_smoke() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github/workflows/build-linux.yml").read_text(encoding="utf-8")
    assert "os: ubuntu-22.04\n" in workflow
    assert "os: ubuntu-24.04-arm\n" in workflow
    assert "prepare_linux_x64_sysroot.sh" not in workflow
    assert "inspect_linux_abi.py" in workflow
    assert "--expected-openssl-major 4" in workflow
    assert "ubuntu:22.04 bash /smoke.sh" in workflow
    assert "set -euo pipefail" in workflow
    smoke = (root / ".github/scripts/smoke_linux_ubuntu22.sh").read_text(encoding="utf-8")
    assert "./PlayStoreAppAudit cli audit --help" in smoke
    assert 'timeout 60s ./PlayStoreAppAudit\n' in smoke
    assert "QT_QPA_PLATFORM=xcb" in smoke


@pytest.mark.parametrize(('arch', 'glibc', 'glibcxx', 'accepted'), [
    ('x64', '2.35', '3.4.30', True),
    ('arm64', '2.39', '3.4.33', True),
    ('arm64', '2.38', '3.4.32', True),
    ('x64', '2.36', '3.4.30', False),
    ('x64', '2.35', '3.4.31', False),
    ('arm64', '2.40', '3.4.33', False),
    ('arm64', '2.39', '3.4.34', False),
])
def test_package_limits_follow_supported_os_not_historical_measurements(
    monkeypatch, tmp_path, arch, glibc, glibcxx, accepted,
):
    report = {'glibc': 'GLIBC_' + glibc, 'glibcxx': 'GLIBCXX_' + glibcxx, 'elf_files': []}
    monkeypatch.setattr(abi, 'inspect_package', lambda *_: report)
    output = tmp_path / 'abi.json'
    monkeypatch.setattr(sys, 'argv', ['inspect', str(tmp_path), '--arch', arch, '--output', str(output)])
    if accepted:
        assert abi.main() == 0
        assert json.loads(output.read_text())['compatibility_baseline'] == (
            'Ubuntu 22.04' if arch == 'x64' else 'Ubuntu 24.04'
        )
    else:
        with pytest.raises(RuntimeError, match='exceeds supported Ubuntu'):
            abi.main()


@pytest.mark.parametrize(('needed', 'selected', 'accepted'), [
    ('libssl.so.3', None, True),
    ('libcrypto.so.3', 3, True),
    ('libcrypto.so.4', 4, True),
    ('libssl.so.3', 4, False),
    ('libcrypto.so.4', 3, False),
])
def test_openssl_inspection_enforces_selected_provider_without_global_major_ban(
    monkeypatch, tmp_path, needed, selected, accepted,
):
    report = {'glibc': 'GLIBC_2.39', 'glibcxx': 'GLIBCXX_3.4.33',
              'elf_files': [{'path': '_ssl.so', 'needed': [needed], 'search_paths': ['$ORIGIN']}]}
    monkeypatch.setattr(abi, 'inspect_package', lambda *_: report)
    output = tmp_path / 'abi.json'
    args = ['inspect', str(tmp_path), '--arch', 'arm64', '--output', str(output)]
    if selected is not None:
        args += ['--expected-openssl-major', str(selected)]
    monkeypatch.setattr(sys, 'argv', args)
    if accepted:
        assert abi.main() == 0
        assert json.loads(output.read_text())['expected_openssl_major'] == selected
    else:
        with pytest.raises(RuntimeError, match='provider contract mismatch'):
            abi.main()


def test_provider_neutral_inspection_still_rejects_build_prefix(monkeypatch, tmp_path):
    report = {'glibc': 'GLIBC_2.39', 'glibcxx': None,
              'elf_files': [{'path': '_ssl.so', 'needed': ['libssl.so.3'],
                             'search_paths': ['/home/runner/private-sdk/lib']}]}
    monkeypatch.setattr(abi, 'inspect_package', lambda *_: report)
    monkeypatch.setattr(sys, 'argv', ['inspect', str(tmp_path), '--arch', 'arm64',
                                    '--output', str(tmp_path / 'abi.json')])
    with pytest.raises(RuntimeError, match='Build-prefix'):
        abi.main()


@pytest.mark.parametrize("version", ["3.14.8", "3.14.9"])
def test_compat_python_preserves_resolved_patch_and_rejects_prerelease(
    version: str,
) -> None:
    file = {
        "platform": "linux", "platform_version": "22.04", "arch": "x64",
        "filename": f"python-{version}-linux-22.04-x64.tar.gz",
        "download_url": "https://github.com/actions/python-versions/releases/download/tag/python.tar.gz",
    }
    manifest = [{"version": version, "stable": True, "files": [file]}]
    assert select_distribution(manifest, version) == file
    with pytest.raises(ValueError, match="Exactly one"):
        select_distribution(manifest, "3.14.10")
    with pytest.raises(ValueError, match="stable, full"):
        select_distribution(manifest, "3.14.8rc1")
    with pytest.raises(ValueError, match="Exactly one"):
        select_distribution([{**manifest[0], "stable": False}], version)
    with pytest.raises(ValueError, match="Unofficial"):
        select_distribution([{**manifest[0], "files": [{**file, "download_url": "https://example.org/python"}]}], version)
