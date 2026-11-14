from __future__ import annotations

import json
from pathlib import Path

import pytest
from probe_setuptools_build import (
    IMPORTS,
    backend_imports,
    candidate_metadata,
    isolated_imports,
    selected_versions,
)


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


@pytest.mark.parametrize('stage', ['baseline', 'adopted', 'unreviewed'])
def test_live_metadata_adoption_preserves_the_exact_qualified_pep517_input(stage: str) -> None:
    baseline = '[build-system]\nrequires = ["setuptools==84.2.1", "wheel==0.48.0"]\n[project]\nname = "fixture"\ndependencies = ["requests==2.34.2"]\n'
    spec = {'requirements': ['setuptools==84.2.1', 'wheel==0.48.0', 'packaging==26.3']}
    expected = baseline.replace('["setuptools==84.2.1", "wheel==0.48.0"]', json.dumps(spec['requirements']))
    if stage == 'unreviewed':
        with pytest.raises(ValueError, match='Unreviewed'):
            candidate_metadata(baseline.replace('84.2.1', '0.0'), spec)
    else:
        assert candidate_metadata(expected if stage == 'adopted' else baseline, spec) == expected


@pytest.mark.parametrize('platform_prefix', ['/tmp/controlled/venv', 'C:/controlled/venv'])
def test_actual_nonisolated_source_worker_requires_every_external_provider(platform_prefix: str) -> None:
    lines = trace().replace('/tmp/pip-build-env-case/overlay', platform_prefix)
    assert set(backend_imports(lines, platform_prefix)) == set(IMPORTS)
    with pytest.raises(ValueError, match='Missing actual'):
        backend_imports(lines, platform_prefix + '-other')
    with pytest.raises(ValueError, match='Missing actual'):
        backend_imports(lines.replace(platform_prefix, platform_prefix + '-other'), platform_prefix)
    with pytest.raises(ValueError, match='fallback'):
        backend_imports(lines + '\n# code object from /foreign/setuptools/_vendor/packaging/version.py', platform_prefix)


def test_source_builder_constraints_match_the_six_native_qualified_contract() -> None:
    scripts = Path(__file__).resolve().parents[1] / '.github/scripts'
    spec = json.loads((scripts / 'setuptools_build_probe_sources.json').read_text())
    assert (scripts / 'source_build_requirements.txt').read_text().splitlines() == spec['requirements']
    assert (scripts / 'source_build_constraints.txt').read_text().splitlines() == spec['build_constraints']


def test_pip_frontend_vendor_is_not_a_setuptools_backend_fallback() -> None:
    lines = trace().replace('/tmp/pip-build-env-case/overlay', '/native/venv')
    pip = "# code object from '/native/venv/lib/python3.14/site-packages/pip/_vendor/packaging/__init__.py'"
    assert set(backend_imports(pip + '\n' + lines, '/native/venv')) == set(IMPORTS)
    with pytest.raises(ValueError, match='fallback'):
        backend_imports(pip + '\n' + lines.replace('/site-packages/jaraco/text/', '/site-packages/setuptools/_vendor/jaraco/text/'), '/native/venv')
