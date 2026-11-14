#!/usr/bin/env bash
# One native Jammy x64 pilot. No application compilation or candidate packaging.
set -euo pipefail
repo=$(pwd)
work=${1:?Pass a new isolated work directory}
evidence="$repo/pilot-evidence"
test "$(uname -m)" = x86_64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 22.04
test ! -e "$work"
# Reuse the read-only native measurement, never guess an OS trust layout.
openssl_dir=$(/usr/bin/python3 - <<'PY'
import json, os, re, subprocess
from pathlib import Path
report = json.loads(Path('pilot-evidence/system-trust-diagnostics.json').read_text())
assert report['source_sha'] == os.environ['GITHUB_SHA']
assert report['default_trust']['result'] == 'default-trust authenticated handshake PASS'
sdk = json.loads(Path('pilot-evidence/cxx-sdk-qualified.json').read_text())
assert sdk['source_sha'] == os.environ['GITHUB_SHA'] and sdk['compatible']
assert sdk['thread_probe'] == 'PASS' and sdk['runtime_sdk_loaded'] is False
assert sdk['link_directory'] == os.environ['PILOT_CXX_LINK_DIR']
assert ('-L' + sdk['link_directory']) in os.environ['CXXFLAGS'].split()
measured = report['commands']['openssl_directory']['stdout']
current = subprocess.check_output(['/usr/bin/openssl', 'version', '-d'], text=True)
assert current == measured, (current, measured)
match = re.fullmatch(r'OPENSSLDIR: "(.+)"\s*', measured)
assert match and Path(match[1]).is_absolute(), measured
print(match[1])
PY
)
printf 'Measured system OpenSSL directory: %s; default-trust handshake verified\n' "$openssl_dir"
mkdir -p "$work/src" "$evidence/sources" "$evidence/legal"
export PILOT_WORK="$work" PILOT_EVIDENCE="$evidence"
python - <<'PY'
import concurrent.futures, hashlib, json, os, shutil, subprocess, tarfile, urllib.request
from pathlib import Path
manifest = Path('.github/scripts/native_runtime_pilot_sources.json')
spec = json.loads(manifest.read_text())
delta_manifest = Path('.github/scripts/linux_x64_native_delta_sources.json')
delta = json.loads(delta_manifest.read_text())
assert hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == delta['base_manifest_canonical_sha256']
work, evidence = Path(os.environ['PILOT_WORK']), Path(os.environ['PILOT_EVIDENCE'])
shutil.copy2(manifest, evidence / manifest.name)
shutil.copy2(delta_manifest, evidence / delta_manifest.name)
providers = {}
for key in ['qt_text_manifest', 'qt_cbor_manifest', 'qt_http_manifest']:
    path = manifest.parent / delta[key]['path']
    value = json.loads(path.read_text())
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == delta[key]['canonical_sha256']
    providers[key] = value
    shutil.copy2(path, evidence)
text = providers['qt_text_manifest']
cbor = providers['qt_cbor_manifest']
# The qualified text-provider inputs are unchanged; Qt itself is already in spec.
extra_sources = [item for item in text['sources'] if not item['name'].startswith('qtbase-')]
extra_sources += text['meson'] + [cbor['source']]
patch = Path(spec['cpython_patch']['path'])
assert hashlib.sha256(patch.read_bytes()).hexdigest() == spec['cpython_patch']['sha256']
shutil.copy2(patch, evidence / patch.name)
def fetch(item):
    dest = (work if item['name'].endswith('.7z') else evidence / 'sources') / item['name']
    try:
        with urllib.request.urlopen(item['url'], timeout=180) as src, dest.open('wb') as out:
            assert src.geturl().startswith('https:'), 'Source HTTPS downgrade rejected'
            shutil.copyfileobj(src, out)
    except Exception:
        print('Source fetch failed:', item['name'], item['url'], flush=True)
        raise
    with dest.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256'], item['name']
    if dest.suffix == '.whl':
        pass  # Original build-tool wheel retained; the full pilot executes matching source.
    elif dest.suffix == '.7z':
        # The generator uses libclang's API with GCC; unused driver aliases form link chains.
        exclusions = ['-x!' + name for name in item.get('exclude_paths', [])]
        subprocess.run(['7z', 'x', '-y', *exclusions, f'-o{work / "src"}', str(dest)],
                       check=True, stdout=subprocess.DEVNULL)
    else:
        with tarfile.open(dest) as archive:
            archive.extractall(work / 'src', filter='data')
    print('Verified official source/tool:', item['name'], flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(fetch, [*spec['sources'], *delta['sources'], *extra_sources]))
for sdk_source in (spec['cxx_link_sdk']['source'], spec['extractor']['source']):
    sdk_archive = evidence / 'sources' / sdk_source['name']
    with urllib.request.urlopen(sdk_source['url'], timeout=180) as src, sdk_archive.open('wb') as out:
        shutil.copyfileobj(src, out)
    with sdk_archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == sdk_source['sha256']
    print('Verified original build-tool source:', sdk_source['name'], flush=True)
source = work / 'src/Python-3.14.10'
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['base_sha256']
subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch.resolve())], cwd=source, check=True)
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256']
for name, expected in spec['security_files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, 'Upstream security protection changed: ' + name
for directory in (work / 'src').iterdir():
    target = evidence / 'legal' / directory.name
    target.mkdir()
    for candidate in directory.iterdir():
        if candidate.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'COPYRIGHT', 'NOTICE')):
            if candidate.is_dir(): shutil.copytree(candidate, target / candidate.name)
            else: shutil.copy2(candidate, target / candidate.name)
security = json.loads((manifest.parent / delta['provider_security_manifest']['path']).read_text())
assert hashlib.sha256(json.dumps(security, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == delta['provider_security_manifest']['canonical_sha256']
shutil.copy2(manifest.parent / delta['provider_security_manifest']['path'], evidence)
for item in [delta['sqlite_legal_notice'], *security['sources']]:
    directory = evidence / ('sources' if item is delta['sqlite_legal_notice'] else 'provider-security-inputs')
    directory.mkdir(exist_ok=True)
    with urllib.request.urlopen(item['url'], timeout=90) as response:
        assert response.geturl().startswith('https://'), 'HTTPS downgrade rejected'
        data = response.read()
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item['name']
    (directory / item['name']).write_bytes(data)
    if item is delta['sqlite_legal_notice']:
        (evidence / 'legal/sqlite-autoconf-3540100' / item['name']).write_bytes(data)
PY
python "$repo/.github/scripts/apply_qt_cbor_upgrade.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" \
  --archive "$evidence/sources/tinycbor-7.1.tar.gz" --evidence "$evidence"
python "$repo/.github/scripts/apply_qt_http_limits.py" apply \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --evidence "$evidence"
python - <<'PY'
import hashlib, json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, '.github/scripts')
from provision_nuitka_scons import apply_source_patch
from probe_qt_text_providers import native_md4c_flags
spec = json.loads(Path('.github/scripts/qt_text_provider_sources.json').read_text())
source = Path(os.environ['PILOT_WORK']) / 'src/qtbase-everywhere-src-6.12.0'
for key in ['qt_public_markdown_header', 'qt_private_markdown_header']:
    item = spec[key]
    assert hashlib.sha256((source / item['file']).read_bytes()).hexdigest() == item['sha256']
header = Path(os.environ['PILOT_WORK']) / 'src/md4c-0.6.0/src/md4c.h'
assert hashlib.sha256(header.read_bytes()).hexdigest() == spec['md4c_header_sha256']
apply_source_patch(source, spec['qt_md4c_patch'])
evidence = Path(os.environ['PILOT_EVIDENCE'])
shutil.copy2(spec['qt_md4c_patch']['path'], evidence)
shutil.copy2(source / 'src/gui/text/qtextmarkdownimporter.cpp', evidence / 'qtextmarkdownimporter-project.cpp')
(evidence / 'qt-md4c-patch-provenance.json').write_text(json.dumps(spec['qt_md4c_patch'], indent=2) + '\n')
# Fail on the actual new parser flag policy before any OpenSSL/Python/Qt rebuild.
probe = Path(os.environ['PILOT_WORK']) / 'md4c-policy'
md4c = Path(os.environ['PILOT_WORK']) / 'src/md4c-0.6.0'
native_md4c_flags(source, md4c, probe, evidence)
PY
prefix="$work/prefix"
ssl_prefix="$prefix/openssl"
mkdir -p "$prefix"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export LD_LIBRARY_PATH="$ssl_prefix/lib:$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
export CMAKE_PREFIX_PATH="$prefix:$ssl_prefix"
bash "$repo/.github/scripts/build_linux_x64_native_libraries.sh"
for dependency in sqlite3 libffi libmpdec liblzma zlib; do
  test "$(pkg-config --variable=libdir "$dependency")" = "$prefix/lib"
  pkg-config --modversion "$dependency"
done

# Guard the demonstrated native-provider CA gap before any Qt compilation.
python "$repo/.github/scripts/apply_qt_ca_guard.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --evidence "$evidence"

cd "$work/src/openssl-4.0.3"
# Preserve measured OS defaults; hashed CA directories may load certificates lazily.
# install_sw installs software only; it does not run install_ssldirs or edit OS trust.
./Configure linux-x86_64 shared --prefix="$ssl_prefix" --libdir=lib --openssldir="$openssl_dir"
make -j2
make test TESTS='test_evp test_x509 test_verify test_ssl_new'
make install_sw
cp configdata.pm "$evidence/openssl-configdata.pm"

cd "$work/src/Python-3.14.10"
./configure --prefix="$prefix/python" --enable-shared --with-openssl="$ssl_prefix" \
  --with-openssl-rpath=auto --with-ensurepip=install \
  CPPFLAGS="-I$prefix/include" LDFLAGS="-L$prefix/lib -Wl,-rpath,$prefix/python/lib -Wl,-rpath,$prefix/lib" \
  --with-pkg-config=yes --with-system-libmpdec=yes
make -j2
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -c "import _ssl, _hashlib, ssl, sysconfig; assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 '); assert not sysconfig.get_config_var('Py_GIL_DISABLED'); print('Built _ssl/_hashlib import:', ssl.OPENSSL_VERSION)"
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -m test -j2 --junit-xml "$evidence/cpython-regressions.xml" test_ssl test_hashlib test_hmac > "$evidence/cpython-regressions.log" 2>&1
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -m test -j2 --junit-xml "$evidence/cpython-native-regressions.xml" \
  test_ctypes test_sqlite3 test_decimal test_lzma test_zlib > "$evidence/cpython-native-regressions.log" 2>&1 \
  || { tail -n 100 "$evidence/cpython-native-regressions.log"; exit 1; }
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python "$repo/.github/scripts/verify_linux_x64_native_delta.py" \
  --prefix "$prefix" --output-dir "$evidence" --native-only
PYTHONPATH="$repo/.github/scripts" python -c \
  "import sys; from pathlib import Path; from verify_native_runtime_pilot import executed_upstream_suites; print('Executed upstream cases:', executed_upstream_suites(Path(sys.argv[1])))" \
  "$evidence/cpython-regressions.xml"
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -m unittest -v test.test_tarfile.TestExtractionFilters.test_link_at_destination > "$evidence/tarfile-security-regression.log" 2>&1
PYTHONPATH="$repo/.github/scripts" python -c \
  "import sys; from pathlib import Path; from verify_native_runtime_pilot import executed_cpython_security; print('Executed upstream security:', executed_cpython_security(Path(sys.argv[1]), Path(sys.argv[2])))" \
  "$evidence/cpython-regressions.xml" "$evidence/tarfile-security-regression.log"
make install
cp config.log "$evidence/cpython-config.log"
cp "$evidence/native_runtime_pilot_sources.json" "$prefix/python/PROJECT_MODIFIED_RUNTIME.json"
cp "$evidence/linux_x64_native_delta_sources.json" "$prefix/python/linux_x64_native_delta_sources.json"
# Do not let setup-python's same-SONAME libpython or CMake roots satisfy this build.
export LD_LIBRARY_PATH="$prefix/python/lib:$ssl_prefix/lib:$prefix/lib"
unset PYTHONHOME Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR
export Python_ROOT_DIR="$prefix/python" Python3_ROOT_DIR="$prefix/python"
export PKG_CONFIG_PATH="$prefix/python/lib/pkgconfig:$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
"$prefix/python/bin/python3.14" -m venv "$work/venv"
export PATH="$work/venv/bin:$PATH"
python "$repo/.github/scripts/bootstrap_pip.py"
python -m pip install -r "$repo/.github/scripts/source_build_requirements.txt" -c "$repo/.github/scripts/source_build_constraints.txt" 'cmake==4.4.4' 'ninja==1.13.2' 'pycparser==3.12' 'pytest==9.2.0' --report "$evidence/build-tools-install.json"
mkdir "$evidence/cffi-wheel"
PYTHONVERBOSE=1 python -m pip wheel --no-index --no-build-isolation --no-deps --verbose \
  --wheel-dir "$evidence/cffi-wheel" "$work/src/cffi-2.1.1" > "$evidence/cffi-build.log" 2>&1 \
  || { tail -n 100 "$evidence/cffi-build.log"; exit 1; }
python "$repo/.github/scripts/probe_setuptools_build.py" --consumer cffi --consumer-log "$evidence/cffi-build.log" --output-dir "$evidence/build-dependencies"
python -m pip install --no-index --no-deps "$evidence"/cffi-wheel/cffi-*.whl
(cd "$work/src/cffi-2.1.1" && python -m pytest -q src/c/test_c.py testing/cffi0/test_ffi_backend.py testing/cffi1/test_ffi_obj.py \
  --junitxml "$evidence/cffi-tests.xml") > "$evidence/cffi-tests.log" 2>&1 \
  || { tail -n 100 "$evidence/cffi-tests.log"; exit 1; }
python "$repo/.github/scripts/verify_linux_x64_native_delta.py" --prefix "$prefix" --output-dir "$evidence" --native-only --cffi

cmake -S "$work/src/libpng-1.6.59" -B "$work/png-build" -GNinja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DPNG_TESTS=ON -DPNG_SHARED=ON -DPNG_STATIC=OFF
cmake --build "$work/png-build"
ctest --test-dir "$work/png-build" --output-on-failure > "$evidence/libpng-regressions.log" 2>&1
cmake --install "$work/png-build"
cmake -S "$work/src/pcre2-10.49" -B "$work/pcre-build" -GNinja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=ON -DPCRE2_BUILD_PCRE2_16=ON -DPCRE2_SUPPORT_JIT=ON \
  -DPCRE2_BUILD_TESTS=ON
cmake --build "$work/pcre-build"
ctest --test-dir "$work/pcre-build" --output-on-failure > "$evidence/pcre2-regressions.log" 2>&1
cmake --install "$work/pcre-build"

# Use the primary Meson source whose243 Python modules equal the qualified wheel.
meson_source="$work/src/meson-1.12.1/meson.py"
python "$meson_source" setup "$work/harfbuzz-build" "$work/src/harfbuzz-15.1.0" \
  --prefix="$prefix" --libdir=lib --buildtype=release --wrap-mode=nofallback \
  -Dauto_features=disabled -Dglib=enabled -Dtests=enabled -Dutilities=enabled \
  -Dsubset=enabled -Draster=disabled -Dvector=disabled -Dgpu=disabled \
  -Dbenchmark=disabled -Dexperimental_api=false -Db_ndebug=false > "$evidence/harfbuzz-configure.log" 2>&1
python "$meson_source" compile -C "$work/harfbuzz-build" -j 2 > "$evidence/harfbuzz-build.log" 2>&1
python "$meson_source" test -C "$work/harfbuzz-build" --no-rebuild --print-errorlogs --num-processes 2 > "$evidence/harfbuzz-tests.log" 2>&1
cp "$work/harfbuzz-build/meson-logs/testlog.json" "$evidence/harfbuzz-testlog.json"
python "$meson_source" install -C "$work/harfbuzz-build" --no-rebuild > "$evidence/harfbuzz-install.log" 2>&1
cmake -S "$work/src/md4c-0.6.0" -B "$work/md4c-build" -GNinja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DBUILD_SHARED_LIBS=ON > "$evidence/md4c-configure.log" 2>&1
cmake --build "$work/md4c-build" --parallel 2 > "$evidence/md4c-build.log" 2>&1
cmake --install "$work/md4c-build" > "$evidence/md4c-install.log" 2>&1
for suite in spec regressions; do
  LD_LIBRARY_PATH="$prefix/lib" python "$work/src/md4c-0.6.0/test/run-testsuite.py" \
    --program "$prefix/bin/md2html" --spec "$work/src/md4c-0.6.0/test/$suite.txt" > "$evidence/md4c-$suite.log" 2>&1
done
mkdir "$work/qt-build"
cd "$work/qt-build"
"$work/src/qtbase-everywhere-src-6.12.0/configure" -prefix "$prefix/qt" \
  -release -opensource -confirm-license -nomake tests -nomake examples \
  -openssl-linked -system-libpng -system-pcre -system-zlib -system-sqlite -no-feature-openssl-runtime \
  -- -DINPUT_harfbuzz=system -DINPUT_libmd4c=system -DOPENSSL_ROOT_DIR="$ssl_prefix" -DCMAKE_PREFIX_PATH="$prefix;$ssl_prefix" \
  -DCMAKE_INSTALL_RPATH="$ssl_prefix/lib;$prefix/lib"
python - <<'PY'
import os
from pathlib import Path
flags = next(line for line in Path('CMakeCache.txt').read_text().splitlines() if line.startswith('CMAKE_CXX_FLAGS:STRING='))
assert '-L' + os.environ['PILOT_CXX_LINK_DIR'] in flags, flags
print('Qt target link SDK flags verified:', flags, flush=True)
for feature in ['system_harfbuzz', 'system_textmarkdownreader']:
    assert f'QT_FEATURE_{feature}:INTERNAL=ON' in Path('CMakeCache.txt').read_text(), feature
PY
cmake --build . --parallel 2
cmake --install .
cp CMakeCache.txt "$evidence/qtbase-CMakeCache.txt"
cp config.summary "$evidence/qtbase-config.summary"
bash "$repo/.github/scripts/probe_linux_x64_qt_sqlite.sh"
mkdir "$work/qtsvg-build"
cd "$work/qtsvg-build"
"$prefix/qt/bin/qt-configure-module" "$work/src/qtsvg-everywhere-src-6.12.0" \
  -- -DCMAKE_INSTALL_RPATH="$prefix/qt/lib;$prefix/lib;$ssl_prefix/lib"
cmake --build . --parallel 2
cmake --install .

export LLVM_INSTALL_DIR="$work/src/libclang"
export PATH="$prefix/qt/bin:$PATH"
export LD_LIBRARY_PATH="$prefix/qt/lib:$LLVM_INSTALL_DIR/lib:$LD_LIBRARY_PATH"
cd "$work/src/pyside-setup-everywhere-src-6.12.0"
PYTHONVERBOSE=1 python setup.py install --ignore-git --qtpaths="$prefix/qt/bin/qtpaths6" \
  --parallel=2 --limited-api=yes --module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test \
  --no-qt-tools > "$evidence/pyside-build.log" 2>&1
python "$repo/.github/scripts/probe_setuptools_build.py" --consumer pyside --consumer-log "$evidence/pyside-build.log" --output-dir "$evidence/build-dependencies"
cd "$repo"
# libclang is a generator prerequisite, never an application runtime search path.
export LD_LIBRARY_PATH="$prefix/qt/lib:$prefix/python/lib:$ssl_prefix/lib:$prefix/lib"
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials=='))+'\n')
PY
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.2.0' --report "$evidence/runtime-install.json"
python -m pip check
export PILOT_PREFIX="$prefix" PILOT_CPYTHON_SOURCE="$work/src/Python-3.14.10"
unset SSL_CERT_FILE SSL_CERT_DIR
export XDG_CONFIG_HOME="$work/profile/config" XDG_DATA_HOME="$work/profile/data" XDG_CACHE_HOME="$work/profile/cache"
export QT_QPA_PLATFORM=xcb
xvfb-run -a python .github/scripts/verify_native_runtime_pilot.py --output-dir "$evidence"
xvfb-run -a python .github/scripts/verify_linux_x64_native_delta.py --prefix "$prefix" --output-dir "$evidence" --cffi
python main.py cli audit --help > "$evidence/cli-smoke.txt"
xvfb-run -a python -m pytest tests/test_cli_headless.py -q > "$evidence/project-cli-regressions.log" 2>&1
python -m compileall -q playstore_app_audit
python - <<'PY'
import json, os, platform, subprocess, sys
from pathlib import Path
summary = {'source_sha':os.environ['GITHUB_SHA'],'scope':'non-release native runtime/framework pilot',
 'runtime_identity':'project-modified CPython 3.14.10, not unchanged official binary',
 'python':sys.version,'architecture':platform.machine(),'prefix':os.environ['PILOT_PREFIX'],
 'gil_disabled':__import__('sysconfig').get_config_var('Py_GIL_DISABLED'),
 'tools':{name:subprocess.run(command,capture_output=True,text=True,check=True).stdout for name,command in {
 'gcc':['gcc','--version'],'cmake':['cmake','--version'],'ninja':['ninja','--version'],
 'meson':[sys.executable,os.path.join(os.environ['PILOT_WORK'],'src/meson-1.12.1/meson.py'),'--version']}.items()}}
Path('pilot-evidence/build-provenance.json').write_text(json.dumps(summary,indent=2))
PY
echo 'Native runtime/framework pilot PASS; no application package produced.'
