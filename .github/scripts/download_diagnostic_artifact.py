"""Read a same-repository diagnostic artifact through verified GitHub REST HTTPS."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request

REPOSITORY = 'mrc-labs/PlayStoreAppAudit'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: object, code: int,
                         msg: str, headers: object, newurl: str) -> None:
        return None


class _HttpsRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: urllib.request.Request, fp: object, code: int,
                         msg: str, headers: object, newurl: str) -> urllib.request.Request | None:
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or not target.hostname or target.username or target.password:
            raise ValueError('Artifact HTTPS downgrade rejected')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_artifact(artifact_id: int) -> tuple[dict, bytes]:
    """Callers must still enforce their exact source/ID/size/digest contract."""
    if not isinstance(artifact_id, int) or artifact_id <= 0:
        raise ValueError('Positive diagnostic artifact ID required')
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        raise ValueError('Read-only artifact token required')
    context = ssl.create_default_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    direct = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _NoRedirect())
    api = f'https://api.github.com/repos/{REPOSITORY}/actions/artifacts/{artifact_id}'
    headers = {'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json',
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'PlayStoreAppAudit-diagnostic-intake'}
    try:
        with direct.open(urllib.request.Request(api, headers=headers), timeout=60) as response:
            metadata = json.load(response)
        try:
            with direct.open(urllib.request.Request(api + '/zip', headers=headers), timeout=180) as response:
                return metadata, response.read()
        except urllib.error.HTTPError as redirect:
            if redirect.code != 302:
                raise
            location = redirect.headers.get('Location', '')
            redirect.close()
        target = urllib.parse.urlsplit(location)
        if target.scheme != 'https' or not target.hostname or target.username or target.password:
            raise ValueError('Invalid GitHub artifact HTTPS location')
        # Never forward the GitHub token to the temporary storage URL.
        storage = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _HttpsRedirect())
        request = urllib.request.Request(location, headers={'User-Agent': headers['User-Agent']})
        with storage.open(request, timeout=180) as response:
            if not response.geturl().startswith('https://'):
                raise ValueError('Artifact HTTPS downgrade rejected')
            return metadata, response.read()
    except urllib.error.URLError as error:
        # Do not expose a temporary signed storage URL in logs.
        raise RuntimeError('Diagnostic artifact request failed: ' + str(getattr(error, 'code', type(error).__name__))) from None
