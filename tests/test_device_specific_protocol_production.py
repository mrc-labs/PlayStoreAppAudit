from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import requests

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverStatus,
)
from playstore_app_audit.services.device_specific_profiles import load_reference_profile
from playstore_app_audit.services.device_specific_protocol import (
    DETAILS_URL,
    normalise_dispenser_endpoint,
    parse_details_version,
    protobuf_string_path,
    protobuf_value,
    provider_context_hash,
    resolve_metadata_with_auth_bundle,
    resolve_metadata_with_dispenser,
)


def _varint(value: int) -> bytes:
    result = bytearray()
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field_varint(number: int, value: int) -> bytes:
    return _varint(number << 3) + _varint(value)


def _field_fixed64(number: int, value: int) -> bytes:
    return _varint((number << 3) | 1) + value.to_bytes(8, "little")


def _field_fixed32(number: int, value: int) -> bytes:
    return _varint((number << 3) | 5) + value.to_bytes(4, "little")


def _field_bytes(number: int, value: bytes | str) -> bytes:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return _varint((number << 3) | 2) + _varint(len(raw)) + raw


def _field_group(number: int, payload: bytes) -> bytes:
    return (
        _varint((number << 3) | 3)
        + payload
        + _varint((number << 3) | 4)
    )


def _details_payload(version_name: str = "1.2.3", version_code: int = 123) -> bytes:
    app_details = _field_varint(3, version_code) + _field_bytes(4, version_name)
    doc_details = _field_bytes(1, app_details)
    doc = _field_bytes(13, doc_details)
    details = _field_bytes(4, doc)
    payload = _field_bytes(2, details)
    return _field_bytes(1, payload)


@dataclass
class _Response:
    status_code: int
    content: bytes = b""
    json_value: object = None
    json_error: bool = False

    def json(self) -> object:
        if self.json_error:
            raise json.JSONDecodeError("bad", "{", 1)
        return self.json_value


class _FakeSession:
    def __init__(
        self,
        *,
        post_response: _Response | None = None,
        get_response: _Response | None = None,
        post_error: Exception | None = None,
        get_error: Exception | None = None,
    ) -> None:
        self.post_response = post_response or _Response(200, json_value={})
        self.get_response = get_response or _Response(200, content=_details_payload())
        self.post_error = post_error
        self.get_error = get_error
        self.post_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.post_calls.append({"url": url, **kwargs})
        if self.post_error is not None:
            raise self.post_error
        return self.post_response

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.get_calls.append({"url": url, **kwargs})
        if self.get_error is not None:
            raise self.get_error
        return self.get_response


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://localhost:3000/api/auth",
        "http://127.0.0.1:3000/api/auth",
        "http://[::1]:3000/api/auth",
        "https://resolver.example/api/auth",
    ],
)
def test_endpoint_accepts_https_or_loopback_http(endpoint: str) -> None:
    resolved = normalise_dispenser_endpoint(endpoint, country="CH", language="en")
    assert resolved.endswith("locale=en_CH")
    assert len(provider_context_hash(endpoint)) == 64


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://resolver.example/api/auth",
        "ftp://localhost/api/auth",
        "https://user:pass@resolver.example/api/auth",
        "https://resolver.example/api/auth?x=1",
        "https://resolver.example/api/auth#fragment",
        "not-a-url",
    ],
)
def test_endpoint_rejects_insecure_or_ambiguous_context(endpoint: str) -> None:
    with pytest.raises(ValueError):
        normalise_dispenser_endpoint(endpoint, country="CH", language="en")
    with pytest.raises(ValueError):
        provider_context_hash(endpoint)


def test_protobuf_helpers_decode_fixed_integer_wire_types() -> None:
    fixed64 = 0x123456789ABCDEF0
    fixed32 = 0x89ABCDEF
    payload = (
        _field_fixed64(7, fixed64)
        + _field_fixed32(8, fixed32)
        + _field_bytes(12, "consistency-token")
    )

    assert protobuf_value(payload, 7) == fixed64
    assert protobuf_value(payload, 8) == fixed32
    assert protobuf_string_path(payload, 12) == "consistency-token"


def test_google_checkin_device_id_can_be_fixed64() -> None:
    android_id = 0x123456789ABCDEF
    payload = (
        _field_fixed64(7, android_id)
        + _field_bytes(12, "consistency-token")
    )

    value = protobuf_value(payload, 7)
    assert isinstance(value, int)
    assert value == android_id


def test_protobuf_helpers_tolerate_proto2_groups_in_checkin_response() -> None:
    payload = b"".join(
        (
            _field_group(3, _field_varint(1, 99)),
            _field_varint(7, 0x123456),
            _field_group(
                10,
                _field_bytes(1, "nested")
                + _field_group(2, _field_varint(1, 1)),
            ),
            _field_bytes(12, "consistency-token"),
            _field_group(20, _field_varint(1, 7)),
        )
    )

    assert protobuf_value(payload, 7) == 0x123456
    assert protobuf_string_path(payload, 12) == "consistency-token"


def test_protobuf_helpers_reject_mismatched_group_end() -> None:
    payload = (
        _varint((3 << 3) | 3)
        + _field_varint(1, 1)
        + _varint((4 << 3) | 4)
    )

    with pytest.raises(ValueError, match="mismatched end group"):
        protobuf_value(payload, 7)


def test_minimal_protobuf_parser_extracts_version_evidence() -> None:
    parsed = parse_details_version(_details_payload("577.0.0.50.72", 474426253))
    assert parsed.version_name == "577.0.0.50.72"
    assert parsed.version_code == 474426253


@pytest.mark.parametrize("payload", [b"", b"\x0a\x02\x12", _details_payload("", 1)])
def test_minimal_protobuf_parser_fails_closed(payload: bytes) -> None:
    with pytest.raises(ValueError):
        parse_details_version(payload)


def _auth_payload() -> dict[str, object]:
    return {
        "authToken": "test-bearer",
        "gsfId": "123456",
        "deviceCheckInConsistencyToken": "consistency",
        "deviceConfigToken": "config",
        "dfeCookie": "cookie",
        "email": "dummy@example.invalid",
        "aasToken": "test-aas",
        "userProfile": {"name": "dummy"},
        "deviceInfoProvider": {
            "userAgentString": "test-agent",
            "mccMnc": "00000",
        },
    }


def test_success_path_is_metadata_only_and_keeps_secrets_out_of_result() -> None:
    session = _FakeSession(
        post_response=_Response(200, json_value=_auth_payload()),
        get_response=_Response(200, content=_details_payload("26.09.03", 262843364)),
    )
    profile = load_reference_profile("android13_api33_s20plus")
    result = resolve_metadata_with_dispenser(
        package_name="com.adobe.scan.android",
        profile=profile,
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=session,  # type: ignore[arg-type]
    )
    assert result.status is ResolverStatus.RESOLVED
    assert result.version_name == "26.09.03"
    assert result.version_code == 262843364
    assert result.diagnostics == ""
    serialized = json.dumps(result.to_mapping())
    assert "test-bearer" not in serialized
    assert "dummy@example.invalid" not in serialized
    assert len(session.post_calls) == 1
    assert len(session.get_calls) == 1
    assert session.get_calls[0]["url"] == DETAILS_URL
    posted_profile = session.post_calls[0]["json"]
    assert posted_profile["CellOperator"] == "228"
    assert posted_profile["SimOperator"] == "01"


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, ResolverStatus.AUTH_FAILED),
        (403, ResolverStatus.AUTH_FAILED),
        (429, ResolverStatus.RATE_LIMITED),
        (503, ResolverStatus.TRANSPORT_ERROR),
    ],
)
def test_dispenser_http_failures_are_typed(
    status_code: int,
    expected: ResolverStatus,
) -> None:
    session = _FakeSession(post_response=_Response(status_code))
    result = resolve_metadata_with_dispenser(
        package_name="com.example.app",
        profile=load_reference_profile("android10_api29_oneplus8pro"),
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=session,  # type: ignore[arg-type]
    )
    assert result.status is expected
    assert result.version_name is None
    assert result.version_code is None


def test_dispenser_transport_and_malformed_json_fail_closed() -> None:
    transport = _FakeSession(post_error=requests.Timeout("offline"))
    result = resolve_metadata_with_dispenser(
        package_name="com.example.app",
        profile=load_reference_profile("android10_api29_oneplus8pro"),
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=transport,  # type: ignore[arg-type]
    )
    assert result.status is ResolverStatus.TRANSPORT_ERROR

    malformed = _FakeSession(post_response=_Response(200, json_error=True))
    result = resolve_metadata_with_dispenser(
        package_name="com.example.app",
        profile=load_reference_profile("android10_api29_oneplus8pro"),
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=malformed,  # type: ignore[arg-type]
    )
    assert result.status is ResolverStatus.MALFORMED_RESPONSE


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (404, ResolverStatus.UNAVAILABLE_FOR_PROFILE),
        (401, ResolverStatus.AUTH_FAILED),
        (403, ResolverStatus.AUTH_FAILED),
        (429, ResolverStatus.RATE_LIMITED),
        (503, ResolverStatus.TRANSPORT_ERROR),
    ],
)
def test_play_http_failures_are_typed(
    status_code: int,
    expected: ResolverStatus,
) -> None:
    session = _FakeSession(
        post_response=_Response(200, json_value=_auth_payload()),
        get_response=_Response(status_code),
    )
    result = resolve_metadata_with_dispenser(
        package_name="com.example.app",
        profile=load_reference_profile("android13_api33_s20plus"),
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=session,  # type: ignore[arg-type]
    )
    assert result.status is expected
    assert result.version_name is None
    assert result.version_code is None


def test_play_malformed_details_fail_closed() -> None:
    session = _FakeSession(
        post_response=_Response(200, json_value=_auth_payload()),
        get_response=_Response(200, content=b"not-protobuf"),
    )
    result = resolve_metadata_with_dispenser(
        package_name="com.example.app",
        profile=load_reference_profile("android13_api33_s20plus"),
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
        session=session,  # type: ignore[arg-type]
    )
    assert result.status is ResolverStatus.MALFORMED_RESPONSE


def test_production_protocol_has_no_download_or_goopdl_runtime_path() -> None:
    source = Path(
        "playstore_app_audit/services/device_specific_protocol.py"
    ).read_text(encoding="utf-8")
    lowered = source.casefold()
    assert "import goopdl" not in lowered
    assert "/purchase" not in lowered
    assert "/delivery" not in lowered
    assert "download_batch" not in lowered


def test_personal_auth_bundle_uses_shared_metadata_only_details_path() -> None:
    session = _FakeSession(
        get_response=_Response(
            200,
            content=_details_payload("577.0.0.50.72", 474426253),
        ),
    )
    profile = load_reference_profile("android13_api33_s20plus")
    auth = _auth_payload()

    result = resolve_metadata_with_auth_bundle(
        package_name="com.facebook.katana",
        profile=profile,
        auth_bundle=auth,
        country="CH",
        language="en",
        provider=ResolverProvider.PERSONAL_GOOGLE_SESSION,
        session=session,  # type: ignore[arg-type]
    )

    assert result.status is ResolverStatus.RESOLVED
    assert result.provider is ResolverProvider.PERSONAL_GOOGLE_SESSION
    assert result.version_name == "577.0.0.50.72"
    assert result.version_code == 474426253
    assert len(session.post_calls) == 0
    assert len(session.get_calls) == 1
    serialized = json.dumps(result.to_mapping())
    assert "test-bearer" not in serialized
    assert "123456" not in serialized
    assert auth["authToken"] == "test-bearer"
