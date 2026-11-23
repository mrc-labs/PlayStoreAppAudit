#!/usr/bin/env bash
# Consumer-only continuation of the one hash-bound Noble ARM64 diagnostic.
set -euo pipefail
repo=$(pwd)
evidence="$repo/linux-arm64-pilot-evidence"
prefix=$(cat "$evidence/reused-prefix.txt")
work=$(dirname "$prefix")
test "$(uname -m)" = aarch64
test "$(. /etc/os-release; echo "$VERSION_ID")" = 24.04
export CC=gcc-13 CXX=g++-13
export PILOT_WORK="$work" PILOT_PREFIX="$prefix" PILOT_EVIDENCE="$evidence"
export LD_LIBRARY_PATH="$prefix/qt/lib:$prefix/python/lib:$prefix/openssl/lib:$prefix/lib"
unset PYTHONHOME Python_ROOT_DIR Python2_ROOT_DIR Python3_ROOT_DIR SSL_CERT_FILE SSL_CERT_DIR
"$prefix/python/bin/python3.14" -m venv "$work/consumer-venv"
export PATH="$work/consumer-venv/bin:$prefix/qt/bin:$PATH"
python -c "import platform,sysconfig; assert platform.python_version() == '3.14.10' and platform.machine() == 'aarch64' and not sysconfig.get_config_var('Py_GIL_DISABLED')"
python "$repo/.github/scripts/bootstrap_pip.py"
python - <<'PY'
import hashlib, json, os, shutil, sysconfig, tarfile
from pathlib import Path
root = Path(os.environ['PILOT_EVIDENCE'])
work = Path(os.environ['PILOT_WORK'])
site = Path(sysconfig.get_path('purelib'))
for package in (root / 'pyside-binding-sdk').iterdir():
    assert not (site / package.name).exists(), package
    shutil.copytree(package, site / package.name)
(work / 'src').mkdir()
# Only Qt generator input is needed; no compiler/build system is invoked.
spec = json.loads((root / 'native_runtime_pilot_sources.json').read_text())
qt = next(item for item in spec['sources'] if item['name'].startswith('qtbase-'))
archive = root / 'sources' / qt['name']
assert hashlib.sha256(archive.read_bytes()).hexdigest() == qt['sha256']
with tarfile.open(archive) as bundle:
    bundle.extractall(work / 'src', filter='data')
PY
python -m pip install --no-index --no-deps "$evidence"/cffi-wheel/cffi-*.whl
python "$repo/.github/scripts/intake_lxml_native.py" --target linux-arm64 --output-dir "$evidence/lxml-intake" --qualify
python -m pip install -r "$evidence/runtime-requirements.txt" 'pytest==9.2.0' --report "$evidence/consumer-runtime-install.json"
python -m pip check
python "$repo/.github/scripts/apply_qt_cldr49.py" \
  --source "$work/src/qtbase-everywhere-src-6.12.0" --archives "$evidence/sources" --evidence "$evidence/consumer-cldr49"
export XDG_CONFIG_HOME="$work/consumer-profile/config" XDG_DATA_HOME="$work/consumer-profile/data" XDG_CACHE_HOME="$work/consumer-profile/cache"
export QT_QPA_PLATFORM=xcb
python .github/scripts/probe_qt_cldr49_runtime.py \
  --xml "$work/src/cldr49-generator-input/cldr49.xml" --output "$evidence/qt-cldr49-runtime.json"
# Execute the security case again on the unchanged actual interpreter. Broad
# provider/SSL/cffi suites retain their original source-bound reports.
python -m test --junit-xml "$evidence/consumer-spki.xml" test_ssl -m '*test_distrusted_spki*' > "$evidence/consumer-spki.log" 2>&1
PYTHONPATH="$repo/.github/scripts" python -c "from pathlib import Path; from verify_linux_arm64_runtime_pilot import require_security_case; require_security_case(Path('$evidence/consumer-spki.xml'))"
python -m unittest -v test.test_tarfile.TestExtractionFilters.test_link_at_destination > "$evidence/consumer-tarfile-security.log" 2>&1
xvfb-run -a python .github/scripts/verify_linux_arm64_runtime_pilot.py --output-dir "$evidence"
xvfb-run -a python .github/scripts/verify_linux_x64_native_delta.py \
  --target linux-arm64 --prefix "$prefix" --output-dir "$evidence" --cffi
python main.py cli audit --help > "$evidence/consumer-cli-smoke.txt"
xvfb-run -a python -m pytest tests/test_cli_headless.py -q > "$evidence/consumer-cli-regressions.log" 2>&1
python -m compileall -q playstore_app_audit
python - <<'PY'
import json, os
from pathlib import Path
root = Path(os.environ['PILOT_EVIDENCE'])
proof = json.loads((root / 'reused-arm64-sdk.json').read_text())
for name in ['python-native-results.json']:
    path = root / name
    if path.exists():
        result = json.loads(path.read_text())
        result['original_native_suite_provenance'] = proof
        result['reused_upstream'] = result.pop('executed_upstream')
        result['cffi']['suite_reused_provenance'] = proof
        path.write_text(json.dumps(result, indent=2) + '\n')
(root / 'consumer-provenance.json').write_text(json.dumps({
    'source_sha': os.environ['GITHUB_SHA'], 'compiled_sdk': proof,
    'executed': 'CLDR/TLS/default trust/provider-security/hash/PNG/text/CBOR/GUI/CLI/parser/SPKI/tarfile/loaded ABI consumers',
    'reused': 'Exact original native SDK/bindings/cffi; unchanged broad upstream suites at their actual compiled source',
    'scope': 'Native diagnostic continuation only; no source rebuild or final package'}, indent=2) + '\n')
PY
echo 'Native Noble ARM64 affected consumers PASS; no application package produced.'
