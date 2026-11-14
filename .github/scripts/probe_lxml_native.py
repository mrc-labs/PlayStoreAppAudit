"""Build only lxml and its current native parsers on one native host."""
from __future__ import annotations

import argparse
import gzip
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
import tempfile
import zipfile
from pathlib import Path

from probe_qt_text_providers import checked_source

REPO = Path(__file__).resolve().parents[2]


def parser_regressions() -> dict:
    from lxml import etree, html

    parser = etree.XMLParser(no_network=True, resolve_entities=False, huge_tree=False)
    root = etree.fromstring('<r xmlns="urn:test"><v>caf\u00e8</v><v>2</v></r>'.encode(), parser)
    assert root.xpath('string(t:v[1])', namespaces={'t': 'urn:test'}) == 'caf\u00e8'
    assert etree.fromstring('<r>\u03a9</r>'.encode('utf-16'), parser).text == '\u03a9'
    with tempfile.TemporaryDirectory() as directory:
        compressed = Path(directory) / 'fixture.xml.gz'
        compressed.write_bytes(gzip.compress(b'<r><v>kept</v></r>'))
        if etree.LIBXML_VERSION >= (2, 15, 0):
            try:
                etree.parse(str(compressed), parser)
            except etree.XMLSyntaxError:
                pass
            else:
                raise AssertionError('Modern parser unexpectedly auto-decompresses by default')
        # Upstream documents explicit opt-in for this isolated, trusted fixture.
        # Never enable decompression globally or change application defaults.
        trusted_gzip = etree.XMLParser(no_network=True, resolve_entities=False, huge_tree=False, decompress=True)
        assert etree.parse(str(compressed), trusted_gzip).getroot()[0].text == 'kept'
    doc = html.fromstring('<html><p>caf\u00e8<br><b>bold</b></p></html>'.encode(),
                         parser=html.HTMLParser(encoding='utf-8', no_network=True))
    assert doc.xpath('string(//p)') == 'caf\u00e8bold'
    entity = etree.fromstring(b'<!DOCTYPE r [<!ENTITY x SYSTEM "https://example.invalid/no">]><r>&x;</r>', parser)
    assert entity.text is None and len(entity) == 1 and isinstance(entity[0], etree._Entity)
    try:
        etree.fromstring(b'<r>' * 300 + b'</r>' * 300, parser)
    except etree.XMLSyntaxError as error:
        assert 'depth' in str(error).lower()
    else:
        raise AssertionError('Parser depth limit weakened')
    style = etree.XML(b'<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                      b'<xsl:template match="/"><out><xsl:value-of select="sum(r/v)"/></out></xsl:template></xsl:stylesheet>')
    transform = etree.XSLT(style, access_control=etree.XSLTAccessControl.DENY_ALL)
    assert transform(etree.XML(b'<r><v>2</v><v>3</v></r>')).getroot().text == '5'
    denied = etree.XML(b'<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                       b'<xsl:template match="/"><xsl:copy-of select="document(\'https://example.invalid/no\')"/>'
                       b'</xsl:template></xsl:stylesheet>')
    try:
        etree.XSLT(denied, access_control=etree.XSLTAccessControl.DENY_ALL)(etree.XML(b'<r/>'))
    except etree.XSLTApplyError as error:
        assert 'read rights' in str(error).lower()
    else:
        raise AssertionError('XSLT external read not blocked')
    return {'xml_namespace_xpath': True, 'utf8_utf16': True, 'gzip_xml': True, 'html_recovery': True,
            'external_entity_unresolved': True, 'depth_limit': True, 'xslt': True, 'external_read_denied': True}


def binary_record(path: Path, output: Path, arch: str, deployment: str | None) -> dict:
    record = {'name': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    if sys.platform == 'win32':
        from inspect_pe import read_pe_machine
        from verify_windows_runtime_pilot import pe_versions, validate_imports

        assert read_pe_machine(path) == (0xAA64 if arch == 'arm64' else 0x8664)
        imports = subprocess.check_output(['dumpbin', '/nologo', '/dependents', str(path)], text=True)
        validate_imports(imports)
        assert not re.search(r'(?:libxml2|libxslt|libexslt|iconv|zlib).*\.dll', imports, re.I)
        versions = pe_versions(path)
        assert all(value <= (10, 0) for value in versions.values())
        record.update(machine=read_pe_machine(path), versions=versions, imports=imports)
    elif sys.platform == 'darwin':
        if arch == 'arm64':
            from probe_macos_arm64_runtime import macho
        else:
            from probe_macos_x64_runtime import macho
        record.update(macho(path, target=True, output=output))
        assert all((tuple(map(int, value.split('.'))) + (0, 0, 0))[:3] <=
                   (tuple(map(int, deployment.split('.'))) + (0, 0, 0))[:3]
                   for value in record['minimum_os'])
        assert not any(re.search(r'lib(?:xml2|xslt|exslt|iconv|zlib)', value) for value in record['dependencies'])
    else:
        from inspect_linux_abi import readelf, required_versions, version_floor

        header = readelf(path, '--file-header')
        assert ('AArch64' if arch == 'arm64' else 'Advanced Micro Devices X86-64') in header
        required = required_versions(readelf(path, '--version-info'))
        limit = (2, 38) if arch == 'arm64' else (2, 35)
        maximum = version_floor(required, 'GLIBC_')
        assert maximum is None or tuple(map(int, maximum[6:].split('.'))) <= limit
        dynamic = readelf(path, '--dynamic')
        assert not re.search(r'NEEDED.*lib(?:xml2|xslt|exslt)', dynamic)
        record.update(header=header, version_needs=required, dynamic=dynamic)
    binaries = output / 'native-binaries'
    binaries.mkdir(exist_ok=True)
    shutil.copy2(path, binaries / path.name)
    return record


def installed_results(spec: dict, output: Path, arch: str, deployment: str | None,
                      compiler: str, wheel: Path, aliases: dict, head: str,
                      compiled_source: str, reused: dict | None = None) -> None:
    from lxml import etree

    assert etree.LXML_VERSION[:3] == (6, 1, 3)
    assert etree.LIBXML_VERSION == etree.LIBXML_COMPILED_VERSION == (2, 15, 4)
    assert etree.LIBXSLT_VERSION == etree.LIBXSLT_COMPILED_VERSION == (1, 1, 45)
    tests = parser_regressions()
    package = Path(etree.__file__).parent
    native = sorted([*package.rglob('*.pyd'), *package.rglob('*.so')])
    assert len(native) >= 2
    images = []
    with zipfile.ZipFile(wheel) as bundle:
        for path in native:
            assert bundle.read('lxml/' + path.relative_to(package).as_posix()) == path.read_bytes()
            images.append(binary_record(path, output, arch, deployment))
    result = {'source_sha': head, 'scope': spec['scope'], 'machine': platform.machine(),
              'compiler': compiler, 'compiled_source_sha': compiled_source, 'reused_provenance': reused, 'deployment': deployment, 'patches': [], 'static_library_aliases': aliases,
              'libxml': etree.LIBXML_VERSION, 'libxslt': etree.LIBXSLT_VERSION, 'tests': tests,
              'images': images, 'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
              'result': 'PASS native controlled lxml/current static parsers; not package acceptance'}
    (output / 'lxml-native-results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-root', type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    arch = os.environ['EXPECTED_ARCH']
    assert platform.machine().lower() in ({'arm64', 'aarch64'} if arch == 'arm64' else {'x86_64', 'amd64'})
    if sys.platform == 'linux':
        assert platform.freedesktop_os_release()['VERSION_ID'] == ('24.04' if arch == 'arm64' else '22.04')
    work = args.work_root.resolve()
    assert not work.exists()
    work.mkdir()
    output = Path('toolchain-delta-evidence').resolve()
    output.mkdir(exist_ok=True)
    spec_path = REPO / '.github/scripts/lxml_native_sources.json'
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    shutil.copy2(spec_path, output)
    if sys.platform == 'linux':
        from download_diagnostic_artifact import fetch_artifact

        label = ('macos' if sys.platform == 'darwin' else 'linux') + '-' + ('arm64' if arch == 'arm64' else 'x64')
        prior = next(item for item in spec['compiled_posix_wheels'] if item['label'] == label)
        metadata, data = fetch_artifact(prior['id'])
        os.environ.pop('GH_TOKEN', None)
        os.environ.pop('GITHUB_TOKEN', None)
        assert metadata['id'] == prior['id'] and not metadata['expired']
        assert metadata['workflow_run']['id'] == prior['run']
        assert metadata['workflow_run']['head_sha'] == prior['source_sha']
        assert len(data) == metadata['size_in_bytes'] == prior['size']
        assert metadata['digest'] == 'sha256:' + prior['sha256']
        assert hashlib.sha256(data).hexdigest() == prior['sha256']
        original = output / ('original-lxml-' + str(prior['id']) + '.zip')
        original.write_bytes(data)
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            old = json.loads(bundle.read('lxml_native_sources.json'))
            assert old == {key: value for key, value in spec.items() if key != 'compiled_posix_wheels'}, 'Changed compiled parser inputs'
            names = [name for name in bundle.namelist() if name.startswith('wheels/lxml-6.1.3-') and name.endswith('.whl')]
            assert len(names) == 1
            wheels = output / 'wheels'
            wheels.mkdir()
            wheel = wheels / Path(names[0]).name
            wheel.write_bytes(bundle.read(names[0]))
        subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheel)], check=True)
        deployment = ('11.0' if arch == 'arm64' else '10.15') if sys.platform == 'darwin' else None
        installed_results(spec, output, arch, deployment, 'Original compiler retained in immutable ZIP', wheel,
                          {}, head, prior['source_sha'], {**prior, 'original_zip': original.name,
                          'scope': 'Original source/static-library/worker/legal bytes reused; only fixture/execution changed'})
        return
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    sources = output / 'sources'
    sources.mkdir()
    legal = output / 'legal'
    legal.mkdir()
    for item in spec['sources']:
        archive = checked_source(item, sources)
        with tarfile.open(archive) as bundle:
            bundle.extractall(work, filter='data')
        source = work / item.get('directory', item['name'].removesuffix('.tar.gz'))
        target = legal / source.name
        target.mkdir()
        for path in source.iterdir():
            if path.is_file() and path.name.upper().startswith(('COPYING', 'COPYRIGHT', 'LICENCE', 'LICENSE', 'NOTICE')):
                shutil.copy2(path, target)
        if source.name == 'zlib-1.4':
            for name in ['README', 'zlib.h']:
                shutil.copy2(source / name, target)
        assert list(target.iterdir()), source
    prefix = work / 'prefix'
    prefix.mkdir()
    env = dict(os.environ)
    deployment = None
    if sys.platform == 'darwin':
        deployment = '11.0' if arch == 'arm64' else '10.15'
        env['MACOSX_DEPLOYMENT_TARGET'] = deployment
        env['ARCHFLAGS'] = '-arch ' + ('arm64' if arch == 'arm64' else 'x86_64')
        env['LDFLAGS'] = env.get('LDFLAGS', '') + ' -Wl,-dead_strip_dylibs'
    compiler = shutil.which('cl' if sys.platform == 'win32' else 'cc')
    assert compiler
    if sys.platform == 'win32':
        from inspect_pe import read_pe_machine

        assert read_pe_machine(Path(compiler)) == (0xAA64 if arch == 'arm64' else 0x8664)
        assert env['VCTOOLSVERSION'].rstrip('\\/').startswith('14.52.')
        env.update(DISTUTILS_USE_SDK='1', MSSdk='1')
    def run(command: list, label: str, *, directory: Path = work) -> str:
        print('lxml native stage:', label, flush=True)
        result = subprocess.run(list(map(str, command)), cwd=directory, env=env,
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / (label + '.log')).write_text(result.stdout, encoding='utf-8')
        if result.returncode:
            failures = [line for line in result.stdout.splitlines() if re.search(
                r'ModuleNotFoundError|BackendUnavailable|fatal error|error:|ERROR:', line)]
            print('\n'.join(failures[:25]) + '\n' + result.stdout[-2500:], flush=True)
        result.check_returncode()
        return result.stdout
    run([compiler, '/?' if sys.platform == 'win32' else '--version'], 'native-compiler')
    aliases = {}
    if sys.platform == 'win32':
        for item in spec['windows_assets']:
            if item['arch'] != arch:
                continue
            archive = checked_source(item, sources)
            with zipfile.ZipFile(archive) as bundle:
                assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in bundle.namelist())
                bundle.extractall(work / 'vendor')
            source = work / 'vendor' / item['name'].removesuffix('.zip')
            shutil.copytree(source / 'include', prefix / 'include', dirs_exist_ok=True)
            shutil.copytree(source / 'lib', prefix / 'lib', dirs_exist_ok=True)
        for library in (prefix / 'lib').glob('*.lib'):
            directives = run(['dumpbin', '/nologo', '/directives', library], library.stem + '-crt')
            assert not re.search(r'(?:^|\s)/DEFAULTLIB:"?LIBCMT', directives, re.I | re.M), 'Vendor static archive requires incompatible static CRT'
    common = ['-GNinja', '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_INSTALL_PREFIX=' + str(prefix),
              '-DCMAKE_INSTALL_LIBDIR=lib', '-DBUILD_SHARED_LIBS=OFF', '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
              '-DCMAKE_PREFIX_PATH=' + str(prefix)]
    if sys.platform == 'win32':
        common += ['-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreadedDLL',
                   '-DIconv_INCLUDE_DIR=' + str(prefix / 'include'), '-DIconv_LIBRARY=' + str(prefix / 'lib/iconv_a.lib')]
    if deployment:
        common += ['-DCMAKE_OSX_DEPLOYMENT_TARGET=' + deployment,
                   '-DCMAKE_OSX_ARCHITECTURES=' + ('arm64' if arch == 'arm64' else 'x86_64')]
    if sys.platform != 'win32':
        # Use the same current GNU iconv source on POSIX, not a stale copied
        # implementation. The host make is recorded; R13 tool gates stay separate.
        make = shutil.which('gmake') or shutil.which('make')
        assert make
        run([make, '--version'], 'host-make')
        iconv = work / 'libiconv-1.19'
        run(['./configure', '--prefix=' + str(prefix), '--disable-shared', '--enable-static', '--with-pic'],
            'iconv-configure', directory=iconv)
        run([make, '-j2'], 'iconv-build', directory=iconv)
        run([make, 'install'], 'iconv-install', directory=iconv)
        run(['cmake', '-S', work / 'zlib-1.4', '-B', work / 'zlib-build', *common,
             '-DZLIB_BUILD_SHARED=OFF', '-DZLIB_BUILD_STATIC=ON', '-DZLIB_BUILD_TESTING=OFF'], 'zlib-configure')
        run(['cmake', '--build', work / 'zlib-build', '--parallel', '2'], 'zlib-build')
        run(['cmake', '--install', work / 'zlib-build'], 'zlib-install')
        common += ['-DIconv_INCLUDE_DIR=' + str(prefix / 'include'),
                   '-DIconv_LIBRARY=' + str(prefix / 'lib/libiconv.a'), '-DIconv_IS_BUILT_IN=FALSE']
    common += ['-DZLIB_INCLUDE_DIR=' + str(prefix / 'include'), '-DZLIB_LIBRARY=' + str(prefix / 'lib' / (
        'zlib.lib' if sys.platform == 'win32' else 'libz.a'))]
    prerequisite = work / 'encoding-provider.c'
    prerequisite.write_text('#include <iconv.h>\n#include <zlib.h>\n#include <stdio.h>\n#include <string.h>\n'
        'int main(void) { if (_libiconv_version != 0x113 || strcmp(zlibVersion(), "1.4")) return 1; '
        'puts("PASS current static iconv1.19/zlib1.4"); return 0; }\n', encoding='utf-8')
    prerequisite_exe = work / ('encoding-provider.exe' if sys.platform == 'win32' else 'encoding-provider')
    if sys.platform == 'win32':
        command = [compiler, '/nologo', '/MD', '/I' + str(prefix / 'include'), prerequisite,
                   prefix / 'lib/iconv_a.lib', prefix / 'lib/zlib.lib', '/Fe:' + str(prerequisite_exe)]
    else:
        command = [compiler, '-I' + str(prefix / 'include'), prerequisite, prefix / 'lib/libiconv.a',
                   prefix / 'lib/libcharset.a', prefix / 'lib/libz.a', '-o', prerequisite_exe]
    run(command, 'encoding-provider-build')
    run([prerequisite_exe], 'encoding-provider-execute')
    for name, options in [('libxml2-2.15.4', ['-DLIBXML2_WITH_PYTHON=OFF', '-DLIBXML2_WITH_PROGRAMS=OFF',
                           '-DLIBXML2_WITH_TESTS=OFF', '-DLIBXML2_WITH_LEGACY=ON', '-DLIBXML2_WITH_ZLIB=ON']),
                          ('libxslt-1.1.45', ['-DLIBXSLT_WITH_PYTHON=OFF', '-DLIBXSLT_WITH_PROGRAMS=OFF',
                           '-DLIBXSLT_WITH_TESTS=OFF'])]:
        build = work / (name + '-build')
        run(['cmake', '-S', work / name, '-B', build, *common, *options], name + '-configure')
        shutil.copy2(build / 'CMakeCache.txt', output / (name + '-CMakeCache.txt'))
        if name.startswith('libxml2'):
            cache = (build / 'CMakeCache.txt').read_text(encoding='utf-8')
            for selected in ['Iconv_LIBRARY', 'ZLIB_LIBRARY']:
                value = re.search(r'^' + selected + r':[^=]+=(.+)$', cache, re.M)
                assert value and Path(value[1]).resolve().is_relative_to(prefix), (selected, value)
        run(['cmake', '--build', build, '--parallel', '2'], name + '-build')
        run(['cmake', '--install', build], name + '-install')
    if sys.platform == 'win32':
        # Match lxml's documented static linker basenames; these are identical
        # newly source-built static archives, never replacement runtime DLLs.
        for original, target in [('libxml2s.lib', 'libxml2_a.lib'), ('libxslts.lib', 'libxslt_a.lib'), ('libexslts.lib', 'libexslt_a.lib')]:
            source = prefix / 'lib' / original
            shutil.copy2(source, prefix / 'lib' / target)
            aliases[target] = {'original': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
    env.update(STATIC='true', WITHOUT_CYTHON='true', LXML_STATIC_INCLUDE_DIRS=os.pathsep.join(
        map(str, [prefix / 'include', prefix / 'include/libxml2'])),
        LXML_STATIC_LIBRARY_DIRS=str(prefix / 'lib'),
        PKG_CONFIG_PATH=str(prefix / 'lib/pkgconfig'), PKG_CONFIG_LIBDIR=str(prefix / 'lib/pkgconfig'),
        XML2_CONFIG=str(prefix / 'bin/xml2-config'), XSLT_CONFIG=str(prefix / 'bin/xslt-config'))
    if sys.platform == 'win32':
        env['LXML_STATIC_CFLAGS'] = '/DLIBXML_STATIC /DLIBXSLT_STATIC /DLIBEXSLT_STATIC'
    if sys.platform != 'win32':
        env['WITH_XML2_CONFIG'] = str(prefix / 'bin/xml2-config')
        env['WITH_XSLT_CONFIG'] = str(prefix / 'bin/xslt-config')
        env['LXML_STATIC_BINARIES'] = os.pathsep.join(map(str, [prefix / 'lib' / name for name in (
            'libexslt.a', 'libxslt.a', 'libxml2.a', 'libiconv.a', 'libcharset.a', 'libz.a')]))
    wheels = output / 'wheels'
    wheels.mkdir()
    env['PYTHONVERBOSE'] = '1'
    run([sys.executable, '-m', 'pip', 'wheel', '--no-index', '--no-build-isolation', '--no-deps', '--verbose',
         '--wheel-dir', wheels, work / 'lxml-6.1.3'], 'lxml-wheel')
    env.pop('PYTHONVERBOSE')
    from probe_setuptools_build import record_consumer_build

    record_consumer_build(output / 'lxml-wheel.log', output / 'build-dependencies', 'lxml')
    wheel = next(wheels.glob('lxml-6.1.3-*.whl'))
    run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps', wheel], 'lxml-install')
    installed_results(spec, output, arch, deployment, compiler, wheel, aliases, head, head)



if __name__ == '__main__':
    main()
