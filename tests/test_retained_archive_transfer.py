from __future__ import annotations

import hashlib
import io
import json

import pytest
import recover_retained_original as transfer


@pytest.mark.parametrize('wrong_order', [False, True])
def test_chunk_transport_requires_identical_complete_original(tmp_path, monkeypatch, wrong_order):
    payloads = {10: b'first', 11: b'second'}
    original = {'artifact': 1, 'run': 2, 'source_sha': 'a' * 40, 'bytes': 11,
                'sha256': hashlib.sha256(b'firstsecond').hexdigest()}
    parts = [{'asset': key, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
             for key, raw in payloads.items()]
    if wrong_order:
        parts.reverse()
    (tmp_path / 'retained_original_archives.json').write_text(json.dumps({
        '1': {'original': original, 'staging': {'release': 454903125, 'parts': parts}}}))
    monkeypatch.setattr(transfer, '__file__', str(tmp_path / 'recover.py'))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr('sys.argv', ['recover', '--artifact', '1'])
    monkeypatch.setenv('GITHUB_SHA', 'b' * 40)
    monkeypatch.setenv('EXPECTED_SHA', 'b' * 40)
    monkeypatch.setenv('GITHUB_RUN_ID', '3')
    monkeypatch.setenv('GH_TOKEN', 'fixture-token')

    class Opener:
        def open(self, request, **kwargs):
            assert request.full_url.startswith('https://api.github.com/repos/mrc-labs/PlayStoreAppAudit/releases/assets/')
            key = int(request.full_url.rsplit('/', 1)[1])
            if request.get_header('Accept') == 'application/octet-stream':
                return io.BytesIO(payloads[key])
            return io.BytesIO(json.dumps({'id': key, 'state': 'uploaded', 'size': len(payloads[key]),
                'digest': 'sha256:' + hashlib.sha256(payloads[key]).hexdigest()}).encode())

    monkeypatch.setattr(transfer.urllib.request, 'build_opener', lambda *args: Opener())
    if wrong_order:
        with pytest.raises(AssertionError):
            transfer.main()
        assert not (tmp_path / 'retained-original/RECOVERY.json').exists()
    else:
        transfer.main()
        assert (tmp_path / 'retained-original/original-input.zip').read_bytes() == b'firstsecond'
        receipt = json.loads((tmp_path / 'retained-original/RECOVERY.json').read_text())
        assert receipt['original'] == original and receipt['recovery_run'] == 3
