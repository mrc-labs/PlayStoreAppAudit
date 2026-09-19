"""Metadata-only direct Google Play authentication for Personal Google Session.

Protocol structure is adapted from Villoh/goopdl 1.2.1 (MIT):
Copyright (c) 2021 Rehmat Alam
Copyright (c) 2025 Mikel Villota

Only check-in, device-config registration and Google Play token exchange are
implemented. There is no APK purchase, delivery or download path.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from contextlib import suppress
from typing import Protocol

import requests

from playstore_app_audit.services import (
    device_specific_personal_session,
    device_specific_protocol,
)

CHECKIN_URL = "https://android.clients.google.com/checkin"
UPLOAD_DEVICE_CONFIG_URL = "https://android.clients.google.com/fdfe/uploadDeviceConfig"
AUTH_URL = "https://android.clients.google.com/auth"
TOC_URL = "https://android.clients.google.com/fdfe/toc"


class DeviceProfileLike(Protocol):
    profile_id: str
    profile_hash: str
    profile: Mapping[str, str]


class PersonalGoogleAuthError(RuntimeError):
    """Direct auth failed at a non-secret protocol stage."""


def _varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def _proto_varint(field: int, value: int) -> bytes:
    return _varint(field << 3) + _varint(value)


def _proto_bytes(field: int, value: str | bytes) -> bytes:
    data = value.encode() if isinstance(value, str) else value
    return _varint((field << 3) | 2) + _varint(len(data)) + data


def _profile_bool(profile: Mapping[str, str], key: str) -> int:
    return int(str(profile.get(key) or "false").casefold() == "true")


def _profile_for_country(
    profile: Mapping[str, str],
    country: str,
) -> dict[str, str]:
    patched = {str(key): str(value) for key, value in profile.items()}
    pair = device_specific_protocol.COUNTRY_MCC_MNC.get(country.upper())
    if pair is not None:
        mcc, mnc = pair
        patched["CellOperator"] = mcc
        patched["SimOperator"] = mnc
    patched.setdefault("Roaming", "mobile-notroaming")
    return patched


def _device_configuration(profile: Mapping[str, str]) -> bytes:
    fields = bytearray()
    for number, key in (
        (1, "TouchScreen"),
        (2, "Keyboard"),
        (3, "Navigation"),
        (4, "ScreenLayout"),
        (7, "Screen.Density"),
        (8, "GL.Version"),
        (12, "Screen.Width"),
        (13, "Screen.Height"),
        (20, "TotalMemoryBytes"),
        (21, "MaxNumOfCPUCores"),
    ):
        value = str(profile.get(key) or "").strip()
        if value:
            fields += _proto_varint(number, int(value))

    fields += _proto_varint(5, _profile_bool(profile, "HasHardKeyboard"))
    fields += _proto_varint(6, _profile_bool(profile, "HasFiveWayNavigation"))
    fields += _proto_varint(19, _profile_bool(profile, "LowRamDevice"))

    for number, key in (
        (9, "SharedLibraries"),
        (10, "Features"),
        (11, "Platforms"),
        (14, "Locales"),
        (15, "GL.Extensions"),
    ):
        for value in filter(None, str(profile.get(key) or "").split(",")):
            fields += _proto_bytes(number, value)

    for feature in filter(None, str(profile.get("Features") or "").split(",")):
        fields += _proto_bytes(
            26,
            _proto_bytes(1, feature) + _proto_varint(2, 0),
        )
    fields += _proto_varint(16, 0)
    return bytes(fields)


def _google_auth_user_agent(profile: Mapping[str, str]) -> str:
    return (
        f"GoogleAuth/1.4 ({profile.get('Build.DEVICE', '')} "
        f"{profile.get('Build.ID', '')})"
    )


def _finsky_user_agent(profile: Mapping[str, str]) -> str:
    platforms = str(profile.get("Platforms") or "").replace(",", ";")
    values = (
        ("api", "3"),
        ("versionCode", str(profile.get("Vending.version") or "")),
        ("sdk", str(profile.get("Build.VERSION.SDK_INT") or "")),
        ("device", str(profile.get("Build.DEVICE") or "")),
        ("hardware", str(profile.get("Build.HARDWARE") or "")),
        ("product", str(profile.get("Build.PRODUCT") or "")),
        (
            "platformVersionRelease",
            str(profile.get("Build.VERSION.RELEASE") or ""),
        ),
        ("model", str(profile.get("Build.MODEL") or "").replace(" ", "%20")),
        ("buildId", str(profile.get("Build.ID") or "")),
        ("isWideScreen", "0"),
        ("supportedAbis", platforms),
    )
    properties = ",".join(f"{key}={value}" for key, value in values)
    return f"Android-Finsky/{profile.get('Vending.versionString', '')} ({properties})"


def _checkin_request(
    profile: Mapping[str, str],
    device_config: bytes,
    locale: str,
) -> bytes:
    build = b"".join(
        _proto_bytes(number, str(profile.get(key) or "").replace("\\:", ":"))
        for number, key in (
            (1, "Build.FINGERPRINT"),
            (2, "Build.HARDWARE"),
            (3, "Build.BRAND"),
            (4, "Build.RADIO"),
            (5, "Build.BOOTLOADER"),
            (6, "Client"),
        )
    )
    build += _proto_varint(7, int(time.time()))
    build += _proto_varint(8, int(profile.get("GSF.version") or 0))
    build += b"".join(
        _proto_bytes(number, str(profile.get(key) or ""))
        for number, key in (
            (9, "Build.DEVICE"),
            (11, "Build.MODEL"),
            (12, "Build.MANUFACTURER"),
            (13, "Build.PRODUCT"),
        )
    )
    build += _proto_varint(10, int(profile.get("Build.VERSION.SDK_INT") or 0))
    build += _proto_varint(14, _profile_bool(profile, "OtaInstalled"))

    checkin = _proto_bytes(1, build) + _proto_varint(2, 0)
    for number, key in ((6, "CellOperator"), (7, "SimOperator"), (8, "Roaming")):
        checkin += _proto_bytes(number, str(profile.get(key) or ""))
    checkin += _proto_varint(9, 0)

    return b"".join(
        (
            _proto_varint(2, 0),
            _proto_bytes(4, checkin),
            _proto_bytes(6, locale),
            _proto_bytes(12, str(profile.get("TimeZone") or "UTC")),
            _proto_varint(14, 3),
            _proto_bytes(18, device_config),
            _proto_varint(20, 0),
        )
    )


def _safe_auth_values(text: str) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in str(text or "").splitlines()
        if "=" in line
    )


def create_personal_auth_bundle(
    *,
    profile: DeviceProfileLike,
    country: str,
    language: str,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> dict[str, object]:
    """Create one volatile Play auth bundle for the selected device profile."""

    credentials = device_specific_personal_session.personal_session_credentials()
    if credentials is None:
        raise PersonalGoogleAuthError("personal_session_not_signed_in")

    country = str(country or "").strip().upper()
    language = str(language or "").strip().lower().replace("_", "-")
    if len(country) != 2 or not country.isalpha() or not language:
        raise PersonalGoogleAuthError("invalid_locale_context")

    email, aas_token = credentials
    profile_data = _profile_for_country(profile.profile, country)
    locale = f"{language.split('-', 1)[0]}_{country}"
    auth_user_agent = _google_auth_user_agent(profile_data)
    finsky_user_agent = _finsky_user_agent(profile_data)
    device_config = _device_configuration(profile_data)

    client = session or requests.Session()
    owns_client = session is None
    try:
        try:
            checkin = client.post(
                CHECKIN_URL,
                data=_checkin_request(profile_data, device_config, locale),
                headers={
                    "app": "com.google.android.gms",
                    "Content-Type": "application/x-protobuffer",
                    "Host": "android.clients.google.com",
                    "User-Agent": auth_user_agent,
                },
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise PersonalGoogleAuthError("checkin_transport_error") from exc

        if checkin.status_code == 429:
            raise PersonalGoogleAuthError("checkin_rate_limited")
        if checkin.status_code != 200:
            raise PersonalGoogleAuthError(f"checkin_http_{checkin.status_code}")

        try:
            android_id = device_specific_protocol.protobuf_value(
                checkin.content,
                7,
            )
        except ValueError as exc:
            raise PersonalGoogleAuthError(
                "checkin_device_id_parse_error"
            ) from exc
        if not isinstance(android_id, int):
            raise PersonalGoogleAuthError("checkin_device_id_type_error")

        try:
            consistency_token = device_specific_protocol.protobuf_string_path(
                checkin.content,
                12,
            )
        except ValueError as exc:
            raise PersonalGoogleAuthError(
                "checkin_consistency_token_parse_error"
            ) from exc
        if not consistency_token:
            raise PersonalGoogleAuthError(
                "checkin_consistency_token_empty"
            )
        gsf_id = format(android_id, "x")

        partial: dict[str, object] = {
            "authToken": "",
            "gsfId": gsf_id,
            "deviceCheckInConsistencyToken": consistency_token,
            "deviceConfigToken": "",
            "dfeCookie": "",
            "deviceInfoProvider": {
                "userAgentString": finsky_user_agent,
                "mccMnc": (
                    f"{profile_data.get('CellOperator', '')}"
                    f"{profile_data.get('SimOperator', '')}"
                ),
            },
        }

        upload_headers = device_specific_protocol.fdfe_headers(
            partial,
            country=country,
            language=language,
        )
        upload_headers.pop("Authorization", None)
        upload_headers["Content-Type"] = "application/x-protobuf"
        try:
            upload = client.post(
                UPLOAD_DEVICE_CONFIG_URL,
                data=_proto_bytes(1, device_config),
                headers=upload_headers,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise PersonalGoogleAuthError("device_config_transport_error") from exc

        if upload.status_code == 429:
            raise PersonalGoogleAuthError("device_config_rate_limited")
        if upload.status_code != 200:
            raise PersonalGoogleAuthError(
                f"device_config_http_{upload.status_code}"
            )
        try:
            config_token = device_specific_protocol.protobuf_string_path(
                upload.content,
                1,
                28,
                1,
            )
        except ValueError as exc:
            raise PersonalGoogleAuthError("device_config_malformed_response") from exc

        try:
            auth_response = client.post(
                AUTH_URL,
                data={
                    "Email": email,
                    "Token": aas_token,
                    "service": "oauth2:https://www.googleapis.com/auth/googleplay",
                    "app": "com.android.vending",
                    "client_sig": "38918a453d07199354f8b19af05ec6562ced5788",
                    "callerPkg": "com.google.android.gms",
                    "callerSig": "38918a453d07199354f8b19af05ec6562ced5788",
                    "androidId": gsf_id,
                    "google_play_services_version": profile_data.get("GSF.version", ""),
                    "sdk_version": profile_data.get("Build.VERSION.SDK_INT", ""),
                    "device_country": country.lower(),
                    "lang": language.split("-", 1)[0],
                    "oauth2_foreground": "1",
                    "token_request_options": "CAA4AVAB",
                    "check_email": "1",
                    "system_partition": "1",
                    "droidguard_results": "null",
                },
                headers={
                    "app": "com.google.android.gms",
                    "device": gsf_id,
                    "User-Agent": auth_user_agent,
                },
                timeout=timeout,
            )
        except requests.RequestException as exc:
            raise PersonalGoogleAuthError("play_token_transport_error") from exc

        auth_values = _safe_auth_values(auth_response.text)
        if auth_response.status_code == 429:
            raise PersonalGoogleAuthError("play_token_rate_limited")
        if auth_response.status_code in {401, 403} or auth_values.get("Error"):
            raise PersonalGoogleAuthError("play_token_auth_failed")
        if auth_response.status_code != 200:
            raise PersonalGoogleAuthError(
                f"play_token_http_{auth_response.status_code}"
            )
        bearer = str(auth_values.get("Auth") or "").strip()
        if not bearer:
            raise PersonalGoogleAuthError("play_token_malformed_response")

        bundle = {
            **partial,
            "authToken": bearer,
            "deviceConfigToken": config_token,
        }

        toc_headers = device_specific_protocol.fdfe_headers(
            bundle,
            country=country,
            language=language,
        )
        try:
            toc = client.get(TOC_URL, headers=toc_headers, timeout=timeout)
        except requests.RequestException:
            toc = None
        if toc is not None and toc.status_code == 200:
            with suppress(ValueError):
                bundle["dfeCookie"] = device_specific_protocol.protobuf_string_path(
                    toc.content,
                    1,
                    6,
                    22,
                )
        return bundle
    finally:
        email = ""
        aas_token = ""
        if owns_client:
            client.close()
