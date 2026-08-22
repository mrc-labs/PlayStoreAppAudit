from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.change_overview as changes
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.change_overview as change_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _row(package: str = "com.example.app", **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "package_name": package,
        "play_title": "Example App",
        "device_change": "Same",
        changes.DEVICE_HISTORY_FLAG: False,
        state.AUDIT_CHANGES_FIELD: [],
    }
    row.update(overrides)
    return row


def _group_map(groups: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(group["key"]): group for group in groups}


def test_first_device_inventory_does_not_claim_every_app_is_newly_installed() -> None:
    rows = [_row(device_change="New on device", **{changes.DEVICE_HISTORY_FLAG: False})]

    groups = changes.build_change_groups(rows, {"had_previous": False, "removed": []})

    assert groups == []
    assert not changes.row_has_meaningful_change(rows[0])


def test_newly_installed_requires_previous_device_inventory() -> None:
    row = _row(device_change="New on device", **{changes.DEVICE_HISTORY_FLAG: True})

    groups = changes.build_change_groups([row], {"had_previous": True, "removed": []})

    assert groups[0]["key"] == "newly_installed"
    assert groups[0]["count"] == 1
    assert groups[0]["items"][0]["package_name"] == "com.example.app"
    assert changes.row_has_meaningful_change(row)


def test_removed_device_apps_require_real_previous_inventory() -> None:
    inventory = {"had_previous": True, "removed": ["com.example.removed"]}

    groups = changes.build_change_groups([], inventory)

    group = _group_map(groups)["removed_from_device"]
    assert group["items"] == [
        {
            "package_name": "com.example.removed",
            "title": "com.example.removed",
            "detail": "No longer present on the connected device",
        }
    ]
    assert changes.build_change_groups([], {"had_previous": False, "removed": ["x"]}) == []


def test_removed_device_apps_use_saved_title_when_available() -> None:
    inventory = {
        "had_previous": True,
        "removed_apps": [
            {"package_name": "com.example.removed", "play_title": "Removed Example"}
        ],
    }

    group = _group_map(changes.build_change_groups([], inventory))["removed_from_device"]

    assert group["items"][0]["title"] == "Removed Example"


def test_store_change_groups_follow_product_order_and_keep_transition_detail() -> None:
    row = _row(
        **{
            state.AUDIT_CHANGES_FIELD: [
                {"type": "maintenance_state_changed", "previous": "Current", "current": "Aging"},
                {"type": "store_version_changed", "previous": "1.0", "current": "2.0"},
                {
                    "type": "newly_unavailable_in_checked_countries",
                    "previous": "available",
                    "current": "not_found_in_checked_countries",
                },
                {"type": "store_latest_update_changed", "previous": "2026-01-01", "current": "2026-08-01"},
            ]
        }
    )

    groups = changes.build_change_groups([row])

    assert [group["key"] for group in groups] == [
        "newly_unavailable_in_checked_countries",
        "store_version_changed",
        "store_latest_update_changed",
        "maintenance_state_changed",
    ]
    mapped = _group_map(groups)
    assert mapped["store_version_changed"]["items"][0]["detail"] == "1.0 → 2.0"
    assert changes.total_change_count(groups) == 4
    assert changes.row_has_meaningful_change(row)


def test_installer_change_from_store_history_and_device_inventory_is_deduplicated() -> None:
    row = _row(
        device_change="Installer changed",
        **{
            changes.DEVICE_HISTORY_FLAG: True,
            state.AUDIT_CHANGES_FIELD: [
                {
                    "type": "installer_source_changed",
                    "previous": "Google Play",
                    "current": "Galaxy Store",
                }
            ],
        },
    )

    group = _group_map(changes.build_change_groups([row]))["installer_source_changed"]

    assert group["count"] == 1
    assert group["items"][0]["detail"] == "Google Play → Galaxy Store"


def test_dialog_groups_items_and_emits_selected_package(app: QApplication) -> None:
    dialog = change_ui.ChangeOverviewDialog()
    groups = [
        {
            "key": "store_version_changed",
            "label": "Play Store version changed",
            "count": 1,
            "items": [
                {
                    "package_name": "com.example.app",
                    "title": "Example App",
                    "detail": "1.0 → 2.0",
                }
            ],
        }
    ]
    selected: list[str] = []
    dialog.package_selected.connect(selected.append)

    dialog.set_groups(groups)
    parent = dialog.tree.topLevelItem(0)
    child = parent.child(0)
    dialog._on_item_selected(child, 0)

    assert "1 change across 1 group" == dialog.summary_label.text()
    assert parent.text(0) == "Play Store version changed (1)"
    assert child.text(0) == "Example App\ncom.example.app"
    assert child.text(1) == "1.0 → 2.0"
    assert selected == ["com.example.app"]

    dialog.deleteLater()
    app.processEvents()
