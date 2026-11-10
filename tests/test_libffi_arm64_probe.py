from __future__ import annotations

import hashlib
from pathlib import Path

import probe_libffi_arm64 as probe
import pytest


def test_altered_libffi_source_is_rejected_before_extraction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_) -> None:
            return None

        def geturl(self) -> str:
            return probe.URL

        def read(self) -> bytes:
            return b'altered source fixture'

    monkeypatch.setattr(probe.urllib.request, 'urlopen', lambda *args, **kwargs: Response())
    extracted = []
    monkeypatch.setattr(probe.tarfile, 'open', lambda *args, **kwargs: extracted.append(args))
    with pytest.raises(ValueError, match='official libffi source digest'):
        probe.fetch_source(tmp_path, tmp_path)
    assert not extracted and not list(tmp_path.glob('*.tar.gz'))


def test_libffi_arm64_prerequisites_cannot_start_full_source_builds() -> None:
    root=Path(__file__).resolve().parents[1]
    script=(root/'.github/scripts/probe_windows_arm64_runtime.ps1').read_text()
    branch=script.split('\nif ($FfiPrerequisitesOnly) {',1)[1].split('\n}',1)[0]
    assert '$HostTools -or $FullPilot' in branch and 'return' in branch
    assert 'probe_libffi_arm64.py' in branch
    assert 'build_windows_arm64_runtime_pilot.py' not in branch


@pytest.mark.parametrize('changed', ['source', 'patch'])
def test_libffi_alignment_patch_integrity_fails_before_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    patch = tmp_path / 'alignment.patch'
    patch.write_bytes(b'reviewed fixture')
    target = tmp_path / 'src/aarch64/ffi.c'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'original fixture')
    spec = {'path':patch.name, 'sha256':hashlib.sha256(patch.read_bytes()).hexdigest(),
            'original_sha256':hashlib.sha256(target.read_bytes()).hexdigest(), 'patched_sha256':'0'*64}
    if changed == 'source':
        target.write_bytes(b'changed source')
    else:
        patch.write_bytes(b'changed patch')
    called = []
    monkeypatch.setattr(probe, 'REPO', tmp_path)
    monkeypatch.setattr(probe, 'run', lambda *args, **kwargs: called.append(args))
    with pytest.raises(ValueError, match='Changed'):
        probe.apply_alignment_patch(tmp_path, tmp_path, spec)
    assert not called
