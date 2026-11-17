"""Build only libffi3.8.1 in a qualified POSIX SDK and exercise its consumers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
from pathlib import Path

from probe_qt_text_providers import checked_source

ROOT = Path(__file__).resolve().parents[2]
SOURCE = {'name': 'libffi-3.8.1.tar.gz', 'directory': 'libffi-3.8.1',
          'url': 'https://github.com/libffi/libffi/releases/download/v3.8.1/libffi-3.8.1.tar.gz',
          'sha256': '81e879c094cc5ec3186c48510c6385ac6b3e866192e8bc71a35245703757ee40'}


def entry(path: Path) -> dict:
    if path.is_symlink():
        return {'link': os.readlink(path)}
    with path.open('rb') as stream:
        return {'bytes': path.stat().st_size, 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


def ffi_files(prefix: Path) -> dict:
    paths = [*prefix.glob('lib/libffi*'), *prefix.glob('include/ffi*.h'), *prefix.glob('lib/pkgconfig/libffi.pc')]
    return {path.relative_to(prefix).as_posix(): entry(path) for path in paths if path.is_file() or path.is_symlink()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64'], required=True)
    args = parser.parse_args()
    system, arch = args.target.split('-')
    cpu = 'arm64' if arch == 'arm64' else 'x86_64'
    assert sys.platform == ('linux' if system == 'linux' else 'darwin')
    assert platform.machine().lower() in ({'aarch64', 'arm64'} if arch == 'arm64' else {'x86_64'})
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA']
    selection = json.loads(Path(os.environ['PSAA_CONTROLLED_RUNTIME_SELECTION']).read_text())
    prefix = Path(selection['prefix']).resolve()
    assert prefix.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve())
    assert selection['target'] == args.target
    assert Path(sys.executable).resolve().is_relative_to(Path(selection['work']).resolve())
    output = ROOT / 'ffi381-evidence'
    output.mkdir()
    sources = output / 'sources'
    sources.mkdir()
    work = Path(os.environ['RUNNER_TEMP']) / ('ffi381-' + args.target + '-' + os.environ['GITHUB_RUN_ID'])
    assert not work.exists()
    work.mkdir()
    environment = dict(os.environ)
    for key in ['GH_TOKEN', 'GITHUB_TOKEN', 'PYTHONPATH', 'PYTHONHOME', 'SSL_CERT_FILE', 'SSL_CERT_DIR']:
        environment.pop(key, None)
    if system == 'macos':
        translated = subprocess.run(['sysctl', '-in', 'sysctl.proc_translated'], capture_output=True, text=True)
        assert translated.stdout.strip() != '1', 'Rosetta is not a native target'
        sdk = subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip()
        deployment = '11.0' if arch == 'arm64' else '10.15'
        environment.update(CC=subprocess.check_output(['xcrun', '--find', 'clang'], text=True).strip(),
                           MACOSX_DEPLOYMENT_TARGET=deployment, SDKROOT=sdk,
                           CFLAGS=f'-O2 -fPIC -arch {cpu} -mmacosx-version-min={deployment} -isysroot {sdk}',
                           LDFLAGS=f'-arch {cpu} -mmacosx-version-min={deployment} -isysroot {sdk}')
    else:
        assert platform.freedesktop_os_release()['VERSION_ID'] == ('24.04' if arch == 'arm64' else '22.04')
        environment.update(CC='gcc-13' if arch == 'arm64' else 'gcc-11', CFLAGS='-O2 -fPIC')

    def run(command: list, name: str, *, cwd: Path = work) -> str:
        result = subprocess.run(list(map(str, command)), cwd=cwd, env=environment, capture_output=True, text=True)
        text = result.stdout + result.stderr
        (output / (name + '.log')).write_text(text, encoding='utf-8')
        if result.returncode:
            print(text[-10000:], flush=True)
        result.check_returncode()
        return text

    environment['QT_PLUGIN_PATH'] = str(prefix / 'qt/plugins')
    if system == 'linux':
        linkage = run(['ldd', prefix / 'qt/plugins/platforms/libqxcb.so'], 'qt-xcb-prerequisite')
        if 'not found' in linkage:
            print(linkage, flush=True)
            raise RuntimeError('Original qualified XCB plugin has missing runner dependencies; FFI build not started')
    before = ffi_files(prefix)
    assert before, 'Missing original private libffi SDK'
    archive = checked_source(SOURCE, sources)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / SOURCE['directory']
    (output / 'legal').mkdir()
    shutil.copy2(source / 'LICENSE', output / 'legal/libffi-LICENSE')
    run([source / 'configure', '--prefix=' + str(prefix), '--libdir=' + str(prefix / 'lib'),
         '--disable-static', '--disable-docs', '--disable-multi-os-directory'], 'configure', cwd=source)
    run(['make', '-j2'], 'build', cwd=source)
    # Installation into this disposable, verified SDK is an upstream ABI-compatible
    # source build, not a swap of unverified vendor library files or an OS change.
    run(['make', 'install'], 'install', cwd=source)
    after = ffi_files(prefix)
    changed = {name: value for name, value in after.items() if before.get(name) != value}
    assert changed
    library = prefix / ('lib/libffi.8.dylib' if system == 'macos' else 'lib/libffi.so.8')
    assert library.resolve().is_relative_to(prefix)
    native = run(['lipo', '-archs', library] if system == 'macos' else ['readelf', '-h', library], 'architecture')
    if system == 'macos':
        assert native.strip() == cpu
    else:
        assert ('AArch64' if arch == 'arm64' else 'Advanced Micro Devices X86-64') in native
    if system == 'macos':
        run(['codesign', '--force', '--sign', '-', library.resolve()], 'engineering-sign')
        after = ffi_files(prefix)
        changed = {name: value for name, value in after.items() if before.get(name) != value}
    # Preserve completed build bytes before later consumers, even if a GUI gate fails.
    overlay = output / 'libffi381-sdk-overlay.tar.xz'
    with tarfile.open(overlay, 'w:xz') as bundle:
        for name in changed:
            bundle.add(prefix / name, arcname='prefix/' + name, recursive=False)
    built = {'source_sha': head, 'target': args.target, 'original_sdk': selection, 'source': SOURCE,
             'before': before, 'after': changed, 'original_prefix': str(prefix),
             'overlay_sha256': hashlib.sha256(overlay.read_bytes()).hexdigest(),
             'compiler': environment['CC'], 'scope': 'Completed FFI build checkpoint; consumer acceptance separate'}
    (output / 'libffi381-build.json').write_text(json.dumps(built, indent=2))
    # A fresh child guarantees that no old FFI mapping survives library installation.
    check = r'''import ctypes,hashlib,json,sys
from pathlib import Path
from audit_runtime_components import loaded_images
library=Path(sys.argv[1]).resolve()
ffi=ctypes.CDLL(str(library));ffi.ffi_get_version.restype=ctypes.c_char_p
assert ffi.ffi_get_version()==b'3.8.1' and ffi.ffi_get_version_number()==30801
callback=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_int)
callbacks=[callback(lambda value,i=i: value+i) for i in range(1200)]
assert all(function(17)==17+i for i,function in enumerate(callbacks))
import cffi,_cffi_backend,_ctypes
c=cffi.FFI(); ccallbacks=[c.callback('int(int)',lambda value,i=i:value+i) for i in range(1200)]
assert all(function(19)==19+i for i,function in enumerate(ccallbacks))
images=[str(p.resolve()) for p in loaded_images() if p.is_file() and 'libffi' in p.name]
assert str(library) in images
print(json.dumps(dict(libffi='3.8.1',callbacks_ctypes=1200,callbacks_cffi=1200,images=images,
 ctypes=_ctypes.__file__,cffi=_cffi_backend.__file__,library_sha256=hashlib.sha256(library.read_bytes()).hexdigest())))
'''
    environment['PYTHONPATH'] = str(ROOT / '.github/scripts')
    measured = json.loads(run([sys.executable, '-c', check, library], 'native-consumers'))
    # Unchanged extension binaries must now resolve their FFI dependency to this SDK.
    for name in ['ctypes', 'cffi']:
        linkage = run(['otool', '-L', measured[name]] if system == 'macos' else ['ldd', measured[name]], name + '-linkage')
        assert str(prefix / 'lib/libffi') in linkage
    material = Path(selection['material_directory'])
    python_archive = material / 'sources/Python-3.14.10.tar.xz'
    assert hashlib.sha256(python_archive.read_bytes()).hexdigest() == 'de414a57119abef52784d8993e341d53aed635fc2b05c2607d9f98a2c5b72032'
    with tarfile.open(python_archive) as bundle:
        bundle.extractall(work, filter='data')
    ctypes_test = ('import sys,unittest;sys.path.append(sys.argv[1]);'
        's=unittest.defaultTestLoader.loadTestsFromNames(["test.test_ctypes."+n for n in '
        '["test_callbacks","test_parameters","test_functions","test_structures","test_as_parameter"]]);'
        'r=unittest.TextTestRunner().run(s);assert r.testsRun>0;sys.exit(not r.wasSuccessful())')
    run([sys.executable, '-I', '-c', ctypes_test, work / 'Python-3.14.10/Lib'], 'ctypes-upstream')
    cffi_archive = material / 'sources/cffi-2.1.1.tar.gz'
    spec = json.loads((ROOT / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
    cffi_source = next(item for item in spec['sources'] if item['name'] == cffi_archive.name)
    assert hashlib.sha256(cffi_archive.read_bytes()).hexdigest() == cffi_source['sha256']
    with tarfile.open(cffi_archive) as bundle:
        bundle.extractall(work, filter='data')
    run([sys.executable, '-m', 'pytest', '-q', str(work / 'cffi-2.1.1/src/c/test_c.py')], 'cffi-upstream', cwd=ROOT)
    run([sys.executable, '-m', 'pytest', '-q', 'tests/test_scraper_transport_tls.py'], 'tls-regression', cwd=ROOT)
    trust = ('import ssl,socket,json;from cryptography.hazmat.backends.openssl.backend import backend;'
        'c=ssl.create_default_context();assert c.check_hostname and c.verify_mode==ssl.CERT_REQUIRED;'
        's=c.wrap_socket(socket.create_connection(("play.google.com",443),timeout=30),server_hostname="play.google.com");'
        'assert s.getpeercert() and s.version() in {"TLSv1.2","TLSv1.3"};'
        'print(json.dumps(dict(protocol=s.version(),python_ssl=ssl.OPENSSL_VERSION,crypto_ssl=backend.openssl_version_text())));s.close()')
    run([sys.executable, '-c', trust], 'default-trust')
    run([sys.executable, '-m', 'pytest', '-q', 'tests/test_imageformats_consumers.py'], 'codecs', cwd=ROOT)
    environment['PLAYSTORE_APP_AUDIT_SMOKE_TEST'] = '1'
    environment['QT_QPA_PLATFORM'] = 'cocoa' if system == 'macos' else 'xcb'
    environment['QT_DEBUG_PLUGINS'] = '1'
    run([sys.executable, 'main.py'], 'gui', cwd=ROOT)
    run([sys.executable, 'main.py', 'cli', 'audit', '--help'], 'cli', cwd=ROOT)
    (output / 'libffi381-result.json').write_text(json.dumps({**built, 'native': measured, 'result': 'PASS',
        'scope': 'ABI-compatible source-built FFI update and affected native consumers only; no Python/Qt/binding/crypto rebuild or final package'}, indent=2))


if __name__ == '__main__':
    main()
