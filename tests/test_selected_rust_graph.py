import pytest
from probe_selected_rust_graphs import qualified_ruff_lock, ruff_codemod_consumer, selected_packages


def test_selected_graph_deduplicates_versions_without_losing_parallel_majors():
    assert selected_packages('root v1.0 (/source)\ncrate v2.0\ncrate v2.0 (*)\ncrate v1.0\n') == [
        {'name': 'crate', 'version': '1.0'}, {'name': 'crate', 'version': '2.0'},
        {'name': 'root', 'version': '1.0'}]


def test_empty_or_diagnostic_only_output_cannot_qualify_a_graph():
    with pytest.raises(ValueError, match='Empty selected Rust'):
        selected_packages('error: could not resolve dependencies\n')


def test_native_consumers_reject_changed_candidate_lock(tmp_path):
    from pathlib import Path

    original = Path(__file__).resolve().parents[1] / '.github/sources/ruff-0.17.5-psaa.Cargo.lock'
    data = qualified_ruff_lock(original)
    changed = tmp_path / 'Cargo.lock'
    changed.write_bytes(data + b'\n')
    with pytest.raises(ValueError, match='qualified lock hash mismatch'):
        qualified_ruff_lock(changed)


def test_codemod_harness_exercises_real_fixes_before_native_compilation(tmp_path):
    from pathlib import Path

    from ruff._find_ruff import find_ruff_bin

    ruff_codemod_consumer(Path(find_ruff_bin()), tmp_path)
