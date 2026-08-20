from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from playstore_app_audit.ui.preferences_window import FormattedAuditTableModel
from playstore_app_audit.ui.results_window import NumericAuditFilterProxy

NUMERIC_COLUMNS = ("health_score", "age_days", "target_sdk", "min_sdk")


def _ordered_values(
    proxy: NumericAuditFilterProxy,
    model: FormattedAuditTableModel,
    column: str,
) -> list[object]:
    column_index = model.columns.index(column)
    return [
        model.row_dict(proxy.mapToSource(proxy.index(row, column_index)).row()).get(column)
        for row in range(proxy.rowCount())
    ]


@pytest.mark.parametrize("column", NUMERIC_COLUMNS)
def test_numeric_columns_sort_numerically_in_both_directions(column: str) -> None:
    values: list[object] = [0, 1, 2, 9, 10, 99, 100, None, ""]
    model = FormattedAuditTableModel()
    model.set_rows(
        [
            {
                "package_name": f"com.example.app{index}",
                "criticality_key": "green",
                column: value,
            }
            for index, value in enumerate(values)
        ]
    )
    proxy = NumericAuditFilterProxy()
    proxy.setSourceModel(model)
    column_index = model.columns.index(column)

    proxy.sort(column_index, Qt.SortOrder.AscendingOrder)
    ascending = _ordered_values(proxy, model, column)
    assert set(ascending[:2]) == {None, ""}
    assert ascending[2:] == [0, 1, 2, 9, 10, 99, 100]

    proxy.sort(column_index, Qt.SortOrder.DescendingOrder)
    descending = _ordered_values(proxy, model, column)
    assert descending[:7] == [100, 99, 10, 9, 2, 1, 0]
    assert set(descending[7:]) == {None, ""}


def test_health_score_display_text_is_unchanged() -> None:
    model = FormattedAuditTableModel()
    model.set_rows([{"package_name": "com.example.app", "health_score": 100}])
    column_index = model.columns.index("health_score")
    assert model.data(model.index(0, column_index), Qt.ItemDataRole.DisplayRole) == "100"
