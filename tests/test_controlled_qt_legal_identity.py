import hashlib
import json
from types import SimpleNamespace

import controlled_qt_legal_identity as identity
import prepare_release_legal_bundle as legal
import pytest


@pytest.mark.parametrize('fault', [None, 'digest', 'source', 'outside', 'bytes', 'version', 'official', 'extra'])
def test_source_identity_requires_closed_actual_binding_bytes(tmp_path, monkeypatch, fault):
    root = tmp_path / 'sdk'
    rows = {}
    modules = {}
    for name in ['PySide6', 'shiboken6', 'PySide6.QtCore', 'PySide6.QtGui']:
        package, _, module = name.partition('.')
        relative = f'venv/site-packages/{package}/' + (module + '.so' if module else '__init__.py')
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        rows[relative] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        modules[name] = SimpleNamespace(__file__=str(path), __version__='6.12.0', qVersion=lambda: '6.12.0')
    qt = root / 'prefix/qt/lib/framework'
    qt.parent.mkdir(parents=True)
    qt.write_bytes(b'actual framework')
    rows['prefix/qt/lib/framework'] = {'bytes': qt.stat().st_size, 'sha256': hashlib.sha256(qt.read_bytes()).hexdigest()}
    receipt = {'source_sha': 'invalid' if fault == 'source' else 'a' * 40, 'original_work_root': str(root), 'paths': rows}
    path = tmp_path / 'receipt.json'
    path.write_text(json.dumps(receipt))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(identity.importlib, 'import_module', lambda name: modules[name])
    monkeypatch.setattr(identity.metadata, 'version', lambda name: '6.11.0' if fault == 'version' else '6.12.0')

    def distribution(name):
        if fault == 'official':
            return SimpleNamespace()
        raise identity.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(identity.metadata, 'distribution', distribution)
    if fault == 'outside':
        modules['PySide6.QtCore'].__file__ = str(tmp_path / 'foreign.so')
    if fault == 'bytes':
        qt.write_bytes(b'modified')
    if fault == 'extra':
        (root / 'venv/site-packages/PySide6/foreign.so').write_bytes(b'unindexed')
    if fault:
        with pytest.raises(RuntimeError):
            identity.source_identity(path, '0' * 64 if fault == 'digest' else digest, '6.12.0')
    else:
        report = identity.source_identity(path, digest, '6.12.0')
        assert report['distribution'] == 'PySide6' and report['sdk_source_sha'] == 'a' * 40
        assert report['verified_qt_binding_paths'] == 5


def test_partial_explicit_source_arguments_fail_closed():
    with pytest.raises(RuntimeError, match='supplied together'):
        identity.resolve_arguments(SimpleNamespace(controlled_qt_sdk_receipt='receipt.json', controlled_qt_sdk_receipt_sha256=None), '6.12.0')


def test_controlled_source_graph_retains_actual_distribution_names(tmp_path, monkeypatch):
    monkeypatch.setattr(legal, '_project_dependency_names', lambda root: ['PySide6-Essentials'])
    distributions = {'PySide6': SimpleNamespace(requires=['shiboken6==6.12.0']),
                     'shiboken6': SimpleNamespace(requires=[])}
    monkeypatch.setattr(legal.metadata, 'distribution', lambda name: distributions[name])
    graph, direct = legal._declared_dependency_candidates(tmp_path, qt_distribution='PySide6')
    assert set(graph) == {'pyside6', 'shiboken6'} and direct == {'pyside6'}
    with pytest.raises(RuntimeError, match='Unsupported'):
        legal._declared_dependency_candidates(tmp_path, qt_distribution='invented-official-alias')
