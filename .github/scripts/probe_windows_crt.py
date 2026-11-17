"""Observe signed native redist payloads before another controlled ARM build."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
from pathlib import Path

from inspect_pe import read_pe_machine


def select_native_runtime(report: dict, tool_version: str) -> Path:
    """Select the current official native CRT, never the colocated x64 helper."""
    candidates = [r for r in report['files'] if
                  Path(r['path']).name.lower() == 'vcruntime140.dll' and
                  Path(r['path']).parents[2].name == tool_version.rstrip('\\')]
    assert len(candidates) == 1, 'Exactly one current-toolset native CRT required'
    row = candidates[0]
    assert row['machine'] == '0xaa64'
    assert row['signature']['status'] == 'Valid' and 'Microsoft' in row['signature']['signer']
    assert row['native_process_load'] == 'loaded' and row['exact_payload_loaded']
    assert tuple(map(int, row['signature']['product_version'].split('.'))) >= tuple(map(int, tool_version.rstrip('\\').split('.')))
    return Path(row['path'])


def diagnose(output: Path) -> dict:
    assert os.name == 'nt' and os.environ['VSCMD_ARG_HOST_ARCH'] == 'arm64'
    root = Path(os.environ['VSINSTALLDIR']) / 'VC/Redist/MSVC'
    paths = sorted(root.glob('*/arm64/Microsoft.VC*.CRT/vcruntime140*.dll'))
    assert paths, 'Native ARM64 redist payload missing; no source build started'
    script = output / 'inspect-official-crt.ps1'
    script.write_text('param([string]$crtFile)\n'
        '$ErrorActionPreference="Stop"\n'
        '$sig=Get-AuthenticodeSignature -LiteralPath $crtFile\n'
        '$info=(Get-Item -LiteralPath $crtFile).VersionInfo\n'
        '@{status=$sig.Status.ToString();signer=$sig.SignerCertificate.Subject;'
        'file_version=$info.FileVersion;product_version=$info.ProductVersion}|ConvertTo-Json\n')
    rows = []
    for path in paths:
        signature = json.loads(subprocess.check_output(['pwsh', '-NoProfile', '-File', script, str(path)], text=True))
        row = {'path': str(path), 'machine': hex(read_pe_machine(path)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'bytes': path.stat().st_size, 'signature': signature}
        try:
            dll = ctypes.WinDLL(str(path), winmode=0x900)
            name = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetModuleFileNameW(ctypes.c_void_p(dll._handle), name, len(name))
            assert length
            row.update(native_process_load='loaded', loaded_path=name.value,
                       exact_payload_loaded=Path(name.value).resolve() == path.resolve())
        except OSError as error:
            row.update(native_process_load='rejected', winerror=error.winerror, reason=str(error))
        rows.append(row)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'redist_root': str(root), 'files': rows,
              'scope': 'Signed vendor CRT observations and native-process load only. No ARM64EC/project target change or architecture exception adopted.'}
    (output / 'native-crt-observations.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    assert all(r['signature']['status'] == 'Valid' and 'Microsoft' in r['signature']['signer'] for r in rows)
    return report
