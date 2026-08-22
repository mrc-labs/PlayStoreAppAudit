from __future__ import annotations

from playstore_app_audit.services.store_locale import (
    StoreLocale,
    locale_from_android_properties,
    primary_language_for_country,
    resolve_store_country,
    resolve_store_language,
    set_active_device_store_locale,
)


def test_country_defaults_use_stable_primary_languages() -> None:
    assert primary_language_for_country("it") == "it"
    assert primary_language_for_country("CH") == "de"
    assert primary_language_for_country("de") == "de"
    assert primary_language_for_country("unknown") == "en"


def test_store_country_resolution_keeps_country_independent_from_android_language() -> None:
    android = StoreLocale("it", "ch", "it-CH", "test")

    resolved = resolve_store_country(host_country="de", android_locale=android)

    assert resolved.country == "de"
    assert resolved.source == "host_region"


def test_store_country_resolution_uses_android_region_only_as_late_fallback() -> None:
    android = StoreLocale("it", "ch", "it-CH", "test")

    resolved = resolve_store_country(host_country=None, android_locale=android)

    assert resolved.country == "ch"
    assert resolved.source == "android_locale_fallback"


def test_store_country_resolution_preserves_manual_override_and_final_us_fallback() -> None:
    android = StoreLocale("it", "ch", "it-CH", "test")

    manual = resolve_store_country("fr", "de", android)
    fallback = resolve_store_country(None, None, StoreLocale("it", "", "it", "test"))

    assert manual.country == "fr"
    assert manual.source == "manual_override"
    assert fallback.country == "us"
    assert fallback.source == "safe_fallback"


def test_auto_language_uses_selected_country_default() -> None:
    set_active_device_store_locale(None)
    assert resolve_store_language("auto", "it") == "it"
    assert resolve_store_language("", "ch") == "de"
    assert resolve_store_language("fr-CH", "ch") == "fr"


def test_auto_language_prefers_active_android_system_language() -> None:
    set_active_device_store_locale(StoreLocale("it", "ch", "it-CH", "test"))
    try:
        assert resolve_store_language("auto", "ch") == "it"
        assert resolve_store_language("", "ch") == "it"
        # A manual setting always wins over the device context.
        assert resolve_store_language("en", "ch") == "en"
    finally:
        set_active_device_store_locale(None)


def test_android_primary_locale_keeps_device_language_and_region() -> None:
    locale = locale_from_android_properties({"persist.sys.locale": "it-CH"})

    assert locale is not None
    assert locale.language == "it"
    assert locale.country == "ch"
    assert locale.locale == "it-CH"
    assert locale.source == "android_getprop:persist.sys.locale"


def test_android_locale_list_uses_first_system_locale() -> None:
    locale = locale_from_android_properties({"persist.sys.locales": "en-CH,it-IT,de-DE"})

    assert locale is not None
    assert locale.language == "en"
    assert locale.country == "ch"
    assert locale.locale == "en-CH"


def test_android_legacy_locale_properties_are_supported() -> None:
    locale = locale_from_android_properties(
        {"persist.sys.language": "de", "persist.sys.country": "CH"}
    )

    assert locale is not None
    assert locale.language == "de"
    assert locale.country == "ch"
    assert locale.locale == "de-CH"
