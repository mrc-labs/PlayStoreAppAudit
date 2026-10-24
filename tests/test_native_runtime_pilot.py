from __future__ import annotations

import hashlib
import json
import struct
import zlib
from pathlib import Path

from verify_native_runtime_pilot import png_fixture

ROOT = Path(__file__).resolve().parents[1]


def test_pilot_patch_and_official_sources_are_hash_bound() -> None:
    spec = json.loads((ROOT / '.github/scripts/native_runtime_pilot_sources.json').read_text())
    patch = spec['cpython_patch']
    assert hashlib.sha256((ROOT / patch['path']).read_bytes()).hexdigest() == patch['sha256']
    assert len(spec['sources']) == 8
    for item in spec['sources']:
        assert item['url'].startswith('https://')
        assert len(item['sha256']) == 64
        assert int(item['sha256'], 16) > 0


def test_malformed_metadata_corpus_reaches_png_end_read_with_valid_container_crc() -> None:
    for kind in (b'zTXt', b'iTXt', b'iCCP'):
        image = png_fixture(kind, b'not-deflate')
        assert image.startswith(b'\x89PNG\r\n\x1a\n')
        position, chunks = 8, []
        while position < len(image):
            size = struct.unpack_from('!I', image, position)[0]
            chunk = image[position + 4:position + 8 + size]
            crc = struct.unpack_from('!I', image, position + 8 + size)[0]
            assert crc == zlib.crc32(chunk)
            chunks.append(chunk[:4])
            position += size + 12
        assert chunks == [b'IHDR', b'IDAT', kind, b'IEND']
        assert position == len(image)


def test_native_pilot_is_single_target_sha_guarded_and_cannot_produce_a_candidate() -> None:
    workflow = (ROOT / '.github/workflows/ui-style-audit.yml').read_text()
    capture, pilot = workflow.split('\n  runtime-pilot:', 1)
    assert 'if: ${{ !inputs.runtime_pilot }}' in capture
    assert 'runs-on: ubuntu-22.04' in pilot
    assert 'matrix:' not in pilot
    assert 'test "$EXPECTED_SHA" = "${{ github.sha }}"' in pilot
    assert 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"' in pilot
    assert 'diagnostic-runtime-framework-' in pilot
    assert 'PlayStoreAppAudit-v' not in pilot
    builder = (ROOT / '.github/scripts/build_native_runtime_pilot.sh').read_text()
    for excluded in ('docker ', 'pyside6-deploy', 'python -m nuitka', 'sign-windows', 'assemble-release'):
        assert excluded not in builder
