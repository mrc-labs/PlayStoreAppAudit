"""Project-owned metadata-only Google Play protocol for Device Specific resolution."""

from __future__ import annotations

import hashlib
import ipaddress
import urllib.parse
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import requests

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services.device_specific_profiles import ReferenceProfile

PROTOCOL_REVISION = "fdfe-details-v1"
DETAILS_URL = "https://android.clients.google.com/fdfe/details"
ENCODED_TARGETS = (
    "CAESN/qigQYC2AMBFfUbyA7SM5Ij/CvfBoIDgxXrBPsDlQUdMfOLAfoFrwEHgAcBrQYhoA0cGt4MKK0Y2gI"
)

COUNTRY_MCC_MNC: dict[str, tuple[str, str]] = {
    "AT": ("232", "01"),
    "AU": ("505", "01"),
    "BE": ("206", "01"),
    "CA": ("302", "720"),
    "CH": ("228", "01"),
    "DE": ("262", "01"),
    "ES": ("214", "01"),
    "FR": ("208", "01"),
    "GB": ("234", "30"),
    "IT": ("222", "01"),
    "NL": ("204", "04"),
    "NO": ("242", "01"),
    "SE": ("240", "01"),
    "US": ("310", "38"),
}

_AUTH_BUNDLE_FIELDS = frozenset(
    {
        "authToken",
        "gsfId",
        "deviceCheckInConsistencyToken",
        "deviceConfigToken",
        "dfeCookie",
        "deviceInfoProvider",
    }
)


class ProtobufDecodeError(ValueError):
    """Raised when the small details-response protobuf subset is malformed."""


@dataclass(frozen=True, slots=True)
class ParsedPlayVersion:
    version_name: str
    version_code: int


def _normalise_country(country: str) -> str:
    value = str(country or "").strip().upper()
    if len(value) != 2 or not value.isalpha():
        raise ValueError("country must be a two-letter code")
    return value


def _normalise_language(language: str) -> str:
    value = str(language or "").strip().lower().replace("_", "-")
    if not value or any(char.isspace() for char in value):
        raise ValueError("language is required")
    return value


def _is_loopback_host(hostname: str) -> bool:
    if hostname.casefold() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


def normalise_dispenser_endpoint(
    dispenser_url: str,
    *,
    country: str,
    language: str,
) -> str:
    parsed = urllib.parse.urlsplit(str(dispenser_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("dispenser endpoint must be an explicit http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("dispenser endpoint must not contain credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("dispenser endpoint must not contain query or fragment")
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ValueError("plain HTTP dispenser endpoints are allowed only on loopback")

    locale = f"{_normalise_language(language)}_{_normalise_country(country)}"
    return urllib.parse.urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urllib.parse.urlencode({"locale": locale}),
            "",
        )
    )


def provider_context_hash(dispenser_url: str) -> str:
    parsed = urllib.parse.urlsplit(str(dispenser_url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("dispenser endpoint must be an explicit http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("dispenser endpoint contains unsupported context")
    if parsed.scheme == "http" and not _is_loopback_host(parsed.hostname):
        raise ValueError("plain HTTP dispenser endpoints are allowed only on loopback")
    canonical = urllib.parse.urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            parsed.path or "/",
            "",
            "",
        )
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def profile_for_country(profile: ReferenceProfile, country: str) -> dict[str, str]:
    patched = dict(profile.profile)
    pair = COUNTRY_MCC_MNC.get(_normalise_country(country))
    if pair is not None:
        mcc, mnc = pair
        patched["CellOperator"] = mcc
        patched["SimOperator"] = mnc
    patched.setdefault("Roaming", "mobile-notroaming")
    return patched


def sanitize_auth_bundle(
    value: object,
    *,
    country: str,
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    bundle = {
        str(key): item
        for key, item in value.items()
        if str(key) in _AUTH_BUNDLE_FIELDS
    }
    auth_token = str(bundle.get("authToken") or "").strip()
    gsf_id = str(bundle.get("gsfId") or "").strip()
    if not auth_token or not gsf_id:
        return None

    device_info_raw = bundle.get("deviceInfoProvider")
    device_info = dict(device_info_raw) if isinstance(device_info_raw, Mapping) else {}
    pair = COUNTRY_MCC_MNC.get(_normalise_country(country))
    if pair is not None:
        device_info["mccMnc"] = "".join(pair)
    bundle["deviceInfoProvider"] = {
        "userAgentString": str(device_info.get("userAgentString") or ""),
        "mccMnc": str(device_info.get("mccMnc") or ""),
    }
    return bundle


def fdfe_headers(
    bundle: Mapping[str, Any],
    *,
    country: str,
    language: str,
) -> dict[str, str]:
    device_info_raw = bundle.get("deviceInfoProvider")
    device_info = dict(device_info_raw) if isinstance(device_info_raw, Mapping) else {}
    locale = f"{_normalise_language(language)}_{_normalise_country(country)}"
    headers = {
        "Authorization": f"Bearer {bundle['authToken']}",
        "User-Agent": str(device_info.get("userAgentString") or "Android-Finsky"),
        "X-DFE-Device-Id": str(bundle["gsfId"]),
        "Accept-Language": locale.replace("_", "-"),
        "Content-Type": "application/x-protobuf",
        "Accept": "application/x-protobuf",
        "X-DFE-Encoded-Targets": ENCODED_TARGETS,
        "X-DFE-Client-Id": "am-android-google",
        "X-DFE-Network-Type": "4",
        "X-DFE-Content-Filters": "",
        "X-Limit-Ad-Tracking-Enabled": "false",
        "X-Ad-Id": "",
        "X-DFE-UserLanguages": locale,
        "X-DFE-Request-Params": "timeoutMs=4000",
        "X-DFE-No-Prefetch": "true",
    }
    optional = {
        "deviceCheckInConsistencyToken": "X-DFE-Device-Checkin-Consistency-Token",
        "deviceConfigToken": "X-DFE-Device-Config-Token",
        "dfeCookie": "X-DFE-Cookie",
    }
    for key, header in optional.items():
        value = str(bundle.get(key) or "").strip()
        if value:
            headers[header] = value

    mcc_mnc = str(device_info.get("mccMnc") or "").strip()
    if mcc_mnc:
        headers["X-DFE-MCCMNC"] = mcc_mnc
    return headers


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(10):
        if offset >= len(data):
            raise ProtobufDecodeError("truncated varint")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, offset
        shift += 7
    raise ProtobufDecodeError("varint exceeds 64-bit encoding")


def _read_group(
    data: bytes,
    offset: int,
    field_number: int,
) -> tuple[bytes, int]:
    start = offset
    while offset < len(data):
        tag_start = offset
        tag, offset = _read_varint(data, offset)
        nested_field = tag >> 3
        wire_type = tag & 7
        if nested_field <= 0:
            raise ProtobufDecodeError("invalid field number")
        if wire_type == 4:
            if nested_field != field_number:
                raise ProtobufDecodeError("mismatched end group")
            return data[start:tag_start], offset
        offset = _skip_value(
            data,
            offset,
            nested_field,
            wire_type,
        )
    raise ProtobufDecodeError("truncated group")


def _skip_value(
    data: bytes,
    offset: int,
    field_number: int,
    wire_type: int,
) -> int:
    if wire_type == 0:
        _value, offset = _read_varint(data, offset)
        return offset
    if wire_type == 1:
        end = offset + 8
        if end > len(data):
            raise ProtobufDecodeError("truncated fixed64")
        return end
    if wire_type == 2:
        size, offset = _read_varint(data, offset)
        end = offset + size
        if end > len(data):
            raise ProtobufDecodeError("truncated bytes field")
        return end
    if wire_type == 3:
        _value, offset = _read_group(data, offset, field_number)
        return offset
    if wire_type == 4:
        raise ProtobufDecodeError("unexpected end group")
    if wire_type == 5:
        end = offset + 4
        if end > len(data):
            raise ProtobufDecodeError("truncated fixed32")
        return end
    raise ProtobufDecodeError(f"unsupported wire type: {wire_type}")


def _fields(data: bytes) -> list[tuple[int, int, int | bytes]]:
    result: list[tuple[int, int, int | bytes]] = []
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        field_number = tag >> 3
        wire_type = tag & 7
        if field_number <= 0:
            raise ProtobufDecodeError("invalid field number")

        if wire_type == 0:
            value, offset = _read_varint(data, offset)
        elif wire_type == 1:
            end = offset + 8
            if end > len(data):
                raise ProtobufDecodeError("truncated fixed64")
            value = int.from_bytes(data[offset:end], "little")
            offset = end
        elif wire_type == 2:
            size, offset = _read_varint(data, offset)
            end = offset + size
            if end > len(data):
                raise ProtobufDecodeError("truncated bytes field")
            value = data[offset:end]
            offset = end
        elif wire_type == 3:
            value, offset = _read_group(data, offset, field_number)
        elif wire_type == 4:
            raise ProtobufDecodeError("unexpected end group")
        elif wire_type == 5:
            end = offset + 4
            if end > len(data):
                raise ProtobufDecodeError("truncated fixed32")
            value = int.from_bytes(data[offset:end], "little")
            offset = end
        else:
            raise ProtobufDecodeError(f"unsupported wire type: {wire_type}")
        result.append((field_number, wire_type, value))
    return result


def _first_bytes(
    fields: list[tuple[int, int, int | bytes]],
    field_number: int,
) -> bytes | None:
    for number, wire_type, value in fields:
        if number == field_number and wire_type == 2 and isinstance(value, bytes):
            return value
    return None


def _navigate(data: bytes, *path: int) -> list[tuple[int, int, int | bytes]]:
    current = data
    for field_number in path:
        nested = _first_bytes(_fields(current), field_number)
        if nested is None:
            return []
        current = nested
    return _fields(current)


def protobuf_value(data: bytes, field_number: int) -> int | bytes:
    """Return the first protobuf field value from the shared tiny decoder."""

    for number, _wire_type, value in _fields(data):
        if number == field_number:
            return value
    raise ProtobufDecodeError(f"protobuf field {field_number} is missing")


def protobuf_string_path(data: bytes, *path: int) -> str:
    value: int | bytes = data
    for field_number in path:
        if not isinstance(value, bytes):
            raise ProtobufDecodeError("protobuf path is not length-delimited")
        value = protobuf_value(value, field_number)
    if not isinstance(value, bytes):
        raise ProtobufDecodeError("protobuf path does not end in bytes")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProtobufDecodeError("protobuf string is not UTF-8") from exc


def parse_details_version(raw: bytes) -> ParsedPlayVersion:
    doc_fields = _navigate(raw, 1, 2, 4)
    if not doc_fields:
        raise ProtobufDecodeError("details response has no DocV2")

    doc_details = _first_bytes(doc_fields, 13)
    if doc_details is None:
        raise ProtobufDecodeError("details response has no DocDetails")
    app_details = _first_bytes(_fields(doc_details), 1)
    if app_details is None:
        raise ProtobufDecodeError("details response has no AppDetails")

    version_code = 0
    version_name = ""
    for number, wire_type, value in _fields(app_details):
        if number == 3 and wire_type == 0 and isinstance(value, int):
            version_code = value
        elif number == 4 and wire_type == 2 and isinstance(value, bytes):
            try:
                version_name = value.decode("utf-8").strip()
            except UnicodeDecodeError as exc:
                raise ProtobufDecodeError("version string is not UTF-8") from exc

    if version_code <= 0 or not version_name:
        raise ProtobufDecodeError("details response has incomplete version evidence")
    return ParsedPlayVersion(version_name=version_name, version_code=version_code)


def _failure(
    *,
    package_name: str,
    profile: ReferenceProfile,
    status: ResolverStatus,
    country: str,
    language: str,
    diagnostics: str,
    provider: ResolverProvider = ResolverProvider.ANONYMOUS_DISPENSER,
) -> ResolverResult:
    return ResolverResult(
        package_name=package_name,
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=provider,
        status=status,
        requested_country=country,
        requested_language=language,
        diagnostics=diagnostics,
    )


def resolve_metadata_with_auth_bundle(
    *,
    package_name: str,
    profile: ReferenceProfile,
    auth_bundle: Mapping[str, Any],
    country: str,
    language: str,
    provider: ResolverProvider,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> ResolverResult:
    """Resolve metadata from a process-local auth bundle without persisting secrets."""

    package = str(package_name or "").strip()
    if not package:
        raise ValueError("package_name is required")
    country = _normalise_country(country)
    language = _normalise_language(language)

    bundle = sanitize_auth_bundle(auth_bundle, country=country)
    if bundle is None:
        return _failure(
            package_name=package,
            profile=profile,
            status=ResolverStatus.AUTH_FAILED,
            country=country,
            language=language,
            diagnostics="personal_auth_context_incomplete",
            provider=provider,
        )

    client = session or requests.Session()
    owns_client = session is None
    try:
        try:
            details_response = client.get(
                DETAILS_URL,
                params={"doc": package, "gl": country},
                headers=fdfe_headers(bundle, country=country, language=language),
                timeout=timeout,
            )
        except requests.RequestException:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.TRANSPORT_ERROR,
                country=country,
                language=language,
                diagnostics="play_transport_error",
                provider=provider,
            )

        if details_response.status_code == 404:
            status = ResolverStatus.UNAVAILABLE_FOR_PROFILE
        elif details_response.status_code in {401, 403}:
            status = ResolverStatus.AUTH_FAILED
        elif details_response.status_code == 429:
            status = ResolverStatus.RATE_LIMITED
        elif details_response.status_code != 200:
            status = ResolverStatus.TRANSPORT_ERROR
        else:
            status = None

        if status is not None:
            return _failure(
                package_name=package,
                profile=profile,
                status=status,
                country=country,
                language=language,
                diagnostics=f"play_http_{details_response.status_code}",
                provider=provider,
            )

        try:
            parsed = parse_details_version(details_response.content)
        except ValueError:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.MALFORMED_RESPONSE,
                country=country,
                language=language,
                diagnostics="play_malformed_details",
                provider=provider,
            )

        return ResolverResult(
            package_name=package,
            profile_id=profile.profile_id,
            profile_hash=profile.profile_hash,
            provider=provider,
            status=ResolverStatus.RESOLVED,
            requested_country=country,
            requested_language=language,
            version_name=parsed.version_name,
            version_code=parsed.version_code,
        )
    finally:
        bundle.clear()
        if owns_client:
            client.close()


def resolve_metadata_with_dispenser(
    *,
    package_name: str,
    profile: ReferenceProfile,
    dispenser_url: str,
    country: str,
    language: str,
    timeout: float = 30.0,
    session: requests.Session | None = None,
) -> ResolverResult:
    package = str(package_name or "").strip()
    if not package:
        raise ValueError("package_name is required")
    country = _normalise_country(country)
    language = _normalise_language(language)

    try:
        endpoint = normalise_dispenser_endpoint(
            dispenser_url,
            country=country,
            language=language,
        )
    except ValueError:
        return _failure(
            package_name=package,
            profile=profile,
            status=ResolverStatus.INCONCLUSIVE,
            country=country,
            language=language,
            diagnostics="invalid_dispenser_endpoint",
        )

    client = session or requests.Session()
    owns_client = session is None
    bundle: dict[str, Any] | None = None
    try:
        try:
            auth_response = client.post(
                endpoint,
                json=profile_for_country(profile, country),
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "StoreAppAudit-DeviceSpecific/1",
                },
                timeout=timeout,
            )
        except requests.RequestException:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.TRANSPORT_ERROR,
                country=country,
                language=language,
                diagnostics="dispenser_transport_error",
            )

        if auth_response.status_code in {401, 403}:
            status = ResolverStatus.AUTH_FAILED
        elif auth_response.status_code == 429:
            status = ResolverStatus.RATE_LIMITED
        elif auth_response.status_code != 200:
            status = ResolverStatus.TRANSPORT_ERROR
        else:
            status = None
        if status is not None:
            return _failure(
                package_name=package,
                profile=profile,
                status=status,
                country=country,
                language=language,
                diagnostics=f"dispenser_http_{auth_response.status_code}",
            )

        try:
            payload = auth_response.json()
        except ValueError:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.MALFORMED_RESPONSE,
                country=country,
                language=language,
                diagnostics="dispenser_malformed_json",
            )

        bundle = sanitize_auth_bundle(payload, country=country)
        if bundle is None:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.MALFORMED_RESPONSE,
                country=country,
                language=language,
                diagnostics="dispenser_incomplete_auth_context",
            )

        try:
            details_response = client.get(
                DETAILS_URL,
                params={"doc": package, "gl": country},
                headers=fdfe_headers(bundle, country=country, language=language),
                timeout=timeout,
            )
        except requests.RequestException:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.TRANSPORT_ERROR,
                country=country,
                language=language,
                diagnostics="play_transport_error",
            )

        if details_response.status_code == 404:
            status = ResolverStatus.UNAVAILABLE_FOR_PROFILE
        elif details_response.status_code in {401, 403}:
            status = ResolverStatus.AUTH_FAILED
        elif details_response.status_code == 429:
            status = ResolverStatus.RATE_LIMITED
        elif details_response.status_code != 200:
            status = ResolverStatus.TRANSPORT_ERROR
        else:
            status = None
        if status is not None:
            return _failure(
                package_name=package,
                profile=profile,
                status=status,
                country=country,
                language=language,
                diagnostics=f"play_http_{details_response.status_code}",
            )

        try:
            parsed = parse_details_version(details_response.content)
        except ValueError:
            return _failure(
                package_name=package,
                profile=profile,
                status=ResolverStatus.MALFORMED_RESPONSE,
                country=country,
                language=language,
                diagnostics="play_malformed_details",
            )

        return ResolverResult(
            package_name=package,
            profile_id=profile.profile_id,
            profile_hash=profile.profile_hash,
            provider=ResolverProvider.ANONYMOUS_DISPENSER,
            status=ResolverStatus.RESOLVED,
            requested_country=country,
            requested_language=language,
            version_name=parsed.version_name,
            version_code=parsed.version_code,
        )
    finally:
        if bundle is not None:
            bundle.clear()
        if owns_client:
            client.close()
