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
    missing_policies = [
        column for column in schema.MODEL_COLUMNS if column not in schema.COLUMN_WIDTH_POLICIES
    ]
    assert not missing_labels
    assert not missing_widths
    assert not missing_policies


def test_semantic_width_categories_keep_short_and_long_values_distinct() -> None:
    categories = schema.ColumnWidthCategory

    assert schema.COLUMN_WIDTH_POLICIES["health_score"].category is categories.COMPACT
    assert schema.COLUMN_WIDTH_POLICIES["target_sdk"].category is categories.COMPACT
    assert schema.COLUMN_WIDTH_POLICIES["app_enabled"].category is categories.COMPACT
    assert schema.COLUMN_WIDTH_POLICIES["version_comparison"].category is categories.MEDIUM
    assert schema.COLUMN_WIDTH_POLICIES["package_name"].category is categories.PRIMARY
    assert schema.COLUMN_WIDTH_POLICIES["store_url"].category is categories.LONG_TEXT
    assert schema.DEFAULT_WIDTHS["health_score"] == 100
    assert schema.DEFAULT_WIDTHS["store_url"] == 250
    assert schema.DEFAULT_WIDTHS["package_name"] > schema.DEFAULT_WIDTHS["health_score"]


def test_selected_table_headers_have_explicit_two_line_titles() -> None:
    assert schema.TABLE_HEADER_LABELS["health_score"] == "Maintenance\nScore"
    assert schema.TABLE_HEADER_LABELS["version_comparison"] == "Installed vs\nStore"
    assert schema.TABLE_HEADER_LABELS["compatibility_status"] == "Android\nCompatibility"
    assert schema.TABLE_HEADER_LABELS["device_change"] == "Device Inventory\nChange"
    assert schema.TABLE_HEADER_LABELS["sensitive_permissions_count"] == (
        "Sensitive Permissions\nCount"
    )
    assert schema.TABLE_HEADER_LABELS["store_url"] == "Store URL"


def test_export_extras_are_unique() -> None:
    assert len(schema.EXPORT_EXTRA_FIELDS) == len(set(schema.EXPORT_EXTRA_FIELDS))
