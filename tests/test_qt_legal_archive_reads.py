import hashlib
import io
import json
import tarfile

import prepare_release_legal_bundle as legal


def source_archive(tmp_path, *, uncommon=False):
    archive = tmp_path / 'official-source.tar.xz'
    files = {f'qt/LICENSES/license-{n}.txt': f'Original legal text {n}'.encode() for n in range(24)}
    reference = 'terms.inc' if uncommon else 'LICENSE'
    files['qt/src/third/' + reference] = b'Actual referenced upstream license'
    files['qt/src/third/qt_attribution.json'] = json.dumps({
        'Name': 'Upstream provider', 'License': 'MIT', 'LicenseFile': reference,
    }).encode()
    with tarfile.open(archive, 'w:xz') as handle:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            handle.addfile(member, io.BytesIO(data))
    return archive


def payloads(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_common_qt_legal_members_need_one_decompression_pass(tmp_path, monkeypatch):
    archive = source_archive(tmp_path)
    original_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    original_open = tarfile.open
    calls = []

    def counted(*args, **kwargs):
        calls.append(args[0])
        return original_open(*args, **kwargs)

    monkeypatch.setattr(legal.tarfile, 'open', counted)
    result = legal._extract_qt_legal_material('qtbase', archive, tmp_path / 'licenses')
    assert len(calls) == 1
    assert len(result[0]) == 24 and len(result[3]) == 1 and len(result[4]) == 1
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == original_sha


def test_cached_and_uncached_reference_resolution_keep_identical_legal_bytes(tmp_path, monkeypatch):
    archive = source_archive(tmp_path, uncommon=True)
    fast = tmp_path / 'fast/licenses'
    reference = tmp_path / 'reference/licenses'
    actual = legal._extract_qt_legal_material('qtbase', archive, fast)
    monkeypatch.setattr(legal, '_qt_legal_member_cache', lambda path: (legal._tar_members(path), {}))
    expected = legal._extract_qt_legal_material('qtbase', archive, reference)
    assert actual == expected
    assert payloads(fast) == payloads(reference)
