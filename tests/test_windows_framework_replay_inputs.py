import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest
from replay_windows_current_framework import compiled_inputs, restore_bound_archive

ROOT = Path(__file__).resolve().parents[1]


def test_both_bound_sdks_match_unchanged_actual_compilation_inputs():
    actual = compiled_inputs((ROOT / '.github/scripts/build_windows_current_framework.py').read_text())
    specs = json.loads((ROOT / '.github/scripts/windows_framework_bound_sdks.json').read_text())
    assert set(specs) == {'x64', 'arm64'}
    assert all(spec['compiled_inputs'] == actual for spec in specs.values())


@pytest.mark.parametrize('before,after', [('-openssl-linked', '-openssl-runtime'),
                                         ('--limited-api=yes', '--limited-api=no')])
def test_replay_rejects_changed_framework_or_binding_compilation(before, after):
    source = (ROOT / '.github/scripts/build_windows_current_framework.py').read_text()
    assert before in source
    assert compiled_inputs(source.replace(before, after)) != compiled_inputs(source)


@pytest.mark.parametrize('fault', [None, 'escape', 'bytes', 'device'])
def test_sdk_hard_links_keep_indexed_bytes_and_reject_escapes(tmp_path, fault):
    entry = {'bytes': 6, 'sha256': hashlib.sha256(b'native').hexdigest()}
    receipt = {'paths': {'prefix/original': entry, 'prefix/alias': dict(entry)}}
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w') as archive:
        original = tarfile.TarInfo('prefix/original')
        original.size = 6
        archive.addfile(original, io.BytesIO(b'native'))
        alias = tarfile.TarInfo('prefix/alias')
        alias.type = tarfile.CHRTYPE if fault == 'device' else tarfile.LNKTYPE
        alias.linkname = '../escape' if fault == 'escape' else 'prefix/original'
        archive.addfile(alias)
    if fault == 'bytes':
        receipt['paths']['prefix/alias']['sha256'] = '0' * 64
    work = tmp_path / 'sdk'
    if fault:
        with pytest.raises((AssertionError, KeyError)):
            restore_bound_archive(data.getvalue(), work, receipt)
        assert not (tmp_path / 'escape').exists()
    else:
        restore_bound_archive(data.getvalue(), work, receipt)
        assert (work / 'prefix/alias').read_bytes() == b'native'
