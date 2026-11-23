from __future__ import annotations

import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.github/scripts'))
from probe_windows_x64_ffi_consumers import restore_ffi  # noqa: E402


@pytest.mark.parametrize('change', ['none', 'zip', 'library', 'source', 'crt'])
def test_retained_sdk_rejects_changed_bytes_or_provenance(tmp_path: Path, change: str) -> None:
    library = b'test-only library fixture; not native qualification'
    report = {'source_sha': 'a' * 40, 'crt': '/MD', 'library_sha256': hashlib.sha256(library).hexdigest()}
    spec = {'source_sha': report['source_sha'], 'library_sha256': report['library_sha256']}
    if change == 'library':
        library += b'changed'
    if change == 'source':
        report['source_sha'] = 'b' * 40
    if change == 'crt':
        report['crt'] = '/MT'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('windows-x64-libffi.json', json.dumps(report))
        for name in ['include/ffi.h', 'include/ffitarget.h', 'share/libffi/copyright']:
            archive.writestr('libffi-sdk/' + name, 'fixture')
        archive.writestr('libffi-sdk/lib/libffi.lib', library)
    data = stream.getvalue()
    spec.update(zip_bytes=len(data), zip_sha256=hashlib.sha256(data).hexdigest())
    if change == 'zip':
        data += b'changed'
    if change == 'none':
        restore_ffi(data, tmp_path, spec)
        assert (tmp_path / 'lib/libffi.lib').read_bytes() == library
    else:
        with pytest.raises((AssertionError, ValueError)):
            restore_ffi(data, tmp_path, spec)


def test_x64_variant_changes_only_source_selection_and_distribution_identity() -> None:
    spec = json.loads((ROOT / '.github/scripts/windows_x64_ffi_consumer_sources.json').read_text())
    patch = spec['cffi_consumer']['patch']
    assert set(patch['files']) == {'setup.py', 'pyproject.toml'}
    assert hashlib.sha256((ROOT / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    assert spec['ffi']['source_sha'] == '522202f8c683cb1c8e4fcd61318277a7899a0e4f'
