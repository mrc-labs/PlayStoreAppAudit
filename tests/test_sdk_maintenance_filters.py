from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.sdk_maintenance as sdk_maintenance
from playstore_app_audit.services import installer_source
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def teardown_function() -> None:
    sdk_maintenance.set_active_sdk_filter(None)


def test_sdk_thresholds_are_numeric_and_exclude_missing_values() -> None:
    value = sdk_maintenance.SdkMaintenanceFilter(target_sdk_max=32, min_sdk_max=23)

    assert sdk_maintenance.row_matches_sdk_filter(
        {"target_sdk": "32", "min_sdk": "21"}, value
    )
    assert not sdk_maintenance.row_matches_sdk_filter(
        {"target_sdk": "33", "min_sdk": "21"}, value
    )
    assert not sdk_maintenance.row_matches_sdk_filter(
        {"target_sdk": "32", "min_sdk": "24"}, value
    )
    assert not sdk_maintenance.row_matches_sdk_filter(
        {"target_sdk": "", "min_sdk": "21"}, value
    )


def test_sdk_compatibility_filter_uses_existing_maintenance_classification() -> None:
    legacy = sdk_maintenance.SdkMaintenanceFilter(compatibility="Legacy target")

    assert sdk_maintenance.row_matches_sdk_filter(
        {"compatibility_status": "Legacy target"}, legacy
    )
    assert not sdk_maintenance.row_matches_sdk_filter(
        {"compatibility_status": "Aging target"}, legacy
    )


def test_sdk_filter_combines_with_structured_installer_filter() -> None:
    installer_source.install_installer_source_extensions()
    sdk_maintenance.install_sdk_maintenance_filter()
    sdk_maintenance.set_active_sdk_filter(
        sdk_maintenance.SdkMaintenanceFilter(target_sdk_max=32)
    )

    matching = {
        "installer_category": installer_source.CATEGORY_ALTERNATIVE_STORE,
        "target_sdk": "31",
    }
    wrong_sdk = {
        "installer_category": installer_source.CATEGORY_ALTERNATIVE_STORE,
        "target_sdk": "34",
    }
    wrong_installer = {
        "installer_category": installer_source.CATEGORY_GOOGLE_PLAY,
        "target_sdk": "31",
    }

    assert device_insights.row_matches_filter(matching, "Alternative stores")
    assert not device_insights.row_matches_filter(wrong_sdk, "Alternative stores")
    assert not device_insights.row_matches_filter(wrong_installer, "Alternative stores")


def test_sdk_filter_description_is_maintenance_neutral() -> None:
    text = sdk_maintenance.describe_sdk_filter(
        sdk_maintenance.SdkMaintenanceFilter(
            target_sdk_max=32,
            min_sdk_max=23,
            compatibility="Aging target",
        )
    )

    assert text == "SDK filter: targetSdk ≤ 32 · minSdk ≤ 23 · Aging target"
    assert "security" not in text.casefold()
    assert "risk" not in text.casefold()


def test_main_window_exposes_builtin_installer_and_sdk_filters(
    app: QApplication,
) -> None:
    window = MainWindow()
    try:
        actions = [action.text() for action in window._filter_menu.actions()]
        assert "Google Play" in actions
        assert "Alternative stores" in actions
        assert "Sideloaded" in actions
        assert "Unknown / preinstalled" in actions
        assert "Other installers" in actions
        assert window.sdk_filter_action.text() == "SDK maintenance filter…"
        assert window.clear_sdk_filter_action.text() == "Clear SDK filter"
    finally:
        window.close()
        app.processEvents()


def test_builtin_filter_selection_is_session_level_and_updates_proxy(
    app: QApplication,
) -> None:
    window = MainWindow()
    try:
        window._apply_filter_preset("Alternative stores")
        assert window._active_filter_preset == "Alternative stores"
        assert window.proxy.v9_preset == "Alternative stores"
    finally:
        window.close()
        app.processEvents()
