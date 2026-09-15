"""Experimental metadata-only Play transport for Track C.

This module deliberately has no anonymous dispenser default.

``goopdl`` is imported lazily and remains an experimental PoC
dependency rather than a production runtime dependency.
"""

from __future__ import annotations

import ipaddress
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping

from .models import (
    ResolverResult,
    ResolverStatus,
)
from .profiles import (
    ReferenceProfile,
    load_reference_profile,
)

AUTH_EMAIL_ENV = (
    "STORE_APP_AUDIT_POC_GOOGLE_EMAIL"
)

AUTH_AAS_ENV = (
    "STORE_APP_AUDIT_POC_GOOGLE_AAS_TOKEN"
)

IDENTITY_FIELDS = frozenset(
    {
        "email",
        "aasToken",
        "password",
        "tokenDispenserUrl",
        "userProfile",
    }
)


def _failure(
    *,
    package_name: str,
    profile: ReferenceProfile,
    auth_mode: str,
    status: ResolverStatus,
    country: str,
    language: str,
    diagnostics: str,
) -> ResolverResult:
    return ResolverResult(
        package_name=package_name,
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        auth_mode=auth_mode,
        status=status,
        requested_country=country,
        requested_language=language,
        diagnostics=diagnostics,
    )



def _is_loopback_host(
    hostname: str,
) -> bool:
    if hostname.casefold() == "localhost":
        return True

    try:
        return ipaddress.ip_address(
            hostname
        ).is_loopback

    except ValueError:
        return False


def _with_locale(
    dispenser_url: str,
    language: str,
    country: str,
) -> str:
    parsed = urllib.parse.urlsplit(
        dispenser_url
    )

    if (
        parsed.scheme
        not in {
            "http",
            "https",
        }
        or not parsed.hostname
    ):
        raise ValueError(
            "dispenser_url must be an "
            "explicit http(s) endpoint"
        )

    if (
        parsed.scheme == "http"
        and not _is_loopback_host(
            parsed.hostname
        )
    ):
        raise ValueError(
            "plain HTTP dispenser endpoints "
            "are allowed only on loopback"
        )

    query = dict(
        urllib.parse.parse_qsl(
            parsed.query,
            keep_blank_values=True,
        )
    )

    query["locale"] = (
        f"{language.casefold()}_"
        f"{country.upper()}"
    )

    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode(
                query
            ),
            parsed.fragment,
        )
    )


def _sanitize_bundle(
    raw_bundle: object,
    *,
    country: str,
    profiles_module: object,
) -> dict[str, object] | None:
    if not isinstance(
        raw_bundle,
        Mapping,
    ):
        return None

    bundle = {
        str(key): value
        for key, value
        in raw_bundle.items()
        if str(key)
        not in IDENTITY_FIELDS
    }

    if not bundle.get(
        "authToken"
    ):
        return None

    device_info = dict(
        bundle.get(
            "deviceInfoProvider"
        )
        or {}
    )

    country_mcc = getattr(
        profiles_module,
        "COUNTRY_MCC",
        {},
    )

    if (
        country.upper()
        in country_mcc
    ):
        mcc, mnc = country_mcc[
            country.upper()
        ]

        device_info[
            "mccMnc"
        ] = f"{mcc}{mnc}"

    bundle[
        "deviceInfoProvider"
    ] = device_info

    return bundle



def _anonymous_bundle(
    *,
    dispenser_url: str,
    profile_data: dict[str, str],
    country: str,
    language: str,
    profiles_module: object,
) -> tuple[
    dict[str, object] | None,
    ResolverStatus | None,
    str,
]:
    try:
        patched = (
            profiles_module
            .patch_profile_country(
                dict(
                    profile_data
                ),
                country,
            )
        )

    except Exception as exc:
        return (
            None,
            "inconclusive",
            "profile_patch_"
            + type(exc).__name__,
        )

    try:
        endpoint = _with_locale(
            dispenser_url,
            language,
            country,
        )

    except ValueError:
        return (
            None,
            "inconclusive",
            "invalid_dispenser_url",
        )

    try:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(
                patched,
                ensure_ascii=False,
            ).encode(
                "utf-8"
            ),
            headers={
                "Content-Type":
                    "application/json",
                "User-Agent":
                    "StoreAppAudit-TrackC-PoC",
            },
            method="POST",
        )

        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            body = response.read()

    except urllib.error.HTTPError as exc:
        if exc.code in {
            401,
            403,
        }:
            return (
                None,
                "auth_failed",
                f"dispenser_http_{exc.code}",
            )

        if exc.code == 429:
            return (
                None,
                "rate_limited",
                "dispenser_http_429",
            )

        return (
            None,
            "transport_error",
            f"dispenser_http_{exc.code}",
        )

    except (
        urllib.error.URLError,
        TimeoutError,
        OSError,
    ) as exc:
        return (
            None,
            "transport_error",
            "dispenser_"
            + type(exc).__name__,
        )

    try:
        raw_bundle = json.loads(
            body.decode(
                "utf-8"
            )
        )

    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return (
            None,
            "malformed_response",
            "dispenser_malformed_json",
        )

    bundle = _sanitize_bundle(
        raw_bundle,
        country=country,
        profiles_module=(
            profiles_module
        ),
    )

    if bundle is None:
        return (
            None,
            "malformed_response",
            "dispenser_missing_auth_token",
        )

    return (
        bundle,
        None,
        "",
    )


def _authenticated_bundle(
    *,
    profile: ReferenceProfile,
    country: str,
    auth_module: object,
) -> dict[str, object] | None:
    email = os.environ.get(
        AUTH_EMAIL_ENV,
        "",
    ).strip()

    aas_token = os.environ.get(
        AUTH_AAS_ENV,
        "",
    ).strip()

    if (
        not email
        or not aas_token
        or not aas_token.startswith(
            "aas_et/"
        )
    ):
        return None

    original_find_profile = (
        auth_module.find_profile
    )

    try:
        def poc_find_profile(
            name: str,
            arch: str = "arm64",
        ) -> tuple[
            str,
            dict[str, str],
        ] | None:
            if (
                name
                == profile.profile_id
            ):
                return (
                    profile.profile_id,
                    dict(
                        profile.profile
                    ),
                )

            return original_find_profile(
                name,
                arch,
            )

        auth_module.find_profile = (
            poc_find_profile
        )

        return (
            auth_module._direct_auth(
                email=email,
                aas_token=aas_token,
                arch="arm64",
                country=country,
                proxy=None,
                profile_name=(
                    profile.profile_id
                ),
            )
        )

    finally:
        auth_module.find_profile = (
            original_find_profile
        )


def _play_failure_status(
    exc: Exception,
) -> ResolverStatus:
    name = type(
        exc
    ).__name__

    if (
        "AppNotAvailable"
        in name
    ):
        return (
            "unavailable_for_profile"
        )

    if any(
        marker in name
        for marker in (
            "Auth",
            "Login",
            "Unauthorized",
        )
    ):
        return "auth_failed"

    if any(
        marker in name
        for marker in (
            "Rate",
            "TooManyRequests",
        )
    ):
        return "rate_limited"

    return "transport_error"


def resolve_package(
    *,
    package_name: str,
    profile_id: str,
    auth_mode: str,
    country: str = "CH",
    language: str = "en",
    dispenser_url: str | None = None,
) -> ResolverResult:
    """Resolve one package/profile using metadata-only Play lookup."""

    profile = (
        load_reference_profile(
            profile_id
        )
    )

    package_name = (
        package_name.strip()
    )

    if not package_name:
        raise ValueError(
            "package_name is required"
        )

    if auth_mode not in {
        "anonymous",
        "authenticated",
    }:
        raise ValueError(
            "Unsupported auth mode: "
            f"{auth_mode}"
        )

    if (
        auth_mode
        == "anonymous"
        and not dispenser_url
    ):
        return _failure(
            package_name=package_name,
            profile=profile,
            auth_mode=auth_mode,
            status="inconclusive",
            country=country,
            language=language,
            diagnostics=(
                "missing_dispenser"
            ),
        )

    if (
        auth_mode
        == "authenticated"
    ):
        email = os.environ.get(
            AUTH_EMAIL_ENV,
            "",
        ).strip()

        aas_token = os.environ.get(
            AUTH_AAS_ENV,
            "",
        ).strip()

        if (
            not email
            or not aas_token
            or not aas_token.startswith(
                "aas_et/"
            )
        ):
            return _failure(
                package_name=(
                    package_name
                ),
                profile=profile,
                auth_mode=auth_mode,
                status="auth_failed",
                country=country,
                language=language,
                diagnostics=(
                    "missing_or_invalid_"
                    "aas_context"
                ),
            )

    try:
        import goopdl.api as api_module
        import goopdl.auth as auth_module
        import goopdl.profiles as profiles_module

    except ImportError:
        return _failure(
            package_name=package_name,
            profile=profile,
            auth_mode=auth_mode,
            status="inconclusive",
            country=country,
            language=language,
            diagnostics=(
                "goopdl_not_installed"
            ),
        )

    bundle: dict[
        str,
        object,
    ] | None = None

    try:
        if (
            auth_mode
            == "anonymous"
        ):
            (
                bundle,
                failure_status,
                diagnostics,
            ) = _anonymous_bundle(
                dispenser_url=(
                    dispenser_url
                    or ""
                ),
                profile_data=(
                    profile.profile
                ),
                country=country,
                language=language,
                profiles_module=(
                    profiles_module
                ),
            )

            if (
                failure_status
                is not None
            ):
                return _failure(
                    package_name=(
                        package_name
                    ),
                    profile=profile,
                    auth_mode=(
                        auth_mode
                    ),
                    status=(
                        failure_status
                    ),
                    country=country,
                    language=language,
                    diagnostics=(
                        diagnostics
                    ),
                )

        else:
            try:
                bundle = (
                    _authenticated_bundle(
                        profile=profile,
                        country=country,
                        auth_module=(
                            auth_module
                        ),
                    )
                )

            except Exception as exc:
                return _failure(
                    package_name=(
                        package_name
                    ),
                    profile=profile,
                    auth_mode=(
                        auth_mode
                    ),
                    status=(
                        "auth_failed"
                    ),
                    country=country,
                    language=language,
                    diagnostics=(
                        "direct_auth_"
                        + type(exc).__name__
                    ),
                )

            if not bundle:
                return _failure(
                    package_name=(
                        package_name
                    ),
                    profile=profile,
                    auth_mode=(
                        auth_mode
                    ),
                    status=(
                        "auth_failed"
                    ),
                    country=country,
                    language=language,
                    diagnostics=(
                        "direct_auth_no_bundle"
                    ),
                )

        try:
            raw = (
                api_module
                ._fetch_details_raw(
                    package_name,
                    bundle,
                    country=country,
                    proxy=None,
                )
            )

        except Exception as exc:
            return _failure(
                package_name=(
                    package_name
                ),
                profile=profile,
                auth_mode=(
                    auth_mode
                ),
                status=(
                    _play_failure_status(
                        exc
                    )
                ),
                country=country,
                language=language,
                diagnostics=(
                    "play_"
                    + type(exc).__name__
                ),
            )

        try:
            details = (
                api_module
                ._parse_details_proto(
                    raw
                )
            )

            version_name = str(
                details.version_string
                or ""
            ).strip()

            version_code = int(
                details.version_code
                or 0
            )

        except Exception as exc:
            return _failure(
                package_name=(
                    package_name
                ),
                profile=profile,
                auth_mode=(
                    auth_mode
                ),
                status=(
                    "malformed_response"
                ),
                country=country,
                language=language,
                diagnostics=(
                    "play_parse_"
                    + type(exc).__name__
                ),
            )

        if (
            not version_name
            or version_code <= 0
        ):
            return _failure(
                package_name=(
                    package_name
                ),
                profile=profile,
                auth_mode=(
                    auth_mode
                ),
                status=(
                    "malformed_response"
                ),
                country=country,
                language=language,
                diagnostics=(
                    "play_missing_"
                    "version_evidence"
                ),
            )

        return ResolverResult(
            package_name=package_name,
            profile_id=(
                profile.profile_id
            ),
            profile_hash=(
                profile.profile_hash
            ),
            auth_mode=auth_mode,
            status="resolved",
            version_name=(
                version_name
            ),
            version_code=(
                version_code
            ),
            requested_country=(
                country
            ),
            requested_language=(
                language
            ),
        )

    finally:
        if isinstance(
            bundle,
            dict,
        ):
            bundle.clear()
