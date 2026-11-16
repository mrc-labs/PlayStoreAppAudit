from __future__ import annotations

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
