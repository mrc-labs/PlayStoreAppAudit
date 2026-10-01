#!/usr/bin/env bash
# Executes the ZIP-roundtripped package with only Ubuntu 22.04 system libraries.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates binutils libegl1 libfontconfig1 libgl1 libx11-xcb1 \
  libxcb1 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render0 libxcb-render-util0 libxcb-shape0 \
  libxcb-shm0 libxcb-sync1 libxcb-util1 libxcb-xfixes0 libxcb-xinerama0 \
  libxcb-xkb1 libxkbcommon-x11-0 xauth xvfb
cat /etc/os-release
ldd --version
dpkg-query -W libc6 libstdc++6
test -x "$PACKAGE_DIR/PlayStoreAppAudit"
cd "$PACKAGE_DIR"
ldd ./PlayStoreAppAudit
export QT_QPA_PLATFORM=offscreen
export PLAYSTORE_APP_AUDIT_SMOKE_TEST=1
export XDG_DATA_HOME=/tmp/audit-smoke-data
timeout 60s ./PlayStoreAppAudit
echo 'Ubuntu 22.04 packaged offscreen GUI smoke PASS'
timeout 60s xvfb-run -a env QT_QPA_PLATFORM=xcb ./PlayStoreAppAudit
echo 'Ubuntu 22.04 packaged xcb GUI smoke PASS'
timeout 60s ./PlayStoreAppAudit cli audit --help > /tmp/cli-help.txt
cat /tmp/cli-help.txt
grep -q 'usage:' /tmp/cli-help.txt
echo 'Ubuntu 22.04 packaged CLI audit --help PASS'
