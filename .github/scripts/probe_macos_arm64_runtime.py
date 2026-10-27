"""Bounded native Apple-silicon host/source/trust qualification before rebuilding."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
import zipfile
from pathlib import Path

from verify_native_runtime_pilot import default_trust_handshake

REPO = Path(__file__).resolve().parents[2]


def contract() -> tuple[dict, dict]:
    arm = json.loads((REPO / '.github/scripts/macos_arm64_runtime_pilot_sources.json').read_text())
    base = json.loads((REPO / '.github/scripts' / arm['base_manifest']).read_text())
    assert hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == arm['base_manifest_canonical_sha256']
    return arm, base


def run(command: list, *, cwd: Path = REPO, log: Path | None = None, env: dict | None = None) -> str:
    print('RUN', *map(str, command), flush=True)
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if log:
        log.write_text(result.stdout)
    if result.returncode:
        print(result.stdout[-16000:], flush=True)
        result.check_returncode()
    return result.stdout


def fetch(item: dict, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / item['name']
    if not path.exists():
        with urllib.request.urlopen(item['url'], timeout=180) as response, path.open('wb') as stream:
            shutil.copyfileobj(response, stream)
    with path.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256'], path
    print('Official input verified:', path.name, flush=True)
    return path


def unpack(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter='data')


def clang_extraction(seven: Path, archive: Path, destination: Path, item: dict) -> list:
    """Unused driver aliases must not bypass the extractor's link safety checks."""
    return [seven, 'x', '-y', *['-x!' + name for name in item['exclude_paths']], '-o' + str(destination), archive]


def load_commands(text: str) -> dict:
    minimum, sdk, rpaths, identity, dependencies = [], [], [], [], []
    for block in re.split(r'Load command \d+\n', text)[1:]:
        command = re.search(r'\bcmd (LC_\w+)', block)
        if not command:
            continue
        kind = command[1]
        if kind in ('LC_BUILD_VERSION', 'LC_VERSION_MIN_MACOSX'):
            if kind == 'LC_BUILD_VERSION':
                assert re.search(r'\bplatform (?:1|macos)\b', block, re.I), 'Non-macOS Mach-O platform'
            value = re.search(r'\b(?:minos|version) (\d+(?:\.\d+)*)', block)
            assert value, block
            minimum.append(value[1])
            value = re.search(r'\bsdk (\d+(?:\.\d+)*)', block)
            if value:
                sdk.append(value[1])
        if kind == 'LC_RPATH':
            rpaths.append(re.search(r'\bpath (.+?) \(offset', block)[1])
        if kind in ('LC_ID_DYLIB', 'LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 'LC_REEXPORT_DYLIB'):
            value = re.search(r'\bname (.+?) \(offset', block)[1]
            (identity if kind == 'LC_ID_DYLIB' else dependencies).append(value)
    assert minimum, 'Missing Mach-O macOS deployment metadata'
    return {'minimum_os': minimum, 'sdk': sdk, 'rpaths': rpaths, 'install_names': identity, 'dependencies': dependencies}


def version(value: str) -> tuple[int, ...]:
    numbers = tuple(map(int, value.split('.')))
    return (numbers + (0, 0, 0))[:3]


def macho(path: Path, *, target: bool, allow_universal: bool = False, output: Path | None = None) -> dict:
    architectures = run(['lipo', '-archs', path]).split()
    assert 'arm64' in architectures and set(architectures) <= {'arm64', 'x86_64'}, ('No native ARM64 slice', path, architectures)
    if target and not allow_universal:
        assert architectures == ['arm64'], ('Controlled target must be ARM64 only', path, architectures)
    raw = run(['otool', '-arch', 'arm64', '-l', path])
    commands = load_commands(raw)
    if target:
        assert all(version(v) <= version('15.0') for v in commands['minimum_os']), ('Raised package floor', path, commands)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if output:
        output.mkdir(exist_ok=True)
        (output / (path.name + '-' + digest[:12] + '-otool.txt')).write_text(raw)
    return {'path': str(path.resolve()), 'architectures': architectures, 'selected_slice': 'arm64', 'sha256': digest, **commands, 'role': 'target image' if target else 'native host tool; not package OS floor'}


def prepare_python(work: Path, evidence: Path, base: dict) -> Path:
    archive = fetch(base['sources'][0], evidence / 'sources')
    source = work / 'src' / base['sources'][0]['directory']
    assert not source.exists()
    unpack(archive, work / 'src')
    patch = REPO / base['cpython_patch']['path']
    assert hashlib.sha256(patch.read_bytes()).hexdigest() == base['cpython_patch']['sha256']
    for name, hashes in base['cpython_patch']['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['base_sha256'], name
    environment = {**os.environ, 'GIT_CEILING_DIRECTORIES': str(source.parent)}
    for flags in (['--check'], []):
        run(['git', 'apply', *flags, patch], cwd=source, env=environment, log=evidence / ('patch-check.log' if flags else 'patch-apply.log'))
    for name, hashes in base['cpython_patch']['files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256'], name
    for name, digest in base['security_files'].items():
        assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
    shutil.copy2(patch, evidence / patch.name)
    (evidence / 'source-patch-preflight.json').write_text(json.dumps({'source_sha': os.environ['GITHUB_SHA'], 'source': base['sources'][0], 'patch': base['cpython_patch'], 'security_files': base['security_files'], 'result': 'PASS unchanged patch applies; original/post/security hashes preserved'}, indent=2))
    return source


def installed_qt(qt: Path, evidence: Path) -> dict:
    """Reject a successful install command that still resolves the build tree."""
    query = run([qt / 'bin/qtpaths6', '--query'])
    values = dict(line.split(':', 1) for line in query.splitlines() if ':' in line)
    assert Path(values['QT_INSTALL_PREFIX']).resolve() == qt.resolve(), ('Installed Qt resolves another prefix', values)
    assert (qt / 'lib/QtGui.framework/Headers/6.12.0/QtGui/rhi/qrhi.h').is_file()
    rows = [macho(path.resolve(), target=True, output=evidence) for path in
            (qt / 'bin/qtpaths6', qt / 'lib/QtCore.framework/QtCore')]
    for row in rows:
        assert len(row['rpaths']) == len(set(row['rpaths'])), ('Duplicate installed rpath', row)
        assert not any('/qt-build' in value or '/src/' in value for value in row['rpaths']), ('Build-tree runtime path', row)
    report = {'query': values, 'images': rows, 'result': 'Installed Qt prefix/framework/rpath/header PASS'}
    (evidence / 'installed-qt.json').write_text(json.dumps(report, indent=2))
    return report


def source_perl(work: Path, evidence: Path, arm: dict) -> dict:
    archive = fetch(arm['host_perl_source'], evidence / 'sources')
    unpack(archive, work)
    source = work / 'perl-5.44.0'
    cc = run(['xcrun', '--find', 'clang']).strip()
    sdk = run(['xcrun', '--sdk', 'macosx', '--show-sdk-path']).strip()
    environment = {**os.environ, 'SDKROOT': sdk}
    flags = '-isysroot ' + sdk + ' -arch arm64'
    run(['sh', 'Configure', '-des', '-Dprefix=' + str(work / 'host-perl'), '-Dcc=' + cc,
         '-Dccflags=' + flags, '-Dldflags=' + flags], cwd=source, env=environment, log=evidence / 'perl-configure.log')
    run(['make', '-j3'], cwd=source, env=environment, log=evidence / 'perl-build.log')
    result = run(['make', 'test_harness'], cwd=source, env={**environment, 'TEST_ARGS': 'op/arith2.t op/pack.t'}, log=evidence / 'perl-regressions.log')
    count = re.search(r'Files=(\d+), Tests=(\d+)', result)
    assert count and int(count[1]) == 2 and int(count[2]) > 0 and 'Result: PASS' in result
    row = macho(source / 'perl', target=False)
    run(['make', 'install'], cwd=source, env=environment, log=evidence / 'perl-install.log')
    row.update(version=run([work / 'host-perl/bin/perl', '-V:version', '-V:archname']), tests=int(count[2]), sdk=sdk)
    assert '5.44.0' in row['version']
    return row


def source_compression(work: Path, evidence: Path, arm: dict, tools: dict, sdk: str, python_source: Path) -> dict:
    """Restore SDK-missing standard Python codecs through current supported sources."""
    prefix = work / 'prefix'
    cmake, ninja = Path(tools['cmake']) / 'cmake', Path(tools['ninja']) / 'ninja'
    environment = {**os.environ, 'SDKROOT': sdk, 'MACOSX_DEPLOYMENT_TARGET': '11.0'}
    common = ['-GNinja', '-DCMAKE_MAKE_PROGRAM=' + str(ninja), '-DCMAKE_BUILD_TYPE=Release',
              '-DCMAKE_INSTALL_PREFIX=' + str(prefix), '-DCMAKE_INSTALL_LIBDIR=lib', '-DCMAKE_INSTALL_NAME_DIR=@rpath',
              '-DCMAKE_OSX_ARCHITECTURES=arm64', '-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0', '-DCMAKE_OSX_SYSROOT=' + sdk,
              '-DCMAKE_INSTALL_RPATH=' + str(prefix / 'lib'), '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local']
    for key, label, subdirectory, extra in [
        ('xz_source', 'xz', '', ['-DBUILD_SHARED_LIBS=ON', '-DBUILD_TESTING=OFF', '-DXZ_TOOL_XZ=OFF', '-DXZ_TOOL_XZDEC=OFF', '-DXZ_TOOL_LZMADEC=OFF', '-DXZ_TOOL_LZMAINFO=OFF', '-DXZ_TOOL_SCRIPTS=OFF']),
        ('zstd_source', 'zstd', 'build/cmake', ['-DZSTD_BUILD_SHARED=ON', '-DZSTD_BUILD_STATIC=OFF', '-DZSTD_BUILD_PROGRAMS=OFF', '-DZSTD_BUILD_TESTS=OFF']),
    ]:
        item = arm[key]
        unpack(fetch(item, evidence / 'sources'), work / 'src')
        source = work / 'src' / item['directory'] / subdirectory
        build = work / (label + '-build')
        run([cmake, '-S', source, '-B', build, *common, *extra], env=environment, log=evidence / (label + '-configure.log'))
        run([cmake, '--build', build, '--parallel', '2'], env=environment, log=evidence / (label + '-build.log'))
        run([cmake, '--install', build], env=environment, log=evidence / (label + '-install.log'))
    probe = work / 'compression-probe.cpp'
    probe.write_text('''#include <lzma.h>
#include <zstd.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
int main(){const uint8_t input[]="native codec probe";uint8_t encoded[512],decoded[512];size_t n=0,r=0,o=0;uint64_t limit=UINT64_MAX;
if(lzma_easy_buffer_encode(6,LZMA_CHECK_CRC64,nullptr,input,sizeof(input),encoded,&n,sizeof(encoded))!=LZMA_OK)return 1;
if(lzma_stream_buffer_decode(&limit,0,nullptr,encoded,&r,n,decoded,&o,sizeof(decoded))!=LZMA_OK||o!=sizeof(input)||memcmp(input,decoded,o))return 2;
n=ZSTD_compress(encoded,sizeof(encoded),input,sizeof(input),1);if(ZSTD_isError(n))return 3;
o=ZSTD_decompress(decoded,sizeof(decoded),encoded,n);if(ZSTD_isError(o)||o!=sizeof(input)||memcmp(input,decoded,o))return 4;
printf("%s %s codec roundtrips PASS\\n",lzma_version_string(),ZSTD_versionString());}
''')
    run(['xcrun', 'clang++', '-arch', 'arm64', '-mmacosx-version-min=11.0', probe,
         '-I' + str(prefix / 'include'), '-L' + str(prefix / 'lib'), '-Wl,-rpath,' + str(prefix / 'lib'),
         '-llzma', '-lzstd', '-o', work / 'compression-probe'], env=environment, log=evidence / 'compression-probe-build.log')
    result = run([work / 'compression-probe'], env=environment, log=evidence / 'compression-probe-run.log')
    assert result.strip() == '5.8.4 1.5.7 codec roundtrips PASS', result
    rows = [macho(next((prefix / 'lib').glob(pattern)).resolve(), target=True, output=evidence)
            for pattern in ('liblzma.*.dylib', 'libzstd.*.dylib')]
    build = work / 'python-codec-configure-probe'
    build.mkdir()
    environment.update(CC=run(['xcrun', '--find', 'clang']).strip(), CXX=run(['xcrun', '--find', 'clang++']).strip(),
        CPPFLAGS='-I' + str(prefix / 'include') + ' -isysroot ' + sdk,
        LDFLAGS='-arch arm64 -L' + str(prefix / 'lib') + ' -Wl,-rpath,' + str(prefix / 'lib'),
        PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig'), PKG_CONFIG_PATH=str(prefix / 'lib/pkgconfig'))
    run([python_source / 'configure', '--prefix=' + str(work / 'unused-codec-prefix'), '--enable-shared', '--with-ensurepip=no'], cwd=build, env=environment, log=evidence / 'python-codec-configure.log')
    modules = dict(re.findall(r'^MODULE_(\w+)_STATE=(\w+)', (build / 'Makefile').read_text(), re.M))
    assert all(modules.get(name) == 'yes' for name in ('_LZMA', '_ZSTD')), ('Native codec integrations missing', modules)
    return {'sources': [arm['xz_source'], arm['zstd_source']], 'native_images': rows,
            'probe': macho(work / 'compression-probe', target=True, output=evidence), 'result': result.strip(), 'python_module_configuration': modules}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    arm, base = contract()
    assert sys.platform == 'darwin' and platform.machine() == 'arm64'
    assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == 'final' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == run(['git', 'rev-parse', 'HEAD']).strip()
    translated = subprocess.run(['sysctl', '-in', 'sysctl.proc_translated'], capture_output=True, text=True)
    assert translated.stdout.strip() != '1', 'Rosetta process rejected'
    assert os.environ['DEVELOPER_DIR'] == arm['developer_dir']
    assert run(['xcodebuild', '-version']).splitlines()[0] == 'Xcode ' + arm['xcode']
    for name in ('SSL_CERT_FILE', 'SSL_CERT_DIR', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH', 'CFLAGS', 'CXXFLAGS', 'CPPFLAGS', 'LDFLAGS'):
        assert not os.environ.get(name), ('Unexpected inherited override', name)
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh isolated work root required'
    work.mkdir()
    evidence = REPO / 'macos-arm64-pilot-evidence'
    evidence.mkdir(exist_ok=True)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'os': platform.mac_ver(), 'machine': platform.machine(), 'python': sys.version, 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'), 'rosetta': False, 'image': {k: v for k, v in os.environ.items() if k.casefold() == 'imageversion'}, 'xcode': run(['xcodebuild', '-version']), 'sdk': run(['xcrun', '--sdk', 'macosx', '--show-sdk-path']).strip(), 'sdk_version': run(['xcrun', '--sdk', 'macosx', '--show-sdk-version']).strip(), 'clang': run(['xcrun', 'clang', '--version']), 'bootstrap': macho(Path(sys.executable).resolve(), target=False), 'bootstrap_trust': default_trust_handshake(), 'python_trust_strategy': arm['python_trust'], 'qt_trust_strategy': arm['qt_trust'], 'package_maximum': arm['accepted_package_maximum']}
    roots = run(['/usr/bin/security', 'find-certificate', '-a', '-p', '/System/Library/Keychains/SystemRootCertificates.keychain'])
    assert 'BEGIN CERTIFICATE' in roots
    (evidence / 'keychain-system-roots.pem').write_text(roots)
    source = work / 'thread-probe.cpp'
    source.write_text('#include <thread>\n#include <condition_variable>\n#include <mutex>\nint main(){std::mutex m;std::condition_variable cv;bool d=false;std::thread t([&]{std::lock_guard<std::mutex>l(m);d=true;cv.notify_one();});{std::unique_lock<std::mutex>l(m);cv.wait(l,[&]{return d;});}t.join();}\n')
    run(['xcrun', 'clang++', '-arch', 'arm64', '-mmacosx-version-min=11.0', '-std=c++17', source, '-o', work / 'thread-probe'], log=evidence / 'target-probe-build.log')
    run([work / 'thread-probe'])
    report['target_probe'] = macho(work / 'thread-probe', target=True)
    assert report['target_probe']['minimum_os'] == ['11.0']
    python_source = prepare_python(work, evidence, base)
    configure = work / 'python-configure-probe'
    configure.mkdir()
    environment = {**os.environ, 'MACOSX_DEPLOYMENT_TARGET': '11.0', 'SDKROOT': report['sdk'], 'PKG_CONFIG_LIBDIR': str(work / 'empty-pkgconfig'), 'CFLAGS': '-arch arm64', 'LDFLAGS': '-arch arm64', 'CC': run(['xcrun', '--find', 'clang']).strip(), 'CXX': run(['xcrun', '--find', 'clang++']).strip()}
    run([python_source / 'configure', '--prefix=' + str(work / 'unused-configure-prefix'), '--enable-shared', '--with-ensurepip=no'], cwd=configure, env=environment, log=evidence / 'python-configure-preflight.log')
    modules = dict(re.findall(r'^MODULE_(\w+)_STATE=(\w+)', (configure / 'Makefile').read_text(), re.M))
    report['bootstrap_sdk_module_configuration'] = modules
    assert all(modules.get(name) == 'yes' for name in ('_CTYPES', '_SQLITE3', '_BZ2', 'ZLIB')), ('Required SDK module missing before rebuilds', modules)
    ca = fetch(arm['certifi_wheel'], work)
    with zipfile.ZipFile(ca) as wheel:
        bundle = wheel.read('certifi/cacert.pem')
    assert bundle.count(b'BEGIN CERTIFICATE') > 0
    (work / 'certifi-cacert.pem').write_bytes(bundle)
    report['private_ca_bundle'] = {'wheel': arm['certifi_wheel'], 'pem_sha256': hashlib.sha256(bundle).hexdigest(), 'certificates': bundle.count(b'BEGIN CERTIFICATE'), 'integration': 'PEM default, not Keychain'}
    (evidence / 'prerequisites.json').write_text(json.dumps(report, indent=2))
    tools = work / 'host-tools'
    run([sys.executable, '-m', 'venv', tools])
    py = tools / 'bin/python'
    run([py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([py, '-m', 'pip', 'install', 'cmake==4.4.4', 'ninja==1.13.2', 'cryptography==50.0.2', *[i['url'] + '#sha256=' + i['sha256'] for i in arm['probe_wheels']], '--report', evidence / 'host-tools-install.json'])
    info = json.loads(run([py, '-c', 'import cmake,ninja,shiboken6_generator,json;from PySide6.QtCore import QLibraryInfo;print(json.dumps(dict(cmake=cmake.CMAKE_BIN_DIR,ninja=ninja.BIN_DIR,libexec=QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath),generator=shiboken6_generator.__path__[0])))']))
    paths = [Path(info['cmake']) / 'cmake', Path(info['ninja']) / 'ninja', Path(info['libexec']) / 'uic', Path(info['libexec']) / 'rcc', Path(info['generator']) / 'shiboken6']
    report['generators'] = [{**macho(p, target=False), 'version': run([p, '--version'])} for p in paths]
    header, typesystem = work / 'probe.h', work / 'typesystem.xml'
    header.write_text('class NativeArmProbe {public:int answer() const;};\n')
    typesystem.write_text('<typesystem package="armprobe"><object-type name="NativeArmProbe"/></typesystem>\n')
    run([paths[-1], '--generator-set=shiboken', '--output-directory=' + str(work / 'generated'), header, typesystem], log=evidence / 'shiboken-generation.log')
    assert any((work / 'generated').rglob('*nativearmprobe*'))
    run([py, REPO / '.github/scripts/verify_macos_arm64_runtime_pilot.py', '--native-prerequisites', '--output-dir', evidence], log=evidence / 'native-tls-prerequisites.log')
    report['compression'] = source_compression(work, evidence, arm, info, report['sdk'], python_source)
    extractor = fetch(arm['host_extractor'], work)
    unpack(extractor, work / 'extractor')
    seven = work / 'extractor/7zz'
    report['extractor'] = macho(seven, target=False)
    run([seven], log=evidence / '7zip-version.log')
    archive = fetch(arm['host_libclang'], work)
    run(clang_extraction(seven, archive, work / 'src', arm['host_libclang']), log=evidence / 'libclang-extract.log')
    library = next((work / 'src/libclang/lib').glob('libclang.dylib')).resolve()
    report['parser'] = macho(library, target=False)
    probe = work / 'parser-probe.cpp'
    probe.write_text('#include <clang-c/Index.h>\n#include <stdio.h>\nint main(int n,char**v){auto i=clang_createIndex(0,0);const char*a[]={"-xc++"};auto t=clang_parseTranslationUnit(i,v[1],a,1,nullptr,0,0);if(!t||clang_getNumDiagnostics(t))return 2;auto s=clang_getClangVersion();puts(clang_getCString(s));clang_disposeString(s);clang_disposeTranslationUnit(t);clang_disposeIndex(i);}\n')
    run(['xcrun', 'clang++', '-arch', 'arm64', probe, '-I' + str(work / 'src/libclang/include'), '-L' + str(library.parent), '-Wl,-rpath,' + str(library.parent), '-lclang', '-o', work / 'parser-probe'], log=evidence / 'parser-build.log')
    report['parser']['execution'] = run([work / 'parser-probe', header], log=evidence / 'parser-execution.log')
    assert '22.1.8' in report['parser']['execution']
    report['source_perl'] = source_perl(work, evidence, arm)
    for name in ('macos_arm64_runtime_pilot_sources.json', arm['base_manifest']):
        shutil.copy2(REPO / '.github/scripts' / name, evidence / name)
    report['result'] = 'PASS native macOS ARM64 prerequisites; no CPython/Qt runtime compiled'
    (evidence / 'prerequisites.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
