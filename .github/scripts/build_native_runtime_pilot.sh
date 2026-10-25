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
work, evidence = Path(os.environ['PILOT_WORK']), Path(os.environ['PILOT_EVIDENCE'])
shutil.copy2(manifest, evidence / manifest.name)
patch = Path(spec['cpython_patch']['path'])
assert hashlib.sha256(patch.read_bytes()).hexdigest() == spec['cpython_patch']['sha256']
shutil.copy2(patch, evidence / patch.name)
def fetch(item):
    dest = (work if item['name'].endswith('.7z') else evidence / 'sources') / item['name']
    with urllib.request.urlopen(item['url'], timeout=180) as src, dest.open('wb') as out:
        shutil.copyfileobj(src, out)
    with dest.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == item['sha256'], item['name']
    if dest.suffix == '.7z':
        subprocess.run(['7z', 'x', '-y', f'-o{work / "src"}', str(dest)], check=True, stdout=subprocess.DEVNULL)
    else:
        with tarfile.open(dest) as archive:
            archive.extractall(work / 'src', filter='data')
    print('Verified official source/tool:', item['name'], flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(fetch, spec['sources']))
for sdk_source in (spec['cxx_link_sdk']['source'], spec['extractor']['source']):
    sdk_archive = evidence / 'sources' / sdk_source['name']
    with urllib.request.urlopen(sdk_source['url'], timeout=180) as src, sdk_archive.open('wb') as out:
        shutil.copyfileobj(src, out)
    with sdk_archive.open('rb') as stream:
        assert hashlib.file_digest(stream, 'sha256').hexdigest() == sdk_source['sha256']
    print('Verified original build-tool source:', sdk_source['name'], flush=True)
source = work / 'src/Python-3.14.9'
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['base_sha256']
subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch.resolve())], cwd=source, check=True)
for name, hashes in spec['cpython_patch']['files'].items():
    assert hashlib.sha256((source / name).read_bytes()).hexdigest() == hashes['patched_sha256']
for directory in (work / 'src').iterdir():
    target = evidence / 'legal' / directory.name
    target.mkdir()
    for candidate in directory.iterdir():
        if candidate.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE')):
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
./Configure linux-x86_64 shared --prefix="$ssl_prefix" --libdir=lib --openssldir="$openssl_dir"
make -j2
make test TESTS='test_evp test_x509 test_verify test_ssl_new'
make install_sw
cp configdata.pm "$evidence/openssl-configdata.pm"

cd "$work/src/Python-3.14.9"
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
make install
cp config.log "$evidence/cpython-config.log"
cp "$evidence/native_runtime_pilot_sources.json" "$prefix/python/PROJECT_MODIFIED_RUNTIME.json"
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
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials=='))+'\n')
PY
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.1.1' --report "$evidence/runtime-install.json"
python -m pip check
export PILOT_PREFIX="$prefix" PILOT_CPYTHON_SOURCE="$work/src/Python-3.14.9"
unset SSL_CERT_FILE SSL_CERT_DIR
export XDG_CONFIG_HOME="$work/profile/config" XDG_DATA_HOME="$work/profile/data" XDG_CACHE_HOME="$work/profile/cache"
export QT_QPA_PLATFORM=xcb
xvfb-run -a python .github/scripts/verify_native_runtime_pilot.py --output-dir "$evidence"
python main.py cli audit --help > "$evidence/cli-smoke.txt"
xvfb-run -a python -m pytest tests/test_cli_headless.py -q > "$evidence/project-cli-regressions.log" 2>&1
python -m compileall -q playstore_app_audit
python - <<'PY'
import json, os, platform, subprocess, sys
from pathlib import Path
summary = {'source_sha':os.environ['GITHUB_SHA'],'scope':'non-release native runtime/framework pilot',
 'runtime_identity':'project-modified CPython 3.14.9, not unchanged official binary',
 'python':sys.version,'architecture':platform.machine(),'prefix':os.environ['PILOT_PREFIX'],
 'gil_disabled':__import__('sysconfig').get_config_var('Py_GIL_DISABLED'),
 'tools':{name:subprocess.run(command,capture_output=True,text=True,check=True).stdout for name,command in {
 'gcc':['gcc','--version'],'cmake':['cmake','--version'],'ninja':['ninja','--version']}.items()}}
Path('pilot-evidence/build-provenance.json').write_text(json.dumps(summary,indent=2))
PY
echo 'Native runtime/framework pilot PASS; no application package produced.'
