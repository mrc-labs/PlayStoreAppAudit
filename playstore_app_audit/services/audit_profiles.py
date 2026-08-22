from __future__ import annotations

from typing import Any

import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state

SETTINGS_KEY = "audit_profiles"
PROFILE_SCHEMA_VERSION = 1
PROFILE_FIELDS = (
    "store_language",
    "fallback_countries",
    "store_workers",
    "cache_enabled",
    "cache_ttl_hours",
    "collect_device_metadata",
    "permissions_audit_enabled",
    "inventory_history_enabled",
    "compare_previous",
    "exclude_system_source",
)

_BOOLEAN_FIELDS = frozenset(
    {
        "cache_enabled",
        "collect_device_metadata",
        "permissions_audit_enabled",
        "inventory_history_enabled",
        "compare_previous",
        "exclude_system_source",
    }
)


def _country(value: object) -> str:
    code = str(value or "").strip().lower()
    return code if len(code) == 2 and code.isalpha() else "us"


def _profile_name(value: object) -> str:
    return " ".join(str(value or "").strip().split())[:80]


def normalise_profile(profile: object) -> dict[str, Any] | None:
    if not isinstance(profile, dict):
        return None
    settings = profile.get("settings")
    if not isinstance(settings, dict):
        return None

    fallback, _invalid = device_metadata.normalise_country_string(
        settings.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES)
    )
    language = str(settings.get("store_language") or "auto").strip().lower() or "auto"
    try:
        ttl = int(settings.get("cache_ttl_hours", 72))
    except (TypeError, ValueError):
        ttl = 72
    ttl = max(1, min(720, ttl))

    clean: dict[str, Any] = {
        "store_language": language,
        "fallback_countries": fallback,
        "store_workers": state.normalise_store_workers(settings.get("store_workers")),
        "cache_ttl_hours": ttl,
    }
    for key in _BOOLEAN_FIELDS:
        default = True if key in {"cache_enabled", "collect_device_metadata", "inventory_history_enabled", "exclude_system_source"} else False
        clean[key] = bool(settings.get(key, default))

    return {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "store_country": _country(profile.get("store_country")),
        "settings": clean,
    }


def capture_profile(settings: dict[str, Any], store_country: object) -> dict[str, Any]:
    raw_settings = {key: settings.get(key) for key in PROFILE_FIELDS}
    profile = normalise_profile(
        {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "store_country": store_country,
            "settings": raw_settings,
        }
    )
    assert profile is not None
    return profile


def load_profiles() -> dict[str, dict[str, Any]]:
    raw = state.load_settings().get(SETTINGS_KEY, {})
    if not isinstance(raw, dict):
        return {}
    profiles: dict[str, dict[str, Any]] = {}
    for name, profile in raw.items():
        clean_name = _profile_name(name)
        clean_profile = normalise_profile(profile)
        if clean_name and clean_profile is not None:
            profiles[clean_name] = clean_profile
    return dict(sorted(profiles.items(), key=lambda item: item[0].casefold()))


def save_profile(name: object, profile: dict[str, Any]) -> dict[str, Any]:
    clean_name = _profile_name(name)
    if not clean_name:
        raise ValueError("Profile name cannot be empty.")
    clean_profile = normalise_profile(profile)
    if clean_profile is None:
        raise ValueError("Invalid audit profile.")

    settings = state.load_settings()
    stored = settings.get(SETTINGS_KEY, {})
    profiles = dict(stored) if isinstance(stored, dict) else {}
    profiles[clean_name] = clean_profile
    settings[SETTINGS_KEY] = profiles
    state.save_settings(settings)
    return clean_profile


def delete_profile(name: object) -> bool:
    clean_name = _profile_name(name)
    settings = state.load_settings()
    stored = settings.get(SETTINGS_KEY, {})
    if not isinstance(stored, dict) or clean_name not in stored:
        return False
    profiles = dict(stored)
    profiles.pop(clean_name, None)
    settings[SETTINGS_KEY] = profiles
    state.save_settings(settings)
    return True


def apply_profile_to_settings(
    profile: dict[str, Any],
    current_settings: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    clean = normalise_profile(profile)
    if clean is None:
        raise ValueError("Invalid audit profile.")
    merged = dict(current_settings or state.load_settings())
    merged.update(clean["settings"])
    return str(clean["store_country"]), merged
