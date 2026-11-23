"""Restore one exact partial OpenSSL SDK; never accept the failed whole pilot."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import posixpath
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from download_diagnostic_artifact import fetch_artifact

REPO = Path(__file__).resolve().parents[2]


def configuration_sha256(raw: bytes) -> str:
    return hashlib.sha256(json.dumps(json.loads(raw), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def restore(data: bytes, work: Path, output: Path, spec: dict) -> dict:
    if len(data) != spec['zip_bytes'] or hashlib.sha256(data).hexdigest() != spec['zip_sha256']:
        raise ValueError('Changed retained partial SDK ZIP')
    assert not (work / 'prefix/openssl').exists(), 'Do not overwrite an existing OpenSSL prefix'
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        for name, digest in spec['component_inputs'].items():
            assert configuration_sha256((REPO / '.github/scripts' / name).read_bytes()) == digest, name
            assert configuration_sha256(original.read(name)) == digest, name
        if spec.get('compiler_sdk'):
            current = json.loads((output / 'prerequisites.json').read_text())
            compiler = {name: current[name] for name in ['xcode', 'sdk_version']}
            compiler['clang_first_line'] = current['clang'].splitlines()[0]
            assert compiler == spec['compiler_sdk'], 'Changed Xcode/Clang/SDK: partial prefix is not qualified for reuse'
        receipt = json.loads(original.read('macos-runtime-sdk.json'))
        assert receipt['source_sha'] == spec['source_sha'] and receipt['machine'] == 'arm64'
        assert not receipt['complete_pilot'] and receipt['pilot_exit_code'] != 0
        assert Path(receipt['original_work_root']) == work, 'Preserve actual install names/default trust paths'
        sdk = original.read('macos-runtime-sdk.tar.zst')
        assert hashlib.sha256(sdk).hexdigest() == receipt['archive_sha256'] == spec['sdk_sha256']
        with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
            paths = set()
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts and path.parts[0] == 'prefix'
                if member.isdir():
                    continue
                assert member.isfile() or member.issym() or member.islnk()
                if member.issym() or member.islnk():
                    target = posixpath.normpath(posixpath.join(str(path.parent) if member.issym() else '', member.linkname))
                    assert not target.startswith('/') and PurePosixPath(target).parts[0] == 'prefix'
                paths.add(member.name)
            assert paths == set(receipt['paths'])
            selected = [member for member in archive.getmembers()
                        if member.name == 'prefix/openssl' or member.name.startswith('prefix/openssl/')]
            assert selected
            archive.extractall(work, members=selected, filter='data')
        restored = 0
        for name, item in receipt['paths'].items():
            if not name.startswith('prefix/openssl/'):
                continue
            path = work / name
            if 'link' in item:
                assert path.is_symlink() and os.readlink(path) == item['link']
            else:
                assert not path.is_symlink() and path.is_file() and path.stat().st_size == item['bytes']
                assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], name
            restored += 1
        assert not (work / 'prefix/python').exists(), 'Not a reusable controlled Python/Qt acceptance'
        assert (work / 'prefix/openssl/lib/libssl.4.dylib').is_file()
        for name in ['openssl-configdata.pm', 'openssl-regressions.log']:
            (output / name).write_bytes(original.read(name))
        (output / 'original-partial-sdk-receipt.json').write_bytes(original.read('macos-runtime-sdk.json'))
    result = {'consumer_source_sha': os.environ.get('GITHUB_SHA'), 'original': spec,
              'restored_paths': restored, 'original_index_paths': len(receipt['paths']), 'unchanged_original_work_root': str(work),
              'scope': 'Byte-verified partial prefix reuse only; original OpenSSL test log is historical; current native Python/Qt/TLS/provider/GUI acceptance still required'}
    (output / 'partial-sdk-intake.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['select', 'restore'])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'darwin'
    spec = json.loads((REPO / '.github/scripts/macos_arm64_partial_sdk_sources.json').read_text())
    root = Path(os.environ['RUNNER_TEMP']).resolve()
    work = root / spec['work_name']
    assert work.parent == root and work.name == spec['work_name']
    args.output.mkdir(parents=True, exist_ok=True)
    if args.mode == 'select':
        assert not work.exists()
        with Path(os.environ['GITHUB_ENV']).open('a') as env:
            env.write('PSAA_MACOS_PILOT_WORK=' + str(work) + '\n')
        return
    assert work.is_dir() and Path(os.environ['PSAA_MACOS_PILOT_WORK']) == work
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['id'] == spec['run']
    assert metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['digest'] == 'sha256:' + spec['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    restore(data, work, args.output, spec)
    with Path(os.environ['GITHUB_ENV']).open('a') as env:
        env.write('PSAA_REUSED_MACOS_OPENSSL=1\n')
    print('PASS byte-verified original partial OpenSSL prefix; no whole runtime acceptance')


if __name__ == '__main__':
    main()
