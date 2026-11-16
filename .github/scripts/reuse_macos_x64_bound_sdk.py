"""Replay native Intel consumers from one completed, byte-closed diagnostic SDK."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from download_diagnostic_artifact import fetch_artifact
from reuse_macos_arm64_partial_sdk import configuration_sha256

ROOT = Path(__file__).resolve().parents[2]


def restore(data: bytes, work: Path, output: Path, spec: dict) -> dict:
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    assert not work.exists(), 'Never overwrite another SDK'
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        for name, digest in spec['component_inputs'].items():
            assert configuration_sha256(original.read(name)) == digest, name
            assert configuration_sha256((ROOT / '.github/scripts' / name).read_bytes()) == digest, name
        for name, digest in spec['compiled_scripts'].items():
            assert hashlib.sha256((ROOT / '.github/scripts' / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest, name
        receipt = json.loads(original.read('macos-runtime-sdk.json'))
        assert receipt['source_sha'] == spec['source_sha'] and receipt['machine'] == 'x86_64'
        assert receipt['complete_pilot'] and receipt['pilot_exit_code'] == 0
        assert receipt['original_work_root'] == str(work) == spec['original_work_root']
        sdk = original.read('macos-runtime-sdk.tar.zst')
        assert hashlib.sha256(sdk).hexdigest() == receipt['archive_sha256'] == spec['sdk_sha256']
        with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
            members = archive.getmembers()
            files = []
            for member in members:
                path = PurePosixPath(member.name)
                assert not path.is_absolute() and '..' not in path.parts and path.parts[0] in {'prefix', 'venv'}
                assert member.isdir() or member.isfile() or member.issym() or member.islnk()
                if not member.isdir():
                    files.append(member.name)
                if member.issym() or member.islnk():
                    target = Path(member.linkname)
                    target = target if target.is_absolute() else (work / path.parent if member.issym() else work) / target
                    assert Path(os.path.normpath(target)).is_relative_to(work), member.name
            assert len(files) == len(set(files)) and set(files) == set(receipt['paths'])
            work.mkdir()
            # Absolute venv links are permitted only inside this exact original root.
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
                assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], name
        original_output = output / 'original-native-results'
        original_output.mkdir()
        for name in original.namelist():
            path = PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            if name.endswith('/') or name.endswith('.tar.zst') or any('certificates' in p for p in path.parts) or path.name.endswith('key.pem'):
                continue
            # Preserve old reports separately; current consumers create fresh reports.
            target = original_output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(original.read(name))
            if name.startswith('provider-security-inputs/'):
                fixture = output / name
                fixture.parent.mkdir(parents=True, exist_ok=True)
                fixture.write_bytes(original.read(name))
        for name in ['cpython-codec-regressions.xml', 'cpython-regressions.xml', 'tarfile-security-regression.log',
                     'cffi-runtime-tests.xml', 'cryptography-source-provenance.json', 'qt-cldr49-runtime-input.xml']:
            (output / name).write_bytes(original.read(name))
        (output / 'wheels').mkdir()
        for name in original.namelist():
            if name.startswith('wheels/cryptography-') and name.endswith('.whl'):
                (output / name).write_bytes(original.read(name))
    intake = {'original': spec, 'verified_paths': len(receipt['paths']), 'consumer_source_sha': os.environ['GITHUB_SHA'],
              'scope': 'Unchanged compiled SDK; original upstream suites retain their source identity. Fresh native consumers only; original workflow cancelled, not green.'}
    (output / 'compiled-sdk-intake.json').write_text(json.dumps(intake, indent=2) + '\n')
    return intake


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--imageformats', action='store_true')
    parser.add_argument('--reuse-unchanged-incidents', action='store_true')
    args = parser.parse_args()
    assert platform.system() == 'Darwin' and platform.machine() == 'x86_64'
    spec = json.loads((ROOT / '.github/scripts/macos_x64_bound_sdk_sources.json').read_text())
    context = {'xcode': subprocess.check_output(['xcodebuild', '-version'], text=True),
               'sdk_version': subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-version'], text=True).strip(),
               'clang_first_line': subprocess.check_output(['xcrun', 'clang', '--version'], text=True).splitlines()[0]}
    assert context == spec['compiler_sdk'], context
    work = Path(os.environ['RUNNER_TEMP']).resolve() / spec['work_name']
    assert str(work) == spec['original_work_root'] and work.parent == Path(os.environ['RUNNER_TEMP']).resolve()
    output = ROOT / 'macos-x64-pilot-evidence'
    output.mkdir(exist_ok=True)
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    os.environ.pop('GH_TOKEN', None)
    restore(data, work, output, spec)
    del data
    roots = subprocess.check_output(['/usr/bin/security', 'find-certificate', '-a', '-p', '/System/Library/Keychains/SystemRootCertificates.keychain'])
    assert b'BEGIN CERTIFICATE' in roots
    (output / 'keychain-system-roots.pem').write_bytes(roots)
    (output / 'current-keychain-capture.json').write_text(json.dumps({'consumer_source_sha': os.environ['GITHUB_SHA'],
        'sha256': hashlib.sha256(roots).hexdigest(), 'scope': 'Fresh read-only public Keychain snapshot; not Python PEM or trust mutation'}, indent=2))
    environment = {**os.environ, 'PILOT_WORK': str(work), 'PILOT_PREFIX': str(work / 'prefix'), 'PILOT_EVIDENCE': str(output),
                   'QT_QPA_PLATFORM': 'cocoa', 'QT_PLUGIN_PATH': str(work / 'prefix/qt/plugins'),
                   'PATH': str(work / 'venv/bin') + os.pathsep + os.environ['PATH']}
    for name in ['SSL_CERT_FILE', 'SSL_CERT_DIR', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH', 'PYTHONHOME', 'PYTHONPATH']:
        environment.pop(name, None)
    python = work / 'venv/bin/python'
    commands = [[python, ROOT / '.github/scripts/verify_macos_x64_runtime_pilot.py', '--output-dir', output],
                [python, ROOT / 'main.py', 'cli', 'audit', '--help'],
                [python, '-m', 'pytest', ROOT / 'tests/test_cli_headless.py', '-q'],
                [python, '-c', 'import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                 'from controlled_qt_legal_identity import source_identity;'
                 'print(json.dumps(source_identity(Path(sys.argv[2]),sys.argv[3],"6.12.0"),indent=2))',
                 ROOT / '.github/scripts', output / 'original-native-results/macos-runtime-sdk.json', spec['receipt_sha256']]]
    if args.reuse_unchanged_incidents:
        commands[0].append('--reuse-unchanged-incidents')
    if args.imageformats:
        commands[0].append('--imageformats')
        native_flags = ['-DCMAKE_OSX_ARCHITECTURES=x86_64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=14.4',
                        '-DCMAKE_OSX_SYSROOT=' + subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip(),
                        '-DCMAKE_C_COMPILER=' + subprocess.check_output(['xcrun', '--find', 'clang'], text=True).strip(),
                        '-DCMAKE_CXX_COMPILER=' + subprocess.check_output(['xcrun', '--find', 'clang++'], text=True).strip(),
                        '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local',
                        '-DCMAKE_INSTALL_RPATH=' + ';'.join(str(work / name) for name in ['prefix/qt/lib', 'prefix/lib', 'prefix/openssl/lib'])]
        commands.insert(0, [python, '-c', 'import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
                           'from complete_qt_imageformats import complete;'
                           'complete(Path(sys.argv[2]),Path(sys.argv[3]),json.loads(sys.argv[4]))',
                           ROOT / '.github/scripts', work, output, json.dumps(native_flags)])
    profile = work / 'profile'
    profile.mkdir(exist_ok=True)
    (profile / 'PlayStoreAppAudit.portable').write_text('isolated diagnostic profile\n')
    for number, command in enumerate(commands):
        # A regular file avoids inherited pipe handles keeping tee alive after PASS.
        print('Starting native consumer', number, list(map(str, command[:2])), flush=True)
        try:
            with (output / f'consumer-{number}.log').open('w') as log:
                result = subprocess.run(list(map(str, command)), cwd=ROOT if number == 0 else profile,
                                        env={**environment, 'PYTHONPATH': str(ROOT)} if number else environment,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=1200)
        finally:
            print((output / f'consumer-{number}.log').read_text(errors='replace')[-6000:], flush=True)
        result.check_returncode()
    print('PASS native Intel consumer-only replay; no Python/Qt/binding rebuild or final candidate', flush=True)


if __name__ == '__main__':
    main()
