from __future__ import annotations

from importlib import resources

import pytest

from playstore_app_audit.services.device_specific_profiles import (
    PRODUCTION_PROFILE_IDS,
    REQUIRED_PROFILE_FIELDS,
    canonical_profile_hash,
    list_reference_profiles,
    load_reference_profile,
)


def test_only_proven_api29_and_api33_profiles_are_promoted() -> None:
    assert PRODUCTION_PROFILE_IDS == (
        "android10_api29_oneplus8pro",
        "android13_api33_s20plus",
    )
    assert [profile.api_level for profile in list_reference_profiles()] == [29, 33]


@pytest.mark.parametrize("profile_id", PRODUCTION_PROFILE_IDS)
def test_production_profiles_are_coherent_hashed_and_attributed(profile_id: str) -> None:
    profile = load_reference_profile(profile_id)
    assert REQUIRED_PROFILE_FIELDS <= set(profile.profile)
    assert canonical_profile_hash(profile.profile) == profile.profile_hash
    assert profile.source_url.startswith("https://")
    assert "GPL-3.0-or-later" in profile.source_license
    assert "AuroraOSS" in profile.source_copyright
    assert int(profile.profile["Build.VERSION.SDK_INT"]) == profile.api_level
    assert profile.profile["Build.VERSION.RELEASE"] == profile.android_release


def test_sanitized_api37_profile_is_not_a_production_resource() -> None:
    root = resources.files("playstore_app_audit.device_profiles")
    assert not root.joinpath("android17_api37_grizzly.json").is_file()
    with pytest.raises(KeyError):
        load_reference_profile("android17_api37_grizzly")
