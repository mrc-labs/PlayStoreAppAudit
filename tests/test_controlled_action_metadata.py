from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.github/scripts'))
from build_controlled_actions import action_metadata  # noqa: E402


@pytest.mark.parametrize('prefix', ['', '# Upstream comment\n', '\n'])
def test_action_rename_preserves_comment_and_does_not_duplicate_yaml_name(prefix: str) -> None:
    original = prefix + "name: 'Setup Python'\ndescription: original\nruns:\n  using: node24\n"
    assert action_metadata(original, 'setup-python') == original.replace("name: 'Setup Python'", 'name: PSAA controlled setup-python')


def test_ambiguous_original_name_is_rejected() -> None:
    with pytest.raises(AssertionError, match='Exactly one'):
        action_metadata('name: first\nname: second\n', 'setup-python')


def test_adopted_bundles_match_qualified_native_source_bytes_and_static_assets() -> None:
    root = Path(__file__).resolve().parents[1]
    spec = json.loads((root / '.github/scripts/controlled_actions_bundles.json').read_text(encoding='utf-8'))
    assert {a['action'] for a in spec['actions']} == {'checkout', 'setup-python', 'upload-artifact', 'download-artifact'}
    for item in spec['actions']:
        directory = root / '.github/actions' / ('controlled-' + item['action'])
        for name, expected in item['files'].items():
            content = (directory / name).read_bytes()
            assert len(content) == expected['bytes'] and hashlib.sha256(content).hexdigest() == expected['sha256'], (item['action'], name)
    assert (root / '.github/actions/controlled-setup-python/.github/python.json').is_file()
