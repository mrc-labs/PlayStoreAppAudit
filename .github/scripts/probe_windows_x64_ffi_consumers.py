"""Qualify ctypes/cffi on the exact retained native /MD static libffi SDK."""
from __future__ import annotations

import hashlib
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

from build_windows_runtime_pilot import fetch
from download_diagnostic_artifact import fetch_artifact
from inspect_pe import read_pe_machine
from probe_libffi_arm64 import exercise_cffi
from probe_windows_arm64_ctypes import exercise_ctypes

REPO = Path(__file__).resolve().parents[2]


def restore_ffi(data: bytes, prefix: Path, spec: dict) -> None:
    if len(data) != spec['zip_bytes'] or hashlib.sha256(data).hexdigest() != spec['zip_sha256']:
        raise ValueError('Changed original qualified x64 libffi artifact')
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        report = json.loads(bundle.read('windows-x64-libffi.json'))
        assert report['source_sha'] == spec['source_sha'] and report['crt'] == '/MD'
        assert report['library_sha256'] == spec['library_sha256']
        for name in ['include/ffi.h', 'include/ffitarget.h', 'lib/libffi.lib', 'share/libffi/copyright']:
            target = prefix / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(bundle.read('libffi-sdk/' + name))
        assert hashlib.sha256((prefix / 'lib/libffi.lib').read_bytes()).hexdigest() == spec['library_sha256']


def qualify(work: Path) -> None:
    assert sys.platform == 'win32' and platform.machine().lower() == 'amd64'
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'x64'
    compiler = Path(shutil.which('cl')).resolve()
    assert read_pe_machine(compiler) == 0x8664 and compiler.parents[3].name.startswith('14.52.')
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert not work.exists()
    work.mkdir(parents=True)
    output = REPO / 'toolchain-delta-evidence'
    spec_path = REPO / '.github/scripts/windows_x64_ffi_consumer_sources.json'
    spec = json.loads(spec_path.read_text())
    ffi = spec['ffi']
    metadata, data = fetch_artifact(ffi['artifact'])
    assert metadata['workflow_run']['head_sha'] == ffi['source_sha'] and metadata['workflow_run']['id'] == ffi['run']
    assert metadata['workflow_run']['head_repository_id'] == 1334403620 and not metadata['expired']
    assert metadata['digest'] == 'sha256:' + ffi['zip_sha256']
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    (output / 'original-qualified-x64-ffi.zip').write_bytes(data)
    shutil.copy2(spec_path, output)
    prefix = output / 'original-libffi-sdk'
    restore_ffi(data, prefix, ffi)
    library = prefix / 'lib/libffi.lib'
    sources = output / 'sources'
    sources.mkdir()
    base = json.loads((REPO / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    python_source = base['sources'][0]
    archive = fetch(python_source, sources)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / 'Python-3.14.10'
    shutil.copy2(source / 'LICENSE', output / 'Python-LICENSE')
    modules = output / 'native-ctypes'
    modules.mkdir()
    ctypes_result = exercise_ctypes(source, prefix / 'include', library, modules, output, compiler, machine=0x8664)
    cffi_result = exercise_cffi(source, work, library, output, spec['cffi_consumer'], arch='AMD64', include=prefix / 'include')
    result = {'source_sha': os.environ['GITHUB_SHA'], 'ffi': ffi, 'compiler': str(compiler), 'crt': '/MD',
              'ctypes': ctypes_result, 'cffi': cffi_result, 'project_cpython_source_patches': [],
              'scope': 'Native original same-patch ctypes and source-labelled cffi consumers only; no libffi rebuild or whole runtime/crypto/package acceptance',
              'result': 'PASS'}
    (output / 'windows-x64-ffi-consumers.json').write_text(json.dumps(result, indent=2) + '\n')
