from __future__ import annotations

import pytest
from probe_setuptools_build import IMPORTS, isolated_imports, selected_versions


def trace() -> str:
    return '\n'.join('# code object from /tmp/pip-build-env-case/overlay/lib/python3.14/site-packages/' + fragment + '__init__.py'
                     for fragment in IMPORTS.values())


@pytest.mark.parametrize('failure', ['fallback', 'other-fallback', 'global', 'missing'])
def test_only_actual_external_isolated_backend_imports_qualify(failure: str) -> None:
    lines = trace()
    if failure == 'fallback':
        lines = lines.replace('/site-packages/jaraco/text/', '/site-packages/setuptools/_vendor/jaraco/text/')
    elif failure == 'other-fallback':
        lines += '\n# code object from /tmp/pip-build-env-case/overlay/lib/python3.14/site-packages/setuptools/_vendor/tomli/__init__.py'
    elif failure == 'global':
        lines = lines.replace('pip-build-env-case', 'global-build-venv')
    else:
        lines = '\n'.join(line for line in lines.splitlines() if '/jaraco/text/' not in line)
    with pytest.raises(ValueError, match='fallback|Missing actual'):
        isolated_imports(lines)


def test_pep517_code_object_trace_records_every_active_core_provider() -> None:
    actual = isolated_imports(trace())
    assert set(actual) == set(IMPORTS)
    assert all('/pip-build-env-case/overlay/' in line and '_vendor' not in line for line in actual.values())


@pytest.mark.parametrize('entry', ['packaging-25.0', 'unreviewed-package-1.0'])
def test_changed_build_dependency_resolution_cannot_be_silently_accepted(entry: str) -> None:
    spec = {'requirements': ['packaging==26.3'], 'packages': {'packaging': {'version': '26.3'}}}
    with pytest.raises(ValueError, match='Unexpected build dependency'):
        selected_versions('Successfully installed ' + entry, spec)
