#!/usr/bin/env bash
# Only the five controlled Jammy x64 runtime providers, before Python/Qt builds.
set -euo pipefail
repo=$(pwd)
work=${PILOT_WORK:?}
evidence=${PILOT_EVIDENCE:?}
prefix="$work/prefix"
test "$(uname -m)" = x86_64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 22.04
test "$(gcc -dumpversion | cut -d. -f1)" = 11
mkdir -p "$prefix"
logged() {
  local name=$1
  shift
  printf 'Native provider: %s\n' "$name"
  "$@" > "$evidence/$name.log" 2>&1 || { tail -n 80 "$evidence/$name.log"; return 1; }
}
cd "$work/src/zlib-1.4"
logged zlib-configure ./configure --prefix="$prefix" --libdir="$prefix/lib"
logged zlib-build make -j2
logged zlib-regressions make test
logged zlib-inflate-build make infcover
logged zlib-inflate-regressions ./infcover
logged zlib-install make install
cd "$work/src/xz-5.8.4"
logged xz-configure ./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-static \
  --disable-xz --disable-xzdec --disable-lzmadec --disable-lzmainfo --disable-scripts --disable-doc --disable-nls
logged xz-build make -j2
logged xz-regressions make check
logged xz-install make install
cd "$work/src/mpdecimal-4.0.1"
logged mpdecimal-configure ./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-cxx --disable-static --enable-shared --enable-pc
logged mpdecimal-build make -j2
logged mpdecimal-regressions make check_local
logged mpdecimal-install make install
cd "$work/src/sqlite-autoconf-3540100"
logged sqlite-configure ./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-static --disable-readline
logged sqlite-build make -j2
logged sqlite-install make install
cd "$work/src/libffi-3.8.0"
logged libffi-configure ./configure --prefix="$prefix" --libdir="$prefix/lib" --disable-static --disable-docs
logged libffi-build make -j2
logged libffi-install make install
cd "$repo"
gcc -std=c11 -I"$prefix/include" .github/scripts/native_provider_consumer.c \
  -L"$prefix/lib" -Wl,-rpath,"$prefix/lib" -lffi -lmpdec -lsqlite3 -llzma -lz \
  -o "$evidence/native-provider-consumer"
cp .github/scripts/native_provider_consumer.c "$evidence/"
"$evidence/native-provider-consumer" > "$evidence/native-provider-prerequisites.json"
ldd "$evidence/native-provider-consumer" > "$evidence/native-provider-consumer-ldd.txt"
python - "$evidence/native-provider-prerequisites.json" <<'PY'
import json, sys
from pathlib import Path
spec = json.loads(Path('.github/scripts/linux_x64_native_delta_sources.json').read_text())
actual = json.loads(Path(sys.argv[1]).read_text())
for name in ('sqlite', 'libmpdec', 'libffi', 'liblzma', 'zlib'):
    assert actual[name] == spec['expected'][name], (name, actual)
assert actual['mixed'] == 27.5 and actual['calls'] == 'SQL/codec/callback PASS'
print('Five native source providers and actual consumer prerequisites PASS:', actual)
PY
