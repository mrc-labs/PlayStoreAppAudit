from __future__ import annotations

import playstore_app_audit.ui.preferences_window as preferences_ui
from playstore_app_audit.ui import column_presets, schema


def _visible(preset: str, *, optional_columns: tuple[str, ...] = ()) -> list[str]:
    return column_presets.visible_columns(
        preset,
        column_presets.SOURCE_DEVICE,
        compare_previous=True,
        device_inventory_history=True,
        health_score_enabled=True,
        optional_columns=optional_columns,
    )


def test_installer_category_is_hidden_from_device_builtin_presets() -> None:
    for preset in ("Source Details", "Technical"):
        columns = _visible(preset, optional_columns=("installer_category",))
        assert "installer_category" not in columns
        assert "installer_source" in columns

    assert "installer_package" in _visible("Technical")


def test_installer_category_is_not_user_selectable_in_customize_view() -> None:
    common, advanced = preferences_ui.custom_column_groups()

    assert "installer_category" not in common
    assert "installer_category" not in advanced


def test_installer_category_remains_internal_for_v21_compatibility() -> None:
    assert "installer_category" in schema.MODEL_COLUMNS
    assert "installer_category" in column_presets.CUSTOM_HIDDEN_COLUMNS
