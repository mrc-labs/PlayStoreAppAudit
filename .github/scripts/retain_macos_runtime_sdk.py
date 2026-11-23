"""Retain exact diagnostic prefix bytes so later failures need not rebuild it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import tarfile
from pathlib import Path


def retain(work: Path, output: Path, exit_code: int, *, sdk_name: str = 'macos-runtime-sdk') -> dict | None:
    assert sdk_name and all(c.isascii() and (c.isalnum() or c == '-') for c in sdk_name)
    work = work.resolve()
    roots = [work / name for name in ['prefix', 'venv'] if (work / name).is_dir()]
    if not roots:
        return None
    index = {}
    for root in roots:
        for path in sorted(root.rglob('*')):
            name = path.relative_to(work).as_posix()
            if path.is_symlink():
                index[name] = {'link': os.readlink(path)}
            elif path.is_file():
                with path.open('rb') as stream:
                    index[name] = {'sha256': hashlib.file_digest(stream, 'sha256').hexdigest(), 'bytes': path.stat().st_size}
    archive = output / (sdk_name + '.tar.zst')
    with tarfile.open(archive, 'w:zst') as bundle:
        for root in roots:
            bundle.add(root, arcname=root.name)
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    result = {'source_sha': os.environ.get('GITHUB_SHA'), 'machine': platform.machine(),
              'original_work_root': str(work), 'producer_python': platform.python_version(),
              'pilot_exit_code': exit_code, 'complete_pilot': exit_code == 0,
              'archive': archive.name, 'archive_sha256': digest, 'paths': index,
              'scope': 'Diagnostic SDK only; partial output is not qualified; reuse requires original source/input/byte guards and affected native consumer checks. Never a final candidate.'}
    (output / (sdk_name + '.json')).write_text(json.dumps(result, indent=2) + '\n')
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--exit-code', type=int, required=True)
    parser.add_argument('--sdk-name', default='macos-runtime-sdk')
    args = parser.parse_args()
    result = retain(args.work, args.output, args.exit_code, sdk_name=args.sdk_name)
    if result:
        print('Retained diagnostic SDK', result['archive_sha256'], len(result['paths']), 'paths; complete pilot:', result['complete_pilot'])


if __name__ == '__main__':
    main()
