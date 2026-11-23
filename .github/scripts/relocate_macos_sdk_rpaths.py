"""Remove only closed-SDK build RPATHs before the existing package/signing gates."""
from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import subprocess
from pathlib import Path, PurePosixPath

from inspect_macos_package import MAGIC
from probe_macos_arm64_runtime import load_commands


def sdk_rpaths(values: list[str], prefix: str) -> list[str]:
    root = PurePosixPath(prefix)
    allowed = {str(root / part) for part in ('lib', 'qt/lib', 'openssl/lib', 'python/lib')}
    return list(dict.fromkeys(value for value in values
                             if value.startswith('/') and posixpath.normpath(value) in allowed))


def relocate(package: Path, selection_path: Path, arch: str) -> dict:
    selection = json.loads(selection_path.read_text(encoding='utf-8'))
    assert selection['target'] == 'macos-' + arch
    raw = Path(selection['qt_receipt']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == selection['qt_receipt_sha256']
    receipt = json.loads(raw)
    assert receipt['source_sha'] == selection['compiled_source_sha']
    work = Path(receipt['original_work_root']).resolve()
    prefix = Path(selection['prefix']).resolve()
    assert prefix == work / 'prefix'
    assert package.is_dir() and package.suffix == '.app'
    package = package.resolve()
    assert not package.is_relative_to(work) and not work.is_relative_to(package)
    selected = 'arm64' if arch == 'arm64' else 'x86_64'
    rows = []
    for path in sorted(package.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in MAGIC:
                continue
        command = ['otool', '-arch', selected, '-l', str(path)]
        before = load_commands(subprocess.check_output(command, text=True))
        removed = sdk_rpaths(before['rpaths'], str(prefix))
        if not removed:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        for value in removed:
            subprocess.run(['install_name_tool', '-delete_rpath', value, str(path)], check=True)
        after = load_commands(subprocess.check_output(command, text=True))
        assert after['rpaths'] == [value for value in before['rpaths'] if value not in removed]
        for key in ('minimum_os', 'sdk', 'install_names', 'dependencies'):
            assert after[key] == before[key], (str(path), key)
        rows.append({'path': path.relative_to(package).as_posix(), 'removed_sdk_rpaths': removed,
                     'before_sha256': digest, 'after_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                     'before': before, 'after': after})
    return {'source_sha': selection['preparation_source_sha'], 'target': selection['target'],
            'compiled_source_sha': selection['compiled_source_sha'],
            'sdk_receipt_sha256': selection['qt_receipt_sha256'], 'images': rows,
            'scope': 'Owned SDK RPATH metadata relocation only; strict inspection and engineering signing follow'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--arch', choices=['x64', 'arm64'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = relocate(args.package, args.selection, args.arch)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Relocated closed SDK RPATHs in', len(result['images']), 'Mach-O images')
