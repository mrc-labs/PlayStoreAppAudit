"""Adopt only the six source/hash/native-qualified FFI security inputs."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from controlled_source_material import retain_zip_material
from download_diagnostic_artifact import fetch_artifact

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA256 = '81e879c094cc5ec3186c48510c6385ac6b3e866192e8bc71a35245703757ee40'


def file_identity(path: Path) -> dict:
    if path.is_symlink():
        return {'link': os.readlink(path)}
    with path.open('rb') as stream:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


def apply_posix(bundle: zipfile.ZipFile, selection: dict, output: Path) -> dict:
    result = json.loads(bundle.read('libffi381-result.json'))
    assert result['result'] == 'PASS' and result['target'] == selection['target']
    assert result['native']['libffi'] == '3.8.1'
    assert result['native']['callbacks_ctypes'] == result['native']['callbacks_cffi'] == 1200
    prefix = Path(selection['prefix']).resolve()
    assert Path(result['original_prefix']).resolve() == prefix
    for key in ['compiled_source_sha', 'compiled_component_sources']:
        assert result['original_sdk'].get(key) == selection.get(key), 'Changed original runtime/framework source'
    for name, expected in result['before'].items():
        assert file_identity(prefix / name) == expected, 'Changed original FFI input: ' + name
    payload = bundle.read('libffi381-sdk-overlay.tar.xz')
    assert hashlib.sha256(payload).hexdigest() == result['overlay_sha256']
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        members = archive.getmembers()
        assert {m.name for m in members} == {'prefix/' + name for name in result['after']}
        for member in members:
            name = member.name.removeprefix('prefix/')
            relative = PurePosixPath(name)
            assert not relative.is_absolute() and '..' not in relative.parts
            target = prefix / relative
            assert target.resolve().is_relative_to(prefix)
            expected = result['after'][name]
            if member.issym():
                assert expected == {'link': member.linkname}
                link = PurePosixPath(member.linkname)
                assert not link.is_absolute() and (target.parent / link).resolve().is_relative_to(prefix)
                if target.exists() or target.is_symlink():
                    target.unlink()
                target.symlink_to(member.linkname)
            else:
                assert member.isfile()
                data = archive.extractfile(member).read()
                assert expected == {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                if target.is_symlink():
                    target.unlink()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(member.mode)
        for name, expected in result['after'].items():
            assert file_identity(prefix / name) == expected
    return {'compiled_source_sha': result['source_sha'], 'overlay_sha256': result['overlay_sha256'],
            'library_sha256': result['native']['library_sha256']}


def apply_windows(bundle: zipfile.ZipFile, selection: dict, output: Path, environment: dict) -> dict:
    base = 'ffi381-consumers/'
    result = json.loads(bundle.read(base + 'windows-ffi381-result.json'))
    assert result['result'] == 'PASS' and result['installed']['libffi'] == '3.8.1'
    assert result['installed']['ctypes_callbacks'] == result['installed']['cffi_callbacks'] == 1200
    original = result['runtime_selection']
    for key in ['target', 'work', 'prefix', 'python', 'qt_receipt_sha256', 'compiled_source_sha']:
        assert original[key] == selection[key], 'Changed original Windows SDK: ' + key
    target = Path(result['ctypes_destination']).resolve()
    assert target.is_relative_to(Path(selection['work']).resolve())
    assert file_identity(target)['sha256'] == result['original_ctypes_sha256']
    module = bundle.read(base + 'native-ctypes/_ctypes.pyd')
    assert hashlib.sha256(module).hexdigest() == result['ctypes']['module_sha256']
    wheels = [name for name in bundle.namelist() if name.startswith(base + 'cffi-wheel/') and name.endswith('.whl')]
    assert len(wheels) == 1
    wheel = bundle.read(wheels[0])
    assert hashlib.sha256(wheel).hexdigest() == result['cffi']['wheel_sha256']
    # Bootstrap owns neither SDK DLL mapping; installation cannot replace a
    # currently loaded SDK module in the installer process.
    target.write_bytes(module)
    staged = output / Path(wheels[0]).name
    staged.write_bytes(wheel)
    subprocess.run([selection['python'], '-m', 'pip', '--isolated', 'install', '--no-index', '--no-deps',
                    '--force-reinstall', str(staged)], env=environment, check=True)
    return {'compiled_source_sha': result.get('compiled_source_sha', result['source_sha']),
            'ffi_library_source_sha': result['qualified_ffi_sdk']['compiled_source_sha'],
            'ctypes_sha256': result['ctypes']['module_sha256'], 'cffi_wheel_sha256': result['cffi']['wheel_sha256']}


def apply(selection: dict, output: Path, environment: dict) -> None:
    specs = json.loads((ROOT / '.github/scripts/qualified_ffi381_overlays.json').read_text())
    assert set(specs) == {'windows-x64', 'windows-arm64', 'linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64'}
    spec = specs[selection['target']]
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_sha'] == spec['source_sha']
    assert len(data) == metadata['size_in_bytes'] == spec['zip_bytes']
    assert metadata['digest'] == 'sha256:' + spec['zip_sha256'] == 'sha256:' + hashlib.sha256(data).hexdigest()
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        identity = (apply_windows(bundle, selection, output, environment) if spec['kind'] == 'windows'
                    else apply_posix(bundle, selection, output))
        retain_zip_material(bundle, output / 'controlled-material', 'Qualified FFI3.8.1 artifact ' + str(spec['artifact']))
        source_name = ('ffi381-consumers/' if spec['kind'] == 'windows' else '') + 'sources/libffi-3.8.1.tar.gz'
        raw = bundle.read(source_name)
        assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256
        with tarfile.open(fileobj=io.BytesIO(raw)) as source:
            license_bytes = source.extractfile('libffi-3.8.1/LICENSE').read()
        legal = output / 'ffi381-original/legal'
        legal.mkdir(parents=True)
        (legal / 'libffi-LICENSE').write_bytes(license_bytes)
    selection['ffi_security_overlay'] = {'version': '3.8.1', **spec, **identity,
        'source_sha256': SOURCE_SHA256, 'scope': 'Qualified ABI-compatible FFI input; original runtime/framework build identities preserved'}
    probe = ('import ctypes,hashlib,sys;import _ctypes,_cffi_backend;'
        'p=ctypes.WinDLL(_cffi_backend.__file__) if sys.platform=="win32" else ctypes.CDLL(sys.argv[1]);'
        'p.ffi_get_version.restype=ctypes.c_char_p;assert p.ffi_get_version()==b"3.8.1";'
        'assert p.ffi_get_version_number()==30801;'
        'assert sys.platform!="win32" or hashlib.sha256(open(_ctypes.__file__,"rb").read()).hexdigest()==sys.argv[2];'
        'print("PASS actual SDK FFI3.8.1 and selected ctypes/cffi")')
    library = Path(selection['prefix']) / ('lib/libffi.8.dylib' if selection['target'].startswith('macos-') else 'lib/libffi.so.8')
    subprocess.run([selection['python'], '-c', probe, str(library), identity.get('ctypes_sha256', '')],
                   env=environment, check=True)
