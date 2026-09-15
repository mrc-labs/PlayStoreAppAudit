"""Reference-profile handling for the isolated resolver PoC."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

PROFILE_SCHEMA = 1

PROFILE_ROOT = (
    Path(__file__).resolve().parent
    / "reference_profiles"
)

REQUIRED_PROFILE_FIELDS = frozenset(
    {
        "Build.HARDWARE",
        "Build.FINGERPRINT",
        "Build.BRAND",
        "Build.DEVICE",
        "Build.VERSION.SDK_INT",
        "Build.VERSION.RELEASE",
        "Build.MODEL",
        "Build.MANUFACTURER",
        "Build.PRODUCT",
        "Build.ID",
        "Screen.Density",
        "Screen.Width",
        "Screen.Height",
        "Platforms",
        "SharedLibraries",
        "Features",
        "GSF.version",
        "Vending.version",
        "Vending.versionString",
    }
)

SECRETISH_KEY_PARTS = (
    "serial",
    "imei",
    "meid",
    "subscriber",
    "account",
    "email",
    "password",
    "cookie",
    "auth_token",
    "aas",
    "android_id",
    "gsfid",
)


@dataclass(
    frozen=True,
    slots=True,
)
class ReferenceProfile:
    profile_id: str
    display_name: str
    android_release: str
    api_level: int
    source: str
    source_ref: str
    source_url: str
    source_license: str
    profile_hash: str
    profile: dict[str, str]


def canonical_profile_hash(
    profile: dict[str, str],
) -> str:
    encoded = json.dumps(
        profile,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")

    return hashlib.sha256(
        encoded
    ).hexdigest()


def _validate_no_secretish_keys(
    profile: dict[str, str],
) -> None:
    for key in profile:
        lower = key.casefold()

        if any(
            marker in lower
            for marker
            in SECRETISH_KEY_PARTS
        ):
            raise ValueError(
                "Profile contains forbidden "
                f"identifier-like key: {key}"
            )


def load_reference_profile(
    profile_id: str,
) -> ReferenceProfile:
    path = (
        PROFILE_ROOT
        / f"{profile_id}.json"
    )

    if not path.is_file():
        raise KeyError(
            "Unknown reference profile: "
            f"{profile_id}"
        )

    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if payload.get("schema") != PROFILE_SCHEMA:
        raise ValueError(
            "Unsupported reference-profile "
            f"schema: {path.name}"
        )

    if payload.get("profile_id") != profile_id:
        raise ValueError(
            "Reference-profile ID mismatch: "
            f"{path.name}"
        )

    raw_profile = payload.get(
        "profile"
    )

    if not isinstance(
        raw_profile,
        dict,
    ):
        raise ValueError(
            "Reference profile has no "
            f"profile object: {path.name}"
        )

    profile = {
        str(key): str(value)
        for key, value
        in raw_profile.items()
    }

    missing = sorted(
        REQUIRED_PROFILE_FIELDS
        - set(profile)
    )

    if missing:
        raise ValueError(
            f"Reference profile {profile_id} "
            "is missing: "
            + ", ".join(missing)
        )

    _validate_no_secretish_keys(
        profile
    )

    api_level = int(
        payload["api_level"]
    )

    if (
        int(
            profile[
                "Build.VERSION.SDK_INT"
            ]
        )
        != api_level
    ):
        raise ValueError(
            "Reference-profile API mismatch: "
            f"{profile_id}"
        )

    android_release = str(
        payload[
            "android_release"
        ]
    )

    if (
        profile[
            "Build.VERSION.RELEASE"
        ]
        != android_release
    ):
        raise ValueError(
            "Reference-profile Android "
            f"release mismatch: {profile_id}"
        )

    calculated_hash = (
        canonical_profile_hash(
            profile
        )
    )

    if (
        calculated_hash
        != payload.get(
            "profile_hash"
        )
    ):
        raise ValueError(
            "Reference-profile hash mismatch: "
            f"{profile_id}"
        )

    return ReferenceProfile(
        profile_id=profile_id,
        display_name=str(
            payload["display_name"]
        ),
        android_release=android_release,
        api_level=api_level,
        source=str(
            payload["source"]
        ),
        source_ref=str(
            payload["source_ref"]
        ),
        source_url=str(
            payload.get(
                "source_url"
            )
            or ""
        ),
        source_license=str(
            payload[
                "source_license"
            ]
        ),
        profile_hash=calculated_hash,
        profile=profile,
    )


def list_reference_profiles(
) -> tuple[ReferenceProfile, ...]:
    profiles = []

    for path in sorted(
        PROFILE_ROOT.glob(
            "*.json"
        )
    ):
        profiles.append(
            load_reference_profile(
                path.stem
            )
        )

    return tuple(profiles)


def resolver_cache_identity(
    *,
    package_name: str,
    profile: ReferenceProfile,
    country: str,
    language: str,
    auth_mode: str,
    auth_context: str,
    protocol_revision: str,
) -> tuple[str, ...]:
    """Return proposed future resolver-cache identity."""

    return (
        "device-specific-v1",
        package_name,
        profile.profile_id,
        profile.profile_hash,
        country.upper(),
        language.casefold(),
        auth_mode,
        auth_context,
        protocol_revision,
    )
