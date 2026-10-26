"""Controlled ARM64 source profile; host prerequisites gate every expensive rebuild."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from build_windows_runtime_pilot import REPO, fetch, run
from inspect_pe import read_pe_machine
from probe_windows_arm64_runtime import require_arm64


def unpack(archive: Path, destination: Path) -> None:
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter='data')


def host_tools(work: Path, arm: dict, base: dict, evidence: Path) -> dict[str, Path]:
    sources = evidence / 'sources'
    sources.mkdir(exist_ok=True)
    # The image extractor only unpacks the hash-verified native 26.05 host tool.
    installer = fetch(arm['host_extractor'], work)
    image_seven = shutil.which('7z')
    assert image_seven
    run([image_seven, 'x', '-y', '-o' + str(work / '7zip'), installer], log=evidence / 'extractor-bootstrap.log')
    seven = next(path for path in (work / '7zip').rglob('7z.exe') if read_pe_machine(path) == 0xAA64)
    require_arm64(seven)
    run([seven], log=evidence / '7zip-version.log')
    # Build the current stable Perl using the unchanged upstream ARM64 Makefile.
    perl_archive = fetch(arm['host_perl_source'], sources)
    unpack(perl_archive, work)
    perl_source = work / 'perl-5.44.0'
    tests = ['op/arith2.t', 'op/pack.t']
    assert all((perl_source / 't' / name).is_file() for name in tests), 'Check upstream test layout before compiling'
    run(['nmake', '-f', 'Makefile', 'CCTYPE=MSVC143', 'WIN64=define',
         'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\')], cwd=perl_source / 'win32', log=evidence / 'perl-build.log')
    perl = perl_source / 'perl.exe'
    require_arm64(perl)
    os.environ['PERL5LIB'] = str(perl_source / 'lib')
    run([perl, '-MConfig', '-e', 'die unless $Config{version} eq "5.44.0"; die unless $Config{archname} =~ /arm64/; use File::Spec; use File::Temp; use Digest::SHA; print "$^V $Config{archname}\\n"'], cwd=perl_source, log=evidence / 'perl-native-probe.log')
    # Targeted upstream core tests for the modules used by source generators.
    run(['nmake', '-f', 'Makefile', 'test', 'CCTYPE=MSVC143', 'WIN64=define',
         'CCHOME=' + os.environ['VCTOOLSINSTALLDIR'].rstrip('\\'), 'TEST_FILES=' + ' '.join(tests)],
        cwd=perl_source / 'win32', log=evidence / 'perl-regressions.log')
    os.environ['PATH'] = str(perl.parent) + os.pathsep + os.environ['PATH']
    assert Path(shutil.which('perl') or '').resolve() == perl.resolve()
    # Only Qt's bootstrap MOC is compiled; native wheel uic/rcc already passed.
    qt_item = next(item for item in base['sources'] if item['directory'] == 'qtbase-everywhere-src-6.12.0')
    qt_archive = fetch(qt_item, sources)
    unpack(qt_archive, work)
    qt_source = work / qt_item['directory']
    build = work / 'qt-host-tools-build'
    build.mkdir()
    run(['cmd', '/d', '/c', qt_source / 'configure.bat', '-prefix', work / 'host-qt', '-release',
         '-opensource', '-confirm-license', '-nomake', 'tests', '-nomake', 'examples', '--',
         '-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL'], cwd=build, log=evidence / 'qt-host-tools-configure.log')
    run(['cmake', '--build', build, '--target', 'moc', '--parallel', '2'], log=evidence / 'qt-host-tools-build.log')
    generators = {}
    for name in ('moc',):
        tool = build / 'bin' / (name + '.exe')
        require_arm64(tool)
        run([tool, '--version'], log=evidence / (name + '-source-version.log'))
        generators[name] = tool
    header = work / 'native_moc_probe.h'
    header.write_text('#include <QObject>\nclass NativeMocProbe : public QObject { Q_OBJECT\nQ_SIGNALS: void ready();\n};\n', encoding='utf-8')
    output = work / 'moc_native_probe.cpp'
    run([generators['moc'], '-I' + str(build / 'include'), '-I' + str(build / 'include/QtCore'),
         '-I' + str(qt_source / 'src/corelib'), header, '-o', output], log=evidence / 'moc-generation.log')
    assert 'NativeMocProbe' in output.read_text(encoding='utf-8') and 'qt_metacall' in output.read_text(encoding='utf-8')
    imports = subprocess.check_output(['dumpbin', '/dependents', str(generators['moc'])], text=True)
    assert 'Qt6Core.dll' not in imports and 'libssl-' not in imports and 'libcrypto-' not in imports, 'Bootstrap MOC must not use a runtime TLS/Qt provider'
    (evidence / 'moc-host-imports.txt').write_text(imports, encoding='utf-8')
    report = {'source_sha':os.environ['GITHUB_SHA'], 'scope':'native host tools only; no controlled runtime build',
        'perl':'5.44.0 native ARM64, official unmodified source; replaces EOL image 5.32.1 AMD64',
        'generators':'MOC 6.12.0 native ARM64 built from exact accepted Qt source; native wheel uic/rcc/Shiboken proved separately',
        'moc_generated_cpp_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'binaries':{str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [seven, perl, *generators.values()]},
        'result':'PASS'}
    (evidence / 'host-tools-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)
    return {'seven':seven, 'perl':perl, 'qt_source':qt_source}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--host-tools-only', action='store_true', required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64'
    require_arm64(Path(sys.executable))
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh host-tool root required'
    work.mkdir()
    evidence = REPO / 'windows-arm64-pilot-evidence'
    arm = json.loads((REPO / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text(encoding='utf-8'))
    base = json.loads((REPO / '.github/scripts' / arm['base_manifest']).read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == arm['base_manifest_canonical_sha256']
    host_tools(work, arm, base, evidence)


if __name__ == '__main__':
    main()
