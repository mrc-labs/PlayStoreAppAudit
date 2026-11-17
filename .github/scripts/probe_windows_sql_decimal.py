"""Native prerequisite for current SQLite/mpdecimal against unchanged CPython C wrappers."""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import xml.etree.ElementTree as ET
from pathlib import Path

from build_windows_runtime_pilot import fetch, run
from inspect_pe import read_pe_machine
from verify_windows_runtime_pilot import pe_versions

REPO = Path(__file__).resolve().parents[2]


def project_sources(project: Path, python_source: Path, mpdecimal: Path) -> list[Path]:
    root = ET.parse(project).getroot()
    result = []
    for node in root.iter('{http://schemas.microsoft.com/developer/msbuild/2003}ClCompile'):
        if 'Include' not in node.attrib:
            continue
        name = node.attrib['Include'].replace('$(mpdecimalDir)', str(mpdecimal)).replace('\\', '/')
        path = Path(name)
        if not path.is_absolute():
            path = project.parent / path
        path = path.resolve(strict=True)
        assert path.is_relative_to(python_source) or path.is_relative_to(mpdecimal)
        result.append(path)
    assert result
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    assert sys.platform == 'win32' and platform.python_version() == '3.14.10'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    assert platform.machine().lower() == ('arm64' if arch == 'arm64' else 'amd64')
    assert os.environ['VSCMD_ARG_HOST_ARCH'] == os.environ['VSCMD_ARG_TGT_ARCH'] == arch
    # DevShell can omit VCToolsVersion after a fresh ARM64 installation.
    # Measure the selected native executable instead of inferring its version.
    compiler = Path(shutil.which('cl') or '').resolve(strict=True)
    assert compiler.is_file() and read_pe_machine(compiler) == (0xAA64 if arch == 'arm64' else 0x8664)
    toolset = compiler.parents[3].name
    assert toolset.startswith('14.52.'), ('Unexpected actual compiler', compiler)
    declared = os.environ.get('VCTOOLSVERSION')
    assert not declared or declared.rstrip('\\/') == toolset, (declared, toolset)
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    output = REPO / 'toolchain-delta-evidence'
    sources = output / 'sources'
    sources.mkdir()
    base = json.loads((REPO / '.github/scripts/windows_runtime_pilot_sources.json').read_text())
    native = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text())
    selected = [base['sources'][0], *[row for row in native['sources'] if row['name'].startswith(('sqlite-', 'mpdecimal-'))]]
    assert [row['name'] for row in selected] == ['Python-3.14.10.tar.xz', 'sqlite-autoconf-3540100.tar.gz', 'mpdecimal-4.0.1.tar.gz']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        archives = list(pool.map(lambda row: fetch(row, sources), selected))
    for archive in archives:
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
    python_source = work / 'Python-3.14.10'
    decimal = work / 'mpdecimal-4.0.1'
    sqlite = work / 'sqlite-autoconf-3540100'
    for item in selected:
        root = work / item['directory']
        legal = output / 'legal' / root.name
        legal.mkdir(parents=True)
        for candidate in root.iterdir():
            if candidate.is_file() and candidate.name.upper().startswith(('LICENSE', 'COPYING', 'COPYRIGHT', 'NOTICE')):
                shutil.copy2(candidate, legal / candidate.name)
    fetch(native['sqlite_legal_notice'], output / 'legal' / sqlite.name)
    prefix = work / 'native-consumers'
    prefix.mkdir()
    common = [compiler, '/nologo', '/MD', '/O2', '/LD', '/D_CRT_SECURE_NO_WARNINGS']
    # This prerequisite uses the actual same-patch installed native interpreter;
    # it neither changes that installation nor qualifies its TLS/native providers.
    includes = ['/I' + str(python_source / 'PC'), '/I' + str(python_source / 'Include'),
                '/I' + str(python_source / 'Include/internal')]
    library = Path(sys.base_prefix) / 'libs/python314.lib'
    assert library.is_file()
    run([*common, '/DSQLITE_ENABLE_MATH_FUNCTIONS', '/DSQLITE_ENABLE_FTS4', '/DSQLITE_ENABLE_FTS5',
         '/DSQLITE_ENABLE_RTREE', '/DSQLITE_OMIT_AUTOINIT', '/DSQLITE_ENABLE_COLUMN_METADATA',
         '/DSQLITE_API=__declspec(dllexport)', sqlite / 'sqlite3.c', '/link',
         '/OUT:' + str(prefix / 'sqlite3.dll'), '/IMPLIB:' + str(prefix / 'sqlite3.lib')],
        cwd=prefix, log=output / 'sqlite-native-build.log')
    sqlite_wrapper = project_sources(python_source / 'PCbuild/_sqlite3.vcxproj', python_source, decimal)
    run([*common, *includes, '/I' + str(sqlite), '/DPy_BUILD_CORE_MODULE',
         '/DPY_SQLITE_HAVE_SERIALIZE', '/DPY_SQLITE_ENABLE_LOAD_EXTENSION', *sqlite_wrapper,
         '/link', library, prefix / 'sqlite3.lib', '/OUT:' + str(prefix / '_sqlite3.pyd')],
        cwd=prefix, log=output / 'sqlite-wrapper-build.log')
    decimal_sources = project_sources(python_source / 'PCbuild/_decimal.vcxproj', python_source, decimal)
    extra: list[str | Path] = []
    if arch == 'x64':
        # Original CPython uses MASM on x64; native ARM64 uses ANSI, never NASM/x64 assembly.
        asm = decimal / 'libmpdec/vcdiv64.asm'
        run(['ml64', '/nologo', '/c', '/Fo' + str(prefix / 'vcdiv64.obj'), asm], cwd=prefix,
            log=output / 'mpdecimal-native-asm.log')
        extra = ['/DMASM', prefix / 'vcdiv64.obj']
    else:
        extra = ['/DANSI']
    run([*common, *includes, '/I' + str(python_source / 'Modules/_decimal'),
         '/I' + str(python_source / 'Modules/_decimal/windows'), '/I' + str(decimal / 'libmpdec'),
         '/DPy_BUILD_CORE_MODULE', '/DBUILD_LIBMPDEC', '/DCONFIG_64', *extra, *decimal_sources,
         '/link', library, '/OUT:' + str(prefix / '_decimal.pyd')], cwd=prefix,
        log=output / 'decimal-wrapper-build.log')
    images = []
    for path in prefix.iterdir():
        if path.suffix.lower() not in {'.dll', '.pyd'}:
            continue
        assert read_pe_machine(path) == (0xAA64 if arch == 'arm64' else 0x8664)
        imports = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
        assert 'VCRUNTIME' in imports.upper(), 'Dynamic CRT must remain selected'
        versions = pe_versions(path)
        assert all(version <= (10, 0) for version in versions.values()), 'Implicit Windows baseline increase'
        shutil.copy2(path, output / path.name)
        (output / (path.name + '-imports.txt')).write_text(imports)
        images.append({'name': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'machine': read_pe_machine(path), 'versions': versions, 'imports': imports})
    code = ('import os,sys; h=os.add_dll_directory(sys.argv[1]); sys.path.insert(0,sys.argv[1]); '
            'import _sqlite3,_decimal,sqlite3,decimal; '
            'assert _sqlite3.__file__.startswith(sys.argv[1]) and _decimal.__file__.startswith(sys.argv[1]); '
            'assert sqlite3.sqlite_version=="3.54.1" and _decimal.__libmpdec_version__=="4.0.1"; '
            'assert decimal.Decimal("1.1")+decimal.Decimal("2.2")==decimal.Decimal("3.3"); '
            'c=sqlite3.connect(":memory:"); assert c.execute("select json_array(1,2)").fetchone()[0]=="[1,2]"; '
            'print("PASS original CPython wrappers/current SQLite3.54.1/mpdecimal4.0.1/native MD")')
    run([sys.executable, '-I', '-c', code, prefix], log=output / 'native-wrapper-consumers.log')
    # Run upstream cases on the actual newly compiled wrappers in this isolated child.
    suite = ('import os,sys,unittest; h=os.add_dll_directory(sys.argv[1]); sys.path.insert(0,sys.argv[1]); '
             'sys.path.append(sys.argv[2]); s=unittest.defaultTestLoader.loadTestsFromNames(["test.test_decimal","test.test_sqlite3"]); '
             'r=unittest.TextTestRunner(verbosity=1).run(s); assert r.testsRun>0; sys.exit(not r.wasSuccessful())')
    run([sys.executable, '-I', '-c', suite, prefix, python_source / 'Lib'], log=output / 'native-upstream-tests.log')
    (output / 'windows-sql-decimal-results.json').write_text(json.dumps({
        'source_sha': os.environ['GITHUB_SHA'], 'sources': selected, 'sqlite_public_domain_notice': native['sqlite_legal_notice'], 'architecture': arch,
        'compiler': toolset, 'compiler_path': str(compiler), 'compiler_sha256': hashlib.sha256(compiler.read_bytes()).hexdigest(), 'declared_toolset': declared, 'crt': '/MD', 'images': images, 'patches': [],
        'scope': 'Original same-patch CPython C-wrapper/native provider prerequisite only; no controlled runtime/TLS/framework/package adoption',
        'result': 'PASS'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
