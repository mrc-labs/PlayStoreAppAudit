"""Qualify a maintained GNU 11 link interface; keep the current OS C++ runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import urllib.request
from pathlib import Path

from inspect_linux_abi import readelf, required_versions, version_floor
from verify_native_runtime_pilot import diagnose_cxx_abi


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--work-root', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    arguments = parser.parse_args()
    work, evidence = arguments.work_root.resolve(), arguments.evidence_dir.resolve()
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64'
    assert not work.exists(), work
    work.mkdir(parents=True)
    selected = evidence / 'selected-cxx-sdk'
    selected.mkdir()
    spec = json.loads(Path('.github/scripts/native_runtime_pilot_sources.json').read_text())['cxx_link_sdk']
    compiler = os.environ.get('CXX', 'c++')
    assert subprocess.check_output([compiler, '-dumpversion'], text=True).strip().split('.')[0] == '11'
    package = work / 'target-libstdcxx.rpm'
    package.write_bytes(urllib.request.urlopen(spec['url'], timeout=90).read())
    assert hashlib.sha256(package.read_bytes()).hexdigest() == spec['sha256']
    expanded = work / 'expanded'
    subprocess.run(['7z', 'x', '-y', '-o' + str(expanded), str(package)], check=True, stdout=subprocess.DEVNULL)
    libraries = list(expanded.rglob('libstdc++.so.6.0.29'))
    if not libraries:
        payloads = [item for item in expanded.rglob('*') if item.is_file() and '.cpio' in item.name]
        assert len(payloads) == 1, payloads
        subprocess.run(['7z', 'x', '-y', '-o' + str(expanded), str(payloads[0])],
                       check=True, stdout=subprocess.DEVNULL)
        libraries = list(expanded.rglob('libstdc++.so.6.0.29'))
    assert len(libraries) == 1, libraries
    library = libraries[0].resolve()
    assert library.is_relative_to(work)
    assert 'Advanced Micro Devices X86-64' in readelf(library, '--file-header')
    dynamic = readelf(library, '--dynamic')
    assert re.search(r'\(SONAME\).*\[libstdc\+\+\.so\.6\]', dynamic), dynamic
    exports = readelf(library, '--version-info')
    assert max(tuple(map(int, item.split('.'))) for item in re.findall(r'GLIBCXX_([0-9.]+)', exports)) <= (3, 4, 29)
    (selected / 'link-library-version-info.txt').write_text(exports)
    link = work / 'link'
    link.mkdir()
    # Ordinary development linker name; the original ELF SONAME stays unchanged.
    (link / 'libstdc++.so').symlink_to(library)
    diagnose_cxx_abi(selected, link_directory=link)
    source = selected / 'threads.cpp'
    executable = selected / 'threads-probe'
    source.write_text('''#include <condition_variable>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>
int main() {
    std::mutex mutex; std::condition_variable condition; bool ready = false;
    std::thread worker([&] { std::unique_lock<std::mutex> lock(mutex);
        condition.wait(lock, [&] { return ready; }); });
    { std::lock_guard<std::mutex> lock(mutex); ready = true; }
    condition.notify_one(); worker.join(); std::cout << "threads PASS\\n";
    std::ifstream maps("/proc/self/maps"); std::cout << maps.rdbuf();
}
''')
    subprocess.run([compiler, '-L' + str(link), '-std=c++17', '-pthread', str(source), '-o', str(executable)], check=True)
    versions = readelf(executable, '--version-info')
    maximum = version_floor(required_versions(versions), 'GLIBCXX_')
    assert maximum and tuple(map(int, maximum.removeprefix('GLIBCXX_').split('.'))) <= (3, 4, 29)
    assert str(work) not in readelf(executable, '--dynamic'), 'Link SDK must not enter runtime search paths'
    result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15, check=True).stdout
    assert 'threads PASS' in result
    runtime = [line.split()[-1] for line in result.splitlines() if 'libstdc++.so' in line]
    assert runtime and all(not Path(path).resolve().is_relative_to(work) for path in runtime), runtime
    report = {'source_sha': os.environ['GITHUB_SHA'], 'compatible': True, 'scope': spec['scope'],
              'package': spec, 'link_directory': str(link), 'sdk_root': str(work),
              'link_library_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
              'thread_probe_glibcxx': maximum, 'runtime_cpp_paths': sorted(set(runtime)),
              'thread_probe': 'PASS', 'runtime_sdk_loaded': False,
              'extraction_tool': subprocess.check_output(['7z'], text=True).splitlines()[:4]}
    (evidence / 'cxx-sdk-qualified.json').write_text(json.dumps(report, indent=2) + '\n')
    with Path(os.environ['GITHUB_ENV']).open('a') as environment:
        environment.write(f'PILOT_CXX_SDK_ROOT={work}\nPILOT_CXX_LINK_DIR={link}\n')
        for variable in ('CXXFLAGS', 'LDFLAGS'):
            environment.write(f'{variable}=-L{link} {os.environ.get(variable, "")}\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
