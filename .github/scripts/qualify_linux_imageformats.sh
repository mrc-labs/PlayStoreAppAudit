#!/usr/bin/env bash
# Matching image module only; restore existing runtime/Qt/binding/cffi bytes first.
set -euo pipefail
repo=$(pwd)
target=${1:?linux-x64 or linux-arm64}
case "$target" in
  linux-x64)
    evidence="$repo/pilot-evidence"
    bindings="$evidence/reused-bindings"
    cffi="$evidence/reused-cffi-wheel"
    export CC=gcc-11 CXX=g++-11
    test "$(uname -m)" = x86_64
    test "$(. /etc/os-release; echo "$VERSION_ID")" = 22.04
    test -n "$PILOT_CXX_LINK_DIR"
    ;;
  linux-arm64)
    evidence="$repo/linux-arm64-pilot-evidence"
    bindings="$evidence/pyside-binding-sdk"
    cffi="$evidence/cffi-wheel"
    export CC=gcc-13 CXX=g++-13
    test "$(uname -m)" = aarch64
    test "$(. /etc/os-release; echo "$VERSION_ID")" = 24.04
    test -z "${PILOT_CXX_LINK_DIR:-}" && test -z "${PILOT_CXX_SDK_ROOT:-}"
    ;;
  *) exit 2 ;;
esac
prefix=$(cat "$evidence/reused-prefix.txt")
work=$(dirname "$prefix")
export PILOT_WORK="$work" PILOT_PREFIX="$prefix" PILOT_EVIDENCE="$evidence"
export LD_LIBRARY_PATH="$prefix/qt/lib:$prefix/python/lib:$prefix/openssl/lib:$prefix/lib"
unset PYTHONHOME PYTHONPATH Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR LLVM_INSTALL_DIR SSL_CERT_FILE SSL_CERT_DIR
"$prefix/python/bin/python3.14" -m venv "$work/imageformats-venv"
export PATH="$work/imageformats-venv/bin:$prefix/qt/bin:$PATH"
python -c 'import platform,sysconfig; assert platform.python_version()=="3.14.10" and not sysconfig.get_config_var("Py_GIL_DISABLED")'
python "$repo/.github/scripts/bootstrap_pip.py"
python - "$bindings" <<'PY'
import shutil,sys,sysconfig
from pathlib import Path
site=Path(sysconfig.get_path('purelib'))
for package in Path(sys.argv[1]).iterdir():
    assert not (site/package.name).exists()
    shutil.copytree(package,site/package.name)
PY
python -m pip install --no-index --no-deps "$cffi"/cffi-*.whl
python "$repo/.github/scripts/intake_lxml_native.py" --target "$target" --output-dir "$evidence/lxml-intake" --qualify
python - "$repo" "$evidence" <<'PY'
from pathlib import Path
import sys
lines=(Path(sys.argv[1])/'requirements.txt').read_text().splitlines()
(Path(sys.argv[2])/'imageformats-runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials=='))+'\n')
PY
python -m pip install -r "$evidence/imageformats-runtime-requirements.txt" 'pytest==9.2.0' 'cmake==4.4.4' 'ninja==1.13.2'
python -m pip check
export QT_QPA_PLATFORM=xcb QT_PLUGIN_PATH="$prefix/qt/plugins"
export XDG_CONFIG_HOME="$work/imageformats-profile/config" XDG_DATA_HOME="$work/imageformats-profile/data" XDG_CACHE_HOME="$work/imageformats-profile/cache"
xvfb-run -a python "$repo/.github/scripts/verify_linux_imageformats.py" --target "$target" --work "$work" --output "$evidence"
