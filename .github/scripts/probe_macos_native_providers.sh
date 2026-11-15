#!/usr/bin/env bash
# Five native source providers and cffi only; never build Python/Qt or a candidate.
set -euo pipefail
repo=$(pwd)
work=${1:?new isolated work directory required}
evidence="$repo/toolchain-delta-evidence"
test "$(uname -s)" = Darwin
test ! -e "$work"
case "$EXPECTED_ARCH" in
  arm64) test "$(uname -m)" = arm64; deployment=11.0; cpu=arm64 ;;
  x64) test "$(uname -m)" = x86_64; deployment=10.15; cpu=x86_64 ;;
  *) exit 1 ;;
esac
test "$(xcodebuild -version | head -n1)" = 'Xcode 26.6'
translated=$(sysctl -in sysctl.proc_translated 2>/dev/null || true)
test "$translated" != 1
export MACOSX_DEPLOYMENT_TARGET="$deployment" ARCHFLAGS="-arch $cpu"
export CC="$(xcrun --find clang)" CXX="$(xcrun --find clang++)"
export CFLAGS="-arch $cpu -mmacosx-version-min=$deployment" CXXFLAGS="$CFLAGS"
export LDFLAGS="-arch $cpu -mmacosx-version-min=$deployment"
export PILOT_WORK="$work" PILOT_EVIDENCE="$evidence"
mkdir -p "$work/src" "$evidence/sources"
python - <<'PY'
import concurrent.futures, hashlib, json, os, shutil, sys, tarfile
from pathlib import Path
sys.path.insert(0, '.github/scripts')
from probe_qt_text_providers import checked_source
spec_path = Path('.github/scripts/linux_x64_native_delta_sources.json')
spec = json.loads(spec_path.read_text())
contract = json.loads(Path('.github/scripts/macos_native_provider_sources.json').read_text())
projection = contract['native_source_projection']
selected = {key: spec[key] for key in projection['keys']}
assert hashlib.sha256(json.dumps(selected,sort_keys=True,separators=(',',':')).encode()).hexdigest() == projection['canonical_sha256']
root = Path(os.environ['PILOT_EVIDENCE'])
shutil.copy2('.github/scripts/macos_native_provider_sources.json', root)
work = Path(os.environ['PILOT_WORK'])
shutil.copy2(spec_path, root)
def stage(item):
    archive = checked_source(item, root / 'sources')
    with tarfile.open(archive) as bundle:
        bundle.extractall(work / 'src', filter='data')
    source = work / 'src' / item['directory']
    legal = root / 'legal' / source.name
    legal.mkdir(parents=True)
    for path in source.iterdir():
        if path.is_file() and path.name.upper().startswith(('LICENSE','COPYING','COPYRIGHT','NOTICE','AUTHORS')):
            shutil.copy2(path, legal / path.name)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    list(pool.map(stage, spec['sources']))
notice = checked_source(spec['sqlite_legal_notice'], root / 'legal/sqlite-autoconf-3540100')
assert notice.is_file()
PY
prefix="$work/prefix"
export DYLD_LIBRARY_PATH="$prefix/lib"
export PKG_CONFIG_PATH="$prefix/lib/pkgconfig" PKG_CONFIG_LIBDIR="$prefix/lib/pkgconfig"
logged() { local name=$1; shift; "$@" > "$evidence/$name.log" 2>&1 || { tail -n 60 "$evidence/$name.log"; return 1; }; }
cd "$work/src/zlib-1.4"
logged zlib-configure ./configure --prefix="$prefix"
logged zlib-build make -j2
logged zlib-tests make test
logged zlib-install make install
cd "$work/src/xz-5.8.4"
logged xz-configure ./configure --prefix="$prefix" --disable-static --disable-xz --disable-xzdec --disable-lzmadec --disable-lzmainfo --disable-scripts --disable-doc --disable-nls
logged xz-build make -j2
logged xz-tests make check
logged xz-install make install
cd "$work/src/mpdecimal-4.0.1"
logged mpdecimal-configure ./configure --prefix="$prefix" --disable-cxx --disable-static --enable-shared --enable-pc
logged mpdecimal-build make -j2
logged mpdecimal-tests make check_local
logged mpdecimal-install make install
cd "$work/src/sqlite-autoconf-3540100"
logged sqlite-configure ./configure --prefix="$prefix" --disable-static --disable-readline --column-metadata
logged sqlite-build make -j2
logged sqlite-install make install
cd "$work/src/libffi-3.8.0"
logged libffi-configure ./configure --prefix="$prefix" --disable-static --disable-docs
logged libffi-build make -j2
logged libffi-install make install
cd "$repo"
"$CC" -std=c11 -arch "$cpu" -mmacosx-version-min="$deployment" -I"$prefix/include" \
  .github/scripts/native_provider_consumer.c -L"$prefix/lib" -Wl,-rpath,"$prefix/lib" \
  -lffi -lmpdec -lsqlite3 -llzma -lz -o "$evidence/native-provider-consumer"
cp .github/scripts/native_provider_consumer.c "$evidence/"
"$evidence/native-provider-consumer" | tee "$evidence/native-provider-prerequisites.json"
python -m pip install -r .github/scripts/source_build_requirements.txt -c .github/scripts/source_build_constraints.txt 'pycparser==3.12' 'pytest==9.2.0' --report "$evidence/provider-build-worker-install.json"
mkdir "$evidence/cffi-wheel"
python -m pip wheel --no-build-isolation --no-deps "$work/src/cffi-2.1.1" -w "$evidence/cffi-wheel" > "$evidence/cffi-build.log" 2>&1
python -m pip install --no-index --no-deps --force-reinstall "$evidence"/cffi-wheel/cffi-*.whl
python -m pytest "$work/src/cffi-2.1.1/src/c/test_c.py" -q --junitxml="$evidence/cffi-tests.xml" > "$evidence/cffi-tests.log" 2>&1
python - <<'PY'
import hashlib, json, os, platform, shutil, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, '.github/scripts')
if os.environ['EXPECTED_ARCH'] == 'arm64':
    from probe_macos_arm64_runtime import macho
else:
    from probe_macos_x64_runtime import macho
import _cffi_backend, cffi
root = Path(os.environ['PILOT_EVIDENCE'])
prefix = Path(os.environ['PILOT_WORK']) / 'prefix'
spec = json.loads(Path('.github/scripts/linux_x64_native_delta_sources.json').read_text())
actual = json.loads((root / 'native-provider-prerequisites.json').read_text())
for name in ['sqlite','libmpdec','libffi','liblzma','zlib']:
    assert actual[name] == spec['expected'][name], actual
assert actual['mixed'] == 27.5 and actual['sqlite_column_metadata'] and actual['calls'] == 'SQL/codec/callback PASS'
assert cffi.__version__ == _cffi_backend.__version__ == '2.1.1'
cases = list(ET.parse(root / 'cffi-tests.xml').getroot().iter('testcase'))
assert cases and not any(c.find(t) is not None for c in cases for t in ['error','failure'])
executed = [c for c in cases if c.find('skipped') is None and c.get('status') != 'notrun']
assert any(c.get('name') == 'test_call_function_9' for c in executed)
assert any('callback' in c.get('name','') for c in executed)
paths = [p for p in (prefix / 'lib').glob('*.dylib') if not p.is_symlink()]
paths += [root / 'native-provider-consumer', Path(_cffi_backend.__file__)]
images = []
retained = root / 'native-provider-binaries'
retained.mkdir()
for path in paths:
    row = macho(path, target=True, output=root)
    assert all((tuple(map(int,v.split('.')))+(0,0,0))[:3] <= (tuple(map(int,os.environ['MACOSX_DEPLOYMENT_TARGET'].split('.')))+(0,0,0))[:3] for v in row['minimum_os'])
    shutil.copy2(path, retained / path.name)
    row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    images.append(row)
imports = subprocess.check_output(['otool','-L',_cffi_backend.__file__],text=True)
assert str(prefix / 'lib/libffi') in imports, imports
result = {'source_sha':os.environ['GITHUB_SHA'],'machine':platform.machine(),'deployment':os.environ['MACOSX_DEPLOYMENT_TARGET'],
          'providers':actual,'images':images,'cffi_suite':'Unmodified complete upstream src/c/test_c.py native backend/FFI cases','cffi_cases':len(cases),'cffi_passed':len(executed),'cffi_skipped':sum(c.find('skipped') is not None for c in cases),
          'cffi_linkage':imports,'patches':[], 'scope':'Native source providers/cffi only; no Python/Qt/CA/package adoption or older-OS execution claim', 'result':'PASS'}
(root / 'macos-native-providers.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY
