"""Short native Qt6.12 bootstrap CA probe; never qualifies a source OpenSSL4 stack."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import ssl
import subprocess
import sys
import sysconfig
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def trust_rejected(labels: list[str]) -> bool:
    reasons = {'UnableToGetIssuerCertificate', 'UnableToGetLocalIssuerCertificate',
        'UnableToVerifyFirstCertificate', 'SelfSignedCertificateInChain', 'CertificateUntrusted',
        'CertificateRejected', 'CertificateRevoked', 'CertificateBlacklisted'}
    invalid_fixture = {'HostNameMismatch', 'CertificateExpired', 'CertificateNotYetValid', 'NoSslSupport'}
    return bool(reasons.intersection(labels)) and not invalid_fixture.intersection(labels)


def manual_chain_outcome(labels: list[str], *, supported: bool) -> dict:
    """An unsupported verifier's empty result is neither acceptance nor rejection."""
    return {'accepted': not labels if supported else None,
            'trust_rejected': trust_rejected(labels) if supported else None,
            'errors': labels, 'manual_verification_supported': supported}


def fetch_inputs(output: Path) -> dict:
    spec = json.loads((REPO / '.github/scripts/provider_ca_security_sources.json').read_text())
    context = ssl.create_default_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    directory = output / 'inputs'
    directory.mkdir(exist_ok=True)
    for item in spec['sources']:
        with urllib.request.urlopen(item['url'], context=context, timeout=90) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('CA fixture HTTPS downgrade rejected')
            data = response.read()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError('Changed reviewed CA fixture: ' + item['name'])
        (directory / item['name']).write_bytes(data)
    return spec


def backend_probe(output: Path, name: str) -> dict:
    from PySide6.QtCore import QCoreApplication, QCryptographicHash, QDateTime, qVersion
    from PySide6.QtNetwork import QSsl, QSslCertificate, QSslConfiguration, QSslSocket

    app = QCoreApplication([])
    assert app is not None and qVersion() == '6.12.0'
    result = {'backend': name, 'scope': 'Official Qt6.12 native host bootstrap; not controlled OpenSSL4 or final package'}
    if not QSslSocket.setActiveBackend(name) or not QSslSocket.supportsSsl():
        return {**result, 'available': False, 'result': 'Backend TLS integration unavailable on this host; not a PASS'}
    result.update(available=True, backend=QSslSocket.activeBackend(),
                  build_library=QSslSocket.sslLibraryBuildVersionString(),
                  runtime_library=QSslSocket.sslLibraryVersionString())
    features = QSslSocket.supportedFeatures(name)
    manual = QSsl.SupportedFeature.CertificateVerification in features
    result['supported_features'] = [feature.name for feature in features]
    result['manual_verification_supported'] = manual
    roots = QSslConfiguration.systemCaCertificates()
    def fingerprint(c: QSslCertificate) -> str:
        return bytes(c.digest(QCryptographicHash.Algorithm.Sha256)).hex()
    result['default_root_fingerprints'] = sorted({fingerprint(c) for c in roots})
    metadata = json.loads((output / 'inputs/impacted-intermediates.json').read_text())
    result['key_encoding'] = []
    for item in metadata:
        certificates = QSslCertificate.fromData(item['pem'].encode())
        assert len(certificates) == 1 and fingerprint(certificates[0]) == item['sha256'].lower()
        encoded = bytes(certificates[0].publicKey().toDer())
        result['key_encoding'].append({'certificate': item['sha256'].lower(), 'name': item['name'],
            'expected_spki': item['spki_sha256'].lower(), 'qt_public_der_sha256': hashlib.sha256(encoded).hexdigest(),
            'matches_spki': hashlib.sha256(encoded).hexdigest() == item['spki_sha256'].lower(),
            'qt_blacklisted': certificates[0].isBlacklisted()})
    now = QDateTime.currentDateTimeUtc()
    rows = []
    with zipfile.ZipFile(output / 'inputs/chains.zip') as archive:
        names = sorted(n for n in archive.namelist() if n.endswith('.pem'))
        assert len(names) == 16
        for filename in names:
            chain = QSslCertificate.fromData(archive.read(filename))
            assert len(chain) >= 2 and all(c.effectiveDate() <= now < c.expiryDate() for c in chain), filename
            hostnames = chain[0].subjectAlternativeNames().get(QSsl.AlternativeNameEntryType.DnsEntry, [])
            assert hostnames and not hostnames[0].startswith('*'), filename
            errors = QSslCertificate.verify(chain, hostnames[0]) if manual else []
            labels = [e.error().name for e in errors]
            rows.append({'fixture': filename, 'hostname': hostnames[0], **manual_chain_outcome(labels, supported=manual)})
    result['chains'] = rows
    connection = QSslSocket()
    connection.setPeerVerifyMode(QSslSocket.PeerVerifyMode.VerifyPeer)
    errors = []
    connection.sslErrors.connect(lambda values: errors.extend(e.error().name for e in values))
    connection.connectToHostEncrypted('www.python.org', 443)
    encrypted = connection.waitForEncrypted(20000)
    result['ordinary_default_handshake'] = {'host': 'www.python.org', 'encrypted': encrypted,
        'errors': errors, 'socket_error': connection.errorString(),
        'peer_sha256': fingerprint(connection.peerCertificate()) if encrypted else None}
    connection.abort()
    result['result'] = 'INCONCLUSIVE manual certificate verification unsupported; native socket evidence required' if not manual else (
        'BLOCKED compromised chain accepted' if any(r['accepted'] for r in rows) else (
        'PASS bootstrap default-policy probe only' if encrypted and not errors and all(r['trust_rejected'] for r in rows)
        else 'INCONCLUSIVE default handshake or chain rejection cause'))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--backend')
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    assert head == os.environ['EXPECTED_SHA'] == os.environ['GITHUB_SHA']
    assert platform.python_version() == '3.14.10' and not sysconfig.get_config_var('Py_GIL_DISABLED')
    actual = platform.machine().lower()
    assert actual in ({'arm64', 'aarch64'} if os.environ['EXPECTED_ARCH'] == 'arm64' else {'amd64', 'x86_64'})
    import PySide6
    import shiboken6
    from PySide6.QtNetwork import QSslSocket

    assert PySide6.__version__ == shiboken6.__version__ == '6.12.0'
    if args.backend:
        result = backend_probe(args.output_dir, args.backend)
        (args.output_dir / ('backend-' + args.backend + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2), flush=True)
        return
    spec = fetch_inputs(args.output_dir)
    results = []
    for backend in QSslSocket.availableBackends():
        if backend not in {'openssl', 'schannel', 'securetransport'}:
            continue
        child = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()),
            '--output-dir', str(args.output_dir.resolve()), '--backend', backend], capture_output=True, text=True)
        (args.output_dir / ('backend-' + backend + '.log')).write_text(child.stdout + child.stderr)
        child.check_returncode()
        results.append(json.loads((args.output_dir / ('backend-' + backend + '.json')).read_text()))
    active = [row for row in results if row['available']]
    report = {'source_sha': head, 'scope': __doc__, 'native_architecture': actual,
              'bootstrap_python': platform.python_version(), 'python_ssl': ssl.OPENSSL_VERSION,
              'pyside': PySide6.__version__, 'inputs': spec, 'backends': results,
              'result': 'PASS bootstrap policies only' if active and all(row['result'].startswith('PASS') for row in active) else 'BLOCKED; inspect actual provider outcomes before source rebuilds'}
    (args.output_dir / 'provider-ca-bootstrap.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)
    assert report['result'].startswith('PASS'), report['result']


if __name__ == '__main__':
    main()
