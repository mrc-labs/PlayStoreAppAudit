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


@pytest.mark.parametrize('invalid', ['', 'missing-target', 'changed-digest'])
def test_streaming_sdk_verification_handles_prior_hardlinks_without_skipping_bytes(invalid):
    import io
    import zipfile

    from extract_macos_pilot_evidence import verify_sdk

    body = b'original native image bytes'
    digest = hashlib.sha256(body).hexdigest()
    first, second = 'prefix/lib/original', 'prefix/lib/alias'
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as archive:
        member = tarfile.TarInfo(first)
        member.size = len(body)
        archive.addfile(member, io.BytesIO(body))
        alias = tarfile.TarInfo(second)
        alias.type = tarfile.LNKTYPE
        alias.linkname = 'prefix/lib/missing' if invalid == 'missing-target' else first
        archive.addfile(alias)
    expected = {'bytes': len(body), 'sha256': digest}
    paths = {first: expected, second: {**expected}}
    if invalid == 'changed-digest':
        paths[second]['sha256'] = '0' * 64
    result = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(raw.getvalue()), mode='r|') as archive, zipfile.ZipFile(result, 'w') as output:
        if invalid:
            with pytest.raises(AssertionError):
                verify_sdk(archive, paths, {second: expected}, output)
        else:
            seen, recovered = verify_sdk(archive, paths, {second: expected}, output)
            assert seen == {first, second} and recovered == {second: digest}
    if not invalid:
        with zipfile.ZipFile(result) as output:
            assert output.read('sdk-native-binaries/' + second) == body
