"""Native source-level relocation/configuration check; not a packaged candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--backend', choices=['openssl', 'securetransport'])
    args = parser.parse_args()
    assert sys.platform == 'darwin'
    output = args.output.resolve()
    if args.backend:
        from PySide6.QtWidgets import QApplication
        from verify_macos_arm64_runtime_pilot import qt_checks
        from verify_native_runtime_pilot import certificate_material

        app = QApplication([])
        assert app.platformName() == 'cocoa'
        folder = output / ('portable-trust-' + args.backend + '-certificates')
        folder.mkdir()
        result = qt_checks(certificate_material(folder), args.backend)
        result['scope'] = 'Actual native Qt provider after Python private-PEM configuration; Keychain anchors remain distinct'
        (output / ('portable-trust-qt-' + args.backend + '.json')).write_text(json.dumps(result, indent=2))
        return
    assert not os.environ.get('SSL_CERT_FILE') and not os.environ.get('SSL_CERT_DIR')
    import certifi

    from playstore_app_audit.platform.certificates import configure_packaged_python_trust
    from playstore_app_audit.services.scraper_transport import install_scraper_transport_timeout

    assert install_scraper_transport_timeout()
    from google_play_scraper.utils import request

    destination = output / 'relocated-python-trust'
    destination.mkdir()
    bundle = destination / 'cacert.pem'
    original = Path(certifi.where())
    shutil.copy2(original, bundle)
    assert bundle.read_bytes() == original.read_bytes()
    with patch.object(certifi, 'where', return_value=str(bundle)):
        configure_packaged_python_trust(packaged=True)
    assert ssl.get_default_verify_paths().cafile == str(bundle)
    context = ssl.create_default_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    with (
        socket.create_connection(('www.python.org', 443), timeout=20) as connection,
        context.wrap_socket(connection, server_hostname='www.python.org') as secure,
    ):
        protocol = secure.version()
        peer = hashlib.sha256(secure.getpeercert(binary_form=True)).hexdigest()
    # Actual dependency transport, no explicit test cafile/context and no
    # SSL verification bypass inherited from upstream's import side effect.
    body = request.get('https://www.python.org')
    assert '<html' in body.lower()
    report = {'source_sha': os.environ['GITHUB_SHA'], 'pem_sha256': hashlib.sha256(bundle.read_bytes()).hexdigest(),
              'configured_default_cafile': str(bundle), 'protocol': protocol, 'peer_sha256': peer,
              'verify_mode': 'CERT_REQUIRED', 'check_hostname': True, 'scraper_verified_default_https': 'PASS',
              'scope': 'Source-level configured PEM relocation and actual default handshake; final Nuitka bundle acceptance remains required'}
    (output / 'portable-python-trust.json').write_text(json.dumps(report, indent=2))
    for backend in ['openssl', 'securetransport']:
        with (output / ('portable-trust-' + backend + '.log')).open('w') as log:
            subprocess.run([sys.executable, __file__, '--output', str(output), '--backend', backend],
                           stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
