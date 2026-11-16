"""Recover bound Windows SDKs; rebuild only tiny diagnostic consumers."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from build_windows_current_framework import ROOT, consumers_only, settings
from download_diagnostic_artifact import fetch_artifact


def compiled_inputs(raw: str) -> dict:
    # b396 changed only extractor selection: ARM retains the same native 7z.exe.
    raw = raw.replace("    matches = [p for p in (work / '7zip').rglob('7z.exe') if read_pe_machine(p) == machine]\n    assert len(matches) == 1\n",
                      "    seven = native_extractor(work / '7zip', arch, machine)\n")
    raw = raw.replace("run([matches[0], 'x', '-y', '-o' + str(src), parser_archive]", "run([seven, 'x', '-y', '-o' + str(src), parser_archive]")
    tree = ast.parse(raw)
    result = {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
              for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in {'prepare', 'build_qt'}}
    binding = raw.split('def bindings_and_consumers(', 1)[1]
    binding = binding.split("    for name in ['SSL_CERT_FILE'", 1)[0].split('    consumers_only(arch, work, output)', 1)[0]
    binding = binding.replace("    state = json.loads((output / 'windows-framework-inputs.json').read_text())\n", '')
    result['binding_build_prefix'] = hashlib.sha256(binding.replace('\r\n', '\n').encode()).hexdigest()
    return result


def restore_bound_archive(sdk: bytes, work: Path, receipt: dict) -> None:
    assert not work.exists()
    with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
        members = archive.getmembers()
        files = []
        for member in members:
            path = PurePosixPath(member.name)
            assert not path.is_absolute() and '..' not in path.parts and path.parts[0] in {'prefix', 'venv'}
            assert member.isdir() or member.isfile() or member.issym() or member.islnk(), ('SDK special file', member.name, member.type)
            if not member.isdir():
                files.append(member.name)
            if member.issym():
                assert receipt['paths'][member.name].get('link') == member.linkname
                target = Path(member.linkname)
                target = target if target.is_absolute() else work / path.parent / target
                assert Path(os.path.normpath(target)).is_relative_to(work), ('SDK symlink escape', member.name)
            if member.islnk():
                target = PurePosixPath(member.linkname)
                assert not target.is_absolute() and '..' not in target.parts and target.parts[0] in {'prefix', 'venv'}
                # The retainer indexes hard links as their actual regular-file bytes.
                assert receipt['paths'][member.name] == receipt['paths'][member.linkname]
        assert len(files) == len(set(files)) and set(files) == set(receipt['paths'])
        work.mkdir()
        archive.extractall(work, members=[member for member in members if not member.issym()], filter='data')
        for member in members:
            if member.issym():
                os.symlink(member.linkname, work / member.name)
    for name, entry in receipt['paths'].items():
        path = work / name
        assert path.resolve().is_relative_to(work)
        if 'link' in entry:
            assert path.is_symlink() and os.readlink(path) == entry['link']
        else:
            assert not path.is_symlink() and path.is_file()
            assert path.stat().st_size == entry['bytes'] and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256'], name


def main() -> None:
    arch, machine, work, compiler = settings()
    spec = json.loads((ROOT / '.github/scripts/windows_framework_bound_sdks.json').read_text())[arch]
    assert compiled_inputs((ROOT / '.github/scripts/build_windows_current_framework.py').read_text()) == spec['compiled_inputs']
    assert not work.exists(), 'Preserve unexpected local native work'
    output = ROOT / 'toolchain-delta-evidence'
    output.mkdir(exist_ok=True)
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert len(data) == spec['zip_bytes'] and hashlib.sha256(data).hexdigest() == spec['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    with zipfile.ZipFile(io.BytesIO(data)) as original:
        state = json.loads(original.read('windows-framework-inputs.json'))
        assert state['source_sha'] == spec['source_sha'] and state['arch'] == arch and state['compiler'] == str(compiler)
        base = json.loads((ROOT / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
        native = json.loads((ROOT / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
        selected = [row for row in base['sources'] if row['directory'].startswith(('libpng-', 'pcre2-', 'qtbase-', 'qtsvg-', 'pyside-'))]
        selected += [next(row for row in native['sources'] if row['directory'] == 'zlib-1.4')]
        assert state['framework_sources'] == selected and state['pyside_patch'] == base['pyside_windows_patch']
        report = json.loads(original.read('pilot-results.json'))
        assert report['source_sha'] == spec['source_sha'] and report['gui'].startswith('native Windows')
        receipt_raw = original.read('windows-framework-sdk.json')
        receipt = json.loads(receipt_raw)
        assert receipt['source_sha'] == spec['source_sha'] and Path(receipt['original_work_root']).resolve() == work
        assert receipt['machine'].lower() == ('arm64' if arch == 'arm64' else 'amd64')
        sdk = original.read('windows-framework-sdk.tar.zst')
        assert hashlib.sha256(sdk).hexdigest() == receipt['archive_sha256']
        with tarfile.open(fileobj=io.BytesIO(sdk)) as archive:
            links = [{'name': member.name, 'type': 'symlink' if member.issym() else 'hardlink', 'target': member.linkname}
                     for member in archive if member.issym() or member.islnk()]
        (output / 'original-sdk-links.json').write_text(json.dumps(links, indent=2))
        print('Original SDK indexed links:', json.dumps(links[:12]), 'total:', len(links), flush=True)
        restore_bound_archive(sdk, work, receipt)
        historical = output / 'original-framework-results'
        historical.mkdir()
        for name in original.namelist():
            path = PurePosixPath(name)
            assert not path.is_absolute() and '..' not in path.parts
            if name.endswith('/') or path.name.endswith('key.pem') or any('certificates' in part for part in path.parts):
                continue
            if name.endswith(('.json', '.xml', '.log', '.patch')) or name.startswith('legal/'):
                target = historical / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original.read(name))
            if name in {'windows-framework-inputs.json', 'windows-framework-qt.json'} or name.startswith('provider-security-inputs/'):
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original.read(name))
        (output / 'original-runtime').mkdir()
        for name in ['cpython-regressions.xml', 'tarfile-security-regression.log']:
            (output / 'original-runtime' / name).write_bytes(original.read('original-runtime/' + name))
        (output / 'original-framework-sdk.json').write_bytes(receipt_raw)
    del data, sdk
    intake = {'original': spec, 'verified_paths': len(receipt['paths']), 'consumer_source_sha': os.environ['GITHUB_SHA'],
              'receipt_sha256': hashlib.sha256(receipt_raw).hexdigest(),
              'scope': 'Original bound SDK bytes; previous whole run failed in diagnostic orchestration. Recompile only the tiny C++ consumers, not Qt/Python/bindings.'}
    (output / 'framework-sdk-intake.json').write_text(json.dumps(intake, indent=2) + '\n')
    # native_security stages fresh public inputs; original copies stay historical.
    if (output / 'provider-security-inputs').exists():
        (output / 'provider-security-inputs').rename(output / 'original-provider-security-inputs')
    consumers_only(arch, work, output)
    print('PASS restored native Windows consumers; no runtime/framework/binding rebuild', hex(machine), flush=True)


if __name__ == '__main__':
    main()
