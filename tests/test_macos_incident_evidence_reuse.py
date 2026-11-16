import hashlib
import json

import pytest
import reuse_macos_x64_incident_evidence as evidence


@pytest.mark.parametrize('fault', [None, 'bytes', 'foreign', 'missing', 'report', 'receipt'])
def test_incident_reuse_is_closed_to_original_reports_and_actual_loaded_bytes(tmp_path, monkeypatch, fault):
    root = tmp_path / 'sdk'
    output = tmp_path / 'output'
    original = output / 'original-native-results'
    original.mkdir(parents=True)
    paths = []
    entries = {}
    for name in ['QtCore', 'QtNetwork', 'libqopensslbackend.dylib']:
        path = root / 'prefix/qt' / ('plugins/tls' if name.endswith('.dylib') else 'lib') / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(name.encode())
        entries[path.relative_to(root).as_posix()] = {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        paths.append(path)
    receipt = json.dumps({'source_sha': 'a' * 40, 'complete_pilot': True, 'original_work_root': str(root), 'paths': entries}).encode()
    report = json.dumps({'backend': 'openssl', 'native_tls_refusals': 14, 'cases': [{}] * 16, 'offline_blacklist_checks': 2}).encode()
    spec = {'source_sha': 'a' * 40, 'run': 1, 'artifact': 2, 'receipt_sha256': hashlib.sha256(receipt).hexdigest(),
            'incident_reports': {'qt-incident-openssl.json': hashlib.sha256(report).hexdigest()}}
    monkeypatch.setattr(evidence, 'SCRIPTS', tmp_path)
    (tmp_path / 'macos_x64_bound_sdk_sources.json').write_text(json.dumps(spec))
    (output / 'compiled-sdk-intake.json').write_text(json.dumps({'original': spec, 'verified_paths': 3}))
    (original / 'macos-runtime-sdk.json').write_bytes(receipt + (b' ' if fault == 'receipt' else b''))
    (original / 'qt-incident-openssl.json').write_bytes(report + (b' ' if fault == 'report' else b''))
    if fault == 'bytes':
        paths[0].write_bytes(b'new provider')
    elif fault == 'foreign':
        paths[0] = tmp_path / 'foreign/QtCore'
    elif fault == 'missing':
        paths.pop()
    if fault:
        with pytest.raises(AssertionError):
            evidence.reuse(output, 'openssl', paths)
    else:
        result = evidence.reuse(output, 'openssl', paths)
        assert result['execution']['source_sha'] == 'a' * 40
        assert 'not re-executed' in result['execution']['mode']
        assert len(result['execution']['actual_loaded_provider_sha256']) == 3
