from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github/scripts'))
import reuse_windows_x64_provider_sdk as intake  # noqa: E402


@pytest.mark.parametrize('failure', [None, 'tamper', 'partial_runtime', 'unsafe_path'])
def test_qualified_runtime_intake_rejects_tampered_partial_or_escaping_sdk(tmp_path, monkeypatch, failure) -> None:
    work, output = tmp_path / 'work', tmp_path / 'out'
    work.mkdir()
    output.mkdir()
    compiler = str(tmp_path / '14.52.37025/bin/Hostarm64/arm64/cl.exe')
    context = {'compiler': compiler, 'machine': 0xAA64, 'sdk': '10.0.26100.0'}
    payload = b'closed native component fixture, never executed'
    name = 'prefix/../escape' if failure == 'unsafe_path' else 'prefix/python/fixture.bin'
    body = io.BytesIO()
    with tarfile.open(fileobj=body, mode='w:zst') as archive:
        member = tarfile.TarInfo(name)
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    sdk = body.getvalue()
    receipt = {'source_sha': 'qualified-head', 'machine': 'ARM64', 'original_work_root': str(work.resolve()),
               'complete_pilot': failure != 'partial_runtime', 'archive_sha256': hashlib.sha256(sdk).hexdigest(),
               'paths': {name: {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}}}
    body = io.BytesIO()
    with zipfile.ZipFile(body, 'w') as archive:
        for name, value in [('native-cpython-msbuild-context.json', context), ('windows-cpython-sdk.json', receipt),
                            ('windows-cpython-providers.json', {'result': 'PASS', 'source_sha': 'qualified-head', 'arch': 'arm64'})]:
            archive.writestr(name, json.dumps(value))
        archive.writestr('windows-cpython-sdk.tar.zst', sdk)
    raw = body.getvalue()
    spec = {'artifact': 1, 'run': 2, 'source_sha': 'qualified-head', 'zip_bytes': len(raw), 'zip_sha256': hashlib.sha256(raw).hexdigest()}
    metadata = {'expired': False, 'workflow_run': {'id': 2, 'head_sha': 'qualified-head', 'head_repository_id': 1334403620}}
    monkeypatch.setattr(intake, 'contract', lambda arch, runtime: spec)
    monkeypatch.setattr(intake, 'fetch_artifact', lambda ident: (metadata, raw + b'changed' if failure == 'tamper' else raw))
    if failure:
        with pytest.raises(AssertionError):
            intake.restore(work, output, [], context, runtime=True)
        assert not (tmp_path / 'escape').exists() and not (work / 'prefix').exists()
    else:
        intake.restore(work, output, [], context, runtime=True)
        assert (work / 'prefix/python/fixture.bin').read_bytes() == payload
