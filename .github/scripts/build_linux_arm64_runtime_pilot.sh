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
import concurrent.futures, hashlib, json, os, shutil, subprocess, sys
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
    unpack(archive, work / 'src')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(stage, runtime_sources(spec, base)))
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
PY
prefix="$work/prefix"
ssl_prefix="$prefix/openssl"
mkdir -p "$prefix"
export CMAKE_BUILD_PARALLEL_LEVEL=2
export LD_LIBRARY_PATH="$ssl_prefix/lib:$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
export CMAKE_PREFIX_PATH="$prefix:$ssl_prefix"

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
  LDFLAGS="-Wl,-rpath,$prefix/python/lib" \
  --with-pkg-config=yes
make -j2
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -c "import _ssl, _hashlib, ssl, sysconfig; assert ssl.OPENSSL_VERSION.startswith('OpenSSL 4.0.3 '); assert not sysconfig.get_config_var('Py_GIL_DISABLED'); print('Built _ssl/_hashlib import:', ssl.OPENSSL_VERSION)"
LD_LIBRARY_PATH="$PWD:$LD_LIBRARY_PATH" ./python -m test -j2 --junit-xml "$evidence/cpython-regressions.xml" test_ssl test_hashlib test_hmac > "$evidence/cpython-regressions.log" 2>&1
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
# Do not let setup-python's same-SONAME libpython or CMake roots satisfy this build.
export LD_LIBRARY_PATH="$prefix/python/lib:$ssl_prefix/lib:$prefix/lib"
unset PYTHONHOME Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR
export Python_ROOT_DIR="$prefix/python" Python3_ROOT_DIR="$prefix/python"
export PKG_CONFIG_PATH="$prefix/python/lib/pkgconfig:$prefix/lib/pkgconfig:$ssl_prefix/lib/pkgconfig"
"$prefix/python/bin/python3.14" -m venv "$work/venv"
export PATH="$work/venv/bin:$PATH"
python -m pip install 'pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70'
python -m pip install 'setuptools==84.2.1' 'wheel==0.48.0' 'cmake==4.4.4' 'ninja==1.13.2' 'packaging==26.3' --report "$evidence/build-tools-install.json"

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

mkdir "$work/qt-build"
cd "$work/qt-build"
"$work/src/qtbase-everywhere-src-6.12.0/configure" -prefix "$prefix/qt" \
  -release -opensource -confirm-license -nomake tests -nomake examples \
  -openssl-linked -system-libpng -system-pcre -no-feature-openssl-runtime \
  -- -DOPENSSL_ROOT_DIR="$ssl_prefix" -DCMAKE_PREFIX_PATH="$prefix;$ssl_prefix" \
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
python setup.py install --ignore-git --qtpaths="$prefix/qt/bin/qtpaths6" \
  --parallel=2 --limited-api=yes --module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test \
  --no-qt-tools
cd "$repo"
# libclang is a generator prerequisite, never an application runtime search path.
export LD_LIBRARY_PATH="$prefix/qt/lib:$prefix/python/lib:$ssl_prefix/lib:$prefix/lib"
unset LLVM_INSTALL_DIR
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('linux-arm64-pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials=='))+'\n')
PY
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.1.1' --report "$evidence/runtime-install.json"
python -m pip check
export PILOT_PREFIX="$prefix" PILOT_CPYTHON_SOURCE="$work/src/Python-3.14.10"
unset SSL_CERT_FILE SSL_CERT_DIR
export XDG_CONFIG_HOME="$work/profile/config" XDG_DATA_HOME="$work/profile/data" XDG_CACHE_HOME="$work/profile/cache"
export QT_QPA_PLATFORM=xcb
xvfb-run -a python .github/scripts/verify_linux_arm64_runtime_pilot.py --output-dir "$evidence"
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
