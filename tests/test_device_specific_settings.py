from __future__ import annotations

from playstore_app_audit.services import device_specific_settings as settings


def test_legacy_enabled_settings_migrate_to_custom_dispenser() -> None:
    values = {
        settings.LEGACY_SETTING_ENABLED: True,
        settings.SETTING_ENDPOINT: " https://resolver.example/api/auth ",
        settings.SETTING_PROFILE_ID: " android13_api33_s20plus ",
    }

    changed = settings.migrate_settings(values, raw_settings=dict(values))

    assert changed is True
    assert values[settings.SETTING_PROVIDER] == "custom_dispenser"
    assert values[settings.SETTING_ENDPOINT] == "https://resolver.example/api/auth"
    assert values[settings.SETTING_PROFILE_ID] == "android13_api33_s20plus"
    assert values[settings.LEGACY_SETTING_ENABLED] is True


def test_legacy_disabled_settings_migrate_to_disabled_provider() -> None:
    values = {settings.LEGACY_SETTING_ENABLED: False}

    settings.migrate_settings(values, raw_settings=dict(values))

    assert values[settings.SETTING_PROVIDER] == "disabled"
    assert values[settings.LEGACY_SETTING_ENABLED] is False


def test_explicit_provider_is_authoritative_over_legacy_boolean() -> None:
    values = {
        settings.SETTING_PROVIDER: "personal_google_session",
        settings.LEGACY_SETTING_ENABLED: False,
    }

    settings.migrate_settings(values, raw_settings=dict(values))

    assert settings.provider_from_settings(values) is (
        settings.DeviceSpecificProvider.PERSONAL_GOOGLE_SESSION
    )
    assert values[settings.LEGACY_SETTING_ENABLED] is True


def test_unknown_provider_fails_closed_to_disabled() -> None:
    values = {
        settings.SETTING_PROVIDER: "not-a-provider",
        settings.LEGACY_SETTING_ENABLED: True,
    }

    settings.migrate_settings(values, raw_settings=dict(values))

    assert values[settings.SETTING_PROVIDER] == "disabled"
    assert settings.provider_from_settings(values) is settings.DeviceSpecificProvider.DISABLED
    assert values[settings.LEGACY_SETTING_ENABLED] is False
