from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import verify_windows_arm64_crypto as crypto


@pytest.mark.parametrize("imports", [
    "KERNEL32.dll\nVCRUNTIME140.dll\nlibcrypto-4-arm64.dll",
    "KERNEL32.dll\nlibssl-4.dll\nucrtbase.dll",
    "KERNEL32.dll\n",
])
def test_linkage_gate_rejects_shared_openssl_or_missing_dynamic_crt(imports: str) -> None:
    with pytest.raises(ValueError):
        crypto.validate_imports(imports)


def test_linkage_gate_accepts_static_openssl_with_dynamic_crt() -> None:
    crypto.validate_imports("KERNEL32.dll\nVCRUNTIME140.dll\napi-ms-win-crt-runtime-l1-1-0.dll")


@pytest.fixture
def evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tmp_path = tmp_path / "evidence"
    tmp_path.mkdir()
    payload = b"source fixture"
    digest = hashlib.sha256(payload).hexdigest()
    monkeypatch.setattr(crypto, "EXPECTED_SOURCE_SHA256", digest)
    (tmp_path / "openssl-4.0.3.tar.gz").write_bytes(payload)
    source = {
        "version": "4.0.3", "source_sha256": digest,
        "source_url": "https://github.com/openssl/openssl/releases/download/openssl-4.0.3/openssl-4.0.3.tar.gz",
        "linkage": "static", "crt": "dynamic",
    }
    (tmp_path / "source-provenance.json").write_text(json.dumps(source), encoding="utf-8")
    (tmp_path / "LICENSE.txt").write_text("Apache License\nVersion 2.0", encoding="utf-8")
    (tmp_path / "cryptography-verification.json").write_text("{}", encoding="utf-8")
    (tmp_path / "cryptography-licenses").mkdir()
    (tmp_path / "cryptography-licenses/LICENSE.APACHE").write_text("crypto license", encoding="utf-8")
    return tmp_path


def test_source_gate_rejects_modified_retained_source(evidence: Path) -> None:
    (evidence / "openssl-4.0.3.tar.gz").write_bytes(b"modified")
    with pytest.raises(ValueError, match="checksum"):
        crypto.validate_source(evidence)


@pytest.mark.parametrize(("field", "value"), [
    ("source_url", "https://example.invalid/source.tar.gz"),
    ("version", "4.1.0"), ("linkage", "shared"), ("crt", "static"),
])
def test_source_gate_rejects_unsupported_provenance(evidence: Path, field: str, value: str) -> None:
    path = evidence / "source-provenance.json"
    source = json.loads(path.read_text(encoding="utf-8"))
    source[field] = value
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError):
        crypto.validate_source(evidence)


def test_source_gate_requires_license_material(evidence: Path) -> None:
    (evidence / "LICENSE.txt").write_text("missing", encoding="utf-8")
    with pytest.raises(ValueError, match="license"):
        crypto.validate_source(evidence)


def test_staging_preserves_exact_sources_and_ships_notices(evidence: Path, tmp_path: Path) -> None:
    package, release = tmp_path / "package", tmp_path / "release"
    crypto.stage_material(evidence, package, release)
    legal = package / "third-party-build/openssl-cryptography"
    retained = release / "prerequisites/openssl-cryptography"
    assert (legal / "LICENSE.txt").read_bytes() == (evidence / "LICENSE.txt").read_bytes()
    assert (legal / "cryptography-licenses/LICENSE.APACHE").is_file()
    assert (retained / "openssl-4.0.3.tar.gz").read_bytes() == b"source fixture"
    assert not (legal / "openssl-4.0.3.tar.gz").exists()


@pytest.mark.parametrize("suffix", ["cryptography-50.0.2.tar.gz", "cryptography-50.0.2-cp314-win_arm64.whl"])
def test_install_report_requires_official_source_rebuild(tmp_path: Path, suffix: str) -> None:
    report = {"install": [{"metadata": {"name": "cryptography", "version": "50.0.2"},
                          "download_info": {"url": f"https://files.pythonhosted.org/packages/{suffix}",
                                            "archive_info": {"hashes": {"sha256": "a" * 64}}}}]}
    (tmp_path / "cryptography-install.json").write_text(json.dumps(report), encoding="utf-8")
    if suffix.endswith(".whl"):
        with pytest.raises(ValueError, match="source archive"):
            crypto.validate_install_report(tmp_path, "50.0.2")
    else:
        assert crypto.validate_install_report(tmp_path, "50.0.2")["url"].endswith(suffix)


@pytest.mark.parametrize('fault', ['receipt-hash', 'compiled-source', 'extension-bytes'])
def test_controlled_provider_rejects_unclosed_sdk_identity(tmp_path, monkeypatch, fault):
    from cryptography.hazmat.bindings import _rust

    monkeypatch.setattr(crypto.platform, 'machine', lambda: 'ARM64')
    monkeypatch.setattr(crypto.platform, 'python_version', lambda: '3.14.10')
    monkeypatch.setattr(crypto.sysconfig, 'get_config_var', lambda name: 0)
    extension = Path(_rust.__file__).resolve()
    receipt = {'source_sha': '1' * 40, 'original_work_root': str(extension.parent),
               'paths': {extension.name: {'bytes': extension.stat().st_size, 'sha256': '0' * 64}}}
    raw = json.dumps(receipt).encode()
    receipt_path = tmp_path / 'sdk.json'
    receipt_path.write_bytes(raw)
    selection = {'target': 'windows-arm64', 'qt_receipt': str(receipt_path),
                 'qt_receipt_sha256': hashlib.sha256(raw).hexdigest(),
                 'compiled_source_sha': '1' * 40}
    if fault == 'receipt-hash':
        selection['qt_receipt_sha256'] = '0' * 64
    elif fault == 'compiled-source':
        selection['compiled_source_sha'] = '2' * 40
    selected = tmp_path / 'selection.json'
    selected.write_text(json.dumps(selection))
    with pytest.raises(RuntimeError, match={'receipt-hash': 'Changed original SDK receipt',
                                         'compiled-source': 'Changed compiled SDK identity',
                                         'extension-bytes': 'differs from original SDK'}[fault]):
        crypto.verify_controlled_sdk(selected, tmp_path / 'evidence', None, None)
    assert not (tmp_path / 'evidence').exists()
