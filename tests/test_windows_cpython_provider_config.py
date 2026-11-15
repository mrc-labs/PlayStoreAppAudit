from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from apply_windows_cpython_providers import apply  # noqa: E402


def test_foreign_project_is_preserved_and_rejected_before_patch(tmp_path: Path) -> None:
    source = tmp_path / 'source'
    project = source / 'PCbuild/libffi.props'
    project.parent.mkdir(parents=True)
    content = b'<Project>unexpected local/vendor work</Project>'
    project.write_bytes(content)
    with pytest.raises(AssertionError, match='PCbuild/libffi.props'):
        apply(source, tmp_path / 'evidence')
    assert project.read_bytes() == content


def test_source_route_is_scoped_to_three_build_files_without_c_implementation_changes() -> None:
    spec = json.loads((ROOT / '.github/scripts/windows_cpython_provider_config_sources.json').read_text())
    assert spec['source_version'] == '3.14.10'
    assert set(spec['patch']['files']) == {'PCbuild/libffi.props', 'PCbuild/pythoncore.vcxproj', 'PCbuild/_lzma.vcxproj'}
    patch = (ROOT / spec['patch']['path']).read_bytes()
    assert hashlib.sha256(patch).hexdigest() == spec['patch']['sha256']
    assert b'PSAAControlledProviders' in patch and b'PSAARequireStaticFFI' in patch


def test_native_controller_rejects_another_patch_before_creating_work(tmp_path: Path, monkeypatch) -> None:
    import probe_windows_cpython_providers as probe

    monkeypatch.setattr(probe.platform, 'python_version', lambda: '3.14.9')
    work = tmp_path / 'no-build'
    with pytest.raises(AssertionError):
        probe.qualify(work)
    assert not work.exists()


def test_cpp_profile_has_only_the_two_native_windows_hosts_and_explicit_guards() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    assert 'tools-cpython-providers-windows' in workflow
    block = workflow.split('\n  native-toolchain-delta:', 1)[1].split('\n  selected-rust-graphs:', 1)[0]
    assert "endsWith(inputs.linux_arm64_pilot, '-windows')" in block
    assert 'probe_windows_cpython_providers.py --work-root' in block
    script = (ROOT / '.github/scripts/probe_windows_cpython_providers.py').read_text()
    assert script.index('Qualify current stable MSBuild') < script.index("fetch_artifact(ffi['artifact'])")
