"""Bounded native ARM64 compiler/loader/Qt-generator qualification, no stack build."""
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
from pathlib import Path

from build_windows_runtime_pilot import REPO, fetch, register_private_dll_directories, run
from inspect_pe import read_pe_machine
from verify_native_runtime_pilot import default_trust_handshake
from verify_windows_runtime_pilot import validate_imports


def require_arm64(path: Path) -> None:
    assert read_pe_machine(path) == 0xAA64, ('Not native ARM64', str(path))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    evidence = REPO / 'windows-arm64-pilot-evidence'
    evidence.mkdir(exist_ok=True)
    assert sys.platform == 'win32' and platform.machine().upper() == 'ARM64'
    assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == 'final'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    require_arm64(Path(sys.executable))
    assert os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    work = args.work_root.resolve()
    assert not work.exists(), 'Fresh isolated probe root required'
    work.mkdir()
    spec = json.loads((REPO / '.github/scripts/windows_arm64_runtime_pilot_sources.json').read_text(encoding='utf-8'))
    base = json.loads((REPO / '.github/scripts' / spec['base_manifest']).read_text(encoding='utf-8'))
    assert hashlib.sha256(json.dumps(base, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == spec['base_manifest_canonical_sha256']
    tools = {}
    for name, arguments in {'cl':['/?'], 'link':['/?'], 'clang-cl':['--version'], 'msbuild':['-version'], 'cmake':['--version'], 'ninja':['--version'], 'perl':['-v']}.items():
        path = Path(shutil.which(name) or '')
        assert path.is_file(), name
        if name in ('cl', 'link', 'clang-cl'):
            require_arm64(path)
        result = subprocess.run([str(path), *arguments], capture_output=True, text=True)
        try:
            machine = hex(read_pe_machine(path))
        except ValueError:
            machine = 'script host tool'
        tools[name] = {'path':str(path), 'machine':machine, 'role':'build-host tool', 'version':result.stdout + result.stderr}
    assert '19.44.' in tools['cl']['version']
    assert re.search(r'clang version (22\.1\.8|23\.1\.4)\b', tools['clang-cl']['version']), 'Recheck unreviewed assembler version'
    trust = default_trust_handshake()
    (evidence / 'prerequisites.json').write_text(json.dumps({'source_sha':os.environ['GITHUB_SHA'],
        'os':platform.platform(), 'image':os.environ.get('IMAGEVERSION'), 'python':sys.version,
        'architecture':platform.machine(), 'gil_disabled':sysconfig.get_config_var('Py_GIL_DISABLED'),
        'msvc_host':os.environ['VSCMD_ARG_HOST_ARCH'], 'msvc_target':os.environ['VSCMD_ARG_TGT_ARCH'],
        'sdk':os.environ.get('WINDOWSSDKVERSION'), 'toolset':os.environ.get('VCTOOLSVERSION'),
        'tools':tools, 'default_trust':trust}, indent=2), encoding='utf-8')
    # Real ARM64 /MD DLL + import library and Python extension; no AMD64/NASM input.
    dependency, extension = work / 'dependency', work / 'extension'
    dependency.mkdir()
    extension.mkdir()
    (dependency / 'probe.c').write_text('__declspec(dllexport) int arm64_answer(void) { return 42; }\n')
    (dependency / 'probe.S').write_text('.text\n.globl arm64_assembly_probe\narm64_assembly_probe:\nret\n')
    run(['clang-cl', '--target=arm64-pc-windows-msvc', '/c', dependency / 'probe.S', '/Fo' + str(dependency / 'assembly.obj')], cwd=dependency, log=evidence / 'assembly-probe.log')
    assembly_headers = subprocess.check_output(['dumpbin', '/headers', str(dependency / 'assembly.obj')], text=True)
    assert 'AA64 machine' in assembly_headers and '8664 machine' not in assembly_headers
    (evidence / 'assembly-headers.txt').write_text(assembly_headers, encoding='utf-8')
    (extension / 'probe.c').write_text('#include <Python.h>\n__declspec(dllimport) int arm64_answer(void);\n'
        'static PyObject *answer(PyObject *s, PyObject *a) { return PyLong_FromLong(arm64_answer()); }\n'
        'static PyMethodDef methods[]={{"answer",answer,METH_NOARGS,NULL},{NULL}};\n'
        'static struct PyModuleDef module={PyModuleDef_HEAD_INIT,"arm64_probe",NULL,-1,methods};\n'
        'PyMODINIT_FUNC PyInit_arm64_probe(void) { return PyModule_Create(&module); }\n')
    project = dependency / 'probe.vcxproj'
    project.write_text('<Project DefaultTargets="Build" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">'
        '<ItemGroup Label="ProjectConfigurations"><ProjectConfiguration Include="Release|ARM64">'
        '<Configuration>Release</Configuration><Platform>ARM64</Platform></ProjectConfiguration></ItemGroup>'
        '<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props"/>'
        '<PropertyGroup Label="Configuration"><ConfigurationType>DynamicLibrary</ConfigurationType>'
        '<PlatformToolset>v143</PlatformToolset></PropertyGroup>'
        '<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.props"/>'
        '<PropertyGroup><OutDir>$(ProjectDir)</OutDir><IntDir>$(ProjectDir)obj\\</IntDir><TargetName>probe</TargetName></PropertyGroup>'
        '<ItemDefinitionGroup><ClCompile><RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary></ClCompile></ItemDefinitionGroup>'
        '<ItemGroup><ClCompile Include="probe.c"/></ItemGroup>'
        '<Import Project="$(VCTargetsPath)\\Microsoft.Cpp.targets"/></Project>')
    run(['msbuild', project, '/p:Configuration=Release', '/p:Platform=ARM64', '/p:PreferredToolArchitecture=ARM64',
         '/p:VCToolsVersion=' + os.environ['VCTOOLSVERSION'], '/p:WindowsTargetPlatformVersion=' + os.environ['WINDOWSSDKVERSION'].rstrip('\\'),
         '/verbosity:diagnostic'], cwd=dependency, log=evidence / 'msbuild-native-dll.log')
    run(['cl', '/nologo', '/MD', '/LD', '/I' + str(Path(sys.base_prefix) / 'include'), extension / 'probe.c', '/link', '/LIBPATH:' + str(Path(sys.base_prefix) / 'libs'), dependency / 'probe.lib', '/OUT:' + str(extension / 'arm64_probe.pyd')], cwd=extension, log=evidence / 'extension-build.log')
    for path in (dependency / 'probe.dll', extension / 'arm64_probe.pyd'):
        require_arm64(path)
        imports = subprocess.check_output(['dumpbin', '/dependents', str(path)], text=True)
        validate_imports(imports)
        assert 'VCRUNTIME140.dll' in imports or 'api-ms-win-crt-' in imports
    headers = subprocess.check_output(['dumpbin', '/headers', str(dependency / 'probe.lib')], text=True)
    assert 'AA64 machine' in headers and '8664 machine' not in headers
    directives = subprocess.check_output(['dumpbin', '/directives', str(dependency / 'obj/probe.obj')], text=True)
    assert 'LIBCMT' not in directives and 'MT_StaticRelease' not in directives
    (evidence / 'msvc-crt-directives.txt').write_text(directives, encoding='utf-8')
    (evidence / 'import-library-headers.txt').write_text(headers, encoding='utf-8')
    code = 'import sys; sys.path.insert(0,sys.argv[1]); import arm64_probe; assert arm64_probe.answer()==42; print("answer=42")'
    environment = {**os.environ, 'PATH':str(dependency) + os.pathsep + os.environ['PATH']}
    failed = subprocess.run([sys.executable, '-I', '-c', code, str(extension)], env=environment, capture_output=True, text=True)
    assert failed.returncode and 'DLL load failed' in failed.stderr
    venv = work / 'host-tools'
    run([sys.executable, '-m', 'venv', venv])
    py = venv / 'Scripts/python.exe'
    require_arm64(py)
    register_private_dll_directories(py, [dependency], evidence)
    run([py, '-I', '-c', code, extension], log=evidence / 'secure-loader.log')
    run([py, '-m', 'pip', 'install', 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'])
    run([py, '-m', 'pip', 'install', *[item['url'] + '#sha256=' + item['sha256'] for item in spec['probe_wheels']], '--report', evidence / 'probe-tools-install.json'])
    package = venv / 'Lib/site-packages/PySide6'
    for name in ('uic', 'rcc'):
        tool = package / (name + '.exe')
        require_arm64(tool)
        run([tool, '--version'], log=evidence / (name + '-version.log'))
    generator = next((venv / 'Lib/site-packages/shiboken6_generator').rglob('shiboken6.exe'))
    require_arm64(generator)
    run([generator, '--version'], log=evidence / 'shiboken-version.log')
    (work / 'probe.h').write_text('class NativeProbe { public: int answer() const { return 42; } };\n')
    (work / 'typesystem.xml').write_text('<typesystem package="arm64_generated"><primitive-type name="int"/><object-type name="NativeProbe"/></typesystem>\n')
    run([generator, '--generator-set=shiboken', '--output-directory=' + str(work / 'generated'), work / 'probe.h', work / 'typesystem.xml'], log=evidence / 'generator-parse.log')
    assert list((work / 'generated').rglob('*_wrapper.cpp')), 'Actual native C++ binding generation required'
    # Configure only: inspect real OpenSSL ARM64 DLL/import-library naming before building it.
    archive = fetch(base['sources'][1], work)
    with tarfile.open(archive) as bundle:
        bundle.extractall(work, filter='data')
    source = work / 'openssl-4.0.3'
    run(['perl', 'Configure', spec['openssl_target'], 'shared', 'no-uplink', 'no-makedepend', 'no-docs', '--prefix=' + str(work / 'openssl'), '--libdir=lib', 'CFLAGS=/MD'], cwd=source, log=evidence / 'openssl-configure-only.log')
    makefile = (source / 'makefile').read_text(encoding='utf-8')
    assert 'CFLAGS=/MD' in makefile
    for name in [*spec['openssl_dlls'], *spec['openssl_import_libraries']]:
        assert name in makefile, ('Unexpected ARM64 OpenSSL output name', name)
    shutil.copy2(source / 'configdata.pm', evidence / 'openssl-configdata.pm')
    report = {'source_sha':os.environ['GITHUB_SHA'], 'scope':'prerequisites only; no controlled-stack build or runtime acceptance',
        'architecture':'ARM64', 'msvc_host':'ARM64', 'msvc_target':'ARM64', 'crt':'/MD',
        'loader':'PATH-only rejected; private venv registration accepted', 'dll':'0xAA64', 'import_library':'AA64 objects',
        'qt_host_tools':'native ARM64 uic/rcc/shiboken 6.12.0; actual binding wrapper generation PASS',
        'moc':'not distributed in PySide wheels; same-source Qt bootstrap tool must be built/verified before binding build',
        'openssl_target':spec['openssl_target'], 'openssl_outputs':spec['openssl_dlls'] + spec['openssl_import_libraries'],
        'nasm':'not used for ARM64', 'result':'PASS'}
    (evidence / 'probe-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
