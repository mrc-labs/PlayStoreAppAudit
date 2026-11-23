"""Measure every packaged Mach-O slice and reject build-prefix dependencies."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from probe_macos_arm64_runtime import load_commands, version

MAGIC = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
         b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}


def validate_commands(commands: dict, ceiling: str) -> None:
    if any(version(value) > version(ceiling) for value in commands['minimum_os']):
        raise RuntimeError('Packaged image exceeds accepted deployment ceiling')
    for name in ['rpaths', 'install_names', 'dependencies']:
        for value in commands[name]:
            if value.startswith('/') and not value.startswith(('/System/Library/', '/usr/lib/')):
                raise RuntimeError('Non-system absolute library origin: ' + value)
            if 'libssl.3.dylib' in value or 'libcrypto.3.dylib' in value:
                raise RuntimeError('Unexpected OpenSSL3 package dependency: ' + value)


def inspect(package: Path, arch: str) -> dict:
    selected = 'arm64' if arch == 'arm64' else 'x86_64'
    ceiling = '15.0' if arch == 'arm64' else '26.0'
    rows = []
    for path in sorted(package.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        with path.open('rb') as stream:
            if stream.read(4) not in MAGIC:
                continue
        architectures = subprocess.check_output(['lipo', '-archs', str(path)], text=True).split()
        if selected not in architectures or not set(architectures) <= {'arm64', 'x86_64'}:
            raise RuntimeError('Wrong native package architecture: ' + str(path))
        commands = load_commands(subprocess.check_output(['otool', '-arch', selected, '-l', str(path)], text=True))
        validate_commands(commands, ceiling)
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        rows.append({'path': path.relative_to(package).as_posix(), 'sha256': digest,
                     'architectures': architectures, 'selected_slice': selected, **commands})
    if not rows:
        raise RuntimeError('No packaged Mach-O images')
    maximum = max((value for row in rows for value in row['minimum_os']), key=version)
    return {'architecture': arch, 'accepted_ceiling': ceiling, 'measured_maximum_deployment': maximum,
            'images': rows, 'scope': 'All packaged Mach-O metadata; not older-OS execution evidence'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package', type=Path)
    parser.add_argument('--arch', choices=['x64', 'arm64'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(inspect(args.package, args.arch), indent=2) + '\n')
