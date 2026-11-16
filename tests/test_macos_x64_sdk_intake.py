"""The consumer replay must reject changed bytes and unsafe SDK contents."""
import hashlib
import io
import json
import tarfile
import zipfile

import pytest
import reuse_macos_x64_bound_sdk as intake


@pytest.mark.parametrize('fault', ['zip', 'sdk', 'partial', 'escape', 'changed-file', None])
def test_closed_intel_sdk_intake(tmp_path, monkeypatch, fault):
    monkeypatch.setenv('GITHUB_SHA', 'c' * 40)
    work = tmp_path / 'owned-sdk'
    output = tmp_path / 'evidence'
    output.mkdir()
    sdk = io.BytesIO()
    name = '../escape' if fault == 'escape' else 'prefix/native'
    with tarfile.open(fileobj=sdk, mode='w') as archive:
        info = tarfile.TarInfo(name)
        info.size = 6
        archive.addfile(info, io.BytesIO(b'native'))
    digest = hashlib.sha256(sdk.getvalue()).hexdigest()
    receipt = {'source_sha': 'a' * 40, 'machine': 'x86_64', 'complete_pilot': fault != 'partial',
               'pilot_exit_code': 0, 'original_work_root': str(work), 'archive_sha256': digest,
               'paths': {name: {'bytes': 6, 'sha256': hashlib.sha256(b'bad' if fault == 'changed-file' else b'native').hexdigest()}}}
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, 'w') as archive:
        archive.writestr('macos-runtime-sdk.json', json.dumps(receipt))
        archive.writestr('macos-runtime-sdk.tar.zst', sdk.getvalue())
        for item in ['cpython-codec-regressions.xml', 'cpython-regressions.xml', 'tarfile-security-regression.log',
                     'cffi-runtime-tests.xml', 'cryptography-source-provenance.json', 'qt-cldr49-runtime-input.xml']:
            archive.writestr(item, 'original evidence')
    data = outer.getvalue()
    spec = {'zip_bytes': len(data), 'zip_sha256': hashlib.sha256(data).hexdigest(), 'sdk_sha256': digest,
            'source_sha': 'a' * 40, 'original_work_root': str(work), 'component_inputs': {}, 'compiled_scripts': {}}
    if fault in ('zip', 'sdk'):
        spec['zip_sha256' if fault == 'zip' else 'sdk_sha256'] = '0' * 64
    if fault:
        with pytest.raises(AssertionError):
            intake.restore(data, work, output, spec)
        assert not (tmp_path / 'escape').exists()
    else:
        report = intake.restore(data, work, output, spec)
        assert report['verified_paths'] == 1 and report['consumer_source_sha'] == 'c' * 40
        assert (work / 'prefix/native').read_bytes() == b'native'
        assert (output / 'original-native-results/cpython-regressions.xml').is_file()
        assert (output / 'qt-cldr49-runtime-input.xml').read_text() == 'original evidence'
