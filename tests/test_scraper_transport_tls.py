from __future__ import annotations

import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from verify_native_runtime_pilot import certificate_material

from playstore_app_audit.services import scraper_transport


def test_import_gate_restores_a_verified_global_https_factory(monkeypatch):
    monkeypatch.setattr(ssl, '_create_default_https_context', ssl._create_unverified_context)
    assert scraper_transport.install_scraper_transport_timeout()
    context = ssl._create_default_https_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname


def test_wrapper_rejects_explicit_unverified_context():
    wrapped = scraper_transport._with_default_timeout(lambda *a, **kw: pytest.fail('Insecure request forwarded'), 25)
    with pytest.raises(ValueError, match='certificate and hostname'):
        wrapped('https://example.invalid', context=ssl._create_unverified_context())


@pytest.mark.parametrize('case', ['valid', 'hostname', 'untrusted', 'expired'])
def test_real_scraper_transport_verifies_certificates_and_hostname(tmp_path, monkeypatch, case):
    paths = certificate_material(tmp_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'verified fixture')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_context.load_cert_chain(paths['expired' if case == 'expired' else 'valid'], paths['key'])
    server.socket = server_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True)
    thread.start()
    from google_play_scraper.utils import request as request_utils

    monkeypatch.delattr(request_utils, scraper_transport._INSTALLED_MARKER, raising=False)
    monkeypatch.setattr(request_utils, 'urlopen', urlopen)
    assert scraper_transport.install_scraper_transport_timeout()
    # Per-call verification must remain strict even if another dependency
    # subsequently repeats upstream's unsafe global mutation.
    monkeypatch.setattr(ssl, '_create_default_https_context', ssl._create_unverified_context)
    host = '127.0.0.1' if case == 'hostname' else 'localhost'
    kwargs = {} if case == 'untrusted' else {'context': ssl.create_default_context(cafile=str(paths['ca']))}
    try:
        if case == 'valid':
            with request_utils.urlopen(f'https://{host}:{server.server_port}', **kwargs) as response:
                assert response.read() == b'verified fixture'
        else:
            with pytest.raises(URLError) as error:
                request_utils.urlopen(f'https://{host}:{server.server_port}', **kwargs)
            assert isinstance(error.value.reason, ssl.SSLCertVerificationError)
            assert error.value.reason.verify_code == {'hostname': 64, 'untrusted': 20, 'expired': 10}[case]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
