"""Retain source/license inputs from already hash-qualified project SDK archives."""
from __future__ import annotations

import hashlib
import io
import json
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def retain_zip_material(archive: zipfile.ZipFile, destination: Path, origin: str, *, depth: int = 0) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    index_path = destination / 'INPUT-MATERIAL.json'
    records = json.loads(index_path.read_text()) if index_path.exists() else []
    for name in archive.namelist():
        path = PurePosixPath(name)
        if name.endswith('/'):
            continue
        if path.name.endswith(('key.pem', '.pfx', '.p12')):
            continue
        if path.name == 'original-qualified-lxml.zip' or re.fullmatch(r'original-lxml-\d+\.zip', path.name):
            if depth >= 3:
                raise ValueError('Excessive parser source archive nesting')
            payload = archive.read(name)
            assert len(payload) < 100 * 1024**2
            index_path.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
            with zipfile.ZipFile(io.BytesIO(payload)) as parser_archive:
                retain_zip_material(parser_archive, destination, origin + ':' + name, depth=depth + 1)
            records = json.loads(index_path.read_text()) if index_path.exists() else records
            continue
        source = 'sources' in path.parts
        legal = 'legal' in path.parts or 'licenses' in path.parts
        if not (source or legal):
            continue
        if path.is_absolute() or '..' in path.parts or any(':' in part or '\\' in part for part in path.parts):
            raise ValueError('Unsafe controlled material member')
        if source and (path.name.startswith(('libclang-', 'rustup-', 'rust-'))
                or re.fullmatch(r'7z\d+-mac\.tar\.xz|nasm-.*-win64\.zip', path.name) or not
                (path.name.endswith(('.tar.gz', '.tar.xz', '.tgz', '.crate', '.zip', '.dat', '.xml'))
                 or path.name.startswith('certifi-') and path.name.endswith('.whl'))):
            continue
        payload = archive.read(name)
        if legal and b'\0' in payload[:4096]:
            continue
        digest = hashlib.sha256(payload).hexdigest()
        relative = ('sources/' + path.name) if source else ('licenses/' + digest + '.txt')
        target = destination / relative
        target.parent.mkdir(exist_ok=True)
        if target.exists() and target.read_bytes() != payload:
            raise ValueError('Conflicting controlled source filename: ' + path.name)
        target.write_bytes(payload)
        record = {'file': relative, 'sha256': digest, 'bytes': len(payload), 'origin': origin,
                  'original_member': name, 'role': 'qualified SDK source input' if source else 'qualified SDK license input'}
        if record not in records:
            records.append(record)
    index_path.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')


def retain_directory_material(root: Path, destination: Path, origin: str) -> None:
    """Collect the same explicit source/license material from a verified intake."""
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as archive:
        for path in root.rglob('*'):
            if path.is_file() and not path.is_relative_to(destination):
                relative = path.relative_to(root)
                source = 'sources' in relative.parts and not path.name.startswith(('libclang-', 'rustup-', 'rust-')) and (
                    path.name.endswith(('.tar.gz', '.tar.xz', '.tgz', '.crate', '.zip', '.dat', '.xml'))
                    or path.name.startswith('certifi-') and path.name.endswith('.whl'))
                if source or 'legal' in relative.parts or 'licenses' in relative.parts or path.name == 'original-qualified-lxml.zip' or re.fullmatch(r'original-lxml-\d+\.zip', path.name):
                    archive.write(path, relative.as_posix())
    stream.seek(0)
    with zipfile.ZipFile(stream) as archive:
        retain_zip_material(archive, destination, origin)


def retain_required_sources(material: Path, repo: Path) -> None:
    """Complete originals selected by the existing, qualified source contracts."""
    from probe_qt_text_providers import checked_source

    scripts = repo / '.github/scripts'
    sources = [json.loads((scripts / 'macos_arm64_runtime_pilot_sources.json').read_text())['cryptography_source']]
    for name in ['qt_text_provider_sources.json', 'qt_data_refresh_sources.json',
                 'qt_cldr49_sources.json', 'linux_x64_native_delta_sources.json', 'lxml_native_sources.json']:
        sources.extend(json.loads((scripts / name).read_text())['sources'])
    sources.append(json.loads((scripts / 'qt_cbor_provider_sources.json').read_text())['source'])
    directory = material.parent / 'controlled-required-originals/sources'
    directory.mkdir(parents=True)
    for spec in sources:
        existing = material / 'sources' / spec['name']
        if existing.exists():
            if hashlib.sha256(existing.read_bytes()).hexdigest() != spec['sha256']:
                raise ValueError('Retained source disagrees with qualified source contract: ' + spec['name'])
        else:
            checked_source(spec, directory)
    retain_directory_material(directory.parent, material, 'Official originals from unchanged qualified source contracts')


def prepare_legal_sources(material: Path, selection: dict, repo: Path, assets: Path,
                          licenses: Path) -> tuple[list[dict], dict]:
    """Add audited SDK originals and the project build/patch recipes to legal assets."""
    records = json.loads((material / 'INPUT-MATERIAL.json').read_text())
    assert records and selection['identity'].startswith('Project-modified')
    sources, license_records = {}, []
    for record in records:
        relative = PurePosixPath(record['file'])
        assert not relative.is_absolute() and '..' not in relative.parts
        path = material / relative
        raw = path.read_bytes()
        assert len(raw) == record['bytes'] and hashlib.sha256(raw).hexdigest() == record['sha256']
        if relative.parts[0] == 'sources':
            target = assets / path.name
            if target.exists() and target.read_bytes() != raw:
                raise ValueError('Conflicting controlled release source: ' + path.name)
            target.write_bytes(raw)
            sources[path.name] = {'component': 'controlled SDK source input', 'filename': path.name,
                'sha256': record['sha256'], 'size': len(raw),
                'download_url': 'https://github.com/mrc-labs/PlayStoreAppAudit/actions',
                'provenance_url': 'https://github.com/mrc-labs/PlayStoreAppAudit/pull/239',
                'controlled_sdk_origin': record['origin'], 'original_member': record['original_member']}
        else:
            digest = record['sha256']
            destination = licenses / 'controlled-runtime/payloads' / (digest + '.txt')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            relative_license = destination.relative_to(licenses.parent).as_posix()
            license_records.append({'file': relative_license, 'sha256': digest,
                                    'origin': record['origin'], 'original_member': record['original_member']})
    # Original Qt archives alone cannot describe project modifications. Carry the
    # exact repository recipe/patch/data inputs alongside their original SDK IDs.
    recipe_name = 'PSAA-v2.4.0-controlled-recipes-' + selection['target'] + '.tar.xz'
    recipe = assets / recipe_name
    # Host paths are local intake implementation details, not portable provenance.
    portable_selection = {key: selection[key] for key in (
        'target', 'identity', 'preparation_source_sha', 'compiled_source_sha',
        'compiled_component_sources', 'qt_receipt_sha256', 'overlay') if key in selection}
    provenance = json.dumps(portable_selection, indent=2).encode()
    with tarfile.open(recipe, 'w:xz') as archive:
        info = tarfile.TarInfo('DEPENDENCY-SDK-SELECTION.json')
        info.size = len(provenance)
        archive.addfile(info, io.BytesIO(provenance))
        for directory in ['.github/scripts', '.github/patches', '.github/sources']:
            for path in sorted((repo / directory).rglob('*')):
                if not path.is_file() or '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                info = archive.gettarinfo(path, arcname=path.relative_to(repo).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
        info = archive.gettarinfo(repo / 'LICENSE', arcname='LICENSE')
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = ''
        with (repo / 'LICENSE').open('rb') as stream:
            archive.addfile(info, stream)
    sources[recipe_name] = {'component': 'project-controlled build and patch recipes', 'filename': recipe_name,
        'sha256': hashlib.sha256(recipe.read_bytes()).hexdigest(), 'size': recipe.stat().st_size,
        'download_url': 'https://github.com/mrc-labs/PlayStoreAppAudit/tree/' + selection['preparation_source_sha'],
        'provenance_url': 'https://github.com/mrc-labs/PlayStoreAppAudit/pull/239'}
    if not sources or not license_records:
        raise ValueError('Controlled source and license material must both be present')
    return list(sources.values()), {'identity': selection['identity'], 'target': selection['target'],
        'sdk_selection': portable_selection, 'sources': sorted(sources), 'license_records': license_records,
        'scope': 'Qualified SDK source/license inputs and exact project recipes. Original upstream Qt attribution records describe upstream archives; actual project modifications retain explicit input/patch provenance.'}
