from __future__ import annotations

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
from playstore_app_audit.services import installer_source
from playstore_app_audit.ui import schema


def test_exact_installer_packages_map_to_stable_categories() -> None:
    play = installer_source.classify_installer_package("com.android.vending")
    galaxy = installer_source.classify_installer_package("com.sec.android.app.samsungapps")
    sideload = installer_source.classify_installer_package("com.google.android.packageinstaller")
    unknown = installer_source.classify_installer_package("")
    other = installer_source.classify_installer_package("com.example.sideload.store")

    assert play.category == installer_source.CATEGORY_GOOGLE_PLAY
    assert play.label == "Google Play (com.android.vending)"
    assert galaxy.category == installer_source.CATEGORY_ALTERNATIVE_STORE
    assert sideload.category == installer_source.CATEGORY_SIDELOADED
    assert unknown.category == installer_source.CATEGORY_UNKNOWN_PREINSTALLED
    # Unknown packages are not guessed from words inside the package name.
    assert other.category == installer_source.CATEGORY_OTHER
    assert other.label == "com.example.sideload.store"


def test_metadata_keeps_raw_installer_package_separate_from_display_label() -> None:
    metadata = {"com.example.app": {"installed_version": "1.0"}}

    installer_source._enrich_metadata(
        metadata,
        ["com.example.app"],
        {"com.example.app": "com.huawei.appmarket"},
    )

    info = metadata["com.example.app"]
    assert info["installer_source"] == "Huawei AppGallery (com.huawei.appmarket)"
    assert info["installer_package"] == "com.huawei.appmarket"
    assert info["installer_category"] == installer_source.CATEGORY_ALTERNATIVE_STORE


def test_filtering_prefers_structured_category_over_display_text() -> None:
    installer_source.install_installer_source_extensions()
    misleading = {
        "installer_category": installer_source.CATEGORY_GOOGLE_PLAY,
        "installer_package": "com.android.vending",
        "installer_source": "Sideload / package installer",
    }

    assert device_insights.row_matches_filter(misleading, "Google Play")
    assert not device_insights.row_matches_filter(misleading, "Sideloaded")


def test_legacy_filter_compatibility_is_exact_not_free_form_substring_matching() -> None:
    installer_source.install_installer_source_extensions()

    assert device_insights.row_matches_filter(
        {"installer_source": "Sideload / package installer"}, "Sideloaded"
    )
    assert not device_insights.row_matches_filter(
        {"installer_source": "user note says sideload happened"}, "Sideloaded"
    )


def test_all_installer_categories_have_builtin_filter_presets() -> None:
    installer_source.install_installer_source_extensions()

    for preset in installer_source.FILTER_PRESETS:
        assert preset in device_insights.BUILTIN_FILTERS


def test_installer_fields_are_technical_columns_and_exported() -> None:
    installer_source.install_installer_source_extensions()

    assert state.TECHNICAL_COLUMNS["installer_category"] == "Installer category"
    assert state.TECHNICAL_COLUMNS["installer_package"] == "Installer package"
    assert "installer_category" in schema.MODEL_COLUMNS
    assert "installer_package" in schema.MODEL_COLUMNS
    assert "installer_category" in schema.EXPORT_EXTRA_FIELDS
    assert "installer_package" in schema.EXPORT_EXTRA_FIELDS


def test_device_snapshot_preserves_structured_installer_fields() -> None:
    installer_source.install_installer_source_extensions()
    row = {
        "package_name": "com.example.app",
        "installer_source": "Google Play (com.android.vending)",
        "installer_package": "com.android.vending",
        "installer_category": installer_source.CATEGORY_GOOGLE_PLAY,
    }

    snapshot = device_insights.make_device_snapshot([row], {})
    app = snapshot["apps"][0]

    assert app["installer_package"] == "com.android.vending"
    assert app["installer_category"] == installer_source.CATEGORY_GOOGLE_PLAY
