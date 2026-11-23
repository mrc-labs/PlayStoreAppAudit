"""Explicit legal identity for source-installed PySide; never impersonate Essentials."""
from __future__ import annotations

import hashlib
import importlib
import importlib.metadata as metadata
import json
import re
from pathlib import Path, PurePosixPath


def source_identity(receipt_path: Path, expected_sha256: str, expected_version: str) -> dict:
    raw = receipt_path.read_bytes()
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256) or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise RuntimeError('Changed controlled Qt SDK receipt')
    receipt = json.loads(raw)
    if not re.fullmatch(r'[0-9a-f]{40}', receipt['source_sha']):
        raise RuntimeError('Missing controlled Qt source identity')
    root = Path(receipt['original_work_root']).resolve()
    try:
        metadata.distribution('PySide6-Essentials')
    except metadata.PackageNotFoundError:
        pass
    else:
        raise RuntimeError('Ambiguous official Essentials and controlled PySide installation')
    for name in ['PySide6', 'shiboken6']:
        if metadata.version(name) != expected_version:
            raise RuntimeError('Controlled PySide/shiboken metadata version mismatch')
    modules = {name: importlib.import_module(name) for name in ['PySide6', 'shiboken6', 'PySide6.QtCore', 'PySide6.QtGui']}
    if any(modules[name].__version__ != expected_version for name in ['PySide6', 'shiboken6']):
        raise RuntimeError('Controlled binding runtime version mismatch')
    if modules['PySide6.QtCore'].qVersion() != expected_version:
        raise RuntimeError('Controlled Qt/binding runtime version mismatch')
    verified = set()
    for name, entry in receipt['paths'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in {'prefix', 'venv'}:
            raise RuntimeError('Unsafe controlled SDK receipt path')
        if not (name.startswith('prefix/qt/') or any(part in ('PySide6', 'shiboken6') or part.lower().startswith(('pyside6-', 'shiboken6-')) for part in relative.parts)):
            continue
        path = root / relative
        if not path.resolve().is_relative_to(root):
            raise RuntimeError('Controlled Qt SDK link escapes prefix')
        if 'link' in entry:
            import os

            if not path.is_symlink() or os.readlink(path) != entry['link']:
                raise RuntimeError('Changed controlled Qt SDK link')
        elif not path.is_file() or path.is_symlink() or path.stat().st_size != entry['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise RuntimeError('Changed controlled Qt/binding SDK file: ' + name)
        verified.add(path.resolve())
    for name, module in modules.items():
        if Path(module.__file__).resolve() not in verified:
            raise RuntimeError('Active binding module is outside controlled SDK: ' + name)
    for name in ['PySide6', 'shiboken6']:
        for path in Path(modules[name].__file__).parent.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.resolve() not in verified:
                raise RuntimeError('Unindexed file in controlled binding package: ' + str(path))
    if not any((root / 'prefix/qt').resolve() in path.parents for path in verified):
        raise RuntimeError('Missing controlled Qt framework bytes')
    return {'distribution': 'PySide6', 'version': expected_version, 'shiboken6_version': expected_version,
            'sdk_source_sha': receipt['source_sha'], 'sdk_receipt_sha256': expected_sha256,
            'verified_qt_binding_paths': len(verified),
            'identity': 'Project-controlled source build; not an unchanged official PySide6-Essentials wheel',
            'scope': 'Legal identity/active SDK byte verification only; native/package/source/legal acceptance remains separately required'}


def add_arguments(parser) -> None:
    parser.add_argument('--controlled-qt-sdk-receipt', type=Path,
                        help='Explicit source-installed PySide identity; default requires official Essentials')
    parser.add_argument('--controlled-qt-sdk-receipt-sha256',
                        help='Exact audited SDK receipt digest; required with the receipt')


def resolve_arguments(args, expected_version: str) -> dict | None:
    receipt = args.controlled_qt_sdk_receipt
    digest = args.controlled_qt_sdk_receipt_sha256
    if bool(receipt) != bool(digest):
        raise RuntimeError('Controlled Qt receipt and exact digest must be supplied together')
    return source_identity(receipt, digest, expected_version) if receipt else None
