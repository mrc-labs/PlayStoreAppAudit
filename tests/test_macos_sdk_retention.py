import hashlib
import tarfile

from retain_macos_runtime_sdk import retain


def test_failed_pilot_retains_exact_prefix_without_claiming_qualification(tmp_path):
    work, output = tmp_path / 'work', tmp_path / 'evidence'
    (work / 'prefix/lib').mkdir(parents=True)
    output.mkdir()
    payload = b'compiled diagnostic bytes'
    (work / 'prefix/lib/provider').write_bytes(payload)
    result = retain(work, output, 17)
    assert result['complete_pilot'] is False and result['pilot_exit_code'] == 17
    assert result['paths']['prefix/lib/provider']['sha256'] == hashlib.sha256(payload).hexdigest()
    with tarfile.open(output / result['archive'], 'r:zst') as archive:
        assert archive.extractfile('prefix/lib/provider').read() == payload
    assert hashlib.sha256((output / result['archive']).read_bytes()).hexdigest() == result['archive_sha256']
