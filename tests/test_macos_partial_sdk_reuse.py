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
from reuse_macos_arm64_partial_sdk import configuration_sha256, restore  # noqa: E402


@pytest.mark.parametrize('change', ['none', 'existing-prefix', 'zip', 'file', 'root', 'source', 'path', 'symlink'])
def test_partial_cache_cannot_bypass_byte_source_or_extraction_guards(tmp_path: Path, change: str) -> None:
    work, output = tmp_path / 'original-work', tmp_path / 'evidence'
    work.mkdir()
    output.mkdir()
    existing = work / 'prefix/lib/fresh-codec.dylib'
    if change == 'existing-prefix':
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b'Preserve new native prerequisite bytes')
    name = 'prefix/openssl/lib/libssl.4.dylib'
    raw = b'test-only extraction fixture; no native acceptance'
    index = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}}
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:zst') as archive:
        member = tarfile.TarInfo('prefix/../escape' if change == 'path' else name)
        if change == 'symlink':
            member.type, member.linkname = tarfile.SYMTYPE, '../../../outside'
        else:
            member.size = len(raw)
        archive.addfile(member, None if member.issym() else io.BytesIO(raw))
    sdk = stream.getvalue()
    receipt = {'source_sha': 'a' * 40, 'machine': 'arm64', 'complete_pilot': False, 'pilot_exit_code': 1,
               'original_work_root': str(work), 'archive_sha256': hashlib.sha256(sdk).hexdigest(), 'paths': index}
    if change == 'file':
        index[name]['sha256'] = 'b' * 64
    if change == 'source':
        receipt['source_sha'] = 'b' * 40
    if change == 'root':
        receipt['original_work_root'] = str(tmp_path / 'another-work')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('macos-runtime-sdk.json', json.dumps(receipt))
        archive.writestr('macos-runtime-sdk.tar.zst', sdk)
        for name in ['openssl-configdata.pm', 'openssl-regressions.log']:
            archive.writestr(name, 'test-only fixture')
    data = stream.getvalue()
    spec = {'source_sha': 'a' * 40, 'zip_bytes': len(data), 'zip_sha256': hashlib.sha256(data).hexdigest(),
            'sdk_sha256': receipt['archive_sha256'], 'component_inputs': {}}
    if change == 'zip':
        data += b'changed'
    if change in {'none', 'existing-prefix'}:
        result = restore(data, work, output, spec)
        assert (work / 'prefix/openssl/lib/libssl.4.dylib').read_bytes() == raw
        assert result['restored_paths'] == 1 and 'partial prefix reuse only' in result['scope']
        if change == 'existing-prefix':
            assert existing.read_bytes() == b'Preserve new native prerequisite bytes'
    else:
        with pytest.raises((AssertionError, ValueError)):
            restore(data, work, output, spec)


def test_configuration_identity_is_independent_of_checkout_line_endings() -> None:
    assert configuration_sha256(b'{"a":1}\n') == configuration_sha256(b'{\r\n "a": 1\r\n}\r\n')


def test_library_stage_runs_from_repository_after_openssl_install() -> None:
    script = (Path(__file__).resolve().parents[1] / '.github/scripts/build_macos_arm64_runtime_pilot.sh').read_text()
    assert 'cd "$repo"\nEXPECTED_ARCH=arm64 PSAA_MAC_PROVIDER_LIBRARY_STAGE=1' in script
    assert 'xcodebuild -version | head' not in script
    assert 'original test/source identity preserved' in script
