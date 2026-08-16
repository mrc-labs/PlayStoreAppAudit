from __future__ import annotations

from playstore_app_audit.ui import schema


def test_final_schema_is_unique_and_contains_each_layer() -> None:
    assert len(schema.MODEL_COLUMNS) == len(set(schema.MODEL_COLUMNS))
    assert set(schema.COMPACT_MODEL_COLUMNS) <= set(schema.MODEL_COLUMNS)
    assert set(schema.DEVICE_EXTRA_COLUMNS) <= set(schema.MODEL_COLUMNS)
    assert set(schema.INSIGHTS_EXTRA_COLUMNS) <= set(schema.MODEL_COLUMNS)


def test_schema_has_labels_and_widths_for_visible_model_columns() -> None:
    missing_labels = [column for column in schema.MODEL_COLUMNS if column not in schema.COLUMN_LABELS]
    missing_widths = [column for column in schema.MODEL_COLUMNS if column not in schema.DEFAULT_WIDTHS]
    assert not missing_labels
    assert not missing_widths


def test_export_extras_are_unique() -> None:
    assert len(schema.EXPORT_EXTRA_FIELDS) == len(set(schema.EXPORT_EXTRA_FIELDS))
