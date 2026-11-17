#!/usr/bin/env bash
# One native Noble ARM64 pilot, gated by the separate prerequisite step. No application compilation or candidate packaging.
set -euo pipefail
repo=$(pwd)
work=${1:?Pass a new isolated work directory}
evidence="$repo/linux-arm64-pilot-evidence"
test "$(uname -m)" = aarch64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 24.04
test -d "$work"
test ! -e "$work/prefix"
export CC=gcc-13 CXX=g++-13
export PATH="$work/host-perl/bin:$work/host-tools/bin:$PATH"
# Reuse the read-only native measurement, never guess an OS trust layout.
openssl_dir=$(/usr/bin/python3 - <<'PY'
import json, os, re, subprocess
from pathlib import Path
report = json.loads(Path('linux-arm64-pilot-evidence/prerequisites.json').read_text())
assert report['source_sha'] == os.environ['GITHUB_SHA']
assert report['result'] == 'PASS native Noble ARM64 prerequisites; no controlled runtime compiled'
assert report['trust']['default_trust']['result'] == 'default-trust authenticated handshake PASS'
assert report['target_probe']['machine'] == 'AArch64'
measured = report['trust']['openssl_directory']
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
import concurrent.futures, hashlib, json, os, shutil, subprocess, sys, urllib.request
from pathlib import Path
sys.path.insert(0, str(Path('.github/scripts').resolve()))
from probe_linux_arm64_runtime import contract, fetch, runtime_sources, unpack
spec, base = contract()
work, evidence = Path(os.environ['PILOT_WORK']), Path(os.environ['PILOT_EVIDENCE'])
for name in ('native_runtime_pilot_sources.json', 'linux_arm64_runtime_pilot_sources.json'):
    shutil.copy2(Path('.github/scripts') / name, evidence / name)
patch = Path(spec['cpython_patch']['path'])
assert hashlib.sha256(patch.read_bytes()).hexdigest() == spec['cpython_patch']['sha256']
shutil.copy2(patch, evidence / patch.name)
def stage(item):
    archive = fetch(item, evidence / 'sources')
    if archive.suffix not in {'.whl', '.zip', '.dat'}:
        unpack(archive, work / 'src')
maintenance_path = Path('.github/scripts/linux_arm64_maintenance_sources.json')
maintenance = json.loads(maintenance_path.read_text())
shutil.copy2(maintenance_path, evidence)
projection = maintenance['native_source_projection']
native = json.loads((maintenance_path.parent / projection['path']).read_text())
selected = {key: native[key] for key in projection['keys']}
assert hashlib.sha256(json.dumps(selected, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == projection['canonical_sha256']
shutil.copy2(maintenance_path.parent / projection['path'], evidence)
providers = {}
for item in maintenance['qt_manifests']:
    path = maintenance_path.parent / item['path']
    value = json.loads(path.read_text())
    assert hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == item['canonical_sha256']
    providers[item['path']] = value
    shutil.copy2(path, evidence)
text = providers['qt_text_provider_sources.json']
extra = native['sources'] + [item for item in text['sources'] if not item['name'].startswith('qtbase-')]
extra += text['meson'] + [providers['qt_cbor_provider_sources.json']['source']]
extra += providers['qt_data_refresh_sources.json']['sources'] + providers['qt_cldr49_sources.json']['sources']
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(stage, runtime_sources(spec, base) + extra))
fetch(spec['host_extractor']['source'], evidence / 'sources')
fetch(spec['host_libclang'], work)  # recheck the exact already-loaded host SDK
source = work / 'src/Python-3.14.10'
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['base_sha256']
subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch.resolve())], cwd=source, check=True)
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256']
for name, expected in spec['security_files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected, 'Upstream security protection changed: ' + name
for directory in [*(work / 'src').iterdir(), work / 'perl-5.44.0', work / 'extractor']:
    if not directory.is_dir():
        continue
    target = evidence / 'legal' / directory.name
    target.mkdir()
    for candidate in directory.iterdir():
        if candidate.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'ARTISTIC')):
            if candidate.is_dir(): shutil.copytree(candidate, target / candidate.name)
            else: shutil.copy2(candidate, target / candidate.name)
security = providers['provider_ca_security_sources.json']
for item in [native['sqlite_legal_notice'], *security['sources']]:
    directory = evidence / ('sources' if item is native['sqlite_legal_notice'] else 'provider-security-inputs')
    directory.mkdir(exist_ok=True)
    with urllib.request.urlopen(item['url'], timeout=90) as response:
        assert response.geturl().startswith('https:'), 'HTTPS downgrade rejected'
        data = response.read()
    assert hashlib.sha256(data).hexdigest() == item['sha256'], item['name']
    (directory / item['name']).write_bytes(data)
    if item is native['sqlite_legal_notice']:
        (evidence / 'legal/sqlite-autoconf-3540100' / item['name']).write_bytes(data)
PY
python "$repo/.github/scripts/apply_qt_cbor_upgrade.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --archive "$evidence/sources/tinycbor-7.1.tar.gz" --evidence "$evidence"
python "$repo/.github/scripts/apply_qt_http_limits.py" apply \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --evidence "$evidence"
python "$repo/.github/scripts/apply_qt_data_refresh.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --archives "$evidence/sources" --evidence "$evidence"
python "$repo/.github/scripts/apply_qt_cldr49.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --archives "$evidence/sources" --evidence "$evidence"
python "$repo/.github/scripts/apply_qt_ca_guard.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --evidence "$evidence"
python - <<'PYMD'
import json, os, shutil, sys
from pathlib import Path
sys.path.insert(0, '.github/scripts')
from provision_nuitka_scons import apply_source_patch
from probe_qt_text_providers import native_md4c_flags
spec = json.loads(Path('.github/scripts/qt_text_provider_sources.json').read_text())
source = Path(os.environ['PILOT_WORK']) / 'src/qtbase-everywhere-src-6.12.0'
apply_source_patch(source, spec['qt_md4c_patch'])
evidence = Path(os.environ['PILOT_EVIDENCE'])
shutil.copy2(spec['qt_md4c_patch']['path'], evidence)
md4c = Path(os.environ['PILOT_WORK']) / 'src/md4c-0.6.0'
native_md4c_flags(source, md4c, Path(os.environ['PILOT_WORK']) / 'md4c-policy', evidence, target='linux-arm64')
PYMD
prefix="$work/prefix"
ssl_prefix="$prefix/openssl"
mkdir -p "$prefix"
export PILOT_PREFIX="$prefix" PILOT_NATIVE_PROVIDER_TARGET=linux-arm64
export CMAKE_BUILD_PARALLEL_LEVEL=2
export LD_LIBRARY_PATH="$ssl_prefix/lib:$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
export CMAKE_PREFIX_PATH="$prefix:$ssl_prefix"

bash "$repo/.github/scripts/build_linux_x64_native_libraries.sh"
cd "$work/src/openssl-4.0.3"
# Preserve measured OS defaults; hashed CA directories may load certificates lazily.
# install_sw installs software only; it does not run install_ssldirs or edit OS trust.
./Configure linux-aarch64 shared --prefix="$ssl_prefix" --libdir=lib --openssldir="$openssl_dir"
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
  test_ctypes test_sqlite3 test_decimal test_lzma test_zlib > "$evidence/cpython-native-regressions.log" 2>&1
PYTHONPATH="$repo/.github/scripts" python -c \
  "import sys; from pathlib import Path; from verify_native_runtime_pilot import executed_upstream_suites; print('Executed upstream cases:', executed_upstream_suites(Path(sys.argv[1])))" \
  "$evidence/cpython-regressions.xml"
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -m unittest -v test.test_tarfile.TestExtractionFilters.test_link_at_destination > "$evidence/tarfile-security-regression.log" 2>&1
python - "$evidence/tarfile-security-regression.log" "$evidence/cpython-regressions.xml" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__import__('os').environ['GITHUB_WORKSPACE']) / '.github/scripts'))
from verify_linux_arm64_runtime_pilot import require_security_case
require_security_case(Path(sys.argv[2]))
text = Path(sys.argv[1]).read_text()
assert 'Ran 1 test' in text and '\nOK\n' in text and 'skipped' not in text, text
print('Executed upstream compromised-SPKI and tar destination-link rejection PASS')
PY
make install
cp config.log "$evidence/cpython-config.log"
cp "$evidence/linux_arm64_runtime_pilot_sources.json" "$prefix/python/PROJECT_MODIFIED_RUNTIME.json"
cp "$evidence/native_runtime_pilot_sources.json" "$prefix/python/native_runtime_pilot_sources.json"
cp "$evidence/linux_arm64_maintenance_sources.json" "$prefix/python/PROJECT_MAINTENANCE_INPUTS.json"
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
python "$repo/.github/scripts/verify_linux_x64_native_delta.py" --prefix "$prefix" --output-dir "$evidence" --native-only --cffi --target linux-arm64

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
retain_sdk() {
  local label=$1
  PILOT_SDK_LABEL="$label" python - <<'PYSDK'
import hashlib, json, os, tarfile
from pathlib import Path
prefix = Path(os.environ['PILOT_PREFIX'])
output = Path(os.environ['PILOT_EVIDENCE'])
label = os.environ['PILOT_SDK_LABEL']
files = {}
for path in sorted(prefix.rglob('*')):
    if path.is_symlink():
        assert path.resolve().is_relative_to(prefix), path
        files[path.relative_to(prefix).as_posix()] = {'symlink': os.readlink(path)}
    elif path.is_file():
        with path.open('rb') as stream:
            files[path.relative_to(prefix).as_posix()] = {'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}
archive = output / (label + '.tar.gz')
with tarfile.open(archive, 'w:gz', compresslevel=1) as bundle:
    bundle.add(prefix, arcname='prefix')
with archive.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
(output / (label + '-provenance.json')).write_text(json.dumps({
    'source_sha': os.environ['GITHUB_SHA'], 'original_prefix': str(prefix),
    'scope': 'Internal intermediate diagnostic SDK; not a candidate or producer input',
    'capture_stage': os.environ.get('PILOT_SDK_STAGE', 'qtbase-and-qtsvg-installed'),
    'archive_sha256': digest, 'files': files}, indent=2) + '\n', encoding='utf-8')
print('Retained intermediate SDK:', label, archive.stat().st_size, digest, flush=True)
PYSDK
}
retain_sdk pre-qt-sdk
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
flags = next(line for line in Path('CMakeCache.txt').read_text().splitlines() if line.startswith('CMAKE_CXX_COMPILER:FILEPATH='))
assert Path(flags.split('=', 1)[1]).resolve() == Path('/usr/bin/g++-13').resolve(), flags
assert not os.environ.get('PILOT_CXX_LINK_DIR') and not os.environ.get('PILOT_CXX_SDK_ROOT')
cache = Path('CMakeCache.txt').read_text().splitlines()
for name in ('OPENSSL_SSL_LIBRARY:FILEPATH=', 'OPENSSL_CRYPTO_LIBRARY:FILEPATH='):
    library = next(line.split('=', 1)[1] for line in cache if line.startswith(name))
    assert Path(library).resolve().is_relative_to(Path(os.environ['PILOT_WORK']) / 'prefix/openssl'), library
print('Native Noble GCC13 selected; no foreign link SDK/sysroot')
PY
cmake --build . --parallel 2
cmake --install .
cp CMakeCache.txt "$evidence/qtbase-CMakeCache.txt"
cp config.summary "$evidence/qtbase-config.summary"
export PILOT_SDK_STAGE=qtbase-installed
retain_sdk qt-sdk
bash "$repo/.github/scripts/probe_linux_x64_qt_sqlite.sh"
mkdir "$work/qtsvg-build"
cd "$work/qtsvg-build"
"$prefix/qt/bin/qt-configure-module" "$work/src/qtsvg-everywhere-src-6.12.0" \
  -- -DCMAKE_INSTALL_RPATH="$prefix/qt/lib;$prefix/lib;$ssl_prefix/lib"
cmake --build . --parallel 2
cmake --install .

export PILOT_SDK_STAGE=qtbase-and-qtsvg-installed
retain_sdk qt-sdk
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
unset LLVM_INSTALL_DIR
# Retain actual matched binding bytes before runtime consumers can fail.
python - <<'PYBINDING'
import hashlib, json, os, shutil
from pathlib import Path
import PySide6, shiboken6
output = Path(os.environ['PILOT_EVIDENCE']) / 'pyside-binding-sdk'
output.mkdir()
site = Path(PySide6.__file__).resolve().parent.parent
for module in [PySide6, shiboken6]:
    package = Path(module.__file__).resolve().parent
    assert package.parent == site and package.name in {'PySide6', 'shiboken6'}
    shutil.copytree(package, output / package.name, symlinks=True)
for metadata in site.iterdir():
    if metadata.is_dir() and metadata.name.lower().startswith(('pyside6', 'shiboken6')) and metadata.name.endswith(('.dist-info', '.egg-info')):
        shutil.copytree(metadata, output / metadata.name, symlinks=True)
files = {}
for path in output.rglob('*'):
    if path.is_symlink():
        assert path.resolve().is_relative_to(output), path
        files[path.relative_to(output).as_posix()] = {'symlink': os.readlink(path)}
    elif path.is_file():
        files[path.relative_to(output).as_posix()] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
(output.parent / 'pyside-binding-sdk-provenance.json').write_text(json.dumps({
    'source_sha': os.environ['GITHUB_SHA'], 'original_site': str(site),
    'qt_compiled_source_sha': os.environ['GITHUB_SHA'],
    'python_compiled_source_sha': os.environ['GITHUB_SHA'],
    'identity': 'Matched native project-built binding diagnostic SDK; not an official unchanged wheel or candidate',
    'files': files}, indent=2) + '\n')
PYBINDING
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('linux-arm64-pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials=='))+'\n')
PY
python "$repo/.github/scripts/intake_lxml_native.py" --target linux-arm64 --output-dir "$evidence/lxml-intake" --qualify
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.2.0' --report "$evidence/runtime-install.json"
python -m pip check
export PILOT_PREFIX="$prefix" PILOT_CPYTHON_SOURCE="$work/src/Python-3.14.10"
unset SSL_CERT_FILE SSL_CERT_DIR
export XDG_CONFIG_HOME="$work/profile/config" XDG_DATA_HOME="$work/profile/data" XDG_CACHE_HOME="$work/profile/cache"
export QT_QPA_PLATFORM=xcb
python .github/scripts/probe_qt_cldr49_runtime.py \
  --xml "$work/src/cldr49-generator-input/cldr49.xml" --output "$evidence/qt-cldr49-runtime.json"
xvfb-run -a python .github/scripts/verify_linux_arm64_runtime_pilot.py --output-dir "$evidence"
xvfb-run -a python .github/scripts/verify_linux_x64_native_delta.py \
  --target linux-arm64 --prefix "$prefix" --output-dir "$evidence" --cffi
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
 'gcc':['gcc-13','--version'],'g++':['g++-13','--version'],'ld':['ld','--version'],
 'cmake':['cmake','--version'],'ninja':['ninja','--version']}.items()}}
Path('linux-arm64-pilot-evidence/build-provenance.json').write_text(json.dumps(summary,indent=2))
PY
echo 'Native Noble ARM64 runtime/framework pilot PASS; no application package produced.'
