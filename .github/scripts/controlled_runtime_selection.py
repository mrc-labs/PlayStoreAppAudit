"""Describe a verified project SDK for subsequent package preparation steps."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def record_selection(target: str, work: Path, output: Path, receipt: Path) -> None:
    windows = target.startswith('windows-')
    python = work / ('venv/Scripts/python.exe' if windows else 'venv/bin/python')
    assert python.is_file() and receipt.is_file()
    raw = receipt.read_bytes()
    original = json.loads(raw)
    assert Path(original['original_work_root']).resolve() == work.resolve()
    (output / 'producer-runtime-selection.json').write_text(json.dumps({
        'target': target, 'work': str(work), 'prefix': str(work / 'prefix'), 'python': str(python),
        'qt_receipt': str(receipt), 'qt_receipt_sha256': hashlib.sha256(raw).hexdigest(),
        'compiled_source_sha': original['source_sha'],
        'identity': 'Project-modified source runtime/framework dependency SDK; not an official unchanged distribution or application candidate',
        'scope': 'Verified intake only; producer installation/source/legal/actual final package validation remain separate gates.'}, indent=2) + '\n')
