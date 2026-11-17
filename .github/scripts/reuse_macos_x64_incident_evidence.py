"""Reuse original Qt incident tests only for the exact unchanged loaded providers."""
from __future__ import annotations

import hashlib
import json
import platform
import re
import ssl
from pathlib import Path

SCRIPTS = Path(__file__).parent


def reuse(output: Path, backend: str, loaded_paths: list[Path]) -> dict:
    spec = json.loads((SCRIPTS / 'macos_x64_bound_sdk_sources.json').read_text())
    intake = json.loads((output / 'compiled-sdk-intake.json').read_text())
    assert intake['original'] == spec and intake['verified_paths'] > 0
    original = output / 'original-native-results'
    raw_receipt = (original / 'macos-runtime-sdk.json').read_bytes()
    assert hashlib.sha256(raw_receipt).hexdigest() == spec['receipt_sha256']
    receipt = json.loads(raw_receipt)
    assert receipt['complete_pilot'] and receipt['source_sha'] == spec['source_sha']
    assert platform.mac_ver()[0] == spec['os_version'], 'Changed native OS: repeat incident qualification'
    original_roots = (original / 'keychain-system-roots.pem').read_bytes()
    assert hashlib.sha256(original_roots).hexdigest() == spec['keychain_pem_sha256']

    def anchors(raw: bytes) -> set[str]:
        certificates = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', raw.decode(), re.S)
        assert certificates
        return {hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest() for cert in certificates}

    assert anchors((output / 'keychain-system-roots.pem').read_bytes()) == anchors(original_roots), 'Changed Keychain roots: repeat incident qualification'
    root = Path(receipt['original_work_root'])
    providers = [path.resolve() for path in loaded_paths if path.name in {'QtCore', 'QtNetwork', 'libssl.4.dylib', 'libcrypto.4.dylib'} or 'tls' in path.parts]
    names = {path.name for path in providers}
    assert names >= {'QtCore', 'QtNetwork', 'libq' + backend + 'backend.dylib'}, ('Missing actual TLS provider', names)
    measured = {}
    for path in providers:
        assert path.is_relative_to(root), ('Foreign loaded TLS provider', path)
        entry = receipt['paths'][path.relative_to(root).as_posix()]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == entry['sha256'] and path.stat().st_size == entry['bytes'], ('Changed TLS provider: rerun incident suite', path)
        measured[str(path)] = digest
    filename = 'qt-incident-' + backend + '.json'
    raw = (original / filename).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == spec['incident_reports'][filename]
    result = json.loads(raw)
    assert result['backend'] == backend and result['native_tls_refusals'] == 14
    assert len(result['cases']) == 16 and result['offline_blacklist_checks'] == 2
    result['execution'] = {'mode': 'reused unchanged original native evidence; not re-executed in this consumer run',
                           'source_sha': spec['source_sha'], 'run': spec['run'], 'artifact': spec['artifact'],
                           'report_sha256': spec['incident_reports'][filename], 'actual_loaded_provider_sha256': measured,
                           'scope': 'Same original Qt/TLS bytes. Fresh default trust, fixture TLS, GUI and affected image consumers remain mandatory. No network-failure fallback.'}
    (output / filename).write_text(json.dumps(result, indent=2) + '\n')
    return result
