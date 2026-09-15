"""Validated production reference profiles for Device Specific resolution."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType


PROFILE_SCHEMA = 1
PRODUCTION_PROFILE_IDS = (
    "android10_api29_oneplus8pro",
    "android13_api33_s20plus",
)

REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "UserReadableName",
        "Build.HARDWARE",
        "Build.RADIO",
        "Build.BOOTLOADER",
        "Build.FINGERPRINT",
        "Build.BRAND",
        "Build.DEVICE",
        "Build.VERSION.SDK_INT",
        "Build.VERSION.RELEASE",
        "Build.MODEL",
        "Build.MANUFACTURER",
        "Build.PRODUCT",
        "Build.ID",
        "TouchScreen",
        "Keyboard",
        "Navigation",
        "ScreenLayout",
        "HasHardKeyboard",
        "HasFiveWayNavigation",
        "GL.Version",
        "Screen.Density",
        "Screen.Width",
        "Screen.Height",
        "Platforms",
        "SharedLibraries",
        "Features",
        "Locales",
        "GSF.version",
        "Vending.version",
        "Vending.versionString",
        "CellOperator",
        "SimOperator",
        "TimeZone",
        "Roaming",
        "Client",
    }
)

FORBIDDEN_KEY_PARTS = (
    "serial",
    "imei",
    "meid",
    "subscriber",
    "account",
    "email",
    "password",
    "cookie",
    "authtoken",
    "auth_token",
    "aastoken",
    "aas_token",
    "androidid",
    "android_id",
    "gsfid",
    "gsf_id",
)


@dataclass(frozen=True, slots=True)
class ReferenceProfile:
    profile_id: str
    display_name: str
    android_release: str
    api_level: int
    source: str
    source_ref: str
    source_url: str
    source_license: str
    source_copyright: str
    profile_hash: str
    profile: Mapping[str, str]


def canonical_profile_hash(profile: Mapping[str, str]) -> str:
    encoded = json.dumps(
        dict(profile),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_keys(profile: Mapping[str, str]) -> None:
    for key in profile:
        compact = key.casefold().replace(".", "").replace("-", "")
        if any(marker in compact for marker in FORBIDDEN_KEY_PARTS):
            raise ValueError(f"reference profile contains forbidden key: {key}")


def load_reference_profile(profile_id: str) -> ReferenceProfile:
    if profile_id not in PRODUCTION_PROFILE_IDS:
        raise KeyError(f"unknown production reference profile: {profile_id}")

    resource = resources.files("playstore_app_audit.device_profiles").joinpath(
        f"{profile_id}.json"
    )
    payload = json.loads(resource.read_text(encoding="utf-8"))

    if not isinstance(payload, dict) or payload.get("schema") != PROFILE_SCHEMA:
        raise ValueError(f"unsupported reference-profile schema: {profile_id}")
    if payload.get("profile_id") != profile_id:
        raise ValueError(f"reference-profile ID mismatch: {profile_id}")

    raw_profile = payload.get("profile")
    if not isinstance(raw_profile, dict):
        raise ValueError(f"reference profile has no profile object: {profile_id}")
    profile = {str(key): str(value) for key, value in raw_profile.items()}

    missing = sorted(REQUIRED_PROFILE_FIELDS - set(profile))
    if missing:
        raise ValueError(
            f"reference profile {profile_id} is missing: {', '.join(missing)}"
        )
    _validate_keys(profile)

    api_level = int(payload.get("api_level") or 0)
    android_release = str(payload.get("android_release") or "")
    if int(profile["Build.VERSION.SDK_INT"]) != api_level:
        raise ValueError(f"reference-profile API mismatch: {profile_id}")
    if profile["Build.VERSION.RELEASE"] != android_release:
        raise ValueError(f"reference-profile Android release mismatch: {profile_id}")

    calculated_hash = canonical_profile_hash(profile)
    if calculated_hash != str(payload.get("profile_hash") or ""):
        raise ValueError(f"reference-profile hash mismatch: {profile_id}")

    source_url = str(payload.get("source_url") or "")
    source_license = str(payload.get("source_license") or "")
    source_copyright = str(payload.get("source_copyright") or "")
    if not source_url.startswith("https://"):
        raise ValueError(f"reference-profile source URL must use HTTPS: {profile_id}")
    if "GPL-3.0-or-later" not in source_license:
        raise ValueError(f"reference-profile license is not attributable: {profile_id}")
    if "AuroraOSS" not in source_copyright:
        raise ValueError(f"reference-profile copyright is not attributable: {profile_id}")

    return ReferenceProfile(
        profile_id=profile_id,
        display_name=str(payload.get("display_name") or ""),
        android_release=android_release,
        api_level=api_level,
        source=str(payload.get("source") or ""),
        source_ref=str(payload.get("source_ref") or ""),
        source_url=source_url,
        source_license=source_license,
        source_copyright=source_copyright,
        profile_hash=calculated_hash,
        profile=MappingProxyType(profile),
    )


def list_reference_profiles() -> tuple[ReferenceProfile, ...]:
    return tuple(load_reference_profile(profile_id) for profile_id in PRODUCTION_PROFILE_IDS)
