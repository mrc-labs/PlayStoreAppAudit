"""Resume one exact compiled SDK without recompiling its Python/Qt providers."""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from apply_qt_http_limits import contract, public_limits
from download_diagnostic_artifact import fetch_artifact
from reuse_macos_arm64_partial_sdk import configuration_sha256

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    spec = json.loads((ROOT / '.github/scripts/macos_arm64_compiled_sdk_sources.json').read_text())
    output = ROOT / 'macos-arm64-pilot-evidence'
    output.mkdir(exist_ok=True)
    context = {'xcode': subprocess.check_output(['xcodebuild', '-version'], text=True),
               'sdk_version': subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-version'], text=True).strip(),
               'clang_first_line': subprocess.check_output(['xcrun', 'clang', '--version'], text=True).splitlines()[0]}
    assert context == spec['compiler_sdk'], context
    work = Path(os.environ['RUNNER_TEMP']).resolve() / spec['work_name']
    assert work.parent == Path(os.environ['RUNNER_TEMP']).resolve() and not work.exists()
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        for name, digest in spec['component_inputs'].items():
            assert configuration_sha256(original.read(name)) == digest
            assert configuration_sha256((ROOT / '.github/scripts' / name).read_bytes()) == digest
        receipt = json.loads(original.read('macos-runtime-sdk.json'))
        assert receipt['source_sha'] == spec['source_sha'] and receipt['machine'] == 'arm64'
        assert Path(receipt['original_work_root']) == work and not receipt['complete_pilot']
        sdk = original.read('macos-runtime-sdk.tar.zst')
        assert hashlib.sha256(sdk).hexdigest() == receipt['archive_sha256'] == spec['sdk_sha256']
        work.mkdir()
        with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
            members = archive.getmembers()
            files = set()
            for member in members:
                path = PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts and path.parts[0] in {'prefix', 'venv'}
                assert member.isdir() or member.isfile() or member.issym() or member.islnk()
                if not member.isdir():
                    files.add(member.name)
                if member.issym() or member.islnk():
                    target = Path(member.linkname)
                    target = target if target.is_absolute() else (work / path.parent if member.issym() else work) / target
                    assert Path(os.path.normpath(target)).is_relative_to(work)
            assert files == set(receipt['paths'])
            archive.extractall(work, members=[m for m in members if not m.issym()], filter='data')
            for member in members:
                if member.issym():
                    os.symlink(member.linkname, work / member.name)
        for name, entry in receipt['paths'].items():
            path = work / name
            assert path.resolve().is_relative_to(work)
            if 'link' in entry:
                assert path.is_symlink() and os.readlink(path) == entry['link']
            else:
                assert path.is_file() and not path.is_symlink() and path.stat().st_size == entry['bytes']
                assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        for source, digest in contract()['final_files'].items():
            name = Path(source).name
            raw = original.read(name)
            assert hashlib.sha256(raw).hexdigest() == digest, name
            (output / name).write_bytes(raw)
        (output / 'original-compiled-sdk-receipt.json').write_bytes(original.read('macos-runtime-sdk.json'))
    (output / 'compiled-sdk-intake.json').write_text(json.dumps({'original': spec, 'verified_paths': len(receipt['paths']),
        'scope': 'Exact compiled bytes only; original failed whole pilot remains unqualified'}, indent=2) + '\n')
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = '14.4'
    public_limits(work / 'prefix/qt', work / 'public-http-tests', output / 'public-http')
    print('PASS exact compiled SDK/public HTTP consumer; bindings/GUI/TLS acceptance remains pending')


if __name__ == '__main__':
    main()
