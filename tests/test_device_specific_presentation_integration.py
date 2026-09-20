from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.presentation as presentation
from playstore_app_audit.ui import column_presets, schema
from playstore_app_audit.ui.details_panel import AppDetailsPanel
from playstore_app_audit.ui.table_window import AuditTableModel


def test_resolver_fields_are_canonical_exportable_technical_evidence() -> None:
    expected = set(
        schema.DEVICE_SPECIFIC_RESOLVER_COLUMNS
    )

    assert expected == {
        "resolved_play_version",
        "resolved_play_version_code",
        "device_specific_profile",
        "device_specific_resolver_status",
    }

    assert expected <= set(schema.MODEL_COLUMNS)
    assert expected <= set(schema.EXPORT_EXTRA_FIELDS)
    assert (
        "device_specific_profile_id"
        in schema.EXPORT_EXTRA_FIELDS
    )

    for source in (
        column_presets.SOURCE_FILE,
        column_presets.SOURCE_DEVICE,
        column_presets.SOURCE_LOCAL_APK,
    ):
        basic = column_presets.visible_columns(
            "Basic",
            source,
            compare_previous=True,
            device_inventory_history=True,
            health_score_enabled=True,
        )

        technical = column_presets.visible_columns(
            "Technical",
            source,
            compare_previous=True,
            device_inventory_history=True,
            health_score_enabled=True,
        )

        assert expected.isdisjoint(basic)
        assert expected <= set(technical)


def test_details_keep_raw_store_fact_beside_resolved_evidence() -> None:
    os.environ.setdefault(
        "QT_QPA_PLATFORM",
        "offscreen",
    )

    app = QApplication.instance() or QApplication([])

    panel = AppDetailsPanel()

    try:
        panel.set_row(
            {
                "package_name": "com.example.app",
                "play_version": "Varies with device",
                "resolved_play_version": "5.0",
                "resolved_play_version_code": 101,
                "device_specific_profile": (
                    "Galaxy S20+ — Android 13 / API 33"
                ),
                "device_specific_resolver_status": "resolved",
            }
        )

        text = panel.store_label.text()

        assert "Store version: Varies with device" in text
        assert "Resolved Store version: 5.0" in text
        assert "Resolved Store version code: 101" in text
        assert (
            "Reference profile: "
            "Galaxy S20+ — Android 13 / API 33"
            in text
        )
        assert "Resolver status: resolved" in text
    finally:
        panel.deleteLater()
        app.processEvents()


@pytest.mark.parametrize(
    ("updates", "expected"),
    [
        (
            {
                "play_version": "Varies with device",
                "resolved_play_version": "5.0",
                "device_specific_resolver_status": "resolved",
            },
            "5.0 (Varies with device)",
        ),
        (
            {
                "play_version": "Varies with device",
                "resolved_play_version": "5.0",
                "device_specific_resolver_status": "inconclusive",
            },
            "Varies with device",
        ),
        (
            {
                "play_version": "Varies with device",
                "resolved_play_version": "",
                "device_specific_resolver_status": "resolved",
            },
            "Varies with device",
        ),
        (
            {
                "play_version": "4.0",
                "resolved_play_version": "5.0",
                "device_specific_resolver_status": "resolved",
            },
            "4.0",
        ),
    ],
)
def test_normal_table_combines_resolved_version_only_for_successful_exact_trigger(
    updates: dict[str, object], expected: str
) -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    model = AuditTableModel()
    row: dict[str, object] = {"package_name": "com.example.app", **updates}
    model.set_rows([row])
    index = model.index(0, model.columns.index("play_version"))

    try:
        assert index.data(Qt.ItemDataRole.DisplayRole) == expected
        assert row["play_version"] == updates["play_version"]
        assert presentation.rows_for_output([row])[0]["play_version"] == updates["play_version"]
    finally:
        model.deleteLater()
        app.processEvents()
