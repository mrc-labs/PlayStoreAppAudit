from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from verify_windows_runtime_pilot import (  # noqa: E402
    controlled_qt_origin,
    pe_versions,
    require_certificate_rejection,
    validate_imports,
)


def test_upstream_qt_package_copy_requires_identical_controlled_bytes(tmp_path: Path) -> None:
    prefix = tmp_path / 'prefix'
    package = tmp_path / 'venv/Lib/site-packages/PySide6'
    original = prefix / 'qt/bin/Qt6Core.dll'
    original.parent.mkdir(parents=True)
    package.mkdir(parents=True)
    original.write_bytes(b'controlled source build output')
    copy = package / original.name
    copy.write_bytes(original.read_bytes())
    assert controlled_qt_origin(copy, prefix, package) == str(original)
    copy.write_bytes(b'same name and version, different binary')
    with pytest.raises(AssertionError, match='differs'):
        controlled_qt_origin(copy, prefix, package)


def test_identical_qt_bytes_from_an_uncontrolled_directory_are_rejected(tmp_path: Path) -> None:
    prefix = tmp_path / 'prefix'
    original = prefix / 'qt/bin/Qt6Core.dll'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'controlled build')
    foreign = tmp_path / original.name
    foreign.write_bytes(original.read_bytes())
    with pytest.raises(AssertionError):
        controlled_qt_origin(foreign, prefix, tmp_path / 'venv/PySide6')


def test_packaged_tls_plugin_requires_the_matching_controlled_plugin(tmp_path: Path) -> None:
    prefix = tmp_path / 'prefix'
    package = tmp_path / 'venv/Lib/site-packages/PySide6'
    original = prefix / 'qt/plugins/tls/qopensslbackend.dll'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'controlled OpenSSL4 TLS plugin')
    copy = package / 'plugins/tls/qopensslbackend.dll'
    copy.parent.mkdir(parents=True)
    copy.write_bytes(original.read_bytes())
    assert controlled_qt_origin(copy, prefix, package) == str(original)
    copy.write_bytes(b'foreign backend')
    with pytest.raises(AssertionError, match='differs'):
        controlled_qt_origin(copy, prefix, package)


def test_schannel_issuer_failure_is_a_real_untrusted_chain_rejection() -> None:
    require_certificate_rejection('untrusted', False, ['UnableToGetIssuerCertificate'])


@pytest.mark.parametrize('case,encrypted,errors', [
    ('untrusted', True, ['UnableToGetIssuerCertificate']),
    ('untrusted', False, ['UnspecifiedError']),
    ('HostNameMismatch', False, ['CertificateExpired']),
    ('CertificateExpired', False, []),
])
def test_other_tls_outcomes_cannot_satisfy_certificate_negatives(case, encrypted, errors) -> None:
    with pytest.raises(AssertionError):
        require_certificate_rejection(case, encrypted, errors)


@pytest.mark.parametrize('imports', [
    'libssl-3-x64.dll', 'LIBCRYPTO-3.dll', 'VCRUNTIME140D.dll',
    'MSVCP140D.dll', 'ucrtbased.dll', 'vcruntime140_1d.dll',
])
def test_provider_or_crt_fallback_is_rejected(imports: str) -> None:
    with pytest.raises(AssertionError):
        validate_imports(imports)


def test_openssl4_and_release_crt_import_names_are_preserved() -> None:
    validate_imports('libssl-4-x64.dll\nlibcrypto-4-x64.dll\nVCRUNTIME140.dll\nMSVCP140.dll\napi-ms-win-crt-runtime-l1-1-0.dll')


def test_pe_os_bounds_read_optional_header_instead_of_host_version(tmp_path: Path) -> None:
    data = bytearray(512)
    struct.pack_into('<I', data, 0x3C, 128)
    optional = 128 + 24
    struct.pack_into('<H', data, optional, 0x20B)
    struct.pack_into('<HH', data, optional + 40, 6, 0)
    struct.pack_into('<HH', data, optional + 48, 10, 0)
    path = tmp_path / 'image.dll'
    path.write_bytes(data)
    assert pe_versions(path) == {'os':(6, 0), 'subsystem':(10, 0)}
    struct.pack_into('<H', data, optional, 0x10B)
    path.write_bytes(data)
    with pytest.raises(AssertionError):
        pe_versions(path)


def test_windows_sources_reuse_accepted_linux_runtime_inputs() -> None:
    linux = json.loads((ROOT / '.github/scripts/native_runtime_pilot_sources.json').read_text())
    windows = json.loads((ROOT / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    assert windows['cpython_patch'] == linux['cpython_patch']
    assert windows['sources'][:7] == linux['sources'][:7]
    for key in ('cpython_patch', 'windows_patch'):
        patch = windows[key]
        assert hashlib.sha256((ROOT / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    for item in [*windows['sources'], *windows['cpython_externals'], windows['extractor'], windows['nasm'], windows['extractor_source'], windows['nasm_source']]:
        assert item['url'].startswith('https://') and len(item['sha256']) == 64
    assert windows['openssl_dlls'] == ['libcrypto-4-x64.dll','libssl-4-x64.dll']
    assert windows['openssl_import_libraries'] == ['libcrypto.lib','libssl.lib']


def test_windows_profile_is_isolated_from_production_and_other_targets() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    job = workflow.split('\n  windows-runtime-pilot:', 1)[1]
    assert 'runs-on: windows-2025' in job and 'matrix:' not in job
    assert 'Dispatch SHA mismatch' in job and 'Checkout SHA mismatch' in job
    assert 'Select only Windows x64 pilot' in job
    assert 'diagnostic-runtime-framework-windows-x64-' in job
    assert 'PlayStoreAppAudit-v' not in job
    for path in (ROOT / '.github/workflows').glob('*.yml'):
        if path.name not in {'ui-style-audit.yml', 'quality.yml'}:
            assert 'build_windows_runtime_pilot' not in path.read_text()


def test_windows_ssl_recipe_preserves_cpython_crt_integration_and_tests_pem_io() -> None:
    builder = (ROOT / '.github/scripts/build_windows_runtime_pilot.py').read_text()
    assert "'no-uplink'" in builder and "'CFLAGS=/MD'" in builder
    assert "load_cert_chain(root/'keycert.pem')" in builder
    assert "cafile=str(root/'pycacert.pem')" in builder
    assert builder.index('PEM file I/O and CRT integration PASS') < builder.index("'--junit-xml'")
