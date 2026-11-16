"""Resume one exact compiled SDK without recompiling its Python/Qt providers."""
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

from apply_qt_http_limits import contract, public_limits
from download_diagnostic_artifact import fetch_artifact
from reuse_macos_arm64_partial_sdk import configuration_sha256

ROOT = Path(__file__).resolve().parents[2]


def imageformats_environment(work: Path, output: Path) -> dict[str, str]:
    environment = {**os.environ, 'QT_PLUGIN_PATH': str(work / 'prefix/qt/plugins'), 'QT_QPA_PLATFORM': 'cocoa',
                   'PILOT_WORK': str(work), 'PILOT_PREFIX': str(work / 'prefix'), 'PILOT_EVIDENCE': str(output)}
    for name in ['GH_TOKEN', 'GITHUB_TOKEN', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH',
                 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'PYTHONHOME', 'PYTHONPATH']:
        environment.pop(name, None)
    return environment


def finish_bindings(work: Path, output: Path, *, consumers_only: bool = False) -> None:
    from probe_macos_arm64_runtime import clang_extraction, fetch, macho, run, unpack
    from probe_macos_arm64_runtime import contract as runtime_contract

    arm, base = runtime_contract()
    if not consumers_only:
        sources = output / 'sources'
        src = work / 'src'
        src.mkdir(exist_ok=True)
        pyside = next(row for row in base['sources'] if row['directory'].startswith('pyside-setup-'))
        unpack(fetch(pyside, sources), src)
        extractor = work / 'extractor'
        extractor.mkdir()
        unpack(fetch(arm['host_extractor'], sources), extractor)
        seven = extractor / '7zz'
        seven.chmod(0o755)
        macho(seven, target=False, output=output)
        archive = fetch(arm['host_libclang'], sources)
        run(clang_extraction(seven, archive, src, arm['host_libclang']), log=output / 'libclang-extract.log')
        library = src / 'libclang/lib/libclang.dylib'
        macho(library.resolve(), target=False, output=output)
    prefix = work / 'prefix'
    python = work / 'venv/bin/python'
    environment = {**os.environ, 'PATH': str(python.parent) + os.pathsep + os.environ['PATH'],
        'PILOT_WORK': str(work), 'PILOT_PREFIX': str(prefix), 'PILOT_EVIDENCE': str(output),
        'SDKROOT': subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip(),
        'CC': subprocess.check_output(['xcrun', '--find', 'clang'], text=True).strip(),
        'CXX': subprocess.check_output(['xcrun', '--find', 'clang++'], text=True).strip(),
        'MACOSX_DEPLOYMENT_TARGET': '14.4', 'CFLAGS': '-arch arm64', 'CXXFLAGS': '-arch arm64', 'ARCHFLAGS': '-arch arm64',
        'Python_ROOT_DIR': str(prefix / 'python'), 'Python3_ROOT_DIR': str(prefix / 'python'),
        'PKG_CONFIG_LIBDIR': f'{prefix}/python/lib/pkgconfig:{prefix}/lib/pkgconfig:{prefix}/openssl/lib/pkgconfig',
        'CMAKE_PREFIX_PATH': f'{prefix}:{prefix}/openssl'}
    if consumers_only:
        environment['PSAA_MACOS_BINDINGS_READY'] = '1'
    environment.pop('GH_TOKEN', None)
    # Preserve the exact source prefix/default trust paths, with no loader fallback.
    for name in ['DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'PYTHONHOME', 'PYTHONPATH']:
        environment.pop(name, None)
    # Fresh read-only OS trust evidence, distinct from the compiled private PEM.
    roots = subprocess.check_output(['/usr/bin/security', 'find-certificate', '-a', '-p',
        '/System/Library/Keychains/SystemRootCertificates.keychain'])
    assert b'BEGIN CERTIFICATE' in roots
    (output / 'keychain-system-roots.pem').write_bytes(roots)
    (output / 'current-keychain-capture.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'os': platform.mac_ver(),
        'sha256': hashlib.sha256(roots).hexdigest(), 'scope': 'Fresh public SystemRoot Keychain snapshot only; no trust store mutation or injection'}, indent=2) + '\n')
    result = subprocess.run(['bash', '-c', 'repo="$PWD"; work="$PILOT_WORK"; prefix="$PILOT_PREFIX"; '
        'evidence="$PILOT_EVIDENCE"; source "$repo/.github/scripts/finish_macos_arm64_runtime_pilot.sh"'],
        cwd=ROOT, env=environment)
    result.check_returncode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group()
    phase.add_argument('--bindings', action='store_true')
    phase.add_argument('--consumers-only', action='store_true')
    parser.add_argument('--imageformats', action='store_true')
    parser.add_argument('--intake-only', action='store_true')
    args = parser.parse_args()
    assert not args.imageformats or args.consumers_only
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    spec = json.loads((ROOT / '.github/scripts' / ('macos_arm64_bound_sdk_sources.json' if args.consumers_only else 'macos_arm64_compiled_sdk_sources.json')).read_text())
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
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        for name, digest in spec['component_inputs'].items():
            assert configuration_sha256(original.read(name)) == digest
            assert configuration_sha256((ROOT / '.github/scripts' / name).read_bytes()) == digest
        receipt = json.loads(original.read('macos-runtime-sdk.json'))
        assert receipt['source_sha'] == spec['source_sha'] and receipt['machine'] == 'arm64'
        assert Path(receipt['original_work_root']) == work and not receipt['complete_pilot']
        sdk = original.read('macos-runtime-sdk.tar.zst')
        assert hashlib.sha256(sdk).hexdigest() == receipt['archive_sha256']
        if 'sdk_sha256' in spec:
            assert receipt['archive_sha256'] == spec['sdk_sha256']
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
        if args.bindings or args.consumers_only:
            for name in original.namelist():
                if args.imageformats:
                    # Original source/legal/runtime proofs stay at the exact bound
                    # artifact; do not duplicate its large archives for one module.
                    continue
                path = PurePosixPath(name)
                assert not path.is_absolute() and '..' not in path.parts
                if name.startswith('lxml-qualified/controlled-runtime/') or name.endswith('/') or name.startswith('macos-runtime-sdk.') or any('certificates' in part for part in path.parts):
                    continue
                if path.name.endswith('key.pem'):
                    continue
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original.read(name))
        (output / 'original-compiled-sdk-receipt.json').write_bytes(original.read('macos-runtime-sdk.json'))
    del data, sdk
    if args.imageformats:
        from complete_qt_imageformats import restore_arm64_overlay

        restore_arm64_overlay(work, output)
    os.environ.pop('GH_TOKEN', None)
    (output / 'compiled-sdk-intake.json').write_text(json.dumps({'original': spec, 'verified_paths': len(receipt['paths']),
        'scope': 'Exact compiled bytes only; original failed whole pilot remains unqualified'}, indent=2) + '\n')
    os.environ['MACOSX_DEPLOYMENT_TARGET'] = '14.4'
    if args.intake_only:
        from controlled_runtime_selection import record_selection

        assert args.imageformats, 'Preserve qualified image plugin membership'
        record_selection('macos-arm64', work, output, output / 'original-compiled-sdk-receipt.json')
        return
    if args.imageformats:
        environment = imageformats_environment(work, output)
        subprocess.run([str(work / 'venv/bin/python'), str(ROOT / '.github/scripts/verify_macos_arm64_imageformats.py'),
                        '--work', str(work), '--output', str(output), '--reuse-overlay'], cwd=ROOT, env=environment, check=True)
        return
    public_limits(work / 'prefix/qt', work / 'public-http-tests', output / 'public-http')
    if args.consumers_only:
        finish_bindings(work, output, consumers_only=True)
    elif args.bindings:
        from retain_macos_runtime_sdk import retain

        try:
            finish_bindings(work, output)
        finally:
            retain(work, output, 0 if (output / 'pilot-results.json').is_file() else 1)
    else:
        print('PASS exact compiled SDK/public HTTP consumer; bindings/GUI/TLS acceptance remains pending')


if __name__ == '__main__':
    main()
