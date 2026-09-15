from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

import pytest

from tools.device_specific_poc.transport import (
    _anonymous_bundle,
    _play_failure_status,
    _with_locale,
)


class _FakeProfiles:
    COUNTRY_MCC = {
        "CH": (
            "228",
            "01",
        )
    }

    @staticmethod
    def patch_profile_country(
        profile: dict[str, str],
        country: str,
    ) -> dict[str, str]:
        assert country == "CH"

        patched = dict(
            profile
        )

        patched[
            "CellOperator"
        ] = "228"

        patched[
            "SimOperator"
        ] = "01"

        return patched


class _Response:
    def __init__(
        self,
        payload: bytes,
    ) -> None:
        self._payload = payload

    def __enter__(
        self,
    ) -> _Response:
        return self

    def __exit__(
        self,
        exc_type: object,
        exc: object,
        traceback: object,
    ) -> None:
        return None

    def read(
        self,
    ) -> bytes:
        return self._payload


def _call_anonymous(
    dispenser_url: str = (
        "http://localhost:3000/api/auth"
    ),
) -> tuple[
    dict[str, object] | None,
    str | None,
    str,
]:
    return _anonymous_bundle(
        dispenser_url=(
            dispenser_url
        ),
        profile_data={
            "Build.VERSION.SDK_INT":
                "33",
        },
        country="CH",
        language="en",
        profiles_module=(
            _FakeProfiles
        ),
    )


@pytest.mark.parametrize(
    (
        "endpoint",
        "allowed",
    ),
    [
        (
            "http://localhost:3000/api/auth",
            True,
        ),
        (
            "http://127.0.0.1:3000/api/auth",
            True,
        ),
        (
            "http://[::1]:3000/api/auth",
            True,
        ),
        (
            "https://example.invalid/api/auth",
            True,
        ),
        (
            "http://example.invalid/api/auth",
            False,
        ),
        (
            "ftp://localhost/api/auth",
            False,
        ),
        (
            "not-a-url",
            False,
        ),
    ],
)
def test_dispenser_endpoint_security_policy(
    endpoint: str,
    allowed: bool,
) -> None:
    if allowed:
        resolved = _with_locale(
            endpoint,
            "en",
            "CH",
        )

        assert (
            "locale=en_CH"
            in resolved
        )

    else:
        with pytest.raises(
            ValueError
        ):
            _with_locale(
                endpoint,
                "en",
                "CH",
            )


def test_insecure_remote_http_degrades_cleanly() -> None:
    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous(
        "http://example.invalid/api/auth"
    )

    assert bundle is None
    assert status == "inconclusive"

    assert (
        diagnostics
        == "invalid_dispenser_url"
    )


@pytest.mark.parametrize(
    (
        "status_code",
        "expected_status",
    ),
    [
        (
            401,
            "auth_failed",
        ),
        (
            403,
            "auth_failed",
        ),
        (
            429,
            "rate_limited",
        ),
        (
            503,
            "transport_error",
        ),
    ],
)
def test_dispenser_http_failures_are_typed(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_status: str,
) -> None:
    def raise_http(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise urllib.error.HTTPError(
            url=(
                "http://localhost:3000/api/auth"
            ),
            code=status_code,
            msg="test",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        raise_http,
    )

    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous()

    assert bundle is None
    assert status == expected_status

    assert (
        diagnostics
        == f"dispenser_http_{status_code}"
    )


def test_dispenser_connection_failure_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_connection(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        raise urllib.error.URLError(
            "offline"
        )

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        fail_connection,
    )

    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous()

    assert bundle is None
    assert status == "transport_error"

    assert diagnostics.startswith(
        "dispenser_"
    )


def test_malformed_dispenser_json_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (
            _Response(
                b"{not-json"
            )
        ),
    )

    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous()

    assert bundle is None

    assert (
        status
        == "malformed_response"
    )

    assert (
        diagnostics
        == "dispenser_malformed_json"
    )


def test_missing_auth_token_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (
            _Response(
                json.dumps(
                    {
                        "email":
                            "dummy@example.invalid",
                    }
                ).encode(
                    "utf-8"
                )
            )
        ),
    )

    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous()

    assert bundle is None

    assert (
        status
        == "malformed_response"
    )

    assert (
        diagnostics
        == "dispenser_missing_auth_token"
    )


def test_successful_bundle_removes_dummy_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response_payload = {
        "authToken":
            "test-bearer-token",
        "gsfId":
            "123456",
        "email":
            "dummy@example.invalid",
        "aasToken":
            "test-aas-token",
        "tokenDispenserUrl":
            "https://example.invalid",
        "userProfile":
            {
                "name":
                    "dummy",
            },
        "deviceInfoProvider":
            {
                "userAgentString":
                    "test-agent",
                "mccMnc":
                    "00000",
            },
    }

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *args, **kwargs: (
            _Response(
                json.dumps(
                    response_payload
                ).encode(
                    "utf-8"
                )
            )
        ),
    )

    (
        bundle,
        status,
        diagnostics,
    ) = _call_anonymous()

    assert status is None
    assert diagnostics == ""
    assert bundle is not None

    assert (
        bundle["authToken"]
        == "test-bearer-token"
    )

    assert "email" not in bundle
    assert "aasToken" not in bundle

    assert (
        "tokenDispenserUrl"
        not in bundle
    )

    assert (
        "userProfile"
        not in bundle
    )

    assert (
        bundle[
            "deviceInfoProvider"
        ][
            "mccMnc"
        ]
        == "22801"
    )


@pytest.mark.parametrize(
    (
        "exception_name",
        "expected_status",
    ),
    [
        (
            "AppNotAvailableError",
            "unavailable_for_profile",
        ),
        (
            "AuthExpiredError",
            "auth_failed",
        ),
        (
            "UnauthorizedError",
            "auth_failed",
        ),
        (
            "RateLimitedError",
            "rate_limited",
        ),
        (
            "ProtocolError",
            "transport_error",
        ),
    ],
)
def test_play_failures_map_conservatively(
    exception_name: str,
    expected_status: str,
) -> None:
    exception_type = type(
        exception_name,
        (
            Exception,
        ),
        {},
    )

    result = (
        _play_failure_status(
            exception_type()
        )
    )

    assert (
        result
        == expected_status
    )
