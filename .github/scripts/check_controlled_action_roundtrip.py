"""Exercise real controlled Action fixture bytes, exclusions and native runtimes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare', 'verify'])
    args = parser.parse_args()
    assert os.environ['GITHUB_SHA'] == os.environ['EXPECTED_SHA'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    arch = os.environ['EXPECTED_ARCH']
    assert platform.machine().lower() in ({'arm64', 'aarch64'} if arch == 'arm64' else {'amd64', 'x86_64'})
    assert sys.version_info[:2] == (3, 14) and sys.version_info.releaselevel == 'final'
    assert not sysconfig.get_config_var('Py_GIL_DISABLED')
    report = Path('controlled-action-native-evidence')
    report.mkdir(exist_ok=True)
    node = json.loads((Path(os.environ['RUNNER_TEMP']) / 'controlled-node.json').read_text())
    assert node['arch'] == arch and node['version'].startswith('v24.')
    expected = {'alpha.txt': b'actual controlled upload/download\n',
                'nested/\u00e1rchive.bin': bytes(range(256))}
    if args.mode == 'prepare':
        fixture = Path('controlled-action-fixture')
        for name, body in {**expected, 'excluded.txt': b'never upload'}.items():
            path = fixture / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
        spec = json.loads(Path('.github/scripts/controlled_actions_bundles.json').read_text())
        for item in spec['actions']:
            for name, digest in item['files'].items():
                raw = (Path('.github/actions') / ('controlled-' + item['action']) / name).read_bytes()
                assert len(raw) == digest['bytes'] and hashlib.sha256(raw).hexdigest() == digest['sha256']
    else:
        received = Path('controlled-action-received')
        assert {p.relative_to(received).as_posix() for p in received.rglob('*') if p.is_file()} == set(expected)
        for name, body in expected.items():
            assert (received / name).read_bytes() == body
        result = {'source_sha': os.environ['GITHUB_SHA'], 'machine': platform.machine(),
                  'python': platform.python_version(), 'gil_disabled': False, 'node': node,
                  'payload_sha256': {name: hashlib.sha256(body).hexdigest() for name, body in expected.items()},
                  'result': 'PASS native controlled checkout/setup/upload/download; exclusion and UTF8/binary byte identity',
                  'scope': 'Action consumers only; no runtime/framework rebuild or release candidate'}
        (report / 'native-action-roundtrip.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
