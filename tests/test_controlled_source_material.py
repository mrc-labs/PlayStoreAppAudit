from __future__ import annotations

import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest
from controlled_source_material import prepare_legal_sources, retain_zip_material
from validate_release_legal_bundle import ValidationError, _validate_controlled_sources


def _archive(files: dict[str, bytes]) -> zipfile.ZipFile:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    stream.seek(0)
    return zipfile.ZipFile(stream)


def test_qualified_sources_and_licenses_preserve_bytes_and_nested_provenance(tmp_path: Path) -> None:
    nested = _archive({'sources/parser.tar.gz': b'parser source fixture', 'legal/COPYING.LIB': b'LGPL fixture'})
    with _archive({'sources/runtime.tar.xz': b'runtime source fixture', 'legal/NOTICE': b'notice fixture',
                   'sources/libclang-host.7z': b'not source', 'prefix/native.dll': b'not source',
                   'legal/temporary-key.pem': b'private fixture',
                   'parser/original-qualified-lxml.zip': nested.fp.getvalue()}) as archive:
        retain_zip_material(archive, tmp_path, 'qualified artifact fixture')
    records = json.loads((tmp_path / 'INPUT-MATERIAL.json').read_text())
    assert len(records) == 4
    assert {record['role'] for record in records} == {'qualified SDK source input', 'qualified SDK license input'}
    assert any('original-qualified-lxml.zip' in record['origin'] for record in records)
    for record in records:
        assert hashlib.sha256((tmp_path / record['file']).read_bytes()).hexdigest() == record['sha256']
    assert (tmp_path / 'sources/runtime.tar.xz').read_bytes() == b'runtime source fixture'
    assert (tmp_path / 'sources/parser.tar.gz').read_bytes() == b'parser source fixture'


def test_conflicting_sources_are_rejected_without_replacing_existing_bytes(tmp_path: Path) -> None:
    with _archive({'sources/provider.tar.gz': b'original'}) as archive:
        retain_zip_material(archive, tmp_path, 'original')
    with _archive({'sources/provider.tar.gz': b'different'}) as archive, pytest.raises(ValueError, match='Conflicting'):
        retain_zip_material(archive, tmp_path, 'changed')
    assert (tmp_path / 'sources/provider.tar.gz').read_bytes() == b'original'


def test_unsafe_source_member_is_rejected(tmp_path: Path) -> None:
    with _archive({'sources/../../outside.tar.gz': b'escape'}) as archive, pytest.raises(ValueError, match='Unsafe'):
        retain_zip_material(archive, tmp_path, 'unsafe')
    assert not (tmp_path.parent / 'outside.tar.gz').exists()


def test_linux_parser_consumer_retains_its_original_compilation_sources(tmp_path: Path) -> None:
    original = _archive({'sources/libxml2.tar.xz': b'compiled parser source', 'legal/COPYING': b'parser license'})
    consumer = _archive({'original-lxml-123.zip': original.fp.getvalue()})
    with _archive({'parser/original-qualified-lxml.zip': consumer.fp.getvalue()}) as archive:
        retain_zip_material(archive, tmp_path, 'verified parser consumer')
    records = json.loads((tmp_path / 'INPUT-MATERIAL.json').read_text())
    assert (tmp_path / 'sources/libxml2.tar.xz').read_bytes() == b'compiled parser source'
    assert all('original-lxml-123.zip' in record['origin'] for record in records)


def test_release_material_contains_original_bytes_recipes_and_validated_licenses(tmp_path: Path) -> None:
    material, assets, package, repo = [tmp_path / name for name in ['material', 'assets', 'package', 'repo']]
    assets.mkdir()
    (repo / '.github/patches').mkdir(parents=True)
    (repo / '.github/patches/provider.patch').write_bytes(b'reviewable patch fixture')
    (repo / 'LICENSE').write_bytes(b'project license fixture')
    with _archive({'sources/provider.tar.gz': b'original source fixture', 'legal/COPYING': b'original license fixture'}) as archive:
        retain_zip_material(archive, material, 'hash-verified SDK fixture')
    selection = {'identity': 'Project-modified fixture', 'target': 'linux-x64', 'preparation_source_sha': 'a' * 40,
                 'work': '/home/runner/private-work', 'python': 'C:\\private\\python.exe'}
    sources, controlled = prepare_legal_sources(material, selection, repo, assets, package / 'licenses')
    assert (assets / 'provider.tar.gz').read_bytes() == b'original source fixture'
    with tarfile.open(assets / 'PSAA-v2.4.0-controlled-recipes-linux-x64.tar.xz') as archive:
        assert archive.extractfile('.github/patches/provider.patch').read() == b'reviewable patch fixture'
        archived = json.load(archive.extractfile('DEPENDENCY-SDK-SELECTION.json'))
        assert archived['preparation_source_sha'] == selection['preparation_source_sha']
        assert 'work' not in archived and 'python' not in archived
    sidecar = package / 'licenses/controlled-runtime/INPUTS.json'
    sidecar.parent.mkdir(exist_ok=True)
    sidecar.write_text(json.dumps(controlled))
    manifest = {'source_assets': sources, 'controlled_dependency_inputs': controlled}
    from validate_release_legal_bundle import _validate_portable_manifest

    _validate_portable_manifest(manifest)
    _validate_controlled_sources(package, manifest)
    record = controlled['license_records'][0]
    (package / record['file']).write_bytes(b'tampered')
    with pytest.raises(ValidationError, match='license bytes changed'):
        _validate_controlled_sources(package, manifest)


def test_build_only_dll_loader_is_forbidden_in_packages(tmp_path: Path) -> None:
    from prepare_release_legal_bundle import _forbidden_matches

    (tmp_path / '_psaa_sdk_dll_paths.py').write_text('build-only')
    assert _forbidden_matches(tmp_path)[0]['reason'] == 'Build-only controlled SDK loader must not ship'
