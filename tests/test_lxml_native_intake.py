from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from intake_lxml_native import verify_zip


def fixture(changed: str) -> tuple[bytes, dict]:
    wheel_buffer = io.BytesIO()
    native = b'closed native module fixture'
    with zipfile.ZipFile(wheel_buffer, 'w') as wheel:
        wheel.writestr('lxml/etree.so', native)
    wheel_bytes = wheel_buffer.getvalue()
    report = {'source_sha': 'execution-head', 'compiled_source_sha': 'compiled-head'}
    if changed == 'lineage':
        report['compiled_source_sha'] = 'relabeled-head'
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, 'w') as archive:
        archive.writestr('lxml-native-results.json', json.dumps(report))
        archive.writestr('wheels/lxml-6.1.3-test.whl', wheel_bytes)
    data = outer.getvalue()
    expected = {'zip_bytes': len(data), 'zip_sha256': hashlib.sha256(data).hexdigest(),
                'source_sha': 'execution-head', 'compiled_source_sha': 'compiled-head',
                'wheel_sha256': hashlib.sha256(wheel_bytes).hexdigest(),
                'native_image_sha256': {'etree.so': hashlib.sha256(native).hexdigest()}}
    if changed == 'wheel':
        expected['wheel_sha256'] = 'unreviewed wheel'
    return data, expected


@pytest.mark.parametrize('changed', ['lineage', 'wheel'])
def test_wrong_parser_lineage_or_wheel_is_rejected_before_install(changed):
    data, expected = fixture(changed)
    with pytest.raises((AssertionError, ValueError)):
        verify_zip(data, expected)


def test_intake_keeps_execution_and_compiled_source_identities_distinct():
    data, expected = fixture('none')
    assert verify_zip(data, expected)[0] == 'lxml-6.1.3-test.whl'
