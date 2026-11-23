"""Transfer one of seven exact retained ZIPs from temporary draft to Actions."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from download_diagnostic_artifact import _HttpsRedirect, _NoRedirect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact', type=int, required=True)
    args = parser.parse_args()
    selected = json.loads(Path(__file__).with_name('retained_original_archives.json').read_text())[str(args.artifact)]
    original, staging = selected['original'], selected['staging']
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA']
    assert staging['release'] == 454903125
    api = 'https://api.github.com/repos/mrc-labs/PlayStoreAppAudit/releases/assets/' + str(staging['asset'])
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _NoRedirect())
    headers = {'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json'}
    try:
        with opener.open(urllib.request.Request(api, headers=headers), timeout=60) as response:
            metadata = json.load(response)
        assert metadata['id'] == staging['asset'] and metadata['state'] == 'uploaded'
        assert metadata['size'] == original['bytes']
        assert metadata['digest'] == 'sha256:' + original['sha256']
        headers['Accept'] = 'application/octet-stream'
        try:
            response = opener.open(urllib.request.Request(api, headers=headers), timeout=180)
        except urllib.error.HTTPError as redirect:
            assert redirect.code == 302
            location = redirect.headers['Location']
            redirect.close()
            target_url = urllib.parse.urlsplit(location)
            assert target_url.scheme == 'https' and target_url.hostname
            assert not target_url.username and not target_url.password
            # Never forward repository credentials to object storage.
            storage = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), _HttpsRedirect())
            response = storage.open(urllib.request.Request(location), timeout=180)
        output = Path('retained-original')
        output.mkdir()
        target = output / 'original-input.zip'
        with response, target.open('wb') as stream:
            shutil.copyfileobj(response, stream)
        assert target.stat().st_size == original['bytes']
        with target.open('rb') as stream:
            assert hashlib.file_digest(stream, 'sha256').hexdigest() == original['sha256']
        receipt = {'original': original, 'recovery_source_sha': os.environ['GITHUB_SHA'],
                   'recovery_run': int(os.environ['GITHUB_RUN_ID']),
                   'staging_asset': staging['asset'], 'identity': 'Unchanged original ZIP; no component compiled'}
        (output / 'RECOVERY.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
        print('PASS unchanged original', args.artifact, original['sha256'])
    except urllib.error.URLError:
        raise RuntimeError('Temporary recovery download failed; signed URL omitted') from None


if __name__ == '__main__':
    main()
