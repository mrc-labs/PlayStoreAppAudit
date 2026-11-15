"""Reuse only hash-closed OpenSSL/codec bytes; failed CPython stays unqualified."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from download_diagnostic_artifact import fetch_artifact

ROOT = Path(__file__).resolve().parents[2]


def contract() -> dict:
    return json.loads((ROOT / '.github/scripts/windows_x64_provider_sdk_sources.json').read_text())


def restore(work: Path, output: Path, selected: list[dict], context: dict) -> None:
    spec = contract()
    metadata, raw = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['id'] == spec['run']
    assert metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(raw) == spec['zip_bytes'] and hashlib.sha256(raw).hexdigest() == spec['zip_sha256']
    assert not (work / 'prefix').exists()
    with zipfile.ZipFile(io.BytesIO(raw)) as original:
        old_context = json.loads(original.read('native-cpython-msbuild-context.json'))
        assert old_context['machine'] == context['machine'] == 0x8664
        assert old_context['sdk'] == context['sdk']
        assert Path(old_context['compiler']).parents[3].name == Path(context['compiler']).parents[3].name
        receipt = json.loads(original.read('windows-cpython-sdk.json'))
        assert receipt['source_sha'] == spec['source_sha'] and receipt['machine'].lower() == 'amd64'
        assert not receipt['complete_pilot'] and Path(receipt['original_work_root']).resolve() == work
        archive = original.read('windows-cpython-sdk.tar.zst')
        assert hashlib.sha256(archive).hexdigest() == receipt['archive_sha256']
        with tarfile.open(fileobj=io.BytesIO(archive)) as bundle:
            members = bundle.getmembers()
            for member in members:
                name = PurePosixPath(member.name)
                assert not name.is_absolute() and '..' not in name.parts and name.parts[0] == 'prefix'
                assert member.isdir() or member.isfile(), 'No unreviewed Windows SDK links'
            assert {m.name for m in members if m.isfile()} == set(receipt['paths'])
            bundle.extractall(work, filter='data')
        for name, expected in receipt['paths'].items():
            path = work / name
            assert path.resolve().is_relative_to(work) and not path.is_symlink()
            assert path.stat().st_size == expected['bytes']
            assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']
        for item in selected:
            data = original.read('sources/' + item['name'])
            assert hashlib.sha256(data).hexdigest() == item['sha256']
            (output / 'sources' / item['name']).write_bytes(data)
        for name in original.namelist():
            if name.startswith(('openssl-', 'xz-', 'zlib-ng-')) and name.endswith(('.log', '.txt')):
                (output / ('original-' + name)).write_bytes(original.read(name))
        shutil.copy2(ROOT / '.github/scripts/windows_x64_provider_sdk_sources.json', output)
    (output / 'partial-provider-intake.json').write_text(json.dumps({
        'original': spec, 'verified_paths': len(receipt['paths']),
        'compiler_sdk': old_context, 'scope': 'Original compiled OpenSSL/codec bytes/tests only; new CPython consumers still required'}, indent=2) + '\n')
