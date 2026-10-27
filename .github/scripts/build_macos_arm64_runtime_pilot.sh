#!/usr/bin/env bash
# One controlled Apple-silicon source prefix. Never an application candidate.
set -euo pipefail
repo=$(pwd)
work=${1:?Pass the qualified isolated work directory}
evidence="$repo/macos-arm64-pilot-evidence"
test "$(uname -m)" = arm64
test -d "$work"
test ! -e "$work/prefix/python"
export PILOT_WORK="$work" PILOT_EVIDENCE="$evidence"
python - <<'PY'
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path('.github/scripts').resolve()))
from probe_macos_arm64_runtime import contract
arm, base = contract()
work, evidence = Path(os.environ['PILOT_WORK']), Path(os.environ['PILOT_EVIDENCE'])
report = json.loads((evidence / 'prerequisites.json').read_text())
assert report['source_sha'] == os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA']
assert report['result'] == 'PASS native macOS ARM64 prerequisites; no CPython/Qt runtime compiled'
assert report['machine'] == 'arm64' and not report['rosetta'] and not report['gil_disabled']
assert report['parser']['execution'].find('22.1.8') >= 0 and report['source_perl']['tests'] > 0
assert report['bootstrap_trust']['result'] == 'default-trust authenticated handshake PASS'
assert report['compression']['result'] == '5.8.4 1.5.7 codec roundtrips PASS'
assert all(report['compression']['python_module_configuration'][name] == 'yes' for name in ('_LZMA', '_ZSTD'))
native = json.loads((evidence / 'native-tls-prerequisites.json').read_text())
assert native['backend'] == 'securetransport' and all(c['result'] == 'PASS' for c in native['cases'])
source = work / 'src/Python-3.14.10'
for name, hashes in base['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256'], name
for name, digest in base['security_files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == digest, name
assert hashlib.sha256((work / 'certifi-cacert.pem').read_bytes()).hexdigest() == report['private_ca_bundle']['pem_sha256']
print('Exact-source/native/trust/parser/security prerequisites PASS before source runtime rebuild')
PY
export CC="$(xcrun --find clang)" CXX="$(xcrun --find clang++)"
export SDKROOT="$(xcrun --sdk macosx --show-sdk-path)"
export PATH="$work/host-tools/bin:$work/host-perl/bin:$PATH"
test "$(xcodebuild -version | head -n 1)" = 'Xcode 26.6'
unset DYLD_LIBRARY_PATH DYLD_FRAMEWORK_PATH PYTHONHOME PYTHONPATH
prefix="$work/prefix"
ssl_prefix="$prefix/openssl"
mkdir -p "$evidence/legal" "$prefix/trust"
cp "$work/certifi-cacert.pem" "$prefix/trust/cert.pem"
python - <<'PY'
import concurrent.futures, hashlib, os, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path('.github/scripts').resolve()))
from probe_macos_arm64_runtime import contract, fetch, unpack
arm, base = contract()
work, evidence = Path(os.environ['PILOT_WORK']), Path(os.environ['PILOT_EVIDENCE'])
items = [*base['sources'][1:7], arm['zlib_source'], arm['certifi_source'], arm['cryptography_source'], arm['host_extractor']['source']]
def stage(item):
    archive = fetch(item, evidence / 'sources')
    unpack(archive, work / 'src')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(stage, items))
shutil.copy2(work / arm['certifi_wheel']['name'], evidence / 'sources' / arm['certifi_wheel']['name'])
assert (work / 'src/certifi-2026.10.23/certifi/cacert.pem').read_bytes() == (work / 'certifi-cacert.pem').read_bytes()
for directory in [*(work / 'src').iterdir(), work / 'perl-5.44.0', work / 'extractor']:
    if not directory.is_dir(): continue
    target = evidence / 'legal' / directory.name
    target.mkdir(exist_ok=True)
    for path in directory.iterdir():
        if path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'ARTISTIC')):
            if path.is_dir(): shutil.copytree(path, target / path.name, dirs_exist_ok=True)
            else: shutil.copy2(path, target / path.name)
PY
export MACOSX_DEPLOYMENT_TARGET=11.0
export CFLAGS='-arch arm64' CXXFLAGS='-arch arm64' ARCHFLAGS='-arch arm64'
export CPPFLAGS="-I$prefix/include -isysroot $SDKROOT"
export LDFLAGS="-arch arm64 -L$prefix/lib -Wl,-rpath,$prefix/lib -Wl,-rpath,$prefix/python/lib"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
export CMAKE_PREFIX_PATH="$prefix:$ssl_prefix"
export CMAKE_BUILD_PARALLEL_LEVEL=2
cd "$work/src/openssl-4.0.3"
"$work/host-perl/bin/perl" Configure darwin64-arm64-cc shared \
  --prefix="$ssl_prefix" --libdir=lib --openssldir="$prefix/trust"
make -j2
make test TESTS='test_evp test_x509 test_verify test_ssl_new' > "$evidence/openssl-regressions.log" 2>&1
make install_sw
cp configdata.pm "$evidence/openssl-configdata.pm"
# CMake owns install rpaths; inherited linker rpaths otherwise make Apple's
# install_name_tool reject the install edit and leave build-tree Qt loaded.
python_link_flags="$LDFLAGS"
unset LDFLAGS

# Required compression source is already qualified on Windows; keep libpng/Qt coherent.
cmake -S "$work/src/zlib-1.3.2" -B "$work/zlib-build" -GNinja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
  -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  -DCMAKE_INSTALL_NAME_DIR=@rpath -DCMAKE_INSTALL_RPATH="$prefix/lib" \
  '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local' -DZLIB_BUILD_TESTING=ON
cmake --build "$work/zlib-build"
ctest --test-dir "$work/zlib-build" --output-on-failure > "$evidence/zlib-regressions.log" 2>&1
cmake --install "$work/zlib-build"

mkdir "$work/python-build"
cd "$work/python-build"
export LDFLAGS="$python_link_flags"
"$work/src/Python-3.14.10/configure" --prefix="$prefix/python" --enable-shared \
  --with-openssl="$ssl_prefix" --with-openssl-rpath=auto --with-ensurepip=install --with-pkg-config=yes
make -j2
# Upstream uses .exe on case-insensitive macOS to avoid the Python/ directory.
test -f ./python.exe && test -x ./python.exe
DYLD_LIBRARY_PATH="$PWD:$ssl_prefix/lib:$prefix/lib" ./python.exe -c "import ssl,_ssl,_hashlib,ctypes,sqlite3,zlib,lzma,sysconfig; from compression import zstd; assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 '); assert not sysconfig.get_config_var('Py_GIL_DISABLED'); assert zlib.ZLIB_RUNTIME_VERSION=='1.3.2'; assert lzma.decompress(lzma.compress(b'native'))==zstd.decompress(zstd.compress(b'native'))==b'native'; print('Built native SSL/hash/ctypes/sqlite/zlib/lzma/zstd PASS',ssl.OPENSSL_VERSION)"
DYLD_LIBRARY_PATH="$PWD:$ssl_prefix/lib:$prefix/lib" ./python.exe -m test -j2 --junit-xml "$evidence/cpython-regressions.xml" test_ssl test_hashlib test_hmac > "$evidence/cpython-regressions.log" 2>&1
DYLD_LIBRARY_PATH="$PWD:$ssl_prefix/lib:$prefix/lib" ./python.exe -m unittest -v test.test_tarfile.TestExtractionFilters.test_link_at_destination > "$evidence/tarfile-security-regression.log" 2>&1
DYLD_LIBRARY_PATH="$PWD:$ssl_prefix/lib:$prefix/lib" ./python.exe -m test -j2 --junit-xml "$evidence/cpython-codec-regressions.xml" test_lzma test_zstd > "$evidence/cpython-codec-regressions.log" 2>&1
PYTHONPATH="$repo/.github/scripts" python - "$evidence" <<'PY'
import sys
from pathlib import Path
from verify_native_runtime_pilot import executed_cpython_security, executed_upstream_suites
evidence = Path(sys.argv[1])
print('Executed upstream cases:', executed_upstream_suites(evidence / 'cpython-regressions.xml'))
print('Executed upstream security:', executed_cpython_security(evidence / 'cpython-regressions.xml', evidence / 'tarfile-security-regression.log'))
from verify_macos_arm64_runtime_pilot import executed_codec_suites
print('Executed native codec suites:', executed_codec_suites(evidence / 'cpython-codec-regressions.xml'))
PY
make install
cp config.log "$evidence/cpython-config.log"
cp Makefile "$evidence/cpython-Makefile"
cp "$evidence/macos_arm64_runtime_pilot_sources.json" "$prefix/python/PROJECT_MODIFIED_RUNTIME.json"
cp "$evidence/native_runtime_pilot_sources.json" "$prefix/python/native_runtime_pilot_sources.json"
unset LDFLAGS
unset Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR PYTHON_ROOT_DIR PYTHON2_ROOT_DIR PYTHON3_ROOT_DIR
export Python_ROOT_DIR="$prefix/python" Python3_ROOT_DIR="$prefix/python"
export PKG_CONFIG_PATH="$prefix/python/lib/pkgconfig:$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="$PKG_CONFIG_PATH"
"$prefix/python/bin/python3.14" -m venv "$work/venv"
export PATH="$work/venv/bin:$PATH"
python -m pip install 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
python -m pip install 'setuptools==84.2.1' 'wheel==0.48.0' 'cmake==4.4.4' 'ninja==1.13.2' 'packaging==26.3' --report "$evidence/build-tools-install.json"
cd "$repo"
# Default verification uses the configured private PEM, not an env/cafile fallback.
python - <<'PY'
import os, ssl, sys
from pathlib import Path
sys.path.insert(0, str(Path('.github/scripts').resolve()))
from verify_native_runtime_pilot import default_trust_handshake
assert not os.environ.get('SSL_CERT_FILE') and not os.environ.get('SSL_CERT_DIR')
assert str(Path(ssl.get_default_verify_paths().cafile).resolve()) == str(Path(os.environ['PILOT_WORK']) / 'prefix/trust/cert.pem')
print('Modified Python private PEM ordinary default trust:', default_trust_handshake())
PY
for component in png pcre; do
  if [ "$component" = png ]; then
    source="$work/src/libpng-1.6.59"
    extra=(-DPNG_TESTS=ON -DPNG_SHARED=ON -DPNG_STATIC=OFF)
  else
    source="$work/src/pcre2-10.49"
    extra=(-DBUILD_SHARED_LIBS=ON -DPCRE2_BUILD_PCRE2_16=ON -DPCRE2_SUPPORT_JIT=ON -DPCRE2_BUILD_TESTS=ON)
  fi
  cmake -S "$source" -B "$work/$component-build" -GNinja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=11.0 -DCMAKE_OSX_SYSROOT="$SDKROOT" \
    -DCMAKE_INSTALL_NAME_DIR=@rpath -DCMAKE_INSTALL_RPATH="$prefix/lib" \
    '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local' -DZLIB_ROOT="$prefix" "${extra[@]}"
  cmake --build "$work/$component-build"
  if [ "$component" = png ]; then label=libpng; else label=pcre2; fi
  ctest --test-dir "$work/$component-build" --output-on-failure > "$evidence/$label-regressions.log" 2>&1
  cmake --install "$work/$component-build"
done

export MACOSX_DEPLOYMENT_TARGET=14.4
mkdir "$work/qt-build"
cd "$work/qt-build"
"$work/src/qtbase-everywhere-src-6.12.0/configure" -prefix "$prefix/qt" \
  -release -opensource -confirm-license -nomake tests -nomake examples \
  -openssl-linked -securetransport -system-libpng -system-pcre -system-zlib -no-feature-openssl-runtime \
  -- -DOPENSSL_ROOT_DIR="$ssl_prefix" -DZLIB_ROOT="$prefix" -DCMAKE_PREFIX_PATH="$prefix;$ssl_prefix" \
  -DCMAKE_OSX_ARCHITECTURES:STRING=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET:STRING=14.4 -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local' -DCMAKE_INSTALL_RPATH="$prefix/qt/lib;$prefix/lib;$ssl_prefix/lib"
python - <<'PY'
import os
from pathlib import Path
lines = Path('CMakeCache.txt').read_text().splitlines()
for name in ('OPENSSL_SSL_LIBRARY:FILEPATH=', 'OPENSSL_CRYPTO_LIBRARY:FILEPATH='):
    value = next(line.split('=', 1)[1] for line in lines if line.startswith(name))
    assert Path(value).resolve().is_relative_to(Path(os.environ['PILOT_WORK']) / 'prefix/openssl'), value
assert any(line == 'CMAKE_OSX_ARCHITECTURES:STRING=arm64' for line in lines)
assert any(line == 'CMAKE_OSX_DEPLOYMENT_TARGET:STRING=14.4' for line in lines)
print('Qt explicit native target/framework14.4/private OpenSSL4 linkage PASS')
PY
cmake --build . --parallel 2
cmake --install .
cp CMakeCache.txt "$evidence/qtbase-CMakeCache.txt"
cp config.summary "$evidence/qtbase-config.summary"
# Resolve the installed framework, not a still-loadable build-tree framework,
# before spending time on Svg and the binding generator/compiler.
PYTHONPATH="$repo/.github/scripts" python - <<'PY'
import os
from pathlib import Path
from probe_macos_arm64_runtime import installed_qt
prefix = Path(os.environ['PILOT_WORK']) / 'prefix'
print(installed_qt(prefix / 'qt', Path(os.environ['PILOT_EVIDENCE']))['result'])
PY
mkdir "$work/qt-header-probe"
cat > "$work/qt-header-probe/CMakeLists.txt" <<'CMAKE'
cmake_minimum_required(VERSION 3.21)
project(NativeQtHeaderProbe LANGUAGES CXX)
find_package(Qt6 6.12.0 EXACT COMPONENTS Gui REQUIRED)
add_executable(native-qt-header main.cpp)
target_link_libraries(native-qt-header PRIVATE Qt6::Gui Qt6::GuiPrivate)
CMAKE
cat > "$work/qt-header-probe/main.cpp" <<'CPP'
#include <qrhi.h>
#include <QtCore/QLibraryInfo>
#include <QtCore/qglobal.h>
#include <cstdio>
int main(){QRhi *rhi=nullptr;puts(qVersion());puts(QLibraryInfo::path(QLibraryInfo::PrefixPath).toUtf8().constData());return rhi?1:0;}
CPP
cmake -S "$work/qt-header-probe" -B "$work/qt-header-probe/build" -GNinja \
  -DCMAKE_PREFIX_PATH="$prefix/qt;$prefix;$ssl_prefix" -DCMAKE_OSX_ARCHITECTURES=arm64 \
  -DCMAKE_OSX_DEPLOYMENT_TARGET=14.4 -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local'
cmake --build "$work/qt-header-probe/build"
"$work/qt-header-probe/build/native-qt-header" > "$evidence/qt-header-probe.txt"
test "$(tail -n 1 "$evidence/qt-header-probe.txt")" = "$prefix/qt"
mkdir "$work/qtsvg-build"
cd "$work/qtsvg-build"
"$prefix/qt/bin/qt-configure-module" "$work/src/qtsvg-everywhere-src-6.12.0" \
  -- -DZLIB_ROOT="$prefix" -DCMAKE_PREFIX_PATH="$prefix;$prefix/qt;$ssl_prefix" \
  -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=14.4 -DCMAKE_OSX_SYSROOT="$SDKROOT" \
  '-DCMAKE_IGNORE_PREFIX_PATH=/opt/homebrew;/usr/local' -DCMAKE_INSTALL_RPATH="$prefix/qt/lib;$prefix/lib;$ssl_prefix/lib"
cmake --build . --parallel 2
cmake --install .
export LLVM_INSTALL_DIR="$work/src/libclang"
export PATH="$prefix/qt/bin:$PATH"
cd "$work/src/pyside-setup-everywhere-src-6.12.0"
python setup.py install --ignore-git --qtpaths="$prefix/qt/bin/qtpaths6" \
  --parallel=2 --limited-api=yes --module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test \
  --no-qt-tools --macos-arch=arm64 --macos-deployment-target=14.4 --macos-sysroot="$SDKROOT" --rpath="$prefix/qt/lib"
unset LLVM_INSTALL_DIR
cd "$repo"
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('macos-arm64-pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials==')) + '\n')
PY
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.1.1' --report "$evidence/runtime-install.json"
python -m pip check
export PILOT_PREFIX="$prefix" QT_QPA_PLATFORM=cocoa QT_PLUGIN_PATH="$prefix/qt/plugins"
unset SSL_CERT_FILE SSL_CERT_DIR DYLD_LIBRARY_PATH DYLD_FRAMEWORK_PATH
python .github/scripts/verify_macos_arm64_runtime_pilot.py --output-dir "$evidence"
(
  cd "$work/profile"
  test -f PlayStoreAppAudit.portable
  python "$repo/main.py" cli audit --help > "$evidence/cli-smoke.txt"
  PYTHONPATH="$repo" python -m pytest "$repo/tests/test_cli_headless.py" -q > "$evidence/project-cli-regressions.log" 2>&1
)
python -m compileall -q playstore_app_audit
python - <<'PY'
import json, os, platform, subprocess, sys, sysconfig
from pathlib import Path
report = {'source_sha': os.environ['GITHUB_SHA'], 'scope': 'project-modified native ARM64 runtime/framework diagnostic; not a final candidate', 'python': sys.version, 'machine': platform.machine(), 'gil_disabled': sysconfig.get_config_var('Py_GIL_DISABLED'), 'prefix': os.environ['PILOT_PREFIX'], 'sdk': os.environ['SDKROOT'], 'tools': {name: subprocess.check_output(argv, text=True) for name, argv in {'xcode': ['xcodebuild', '-version'], 'clang': ['xcrun', 'clang', '--version'], 'cmake': ['cmake', '--version'], 'ninja': ['ninja', '--version']}.items()}}
Path('macos-arm64-pilot-evidence/build-provenance.json').write_text(json.dumps(report, indent=2))
PY
echo 'Native macOS ARM64 controlled runtime-framework pilot PASS; no application candidate produced.'
