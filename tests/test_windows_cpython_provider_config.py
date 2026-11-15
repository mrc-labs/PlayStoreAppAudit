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



@pytest.mark.parametrize('kind', ['TLSv1_2', 'TLSv1_3', 'hostname', 'untrusted', 'expired'])
def test_isolated_tls_fixtures_authenticate_and_reject_all_three_negatives(tmp_path: Path, kind: str) -> None:
    import socket
    import ssl

    import probe_windows_cpython_providers as probe
    from verify_native_runtime_pilot import tls_server

    openssl = Path('C:/Program Files/Git/usr/bin/openssl.exe')
    if not openssl.is_file():
        import shutil
        selected = shutil.which('openssl')
        if selected is None:
            pytest.skip('Fixture generator requires an OpenSSL CLI; native diagnostic never skips')
        openssl = Path(selected)
    paths = probe.tls_fixtures(tmp_path, openssl)
    positive = kind.startswith('TLS')
    context = ssl.create_default_context(cafile=str(paths['ca']) if kind != 'untrusted' else None)
    if positive:
        context.minimum_version = context.maximum_version = getattr(ssl.TLSVersion, kind)
    with (tls_server(paths, 'expired' if kind == 'expired' else 'valid', expected_rejection=not positive) as port,
          socket.create_connection(('127.0.0.1', port), timeout=5) as raw):
        if positive:
            with context.wrap_socket(raw, server_hostname='localhost') as connection:
                assert connection.version() == kind.replace('TLSv1_', 'TLSv1.')
                connection.sendall(b'GET / HTTP/1.0\r\n\r\n')
                assert b'200 OK' in connection.recv(4096)
        else:
            with pytest.raises(ssl.SSLCertVerificationError) as error:
                context.wrap_socket(raw, server_hostname='wrong.invalid' if kind == 'hostname' else 'localhost')
            assert error.value.verify_code == {'hostname': 62, 'untrusted': 20, 'expired': 10}[kind]


def test_pcbuild_sqlite_version_layout_preserves_source_bytes(tmp_path: Path) -> None:
    from probe_windows_cpython_providers import sqlite_layout

    source = tmp_path / 'sqlite-autoconf-3540100'
    source.mkdir()
    header = b'#define SQLITE_VERSION        "3.54.1"\n'
    (source / 'sqlite3.h').write_bytes(header)
    (source / 'sqlite3.c').write_bytes(b'original amalgamation bytes')
    result = sqlite_layout(source)
    assert result.name.endswith('3.54.1.0')
    assert (result / 'sqlite3.h').read_bytes() == header
    assert (result / 'sqlite3.c').read_bytes() == b'original amalgamation bytes'


def test_sqlite_layout_rejects_unexpected_version_without_moving_source(tmp_path: Path) -> None:
    from probe_windows_cpython_providers import sqlite_layout

    source = tmp_path / 'sqlite-autoconf-3540100'
    source.mkdir()
    (source / 'sqlite3.h').write_bytes(b'#define SQLITE_VERSION "3.54.10"\n')
    with pytest.raises(AssertionError, match='Unexpected controlled SQLite'):
        sqlite_layout(source)
    assert source.is_dir() and not (tmp_path / 'sqlite-3.54.1.0').exists()
