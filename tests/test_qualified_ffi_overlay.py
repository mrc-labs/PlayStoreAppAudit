"""Byte/path guards only; opaque fixtures do not claim native ABI qualification."""
import hashlib
import io
import json
import tarfile
import zipfile

import pytest
from apply_qualified_ffi381 import apply_posix


@pytest.mark.parametrize('fault', [None, 'original', 'archive', 'escape'])
def test_ffi_overlay_requires_original_bytes_and_closed_archive(tmp_path, fault):
    prefix = tmp_path / 'prefix'
    (prefix / 'lib').mkdir(parents=True)
    target = prefix / 'lib/libffi.8.dylib'
    target.write_bytes(b'original fixture')
    def identity(raw: bytes) -> dict:
        return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
    selection = {'prefix': str(prefix), 'target': 'macos-arm64', 'compiled_source_sha': 'a' * 40}
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as archive:
        member = tarfile.TarInfo('prefix/lib/libffi.8.dylib')
        if fault == 'escape':
            member.type, member.linkname = tarfile.SYMTYPE, '../../escape'
            archive.addfile(member)
            after = {'link': member.linkname}
        else:
            member.size = len(b'new fixture')
            archive.addfile(member, io.BytesIO(b'new fixture'))
            after = identity(b'new fixture')
    payload = stream.getvalue()
    result = {'result': 'PASS', 'target': selection['target'], 'source_sha': 'b' * 40,
        'original_prefix': str(prefix), 'original_sdk': selection,
        'before': {'lib/libffi.8.dylib': identity(b'original fixture')},
        'after': {'lib/libffi.8.dylib': after}, 'overlay_sha256': hashlib.sha256(payload).hexdigest(),
        'native': {'libffi': '3.8.1', 'callbacks_ctypes': 1200, 'callbacks_cffi': 1200,
                   'library_sha256': hashlib.sha256(b'new fixture').hexdigest()}}
    if fault == 'original':
        target.write_bytes(b'unknown fixture')
    if fault == 'archive':
        payload += b'changed'
    zipped = io.BytesIO()
    with zipfile.ZipFile(zipped, 'w') as archive:
        archive.writestr('libffi381-result.json', json.dumps(result))
        archive.writestr('libffi381-sdk-overlay.tar.xz', payload)
    zipped.seek(0)
    with zipfile.ZipFile(zipped) as archive:
        if fault:
            with pytest.raises(AssertionError):
                apply_posix(archive, selection, tmp_path)
            assert target.read_bytes() == (b'unknown fixture' if fault == 'original' else b'original fixture')
        else:
            applied = apply_posix(archive, selection, tmp_path)
            assert target.read_bytes() == b'new fixture'
            assert applied['compiled_source_sha'] == result['source_sha']
