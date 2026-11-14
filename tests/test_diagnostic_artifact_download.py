from __future__ import annotations

import io
import json
import urllib.error
import urllib.request

import download_diagnostic_artifact as download
import probe_qt_http_limits as probe
import pytest


@pytest.mark.parametrize('location', ['https://storage.example/artifact?secret=temporary',
                                     'http://storage.example/artifact', 'https://user:password@storage.example/file'])
def test_artifact_token_is_not_forwarded_to_storage(monkeypatch, location):
    monkeypatch.setenv('GH_TOKEN', 'test-read-token')
    calls = []

    class Response(io.BytesIO):
        def geturl(self):
            return location

    class Opener:
        def __init__(self, storage):
            self.storage = storage

        def open(self, request, timeout):
            calls.append(request)
            if self.storage:
                assert request.get_header('Authorization') is None
                return Response(b'artifact bytes')
            assert request.get_header('Authorization') == 'Bearer test-read-token'
            assert request.full_url.startswith('https://api.github.com/repos/mrc-labs/PlayStoreAppAudit/')
            if not request.full_url.endswith('/zip'):
                return Response(json.dumps({'id': 42}).encode())
            raise urllib.error.HTTPError(request.full_url, 302, 'Redirect', {'Location': location}, None)

    def opener(*handlers):
        return Opener(any(isinstance(handler, download._HttpsRedirect) for handler in handlers))

    monkeypatch.setattr(download.urllib.request, 'build_opener', opener)
    if location.startswith('https://storage.'):
        assert download.fetch_artifact(42) == ({'id': 42}, b'artifact bytes')
        assert len(calls) == 3
    else:
        with pytest.raises(ValueError, match='Invalid GitHub artifact HTTPS location'):
            download.fetch_artifact(42)
        assert len(calls) == 2


@pytest.mark.parametrize('location', ['http://storage.example/file', 'https://user@storage.example/file'])
def test_storage_redirect_cannot_downgrade_or_embed_credentials(location):
    with pytest.raises(ValueError, match='HTTPS downgrade'):
        download._HttpsRedirect().redirect_request(
            urllib.request.Request('https://storage.example/original'), None, 302, '', {}, location)


def test_download_failure_does_not_log_signed_url(monkeypatch):
    monkeypatch.setenv('GH_TOKEN', 'test-token')

    class Opener:
        def open(self, *args, **kwargs):
            raise urllib.error.URLError('https://storage.example/?private-signed-query')

    monkeypatch.setattr(download.urllib.request, 'build_opener', lambda *a: Opener())
    with pytest.raises(RuntimeError) as error:
        download.fetch_artifact(42)
    assert 'private-signed-query' not in str(error.value) and 'test-token' not in str(error.value)


@pytest.mark.parametrize('field', ['id', 'run_id', 'head_sha', 'repository_id', 'head_repository_id', 'expired', 'digest', 'size_in_bytes', 'truncated'])
def test_changed_sdk_identity_stops_before_zip_open(monkeypatch, field):
    run = {'id': 43570953718, 'head_sha': probe.COMPILED_SOURCE,
           'repository_id': 1334403620, 'head_repository_id': 1334403620}
    metadata = {'id': probe.COMPILED_ARTIFACT, 'workflow_run': run, 'expired': False,
                'size_in_bytes': 138377365, 'digest': 'sha256:' + probe.COMPILED_ZIP_SHA256}
    if field == 'run_id':
        run['id'] = 0
    elif field in run and field != 'id':
        run[field] = 'changed'
    elif field != 'truncated':
        metadata[field] = 'changed'

    class UnreadPayload:
        def __len__(self):
            raise AssertionError('Invalid metadata must be rejected before reading the payload')

    opened = []
    monkeypatch.setattr(probe.zipfile, 'ZipFile', lambda *args: opened.append(args))
    with pytest.raises(ValueError, match='immutable Qt diagnostic SDK'):
        probe.verified_sdk(metadata, b'truncated' if field == 'truncated' else UnreadPayload())
    assert opened == []
