"""Settings contract for Device Specific provider/profile selection."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any

SETTING_PROVIDER = "device_specific_provider"
SETTING_ENDPOINT = "device_specific_resolver_endpoint"
SETTING_PROFILE_ID = "device_specific_resolver_profile"
LEGACY_SETTING_ENABLED = "device_specific_resolver_enabled"

CONNECTED_DEVICE_PROFILE_ID = "connected_device"


class DeviceSpecificProvider(StrEnum):
    DISABLED = "disabled"
    PERSONAL_GOOGLE_SESSION = "personal_google_session"
    CUSTOM_DISPENSER = "custom_dispenser"


def normalise_provider(value: object) -> DeviceSpecificProvider:
    text = str(value or "").strip().casefold()
    try:
        return DeviceSpecificProvider(text)
    except ValueError:
        return DeviceSpecificProvider.DISABLED


def provider_from_settings(settings: Mapping[str, Any]) -> DeviceSpecificProvider:
    """Return the configured provider, including the one-time legacy meaning."""

    if SETTING_PROVIDER in settings:
        return normalise_provider(settings.get(SETTING_PROVIDER))
    if settings.get(LEGACY_SETTING_ENABLED) is True:
        return DeviceSpecificProvider.CUSTOM_DISPENSER
    return DeviceSpecificProvider.DISABLED


def migrate_settings(
    settings: dict[str, Any],
    *,
    raw_settings: Mapping[str, Any] | None = None,
) -> bool:
    """Normalize Device Specific settings and report whether persistence is needed."""

    raw = raw_settings if raw_settings is not None else settings
    changed = False

    if SETTING_PROVIDER not in raw:
        provider = (
            DeviceSpecificProvider.CUSTOM_DISPENSER
            if raw.get(LEGACY_SETTING_ENABLED) is True
            else DeviceSpecificProvider.DISABLED
        )
        settings[SETTING_PROVIDER] = provider.value
        changed = True
    else:
        provider = normalise_provider(settings.get(SETTING_PROVIDER))
        normalized = provider.value
        if settings.get(SETTING_PROVIDER) != normalized:
            settings[SETTING_PROVIDER] = normalized
            changed = True

    endpoint = str(settings.get(SETTING_ENDPOINT) or "").strip()
    if settings.get(SETTING_ENDPOINT) != endpoint:
        settings[SETTING_ENDPOINT] = endpoint
        changed = True

    profile_id = str(settings.get(SETTING_PROFILE_ID) or "").strip()
    if settings.get(SETTING_PROFILE_ID) != profile_id:
        settings[SETTING_PROFILE_ID] = profile_id
        changed = True

    # Keep the old boolean coherent while v2.1 branches are being integrated.
    legacy_enabled = provider is not DeviceSpecificProvider.DISABLED
    if settings.get(LEGACY_SETTING_ENABLED) is not legacy_enabled:
        settings[LEGACY_SETTING_ENABLED] = legacy_enabled
        changed = True

    return changed
