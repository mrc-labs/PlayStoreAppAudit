import hashlib
import tarfile

import pytest
from retain_macos_runtime_sdk import retain


@pytest.mark.parametrize('sdk_name', ['macos-runtime-sdk', 'windows-cpython-sdk'])
def test_failed_pilot_retains_exact_prefix_without_claiming_qualification(tmp_path, sdk_name):
    work, output = tmp_path / 'work', tmp_path / 'evidence'
    (work / 'prefix/lib').mkdir(parents=True)
    output.mkdir()
    payload = b'compiled diagnostic bytes'
    (work / 'prefix/lib/provider').write_bytes(payload)
    result = retain(work, output, 17, sdk_name=sdk_name)
    assert result['archive'] == sdk_name + '.tar.zst'
    assert result['complete_pilot'] is False and result['pilot_exit_code'] == 17
    assert result['paths']['prefix/lib/provider']['sha256'] == hashlib.sha256(payload).hexdigest()
    with tarfile.open(output / result['archive'], 'r:zst') as archive:
        assert archive.extractfile('prefix/lib/provider').read() == payload
    assert hashlib.sha256((output / result['archive']).read_bytes()).hexdigest() == result['archive_sha256']
