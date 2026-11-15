"""Run original CPython ctypes against the already-qualified native ARM64 FFI."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from build_windows_runtime_pilot import fetch, run
from download_diagnostic_artifact import fetch_artifact
from inspect_pe import read_pe_machine
from probe_windows_sql_decimal import project_sources
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]
FFI_ARTIFACT = 14090737696
FFI_SOURCE = '11cedced38c89fe350a0918f138664b94b4a4c34'
FFI_ZIP_SHA256 = 'e210e199c4a6f0b2f2412d5b8e4d3477423103fd8500c1fddac410b3f53e9dec'
FFI_LIBRARY_SHA256 = '95d41ce461d52b88c9a8a6811aac198eab83b8e3e8b9469b52fbf473d2f6bf29'


def restore_ffi(data: bytes, prefix: Path) -> None:
    if len(data) != 8836195 or hashlib.sha256(data).hexdigest() != FFI_ZIP_SHA256:
        raise ValueError('Changed qualified ARM64 FFI artifact')
    prefix.mkdir()
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        library = bundle.read('libffi-prerequisites/Ffi_staticLib_arm64.lib')
        assert hashlib.sha256(library).hexdigest() == FFI_LIBRARY_SHA256
        (prefix / 'ffi.lib').write_bytes(library)
        for name in ['ffi.h', 'fficonfig.h']:
            (prefix / name).write_bytes(bundle.read('libffi-prerequisites/configured-' + name))
        source_name = next(n for n in bundle.namelist() if n.endswith('/libffi-3.8.0.tar.gz'))
        source = bundle.read(source_name)
        assert hashlib.sha256(source).hexdigest() == '7da3e2d9a171eb0a038f592ecad3ff2bb2550f3496d87b3b29ad0cf4430c0db4'
        (prefix / 'libffi-3.8.0.tar.gz').write_bytes(source)
        with tarfile.open(fileobj=io.BytesIO(source)) as archive:
            for name in ['src/aarch64/ffitarget.h', 'LICENSE']:
                (prefix / Path(name).name).write_bytes(archive.extractfile('libffi-3.8.0/' + name).read())
        for name in ['libffi-probe.json', 'libffi_arm64_probe_sources.json', 'cffi-ownlib.json', 'cffi-varargs.json']:
            (prefix / name).write_bytes(bundle.read('libffi-prerequisites/' + name))
        for name in bundle.namelist():
            if name.endswith('.patch'):
                (prefix / Path(name).name).write_bytes(bundle.read(name))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.machine().lower() == 'arm64' and platform.python_version() == '3.14.10'
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == 'arm64'
    compiler = Path(shutil.which('cl')).resolve()
    assert read_pe_machine(compiler) == 0xAA64 and compiler.parents[3].name.startswith('14.52.')
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    output = REPO / 'toolchain-delta-evidence'
    metadata, data = fetch_artifact(FFI_ARTIFACT)
    assert metadata['workflow_run']['head_sha'] == FFI_SOURCE and metadata['workflow_run']['id'] == 43538466498
    assert metadata['workflow_run']['head_repository_id'] == 1334403620 and not metadata['expired']
    assert metadata['digest'] == 'sha256:' + FFI_ZIP_SHA256
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    prefix = output / 'original-libffi-sdk'
    restore_ffi(data, prefix)
    sources = output / 'sources'
    sources.mkdir()
    base = json.loads((REPO / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    python = base['sources'][0]
    archive = fetch(python, sources)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / 'Python-3.14.10'
    shutil.copy2(source / 'LICENSE', output / 'Python-LICENSE')
    modules = output / 'native-ctypes'
    modules.mkdir()
    files = project_sources(source / 'PCbuild/_ctypes.vcxproj', source, source)
    assert len(files) == 6
    run([compiler, '/nologo', '/MD', '/O2', '/LD', '/DPy_BUILD_CORE_MODULE',
         '/DUSING_MALLOC_CLOSURE_DOT_C=1', '/DHAVE_FFI_PREP_CIF_VAR=1', '/DFFI_BUILDING_DLL',
         '/I' + str(source / 'PC'), '/I' + str(source / 'Include'), '/I' + str(source / 'Include/internal'),
         '/I' + str(prefix), *files, '/link', Path(sys.base_prefix) / 'libs/python314.lib', prefix / 'ffi.lib',
         '/OUT:' + str(modules / '_ctypes.pyd')], cwd=modules, log=output / 'ctypes-build.log')
    native = modules / '_ctypes.pyd'
    assert read_pe_machine(native) == 0xAA64
    versions = pe_versions(native)
    assert max(versions.values()) <= (10, 0)
    imports = subprocess.check_output(['dumpbin', '/dependents', native], text=True)
    assert 'ffi.dll' not in imports.lower() and 'libffi' not in imports.lower()
    assert 'VCRUNTIME140' in imports.upper(), 'Dynamic release CRT import required'
    (output / 'ctypes-imports.txt').write_text(imports)
    # Original Windows closure allocation remains selected. Only this isolated
    # child imports the new module; neither the runner nor application is changed.
    cases = ['test_callbacks', 'test_callargs', 'test_functions', 'test_structures', 'test_as_parameter']
    code = ('import sys,unittest; sys.path.insert(0,sys.argv[1]); sys.path.append(sys.argv[2]); '
            'import _ctypes,ctypes; assert _ctypes.__file__.startswith(sys.argv[1]); '
            'suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[3:]); '
            'r=unittest.TextTestRunner(verbosity=1).run(suite); assert r.testsRun>0; sys.exit(not r.wasSuccessful())')
    run([sys.executable, '-I', '-c', code, modules, source / 'Lib',
         *['test.test_ctypes.' + name for name in cases]], log=output / 'ctypes-upstream-tests.log')
    report = {'source_sha': os.environ['GITHUB_SHA'], 'python_source': python,
              'ffi_original_source_sha': FFI_SOURCE, 'ffi_artifact': FFI_ARTIFACT,
              'ffi_zip_sha256': FFI_ZIP_SHA256, 'ffi_library_sha256': FFI_LIBRARY_SHA256,
              'module_sha256': hashlib.sha256(native.read_bytes()).hexdigest(), 'machine': 0xAA64,
              'compiler': str(compiler), 'crt': '/MD', 'pe_versions': versions, 'upstream_modules': cases,
              'project_cpython_source_patches': [], 'configuration': ['USING_MALLOC_CLOSURE_DOT_C', 'HAVE_FFI_PREP_CIF_VAR'],
              'scope': 'Original same-patch private ctypes consumer only; no whole Python/SSL/crypto/package adoption', 'result': 'PASS'}
    (output / 'arm64-ctypes-results.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
