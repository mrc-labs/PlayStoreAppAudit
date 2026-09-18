from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from playstore_app_audit.services import device_specific_personal_auth as personal_auth
from playstore_app_audit.services import device_specific_personal_session as personal_session
from playstore_app_audit.services.device_specific_profiles import load_reference_profile


@dataclass
class _Response:
    status_code: int
    content: bytes = b""
    text: str = ""


class _FakeSession:
    def __init__(self, responses: dict[tuple[str, str], _Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append(("POST", url, kwargs))
        return self.responses[("POST", url)]

    def get(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append(("GET", url, kwargs))
        return self.responses[("GET", url)]


@pytest.fixture(autouse=True)
def clear_personal_session() -> None:
    personal_session.clear_personal_session()
    yield
    personal_session.clear_personal_session()


def _checkin_payload() -> bytes:
    return personal_auth._proto_varint(7, 0x1234) + personal_auth._proto_bytes(
        12,
        "consistency-token",
    )


def _config_payload() -> bytes:
    nested = personal_auth._proto_bytes(1, "device-config-token")
    nested = personal_auth._proto_bytes(28, nested)
    return personal_auth._proto_bytes(1, nested)


def _successful_session() -> _FakeSession:
    return _FakeSession(
        {
            ("POST", personal_auth.CHECKIN_URL): _Response(
                200,
                content=_checkin_payload(),
            ),
            ("POST", personal_auth.UPLOAD_DEVICE_CONFIG_URL): _Response(
                200,
                content=_config_payload(),
            ),
            ("POST", personal_auth.AUTH_URL): _Response(
                200,
                text="Auth=play-bearer-token\n",
            ),
            ("GET", personal_auth.TOC_URL): _Response(503),
        }
    )


def test_personal_auth_requires_process_local_session() -> None:
    profile = load_reference_profile("android13_api33_s20plus")

    with pytest.raises(
        personal_auth.PersonalGoogleAuthError,
        match="personal_session_not_signed_in",
    ):
        personal_auth.create_personal_auth_bundle(
            profile=profile,
            country="CH",
            language="en",
            session=_successful_session(),  # type: ignore[arg-type]
        )


def test_personal_auth_builds_volatile_bundle_without_identity_fields() -> None:
    email = "private.user@example.com"
    aas = "aas_et/PRIVATE-AAS"
    personal_session.install_personal_session(email, aas)
    profile = load_reference_profile("android13_api33_s20plus")
    session = _successful_session()

    bundle = personal_auth.create_personal_auth_bundle(
        profile=profile,
        country="CH",
        language="en",
        session=session,  # type: ignore[arg-type]
    )

    assert bundle["authToken"] == "play-bearer-token"
    assert bundle["gsfId"] == "1234"
    assert bundle["deviceCheckInConsistencyToken"] == "consistency-token"
    assert bundle["deviceConfigToken"] == "device-config-token"

    serialized = json.dumps(bundle)
    assert email not in serialized
    assert aas not in serialized
    assert "PRIVATE-AAS" not in serialized

    auth_call = next(
        call
        for call in session.calls
        if call[0] == "POST" and call[1] == personal_auth.AUTH_URL
    )
    posted = auth_call[2]["data"]
    assert posted["Email"] == email
    assert posted["Token"] == aas

    checkin_call = session.calls[0]
    assert checkin_call[1] == personal_auth.CHECKIN_URL
    assert email not in repr(checkin_call[2]["data"])
    assert aas not in repr(checkin_call[2]["data"])


def test_personal_auth_patches_store_country_without_reading_sim_identity() -> None:
    personal_session.install_personal_session(
        "private.user@example.com",
        "aas_et/PRIVATE-AAS",
    )
    profile = load_reference_profile("android13_api33_s20plus")
    session = _successful_session()

    bundle = personal_auth.create_personal_auth_bundle(
        profile=profile,
        country="IT",
        language="it",
        session=session,  # type: ignore[arg-type]
    )

    device_info = bundle["deviceInfoProvider"]
    assert isinstance(device_info, dict)
    assert device_info["mccMnc"] == "22201"


def test_personal_auth_failure_is_non_secret() -> None:
    email = "private.user@example.com"
    aas = "aas_et/PRIVATE-AAS"
    personal_session.install_personal_session(email, aas)
    profile = load_reference_profile("android13_api33_s20plus")
    session = _successful_session()
    session.responses[("POST", personal_auth.AUTH_URL)] = _Response(
        403,
        text="Error=BadAuthentication\n",
    )

    with pytest.raises(personal_auth.PersonalGoogleAuthError) as raised:
        personal_auth.create_personal_auth_bundle(
            profile=profile,
            country="CH",
            language="en",
            session=session,  # type: ignore[arg-type]
        )

    message = str(raised.value)
    assert message == "play_token_auth_failed"
    assert email not in message
    assert aas not in message
