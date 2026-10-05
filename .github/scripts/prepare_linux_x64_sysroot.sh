#!/usr/bin/env bash
# Compile natively on Ubuntu 24.04, targeting the supported Ubuntu 22 x64 ABI.
set -euo pipefail
test "$(uname -m)" = x86_64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 24.04
mkdir -p linux-diagnostics
# Qt's deployment scanner walks the project directory. Keep the downloaded
# interpreter (including intentionally non-UTF-8 CPython fixtures) outside it.
compat_root="$RUNNER_TEMP/linux-compat-build"
mkdir "$compat_root"
resolved_python="$(python -c 'import platform, sys; assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == "final"; print(platform.python_version())')"
# Development tracks stable 3.14; the compatibility distribution must use
# the identical resolved full patch. Future release freezes pin it upstream.
python .github/scripts/download_linux_compat_python.py \
  --version "$resolved_python" --output-dir "$compat_root"
cp "$compat_root/python-distribution.json" linux-diagnostics/
mkdir "$compat_root/python-installer"
tar -xzf "$compat_root/python.tar.gz" -C "$compat_root/python-installer"
# The upstream installer replaces this patch's distribution in the ephemeral
# runner toolcache. Its patch stays identical to setup-python's resolved patch.
(cd "$compat_root/python-installer"; bash setup.sh)
test "$(python -c 'import platform; print(platform.python_version())')" = "$resolved_python"

docker pull ubuntu:22.04
docker image inspect ubuntu:22.04 --format '{{json .RepoDigests}}' > linux-diagnostics/sysroot-image.json
docker run --rm -v "$compat_root:/out" ubuntu:22.04 bash -euo pipefail -c '
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    libc6-dev linux-libc-dev libssl-dev libsqlite3-dev uuid-dev libffi-dev \
    libbz2-dev liblzma-dev zlib1g-dev libcrypt-dev
  # USN-8847-1: the target OpenSSL integration must include the vendor fix.
  ssl_package_version=$(dpkg-query -W -f="\${Version}" libssl3)
  dpkg --compare-versions "$ssl_package_version" ge 3.0.2-0ubuntu1.30
  mkdir -p /out/sysroot/usr/lib /out/sysroot/lib /out/sysroot/lib64
  cp -a /usr/include /out/sysroot/usr/
  cp -a /usr/lib/x86_64-linux-gnu /out/sysroot/usr/lib/
  cp -a /lib/x86_64-linux-gnu /out/sysroot/lib/
  cp -a /lib64/. /out/sysroot/lib64/
  dpkg-query -W > /out/sysroot-packages.txt
  mkdir /out/runtime
  for stem in libssl libcrypto libsqlite3 libuuid libffi libbz2 liblzma libz libcrypt; do
    for lib in /usr/lib/x86_64-linux-gnu/$stem.so.*; do
      test -e "$lib"
      cp -L "$lib" /out/runtime/
    done
  done
'
cp "$compat_root/sysroot-packages.txt" linux-diagnostics/
# Never add the complete sysroot to LD_LIBRARY_PATH: the compiler and all build
# tools must use the host's libc. Only Python's compatible non-libc dependencies
# are selected here, before Nuitka collects standalone runtime dependencies.
compat_libs="$compat_root/runtime"
export LD_LIBRARY_PATH="$compat_libs:${LD_LIBRARY_PATH:-}"
sysroot="$compat_root/sysroot"
cat > "$compat_root/probe.c" <<'C'
#define _GNU_SOURCE
#include <math.h>
#include <stdlib.h>
int main(int argc, char **argv) {
    return argc != 2 || fmod((double)strtol(argv[1], 0, 10), 2.0) != 1.0;
}
C
gcc --version | tee linux-diagnostics/compiler.txt
gcc --sysroot="$sysroot" -L"$sysroot/usr/lib/x86_64-linux-gnu" \
  -L"$sysroot/lib/x86_64-linux-gnu" -fno-builtin-fmod \
  "$compat_root/probe.c" -lm -o "$compat_root/probe"
readelf --version-info "$compat_root/probe" > linux-diagnostics/sysroot-probe-versions.txt
docker run --rm -v "$compat_root/probe:/probe:ro" ubuntu:22.04 /probe 5
{
  echo "CCFLAGS=--sysroot=$sysroot"
  echo "LDFLAGS=--sysroot=$sysroot -L$sysroot/usr/lib/x86_64-linux-gnu -L$sysroot/lib/x86_64-linux-gnu -Wl,-rpath-link,$sysroot/usr/lib/x86_64-linux-gnu -Wl,-rpath-link,$sysroot/lib/x86_64-linux-gnu"
  echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
  echo "LINUX_COMPAT_RUNTIME=$compat_libs"
  echo "LINUX_COMPAT_SYSROOT=Ubuntu 22.04 x64 (native Ubuntu 24.04 compiler)"
} >> "$GITHUB_ENV"
