from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pytest
from probe_windows_arm64_runtime import require_arm64

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('machine', [0x8664, 0x014c, 0xa641])
def test_arm64_probe_rejects_emulated_or_ec_target(tmp_path: Path, machine: int) -> None:
    image = bytearray(128)
    image[:2] = b'MZ'
    struct.pack_into('<I', image, 0x3c, 64)
    image[64:68] = b'PE\0\0'
    struct.pack_into('<H', image, 68, machine)
    path = tmp_path / 'probe.dll'
    path.write_bytes(image)
    with pytest.raises(AssertionError, match='Not native ARM64'):
        require_arm64(path)


def test_arm64_probe_accepts_real_target(tmp_path: Path) -> None:
    image = bytearray(128)
    image[:2] = b'MZ'
    struct.pack_into('<I', image, 0x3c, 64)
    image[64:68] = b'PE\0\0'
    struct.pack_into('<H', image, 68, 0xaa64)
    path = tmp_path / 'probe.dll'
    path.write_bytes(image)
    require_arm64(path)


def test_arm64_contract_preserves_qualified_sources_and_distinguishes_host_tools() -> None:
    base = json.loads((ROOT / '.github/scripts/windows_runtime_pilot_sources.json').read_text(encoding='utf-8'))
    arm = json.loads((ROOT / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert arm['base_manifest_canonical_sha256'] == digest
    assert arm['openssl_target'] == 'VC-WIN64-CLANGASM-ARM'
    assert arm['openssl_dlls'] == ['libcrypto-4-arm64.dll', 'libssl-4-arm64.dll']
    assert '_arm64.7z' in arm['host_libclang']['name']
    for item in arm['probe_wheels']:
        assert 'win_arm64' in item['name'] and len(item['sha256']) == 64
        assert item['version'] == '6.12.0'


def test_arm64_probe_is_single_target_and_cannot_start_a_stack_rebuild() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text(encoding='utf-8')
    job = workflow.split('\n  windows-arm64-runtime-probe:', 1)[1]
    assert 'runs-on: windows-11-arm' in job and 'matrix:' not in job
    assert 'Dispatch SHA mismatch' in job and 'Checkout SHA mismatch' in job
    assert 'architecture: arm64' in job and 'Select only Windows ARM64 prerequisites' in job
    probe = (ROOT / '.github/scripts/probe_windows_arm64_runtime.py').read_text(encoding='utf-8')
    assert "'nmake'" not in probe and "'--build'" not in probe
    assert 'nasm.exe' not in probe and 'VC-WIN64A' not in probe
