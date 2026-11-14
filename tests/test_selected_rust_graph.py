import pytest
from probe_selected_rust_graphs import selected_packages


def test_selected_graph_deduplicates_versions_without_losing_parallel_majors():
    assert selected_packages('root v1.0 (/source)\ncrate v2.0\ncrate v2.0 (*)\ncrate v1.0\n') == [
        {'name': 'crate', 'version': '1.0'}, {'name': 'crate', 'version': '2.0'},
        {'name': 'root', 'version': '1.0'}]


def test_empty_or_diagnostic_only_output_cannot_qualify_a_graph():
    with pytest.raises(ValueError, match='Empty selected Rust'):
        selected_packages('error: could not resolve dependencies\n')
