"""Reuse only unchanged Python upstream suites from one immutable diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import zipfile
from pathlib import Path

from download_diagnostic_artifact import fetch_artifact

REPO = Path(__file__).resolve().parents[2]
SOURCE = '69c3d04a7b3af5db8c8847f5a7e7df75a586dcf2'
ARTIFACT = 14098850639
DIGEST = 'd33de909db30a6f56ff438ec57f08091c72e486ffbb0b68b257de6f7c883579a'


def unchanged_inputs(archive: zipfile.ZipFile) -> None:
    for name in ['native_runtime_pilot_sources.json', 'source_build_requirements.txt', 'source_build_constraints.txt']:
        member = name if name.endswith('.json') else 'build-dependencies/' + name
        original = archive.read(member)
        current = (REPO / '.github/scripts' / name).read_bytes()
        if name.endswith('.json'):
            same = json.loads(original) == json.loads(current)
        else:
            same = original.replace(b'\r\n', b'\n') == current.replace(b'\r\n', b'\n')
        if not same:
            raise ValueError('Changed Python source/build contract requires its upstream suites: ' + name)
    original = json.loads(archive.read('linux_x64_native_delta_sources.json'))
    current = json.loads((REPO / '.github/scripts/linux_x64_native_delta_sources.json').read_text(encoding='utf-8'))
    if original['sources'] != current['sources']:
        raise ValueError('Changed Python providers require upstream suites')
    original = json.loads(archive.read('qt_text_provider_sources.json'))
    current = json.loads((REPO / '.github/scripts/qt_text_provider_sources.json').read_text(encoding='utf-8'))
    if any(original[key] != current[key] for key in ('sources', 'meson')):
        raise ValueError('Changed text-provider inputs require upstream suites')


def evidence(output: Path) -> dict:
    """Fail closed on edited inputs or reports; preserve their actual execution SHA."""
    original = output / 'original-python-14098850639.zip'
    if hashlib.sha256(original.read_bytes()).hexdigest() != DIGEST:
        raise ValueError('Changed original Python evidence ZIP')
    with zipfile.ZipFile(original) as archive:
        unchanged_inputs(archive)
        xml = archive.read('cpython-native-regressions.xml')
    saved = output / 'reused-python/cpython-native-regressions.xml'
    if saved.read_bytes() != xml:
        raise ValueError('Changed reused Python suite report')
    return {'source_sha': SOURCE, 'run': 43554126327, 'artifact': ARTIFACT, 'zip_sha256': DIGEST,
            'scope': 'Unchanged Python/provider upstream suites only; overall original run failed at QtGui',
            'report_sha256': hashlib.sha256(xml).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    metadata, data = fetch_artifact(ARTIFACT)
    os.environ.pop('GH_TOKEN', None)
    os.environ.pop('GITHUB_TOKEN', None)
    if (metadata['id'] != ARTIFACT or metadata['expired'] or len(data) != 278768547
            or metadata['size_in_bytes'] != len(data) or metadata['digest'] != 'sha256:' + DIGEST
            or metadata['workflow_run']['id'] != 43554126327
            or metadata['workflow_run']['head_sha'] != SOURCE
            or metadata['workflow_run']['head_repository_id'] != 1334403620
            or hashlib.sha256(data).hexdigest() != DIGEST):
        raise ValueError('Changed immutable Python diagnostic evidence')
    output = args.output_dir
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        unchanged_inputs(archive)
        saved = output / 'reused-python'
        saved.mkdir()
        for name in ['cpython-native-regressions.xml', 'cpython-regressions.xml', 'tarfile-security-regression.log']:
            (saved / name).write_bytes(archive.read(name))
    (output / 'original-python-14098850639.zip').write_bytes(data)
    report = evidence(output)
    (output / 'reused-python-provenance.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
