"""Qualify only the stable port's native AArch64 adb and read-only consumers."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from inspect_linux_abi import readelf, required_versions, version_floor

REPO = Path(__file__).resolve().parents[2]


def run(command: list[str], log: Path, *, env: dict | None = None, cwd: Path | None = None) -> str:
    result = subprocess.run(command, env=env, cwd=cwd, text=True, encoding='utf-8',
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1800)
    log.write_text(result.stdout, encoding='utf-8')
    print(log.name, result.returncode, flush=True)
    if result.returncode:
        print(result.stdout[-5000:], flush=True)
        result.check_returncode()
    return result.stdout


def within_floor(names: list[str]) -> None:
    for prefix, ceiling in [('GLIBC_', (2, 38)), ('GLIBCXX_', (3, 4, 32))]:
        value = version_floor(names, prefix)
        if value and tuple(map(int, value[len(prefix):].split('.'))) > ceiling:
            raise ValueError('ADB dependency exceeds accepted ARM64 ABI floor: ' + value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert platform.machine() == 'aarch64' and platform.system() == 'Linux'
    assert platform.freedesktop_os_release()['VERSION_ID'] == '24.04'
    assert not args.work.exists()
    args.work.mkdir(parents=True)
    out = args.output.resolve()
    (out / 'sources').mkdir(parents=True)
    spec_path = REPO / '.github/scripts/adb_linux_arm64_sources.json'
    spec = json.loads(spec_path.read_text())
    shutil.copy2(spec_path, out)
    source = args.work / 'android-tools-37.0.0p1'
    for item in spec['sources']:
        dest = out / 'sources' / item['name']
        with urllib.request.urlopen(item['url'], timeout=180) as response:
            assert response.geturl().startswith('https:')
            dest.write_bytes(response.read())
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == item['sha256']
        target = source if item['name'].endswith('-vendor.tar.xz') else args.work
        with tarfile.open(dest) as archive:
            archive.extractall(target, filter='data')
    env = {**os.environ, 'CC': 'gcc-13', 'CXX': 'g++-13', 'CARGO_NET_OFFLINE': 'true',
           'RUSTUP_TOOLCHAIN': '1.99.1', 'CMAKE_BUILD_PARALLEL_LEVEL': '2'}
    rust = run(['rustc', '-vV'], out / 'rustc.txt', env=env)
    assert 'release: 1.99.1' in rust and 'host: aarch64-unknown-linux-gnu' in rust
    gcc = run(['gcc-13', '-dumpmachine'], out / 'compiler-target.txt', env=env)
    assert gcc.strip() == 'aarch64-linux-gnu'
    # Offline lock generation uses only the exact original vendor archive.
    rust_source = source / 'vendor/adb/client/adbmdns'
    run(['cargo', 'generate-lockfile', '--offline'], out / 'cargo-lock.log', env=env, cwd=rust_source)
    shutil.copy2(rust_source / 'Cargo.lock', out)
    assert spec['boringssl_revision'] in (source / 'CMakeLists.txt').read_text()
    usb = args.work / 'libusb-1.0.30'
    usb_prefix = args.work / 'libusb-prefix'
    run([str(usb / 'configure'), '--prefix=' + str(usb_prefix), '--libdir=' + str(usb_prefix / 'lib'),
         '--disable-static', '--enable-tests-build'], out / 'libusb-configure.log', env=env, cwd=usb)
    run(['make', '-j2'], out / 'libusb-build.log', env=env, cwd=usb)
    run(['make', 'check'], out / 'libusb-check.log', env=env, cwd=usb)
    run(['make', 'install'], out / 'libusb-install.log', env=env, cwd=usb)
    env.update(PKG_CONFIG_PATH=str(usb_prefix / 'lib/pkgconfig'), LD_LIBRARY_PATH=str(usb_prefix / 'lib'))
    selected_usb = run(['pkg-config', '--modversion', 'libusb-1.0'], out / 'libusb-selected.txt', env=env)
    assert selected_usb.strip() == '1.0.30'
    probe = out / 'libusb-api-probe.c'
    probe.write_text('#include <libusb.h>\n#include <stdio.h>\nint main(void) {\n'
                     ' (void)&libusb_get_ssplus_usb_device_capability_descriptor;\n'
                     ' (void)&libusb_free_ssplus_usb_device_capability_descriptor;\n'
                     ' if (sizeof(struct libusb_ssplus_usb_device_capability_descriptor) == 0 || LIBUSB_SPEED_SUPER_PLUS_X2 <= 0) return 1;\n'
                     ' const struct libusb_version *v = libusb_get_version();\n'
                     ' printf("%u.%u.%u\\n", v->major, v->minor, v->micro);\n'
                     ' return !(v->major == 1 && v->minor == 0 && v->micro == 30); }\n')
    flags = run(['pkg-config', '--cflags', '--libs', 'libusb-1.0'], out / 'libusb-flags.txt', env=env)
    consumer = out / 'libusb-api-probe'
    run(['gcc-13', str(probe), *shlex.split(flags), '-o', str(consumer)], out / 'libusb-probe-build.log', env=env)
    run([str(consumer)], out / 'libusb-probe-run.log', env=env)
    legal = out / 'legal'
    for path in [*source.rglob('*'), *usb.rglob('*')]:
        if path.is_file() and path.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING', 'NOTICE', 'COPYRIGHT')):
            origin = source if path.is_relative_to(source) else usb
            target = legal / origin.name / path.relative_to(origin)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    assert len(list(legal.rglob('*'))) > 20
    build = args.work / 'build'
    run(['cmake', '-S', str(source), '-B', str(build), '-GNinja', '-DCMAKE_BUILD_TYPE=Release',
         '-DANDROID_TOOLS_PATCH_VENDOR=OFF', '-DANDROID_TOOLS_ADB_ENABLE_MDNS=ON',
         '-DANDROID_TOOLS_USE_BUNDLED_CORROSION=ON', '-DANDROID_TOOLS_USE_BUNDLED_FMT=ON',
         '-DCMAKE_BUILD_RPATH=' + str(usb_prefix / 'lib')],
        out / 'configure.log', env=env)
    cache = (build / 'CMakeCache.txt').read_text()
    assert 'ANDROID_TOOLS_ADB_ENABLE_MDNS:BOOL=ON' in cache
    shutil.copy2(build / 'CMakeCache.txt', out)
    run(['cmake', '--build', str(build), '--target', 'adb', '--parallel', '2'], out / 'build.log', env=env)
    adb = build / 'vendor/adb'
    assert adb.is_file()
    header = readelf(adb, '--file-header')
    assert re.search(r'Machine:\s+AArch64', header)
    # Record every actual linked ELF requirement, including system providers.
    linkage = run(['ldd', str(adb)], out / 'linkage.txt', env=env)
    assert 'not found' not in linkage
    paths = {adb, *(Path(p) for p in re.findall(r'(?:=>\s+|^\s*)(/\S+)', linkage, re.M))}
    images = []
    for path in sorted(paths):
        assert re.search(r'Machine:\s+AArch64', readelf(path, '--file-header')), path
        needs = required_versions(readelf(path, '--version-info'))
        within_floor(needs)
        images.append({'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'required_versions': needs, 'dynamic': readelf(path, '--dynamic')})
    version = run([str(adb), 'version'], out / 'adb-version.txt', env=env)
    assert '37.0.0' in version and re.search(r'arm64|aarch64', version, re.I)
    run([str(adb), 'help'], out / 'adb-help.txt', env=env)
    assert 'mdns' in (out / 'adb-help.txt').read_text()
    # Use a private server port/key/home; no physical device or existing server.
    profile = args.work / 'profile'
    profile.mkdir()
    env.update(HOME=str(profile), ANDROID_USER_HOME=str(profile), ADB_SERVER_PORT='15037',
               ADB_MDNS_AUTO_CONNECT='0')
    try:
        devices = run([str(adb), '-P', '15037', 'devices', '-l'], out / 'adb-devices.txt', env=env)
        assert 'List of devices attached' in devices
        run([str(adb), '-P', '15037', 'mdns', 'check'], out / 'adb-mdns-check.txt', env=env)
        run([str(adb), '-P', '15037', 'server-status'], out / 'adb-server-status.txt', env=env)
    finally:
        run([str(adb), '-P', '15037', 'kill-server'], out / 'adb-private-server-stop.txt', env=env)
    shutil.copy2(adb, out / 'adb')
    shutil.copytree(usb_prefix / 'lib', out / 'private-libusb', symlinks=True)
    report = {'source_sha': os.environ['GITHUB_SHA'], 'identity': spec['identity'], 'images': images,
              'libusb': {'version': '1.0.30', 'prefix': str(usb_prefix), 'linkage': 'private shared LGPL library'},
              'version': version, 'mdns': 'enabled; native private-server check executed',
              'result': 'PASS native source/ABI/read-only host diagnostic; physical USB/wireless device not tested',
              'producer_adoption': False}
    (out / 'adb-native-results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(report['result'], flush=True)


if __name__ == '__main__':
    main()
