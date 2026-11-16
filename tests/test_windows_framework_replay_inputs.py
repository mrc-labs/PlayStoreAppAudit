import json
from pathlib import Path

import pytest
from replay_windows_current_framework import compiled_inputs

ROOT = Path(__file__).resolve().parents[1]


def test_both_bound_sdks_match_unchanged_actual_compilation_inputs():
    actual = compiled_inputs((ROOT / '.github/scripts/build_windows_current_framework.py').read_text())
    specs = json.loads((ROOT / '.github/scripts/windows_framework_bound_sdks.json').read_text())
    assert set(specs) == {'x64', 'arm64'}
    assert all(spec['compiled_inputs'] == actual for spec in specs.values())


@pytest.mark.parametrize('before,after', [('-openssl-linked', '-openssl-runtime'),
                                         ('--limited-api=yes', '--limited-api=no')])
def test_replay_rejects_changed_framework_or_binding_compilation(before, after):
    source = (ROOT / '.github/scripts/build_windows_current_framework.py').read_text()
    assert before in source
    assert compiled_inputs(source.replace(before, after)) != compiled_inputs(source)
