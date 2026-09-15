from __future__ import annotations

from tools.device_specific_poc.profiles import (
    SECRETISH_KEY_PARTS,
    canonical_profile_hash,
    list_reference_profiles,
    load_reference_profile,
    resolver_cache_identity,
)

EXPECTED_APIS = {
    "android10_api29_oneplus8pro": 29,
    "android13_api33_s20plus": 33,
    "android17_api37_grizzly": 37,
}


def test_reference_profile_matrix_is_exactly_the_poc_matrix() -> None:
    profiles = {
        profile.profile_id:
            profile
        for profile
        in list_reference_profiles()
    }

    assert (
        set(profiles)
        == set(EXPECTED_APIS)
    )

    for (
        profile_id,
        api_level,
    ) in EXPECTED_APIS.items():
        profile = profiles[
            profile_id
        ]

        assert (
            profile.api_level
            == api_level
        )

        assert (
            int(
                profile.profile[
                    "Build.VERSION.SDK_INT"
                ]
            )
            == api_level
        )

        assert (
            profile.profile_hash
            == canonical_profile_hash(
                profile.profile
            )
        )


def test_reference_profiles_have_no_identifier_like_keys() -> None:
    for profile in (
        list_reference_profiles()
    ):
        for key in (
            profile.profile
        ):
            lower = (
                key.casefold()
            )

            assert not any(
                marker in lower
                for marker
                in SECRETISH_KEY_PARTS
            )


def test_grizzly_snapshot_excludes_personal_context() -> None:
    profile = (
        load_reference_profile(
            "android17_api37_grizzly"
        )
    )

    forbidden = {
        "Locales",
        "TimeZone",
        "CellOperator",
        "SimOperator",
        "Roaming",
    }

    assert (
        forbidden.isdisjoint(
            profile.profile
        )
    )

    assert (
        profile.profile[
            "Build.DEVICE"
        ]
        == "grizzly"
    )

    assert (
        profile.profile[
            "Build.VERSION.SDK_INT"
        ]
        == "37"
    )


def test_cache_identity_changes_with_profile_and_auth_context() -> None:
    profile = (
        load_reference_profile(
            "android13_api33_s20plus"
        )
    )

    anonymous = (
        resolver_cache_identity(
            package_name=(
                "com.facebook.katana"
            ),
            profile=profile,
            country="CH",
            language="en",
            auth_mode=(
                "anonymous"
            ),
            auth_context=(
                "self-hosted-a"
            ),
            protocol_revision=(
                "fdfe-poc-v1"
            ),
        )
    )

    authenticated = (
        resolver_cache_identity(
            package_name=(
                "com.facebook.katana"
            ),
            profile=profile,
            country="CH",
            language="en",
            auth_mode=(
                "authenticated"
            ),
            auth_context=(
                "google-aas"
            ),
            protocol_revision=(
                "fdfe-poc-v1"
            ),
        )
    )

    assert (
        anonymous
        != authenticated
    )

    other_profile = (
        load_reference_profile(
            "android10_api29_oneplus8pro"
        )
    )

    other_profile_key = (
        resolver_cache_identity(
            package_name=(
                "com.facebook.katana"
            ),
            profile=(
                other_profile
            ),
            country="CH",
            language="en",
            auth_mode=(
                "anonymous"
            ),
            auth_context=(
                "self-hosted-a"
            ),
            protocol_revision=(
                "fdfe-poc-v1"
            ),
        )
    )

    assert (
        anonymous
        != other_profile_key
    )
