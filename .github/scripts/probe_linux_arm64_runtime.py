"""Qualify one native Noble ARM64 host before controlled runtime compilation."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import ssl
import subprocess
import sys
import sysconfig
import tarfile
import urllib.request
from pathlib import Path

from inspect_linux_abi import readelf, required_versions, version_floor
from verify_native_runtime_pilot import default_trust_handshake

REPO = Path(__file__).resolve().parents[2]


def contract() -> tuple[dict, dict]:
    arm = json.loads((REPO / '.github/scripts/linux_arm64_runtime_pilot_sources.json').read_text())
    base = json.loads((REPO / '.github/scripts' / arm['base_manifest']).read_text())
    assert hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == arm['base_manifest_canonical_sha256']
    return arm, base


def runtime_sources(arm: dict, base: dict) -> list[dict]:
    """One explicit current security-patch override, otherwise accepted sources."""
    return [arm['cpython_source'], *base['sources'][1:7]]


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


def elf(path: Path, *, target: bool) -> dict:
    header = readelf(path, '--file-header')
    assert re.search(r'Machine:\s+AArch64\s', header), ('Non-native ELF', path, header)
    needs = required_versions(readelf(path, '--version-info'))
    maxima = {key:version_floor(needs, key + '_') for key in ('GLIBC', 'GLIBCXX')}
    if target:
        for key, ceiling in [('GLIBC', (2, 38)), ('GLIBCXX', (3, 4, 32))]:
            value = maxima[key]
            assert value is None or tuple(map(int, value.removeprefix(key + '_').split('.'))) <= ceiling, (path, key, value, ceiling)
    return {'path':str(path.resolve()), 'machine':'AArch64', 'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'required_versions':needs, 'maxima':maxima, 'role':'target ABI probe' if target else 'native build-host tool; Noble ABI, not application floor'}


def generator_paths(info: dict) -> list[Path]:
    """Use Qt's reported libexec directory; Linux tools are not Windows peers."""
    return [Path(info['cmake']) / 'cmake', Path(info['ninja']) / 'ninja',
        Path(info['libexec']) / 'uic', Path(info['libexec']) / 'rcc', Path(info['generator']) / 'shiboken6']


def trust(evidence: Path) -> dict:
    directory = run(['/usr/bin/openssl', 'version', '-d'])
    match = re.fullmatch(r'OPENSSLDIR: "(.+)"\s*', directory)
    assert match and Path(match[1]).is_absolute()
    paths = {Path(match[1]), Path(match[1]) / 'cert.pem', Path(match[1]) / 'certs', Path('/etc/ssl/certs/ca-certificates.crt')}
    defaults = ssl.get_default_verify_paths()
    paths.update(Path(value) for key, value in defaults._asdict().items() if value and not key.endswith('_env'))
    rows = []
    for path in sorted(paths):
        row = {'path':str(path), 'resolved':str(path.resolve()), 'exists':path.exists(), 'readable':os.access(path, os.R_OK),
            'symlink':os.readlink(path) if path.is_symlink() else None, 'permissions':run(['namei', '-l', path])}
        if path.is_file():
            raw = path.read_bytes()
            row.update(sha256=hashlib.sha256(raw).hexdigest(), pem_certificates=raw.count(b'-----BEGIN CERTIFICATE-----'))
        if path.is_dir():
            row['hashed_entries'] = [{'path':str(p), 'resolved':str(p.resolve()), 'readable':os.access(p, os.R_OK),
                'symlink':os.readlink(p) if p.is_symlink() else None} for p in path.iterdir() if re.fullmatch(r'[0-9a-f]{8}\.\d+', p.name)]
        rows.append(row)
    report = {'source_sha':os.environ['GITHUB_SHA'], 'openssl_directory':directory, 'paths':rows, 'default_paths':defaults._asdict()}
    (evidence / 'system-trust-diagnostics.json').write_text(json.dumps(report, indent=2))
    report['default_trust'] = default_trust_handshake()
    (evidence / 'system-trust-diagnostics.json').write_text(json.dumps(report, indent=2))
    return report


def source_perl(work: Path, evidence: Path, arm: dict) -> Path:
    """Same approved stable source; unmodified upstream Unix build and harness."""
    archive = fetch(arm['host_perl_source'], evidence / 'sources')
    unpack(archive, work)
    source = work / 'perl-5.44.0'
    assert all((source / 't' / name).is_file() for name in ('op/arith2.t', 'op/pack.t'))
    run(['sh', 'Configure', '-des', '-Dusethreads', '-Dcc=gcc-13', '-Dprefix=' + str(work / 'host-perl'),
         '-Dman1dir=none', '-Dman3dir=none'], cwd=source, log=evidence / 'perl-configure.log')
    run(['make', '-j2'], cwd=source, log=evidence / 'perl-build.log')
    tool = source / 'perl'
    elf(tool, target=False)
    run([tool, '-Ilib', '-MConfig', '-e', 'die unless $Config{version} eq "5.44.0"; die unless $Config{archname} =~ /aarch64/; use File::Spec; use File::Temp; use Digest::SHA; print "$^V $Config{archname}\\n"'], cwd=source, log=evidence / 'perl-native-probe.log')
    output = run(['make', 'test_harness'], cwd=source, env={**os.environ, 'TEST_ARGS':'op/arith2.t op/pack.t'}, log=evidence / 'perl-regressions.log')
    count = re.search(r'Files=(\d+), Tests=(\d+)', output)
    assert count and int(count[1]) == 2 and int(count[2]) > 0 and 'Result: PASS' in output
    run(['make', 'install'], cwd=source, log=evidence / 'perl-install.log')
    return work / 'host-perl/bin/perl'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'linux' and platform.machine() == 'aarch64'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '24.04'
    assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == 'final' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == run(['git', 'rev-parse', 'HEAD']).strip()
    for name in ('CXXFLAGS', 'CFLAGS', 'LDFLAGS', 'CMAKE_SYSROOT', 'PILOT_CXX_SDK_ROOT', 'PILOT_CXX_LINK_DIR'):
        assert not os.environ.get(name), ('Unexpected inherited SDK flags', name, os.environ.get(name))
    assert all(Path(p).resolve() == (Path(sys.base_prefix) / 'lib').resolve()
               for p in os.environ.get('LD_LIBRARY_PATH', '').split(':') if p), 'Foreign bootstrap loader path'
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh isolated ARM64 work root required'
    work.mkdir()
    evidence = REPO / 'linux-arm64-pilot-evidence'
    evidence.mkdir(exist_ok=True)
    arm, _ = contract()
    report = {'source_sha':os.environ['GITHUB_SHA'], 'os':platform.freedesktop_os_release(),
        'runner_image':{k:v for k, v in os.environ.items() if k.casefold() in ('imageos', 'imageversion')},
        'architecture':platform.machine(), 'python':sys.version, 'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),
        'accepted_target':'Ubuntu 24.04 ARM64; GLIBC <=2.38 / GLIBCXX <=3.4.32; no Ubuntu22.04 ARM64 claim',
        'bootstrap':elf(Path(sys.executable).resolve(), target=False), 'system_perl':run(['perl', '-V:version', '-V:archname'])}
    report['trust'] = trust(evidence)
    assert run(['g++-13', '-dumpmachine']).strip() == 'aarch64-linux-gnu'
    report['compiler'] = run(['g++-13', '--version'])
    report['compiler_image'] = elf(Path(shutil.which('g++-13') or '').resolve(), target=False)
    report['packages'] = run(['dpkg-query', '-W', 'gcc-13', 'g++-13', 'libstdc++-13-dev', 'libstdc++6', 'libc6', 'binutils', 'perl', 'ca-certificates'])
    link = Path(run(['g++-13', '-print-file-name=libstdc++.so']).strip()).resolve()
    report['link_sdk'] = elf(link, target=False)
    report['linker'] = run(['ld', '--version'])
    source = work / 'thread-probe.cpp'
    source.write_text('#include <condition_variable>\n#include <mutex>\n#include <thread>\nint main(){std::mutex m; std::condition_variable cv; bool done=false; std::thread t([&]{std::lock_guard<std::mutex> l(m); done=true; cv.notify_one();}); {std::unique_lock<std::mutex> l(m); cv.wait(l,[&]{return done;});}t.join();}\n')
    binary = work / 'thread-probe'
    run(['g++-13', '-std=c++17', source, '-pthread', '-o', binary], log=evidence / 'cxx-probe-build.log')
    run([binary], log=evidence / 'cxx-probe-run.log')
    report['target_probe'] = elf(binary, target=True)
    report['result'] = 'Native ABI/trust probes PASS; host tool qualification pending'
    (evidence / 'prerequisites.json').write_text(json.dumps(report, indent=2))
    # Hash-bound same-version architecture variants, isolated from the new runtime.
    tools = work / 'host-tools'
    run([sys.executable, '-m', 'venv', tools])
    py = tools / 'bin/python'
    run([py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([py, '-m', 'pip', 'install', 'cmake==4.4.4', 'ninja==1.13.2', *[w['url'] + '#sha256=' + w['sha256'] for w in arm['probe_wheels']], '--report', evidence / 'host-tools-install.json'])
    tools_info = json.loads(run([py, '-c', 'import cmake,ninja,shiboken6_generator,json; from PySide6.QtCore import QLibraryInfo; print(json.dumps(dict(cmake=cmake.CMAKE_BIN_DIR,ninja=ninja.BIN_DIR,libexec=QLibraryInfo.path(QLibraryInfo.LibraryPath.LibraryExecutablesPath),generator=shiboken6_generator.__path__[0])))']))
    paths = generator_paths(tools_info)
    report['generators'] = []
    for path in paths:
        row = elf(path, target=False)
        row['version'] = run([path, '--version'])
        report['generators'].append(row)
    header = work / 'probe.h'
    header.write_text('class NativeArmProbe { public: int answer() const; };\n')
    xml = work / 'typesystem.xml'
    xml.write_text('<typesystem package="armprobe"><object-type name="NativeArmProbe"/></typesystem>\n')
    run([paths[-1], '--generator-set=shiboken', '--output-directory=' + str(work / 'generated'), header, xml], log=evidence / 'shiboken-generation.log')
    assert any((work / 'generated').rglob('*nativearmprobe*'))
    archive = fetch(arm['host_extractor'], work)
    extractor = work / 'extractor'
    extractor.mkdir()
    unpack(archive, extractor)
    seven = extractor / '7zz'
    elf(seven, target=False)
    run([seven], log=evidence / '7zip-version.log')
    sdk = fetch(arm['host_libclang'], work)
    run([seven, 'x', '-y', *['-x!' + name for name in arm['host_libclang']['exclude_paths']], '-o' + str(work / 'src'), sdk], log=evidence / 'libclang-extract.log')
    library = next((work / 'src/libclang/lib').glob('libclang.so*')).resolve()
    report['parser'] = elf(library, target=False)
    assert (work / 'src/libclang/lib/cmake/clang/ClangConfig.cmake').is_file()
    parser_probe = work / 'parser-probe.cpp'
    parser_probe.write_text('#include <clang-c/Index.h>\n#include <stdio.h>\nint main(int n,char**v){auto i=clang_createIndex(0,0); const char*args[]={"-xc++"};auto t=clang_parseTranslationUnit(i,v[1],args,1,nullptr,0,0);if(!t||clang_getNumDiagnostics(t))return 2; auto s=clang_getClangVersion();puts(clang_getCString(s));clang_disposeString(s);clang_disposeTranslationUnit(t);clang_disposeIndex(i);}\n')
    run(['g++-13', parser_probe, '-I' + str(work / 'src/libclang/include'), '-L' + str(library.parent), '-Wl,-rpath,' + str(library.parent), '-lclang', '-o', work / 'parser-probe'], log=evidence / 'parser-probe-build.log')
    elf(work / 'parser-probe', target=False)
    report['parser']['execution'] = run([work / 'parser-probe', header], log=evidence / 'parser-native-probe.log')
    assert '22.1.8' in report['parser']['execution']
    # The distro interpreter's support/integration is recorded; use the same
    # current stable source route already qualified, without changing OS Perl.
    perl = source_perl(work, evidence, arm)
    report['source_perl'] = elf(perl, target=False)
    report['source_perl']['version'] = run([perl, '-V:version', '-V:archname'])
    for name in ('linux_arm64_runtime_pilot_sources.json', 'native_runtime_pilot_sources.json'):
        shutil.copy2(REPO / '.github/scripts' / name, evidence / name)
    report['result'] = 'PASS native Noble ARM64 prerequisites; no controlled runtime compiled'
    (evidence / 'prerequisites.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
