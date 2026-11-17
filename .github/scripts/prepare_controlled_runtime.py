"""Prepare the six qualified v2.4 dependency SDKs; never compile an application."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from complete_qt_imageformats import restore_qualified_overlay
from download_diagnostic_artifact import fetch_artifact

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ('windows-x64', 'windows-arm64', 'linux-x64', 'linux-arm64', 'macos-x64', 'macos-arm64')


def qualified_download(artifact: int, source: str, run: int) -> bytes:
    metadata, data = fetch_artifact(artifact)
    assert not metadata['expired'] and metadata['workflow_run']['head_repository_id'] == 1334403620
    assert metadata['workflow_run']['id'] == run and metadata['workflow_run']['head_sha'] == source
    assert len(data) == metadata['size_in_bytes']
    assert metadata['digest'] == 'sha256:' + hashlib.sha256(data).hexdigest()
    return data


def linux_selection(target: str) -> tuple[dict, dict[str, str]]:
    output = ROOT / 'controlled-runtime-evidence'
    output.mkdir()
    if target == 'linux-x64':
        import reuse_linux_pre_qt_sdk as sdk

        data = qualified_download(sdk.QT_ARTIFACT, sdk.QT_SOURCE, 43623545058)
        sdk.restore(data, output, Path(os.environ['RUNNER_TEMP']), with_qt=True, material=output / 'controlled-material')
        del data
        data = qualified_download(sdk.BINDING_ARTIFACT, sdk.BINDING_SOURCE, 43666656687)
        sdk.restore_bindings(data, output, with_cffi=True)
        binding_source = sdk.BINDING_SOURCE
        compiled_sources = {'python': sdk.SOURCE, 'qt': sdk.QT_SOURCE, 'bindings': sdk.BINDING_SOURCE}
        bindings, cffi = output / 'reused-bindings', output / 'reused-cffi-wheel'
    else:
        import reuse_linux_arm64_pilot as sdk

        data = qualified_download(sdk.ARTIFACT, sdk.SOURCE, 43667240760)
        sdk.restore(data, output, Path(os.environ['RUNNER_TEMP']))
        binding_source = sdk.SOURCE
        compiled_sources = {'runtime_qt_bindings': sdk.SOURCE}
        bindings, cffi = output / 'pyside-binding-sdk', output / 'cffi-wheel'
    del data
    prefix = Path((output / 'reused-prefix.txt').read_text().strip())
    work = prefix.parent
    loader = os.pathsep.join(str(prefix / name) for name in ['qt/lib', 'python/lib', 'openssl/lib', 'lib'])
    environment = {**os.environ, 'LD_LIBRARY_PATH': loader}
    for key in ['PYTHONHOME', 'PYTHONPATH', 'Python_ROOT_DIR', 'Python2_ROOT_DIR', 'Python3_ROOT_DIR', 'SSL_CERT_FILE', 'SSL_CERT_DIR']:
        environment.pop(key, None)
    venv = work / 'venv'
    assert not venv.exists()
    subprocess.run([str(prefix / 'python/bin/python3.14'), '-m', 'venv', str(venv)], env=environment, check=True)
    python = venv / 'bin/python'
    site = Path(subprocess.check_output([str(python), '-c', 'import sysconfig;print(sysconfig.get_path("purelib"))'], env=environment, text=True).strip())
    assert site.is_relative_to(venv)
    for package in bindings.iterdir():
        assert not (site / package.name).exists()
        shutil.copytree(package, site / package.name)
    wheels = list(cffi.glob('cffi-*.whl'))
    assert len(wheels) == 1
    subprocess.run([str(python), '-m', 'pip', 'install', '--no-index', '--no-deps', str(wheels[0])], env=environment, check=True)
    # This derived receipt describes unchanged, already hash-verified Qt/binding
    # bytes at their new venv paths. It does not relabel their compiled sources.
    paths = {}
    for directory in [prefix / 'qt', *(path for path in site.iterdir()
                         if path.name in {'PySide6', 'shiboken6'} or path.name.lower().startswith(('pyside6-', 'shiboken6-')))]:
        for path in directory.rglob('*'):
            if '__pycache__' in path.parts or not (path.is_file() or path.is_symlink()):
                continue
            relative = path.relative_to(work).as_posix()
            assert path.resolve().is_relative_to(work)
            paths[relative] = ({'link': os.readlink(path)} if path.is_symlink() else
                               {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    receipt = output / 'assembled-qt-binding-receipt.json'
    receipt.write_text(json.dumps({'source_sha': binding_source, 'original_work_root': str(work),
        'compiled_component_sources': compiled_sources, 'paths': paths}, indent=2))
    return {'target': target, 'work': str(work), 'prefix': str(prefix), 'python': str(python),
            'qt_receipt': str(receipt), 'qt_receipt_sha256': hashlib.sha256(receipt.read_bytes()).hexdigest(),
            'compiled_component_sources': compiled_sources}, environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--export-github-environment', action='store_true')
    args = parser.parse_args()
    target = args.target
    system, arch = target.split('-')
    assert platform.system() == {'windows': 'Windows', 'linux': 'Linux', 'macos': 'Darwin'}[system]
    assert platform.machine().lower() in ({'arm64', 'aarch64'} if arch == 'arm64' else {'amd64', 'x86_64'})
    os.environ['EXPECTED_ARCH'] = arch
    if system == 'linux':
        assert platform.freedesktop_os_release()['VERSION_ID'] == ('24.04' if arch == 'arm64' else '22.04')
        selection, environment = linux_selection(target)
        output = ROOT / 'controlled-runtime-evidence'
    else:
        script, options, directory = {
            'windows': ('replay_windows_current_framework.py', ['--intake-only'], 'toolchain-delta-evidence'),
            'macos-x64': ('reuse_macos_x64_bound_sdk.py', ['--intake-only', '--imageformats', '--reuse-imageformats-overlay', '--diagnose-gui'], 'macos-x64-pilot-evidence'),
            'macos-arm64': ('reuse_macos_arm64_compiled_sdk.py', ['--intake-only', '--consumers-only', '--imageformats'], 'macos-arm64-pilot-evidence'),
        }['windows' if system == 'windows' else target]
        subprocess.run([sys.executable, str(ROOT / '.github/scripts' / script), *options], cwd=ROOT, check=True)
        output = ROOT / directory
        selection = json.loads((output / 'producer-runtime-selection.json').read_text())
        environment = dict(os.environ)
    work, prefix = Path(selection['work']), Path(selection['prefix'])
    if system != 'macos':
        spec = json.loads((ROOT / '.github/scripts/qualified_imageformat_overlays.json').read_text())[target]
        restore_qualified_overlay(work, output, spec)
    for key in ['GH_TOKEN', 'GITHUB_TOKEN', 'PYTHONHOME', 'PYTHONPATH', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'DYLD_LIBRARY_PATH', 'DYLD_FRAMEWORK_PATH']:
        environment.pop(key, None)
    if system == 'windows':
        paths = [Path(selection['python']).parent, prefix / 'qt/bin', prefix / 'bin', prefix / 'openssl/bin']
        environment['PATH'] = os.pathsep.join(map(str, paths)) + os.pathsep + environment['PATH']
    python = selection['python']
    if system == 'windows':
        site = Path(subprocess.check_output([python, '-c', 'import sysconfig;print(sysconfig.get_path("purelib"))'], env=environment, text=True).strip())
        assert site.resolve().is_relative_to(work)
        hook = site / '_psaa_sdk_dll_paths.py'
        pth = site / '_psaa_controlled_sdk.pth'
        assert not hook.exists() and not pth.exists()
        hook.write_text('import os\nfrom pathlib import Path\n'
            f'_root=Path({str(prefix)!r}).resolve()\n_handles=[]\n'
            'for _name in ["python","qt/bin","bin","openssl/bin"]:\n'
            '    _directory=(_root/_name).resolve()\n'
            '    assert _directory.is_relative_to(_root) and _directory.is_dir()\n'
            '    _handles.append(os.add_dll_directory(str(_directory)))\n', encoding='utf-8')
        pth.write_text('import _psaa_sdk_dll_paths\n', encoding='utf-8')
    # Install the already-qualified lxml wheel into fresh Linux venvs only.
    if system == 'linux':
        staged = output / 'producer-lxml-intake'
        subprocess.run([sys.executable, str(ROOT / '.github/scripts/intake_lxml_native.py'), '--target', target, '--output-dir', str(staged)], check=True)
        subprocess.run([python, str(ROOT / '.github/scripts/intake_lxml_native.py'), '--target', target, '--output-dir', str(staged), '--qualify'], env=environment, check=True)
    requirements = output / 'controlled-package-requirements.txt'
    lines = (ROOT / 'requirements.txt').read_text().splitlines()
    lines = [line for line in lines if not line.startswith('PySide6-Essentials==')]
    lines += [line for line in (ROOT / 'requirements-dev.txt').read_text().splitlines() if not line.startswith('-r ')]
    lines += ['PySide6==6.12.0', 'Nuitka==4.3.5']
    requirements.write_text('\n'.join(lines) + '\n')
    subprocess.run([python, str(ROOT / '.github/scripts/bootstrap_pip.py')], env=environment, check=True)
    subprocess.run([python, '-m', 'pip', 'install', '-r', str(ROOT / '.github/scripts/source_build_requirements.txt'),
                    '-c', str(ROOT / '.github/scripts/source_build_constraints.txt')], env=environment, check=True)
    subprocess.run([python, '-m', 'pip', 'install', '--no-build-isolation', '-r', str(requirements)], env=environment, check=True)
    subprocess.run([python, '-m', 'pip', 'check'], env=environment, check=True)
    subprocess.run([python, '-c', 'import platform,ssl,sysconfig;from PySide6.QtCore import qVersion;'
        'from cryptography.hazmat.backends.openssl.backend import backend;'
        'assert platform.python_version()=="3.14.10" and not sysconfig.get_config_var("Py_GIL_DISABLED");'
        'assert ssl.OPENSSL_VERSION.startswith("OpenSSL 4.0.3 ");'
        'assert backend.openssl_version_text().startswith("OpenSSL 4.0.3 ");assert qVersion()=="6.12.0"'], env=environment, check=True)
    subprocess.run([python, '-c', 'import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);'
        'from controlled_qt_legal_identity import source_identity;'
        'Path(sys.argv[4]).write_text(json.dumps(source_identity(Path(sys.argv[2]),sys.argv[3],"6.12.0"),indent=2))',
        str(ROOT / '.github/scripts'), selection['qt_receipt'], selection['qt_receipt_sha256'],
        str(output / 'controlled-qt-identity.json')], env=environment, check=True)
    selection.update(overlay=json.loads((output / 'imageformats/overlay-intake.json').read_text()),
                     preparation_source_sha=os.environ['GITHUB_SHA'], identity='Project-modified v2.4 dependency inputs; no application compiled',
                     loader_path=environment.get('LD_LIBRARY_PATH', ''))
    (output / 'producer-runtime-selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    from controlled_source_material import retain_directory_material

    retain_directory_material(output, output / 'controlled-material', target + ' verified SDK intake')
    selection['material_directory'] = str(output / 'controlled-material')
    (output / 'producer-runtime-selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    material_records = json.loads((output / 'controlled-material/INPUT-MATERIAL.json').read_text())
    assert any(record['file'].startswith('sources/') for record in material_records)
    assert any(record['file'].startswith('licenses/') for record in material_records)
    (output / 'controlled-material-summary.json').write_text(json.dumps({
        'target': target, 'preparation_source_sha': os.environ['GITHUB_SHA'],
        'source_inputs': sorted({record['file'] for record in material_records if record['file'].startswith('sources/')}),
        'license_payloads': len({record['sha256'] for record in material_records if record['file'].startswith('licenses/')}),
        'scope': 'Retained original source and license bytes; package acceptance not claimed'}, indent=2) + '\n')
    if args.export_github_environment:
        values = {'PSAA_RUNTIME_PYTHON': python, 'PSAA_RUNTIME_EVIDENCE': str(output),
                  'PSAA_CONTROLLED_QT_RECEIPT': selection['qt_receipt'],
                  'PSAA_CONTROLLED_QT_RECEIPT_SHA256': selection['qt_receipt_sha256'],
                  'PYTHONHOME': '', 'PYTHONPATH': '', 'DYLD_LIBRARY_PATH': '', 'DYLD_FRAMEWORK_PATH': ''}
        if system == 'linux':
            values.update(LD_LIBRARY_PATH=environment['LD_LIBRARY_PATH'],
                          CC='gcc-13' if arch == 'arm64' else 'gcc-11', CXX='g++-13' if arch == 'arm64' else 'g++-11')
        assert all('\n' not in value and '\r' not in value for value in values.values())
        with Path(os.environ['GITHUB_ENV']).open('a', encoding='utf-8') as stream:
            stream.write(''.join(f'{key}={value}\n' for key, value in values.items()))
        with Path(os.environ['GITHUB_PATH']).open('a', encoding='utf-8') as stream:
            for directory in [Path(python).parent, *([prefix / 'qt/bin', prefix / 'bin', prefix / 'openssl/bin'] if system == 'windows' else [])]:
                stream.write(str(directory) + '\n')
    print('PASS controlled dependency intake only:', target, flush=True)


if __name__ == '__main__':
    main()
