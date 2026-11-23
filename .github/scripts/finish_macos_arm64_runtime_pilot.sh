#!/usr/bin/env bash
# Same remaining binding/runtime consumers for a fresh or exact retained SDK.
set -euo pipefail
: "${repo:?}" "${work:?}" "${prefix:?}" "${evidence:?}"
export PATH="$prefix/qt/bin:$PATH"
if [ "${PSAA_MACOS_BINDINGS_READY:-0}" != 1 ]; then
export LLVM_INSTALL_DIR="$work/src/libclang"
export PATH="$prefix/qt/bin:$PATH"
cd "$work/src/pyside-setup-everywhere-src-6.12.0"
PYTHONVERBOSE=1 python setup.py install --ignore-git --qtpaths="$prefix/qt/bin/qtpaths6" \
  --parallel=2 --limited-api=yes --module-subset=Core,Gui,Widgets,Network,Svg,SvgWidgets,Test \
  --no-qt-tools --macos-arch=arm64 --macos-deployment-target=14.4 --macos-sysroot="$SDKROOT" --rpath="$prefix/qt/lib" > "$evidence/pyside-build.log" 2>&1
python "$repo/.github/scripts/probe_setuptools_build.py" --consumer pyside --consumer-log "$evidence/pyside-build.log" --output-dir "$evidence/build-dependencies"
unset LLVM_INSTALL_DIR
fi
cd "$repo"
python - <<'PY'
from pathlib import Path
lines = Path('requirements.txt').read_text().splitlines()
Path('macos-arm64-pilot-evidence/runtime-requirements.txt').write_text('\n'.join(x for x in lines if not x.startswith('PySide6-Essentials==')) + '\n')
PY
python "$repo/.github/scripts/intake_lxml_native.py" --target macos-arm64 --output-dir "$evidence/lxml-qualified" --qualify
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.2.0' --report "$evidence/runtime-install.json"
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
