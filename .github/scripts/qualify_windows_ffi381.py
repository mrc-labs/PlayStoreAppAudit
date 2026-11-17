"""Relink only ctypes/cffi against qualified native static FFI3.8.1 SDKs."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDKS = {
    'x64': {'artifact': 14296314344, 'run': 44011371279, 'bytes': 7411383,
            'sha256': 'ba945f2c23f80e7e15d37b832042dd5334a37ace9c9aecfc9f5ff9da967ddba1',
            'library_sha256': '903417f192ff98fb9641af5fdbf8ca74bd04dda698499816add6d1422e502cfa',
            'root': 'libffi-sdk', 'library': 'lib/libffi.lib', 'license': 'share/libffi/copyright'},
    'arm64': {'artifact': 14297375490, 'run': 44011374742, 'bytes': 1917328,
              'sha256': '8040cd3ee0a664442f97346a803575b9142db5acd6ed5739666e5fd3b50c7367',
              'library_sha256': '2720e3308ae254c573612a53b5b7896a5a6944699656ecedfa59802e09b51d0d',
              'root': 'libffi381-sdk', 'library': 'lib/ffi.lib', 'license': 'LICENSE'},
}
SDK_SOURCE = '305d6b2a16bf1a4513609a811001ebe7086b2717'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def install_and_exercise(output: Path) -> None:
    """Called by bootstrap after the SDK build process has released its DLLs."""
    state = json.loads((output / 'ffi381-staged.json').read_text())
    selection = state['runtime_selection']
    work = Path(selection['work']).resolve()
    destination = Path(state['ctypes_destination']).resolve()
    assert destination.is_relative_to(work) and digest(destination) == state['original_ctypes_sha256']
    source = output / 'native-ctypes/_ctypes.pyd'
    assert digest(source) == state['ctypes']['module_sha256']
    shutil.copy2(source, destination)
    environment = dict(os.environ)
    for key in ['GH_TOKEN', 'GITHUB_TOKEN', 'PYTHONHOME', 'PYTHONPATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR']:
        environment.pop(key, None)
    python = selection['python']
    check = r'''import ctypes,hashlib,json,sys
import _ctypes,cffi,_cffi_backend
assert hashlib.sha256(open(_ctypes.__file__,'rb').read()).hexdigest()==sys.argv[1]
library=ctypes.WinDLL(_cffi_backend.__file__);library.ffi_get_version.restype=ctypes.c_char_p
assert library.ffi_get_version()==b'3.8.1' and library.ffi_get_version_number()==30801
callback=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int)
callbacks=[callback(lambda value,i=i:value+i) for i in range(1200)]
assert all(f(11)==11+i for i,f in enumerate(callbacks))
c=cffi.FFI(); callbacks2=[c.callback('int(int)',lambda value,i=i:value+i) for i in range(1200)]
assert all(f(17)==17+i for i,f in enumerate(callbacks2))
print(json.dumps(dict(ctypes=_ctypes.__file__,cffi=_cffi_backend.__file__,libffi='3.8.1',ctypes_callbacks=1200,cffi_callbacks=1200)))
'''
    result = subprocess.run([python, '-c', check, state['ctypes']['module_sha256']], cwd=ROOT,
                            env=environment, capture_output=True, text=True, check=True)
    measured = json.loads(result.stdout)
    (output / 'installed-native-consumers.json').write_text(json.dumps(measured, indent=2))
    for name, command in [('tls-codecs', [python, '-m', 'pytest', '-q', 'tests/test_scraper_transport_tls.py', 'tests/test_imageformats_consumers.py']),
                          ('cli', [python, 'main.py', 'cli', 'audit', '--help']), ('gui', [python, 'main.py'])]:
        if name == 'gui':
            environment.update(PLAYSTORE_APP_AUDIT_SMOKE_TEST='1', QT_QPA_PLATFORM='windows')
        result = subprocess.run(command, cwd=ROOT, env=environment, capture_output=True, text=True)
        (output / (name + '.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            print((result.stdout + result.stderr)[-10000:], flush=True)
        result.check_returncode()
    state.update(result='PASS', installed=measured,
                 scope='Actual controlled native Python with relinked static FFI ctypes/cffi, original upstream tests and affected GUI/CLI/TLS/codec consumers; no Python/Qt/crypto rebuild or final package')
    (output / 'windows-ffi381-result.json').write_text(json.dumps(state, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'toolchain-delta-evidence/ffi381-consumers'
    if args.install:
        install_and_exercise(output)
        return
    assert sys.platform == 'win32' and platform.python_version() == '3.14.10'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    assert arch in SDKS and platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == arch
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    selection = json.loads((output.parent / 'producer-runtime-selection.json').read_text())
    assert selection['target'] == 'windows-' + arch
    assert Path(sys.executable).resolve().is_relative_to(Path(selection['work']).resolve())
    assert '_cffi_backend' not in sys.modules, 'Release the old backend before installing the isolated new wheel'
    ctypes_destination = Path(importlib.util.find_spec('_ctypes').origin).resolve()
    assert ctypes_destination.is_relative_to(Path(selection['work']).resolve())
    old_ctypes = digest(ctypes_destination)
    output.mkdir()
    from download_diagnostic_artifact import fetch_artifact

    spec = SDKS[arch]
    metadata, data = fetch_artifact(spec['artifact'])
    assert not metadata['expired'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['workflow_run']['id'] == spec['run'] and metadata['workflow_run']['head_sha'] == SDK_SOURCE
    assert metadata['size_in_bytes'] == spec['bytes'] == len(data)
    assert metadata['digest'] == 'sha256:' + spec['sha256'] == 'sha256:' + hashlib.sha256(data).hexdigest()
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    sdk = output / 'libffi381-sdk'
    (sdk / 'include').mkdir(parents=True)
    (sdk / 'lib').mkdir()
    sources = output / 'sources'
    sources.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        for name in ['ffi.h', 'ffitarget.h']:
            (sdk / 'include' / name).write_bytes(bundle.read(spec['root'] + '/include/' + name))
        if arch == 'arm64':
            (sdk / 'include/fficonfig.h').write_bytes(bundle.read(spec['root'] + '/include/fficonfig.h'))
        library = sdk / 'lib' / Path(spec['library']).name
        library.write_bytes(bundle.read(spec['root'] + '/' + spec['library']))
        assert digest(library) == spec['library_sha256']
        (sdk / 'LICENSE').write_bytes(bundle.read(spec['root'] + '/' + spec['license']))
        source = bundle.read('sources/libffi-3.8.1.tar.gz')
        assert hashlib.sha256(source).hexdigest() == '81e879c094cc5ec3186c48510c6385ac6b3e866192e8bc71a35245703757ee40'
        (sources / 'libffi-3.8.1.tar.gz').write_bytes(source)
    del data
    work = Path(os.environ['RUNNER_TEMP']) / ('ffi381-consumers-' + arch + '-' + os.environ['GITHUB_RUN_ID'])
    assert not work.exists()
    work.mkdir()
    material = Path(selection['material_directory'])
    python_archive = material / 'sources/Python-3.14.10.tar.xz'
    assert digest(python_archive) == 'de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032'
    with tarfile.open(python_archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / 'Python-3.14.10'
    from inspect_pe import read_pe_machine
    from probe_libffi_arm64 import exercise_cffi
    from probe_windows_arm64_ctypes import exercise_ctypes

    compiler = Path(shutil.which('cl.exe')).resolve()
    machine = 0xAA64 if arch == 'arm64' else 0x8664
    assert read_pe_machine(compiler) == machine and compiler.parents[3].name.startswith('14.52.')
    modules = output / 'native-ctypes'
    modules.mkdir()
    ctypes_result = exercise_ctypes(source, sdk / 'include', library, modules, output, compiler, machine=machine)
    cffi_spec = json.loads((ROOT / '.github/scripts/windows_ffi381_cffi_sources.json').read_text())[arch]
    cffi_result = exercise_cffi(source, work, library, output, cffi_spec, arch='ARM64' if arch == 'arm64' else 'AMD64',
                                include=sdk / 'include', expected_ffi='3.8.1', runtime_python=Path(sys.executable))
    (output / 'ffi381-staged.json').write_text(json.dumps({'source_sha': os.environ['GITHUB_SHA'],
        'runtime_selection': selection, 'qualified_ffi_sdk': {**spec, 'compiled_source_sha': SDK_SOURCE},
        'ctypes_destination': str(ctypes_destination), 'original_ctypes_sha256': old_ctypes,
        'ctypes': ctypes_result, 'cffi': cffi_result, 'cffi_source': cffi_spec}, indent=2))


if __name__ == '__main__':
    main()
