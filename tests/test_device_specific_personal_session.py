from __future__ import annotations

import pytest
import requests

from playstore_app_audit.services import device_specific_personal_session as personal


@pytest.fixture(autouse=True)
def clear_session() -> None:
    personal.clear_personal_session()
    yield
    personal.clear_personal_session()


def test_installed_personal_session_exposes_only_non_identifying_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(personal.secrets, "token_hex", lambda _size: "session-random")
    email = "private.user@example.com"
    token = "aas_et/SECRET-AAS"

    personal.install_personal_session(email, token)

    status = personal.personal_session_status()
    credentials = personal.personal_session_credentials()

    assert status.signed_in is True
    assert len(status.context_hash) == 64
    assert email not in repr(status)
    assert token not in repr(status)
    assert "private.user" not in status.context_hash
    assert "SECRET" not in status.context_hash
    assert credentials == (email, token)


def test_clear_personal_session_removes_process_local_credentials() -> None:
    personal.install_personal_session(
        "private.user@example.com",
        "aas_et/SECRET-AAS",
    )

    personal.clear_personal_session()

    assert personal.personal_session_credentials() is None
    assert personal.personal_session_status().signed_in is False
    assert personal.personal_session_status().context_hash == ""


def test_exchange_oauth_for_aas_uses_one_time_token_without_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200
        text = "Token=aas_et/RESULT\n"

        def raise_for_status(self) -> None:
            return None

    def post(url: str, **kwargs: object) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(personal.requests, "post", post)

    result = personal.exchange_oauth_for_aas(
        "private.user@example.com",
        "oauth2_4/ONE-TIME",
    )

    assert result == "aas_et/RESULT"
    data = captured["data"]
    assert isinstance(data, dict)
    assert data["Email"] == "private.user@example.com"
    assert data["Token"] == "oauth2_4/ONE-TIME"
    assert "EncryptedPasswd" not in data
    assert "Passwd" not in data
    assert "password" not in " ".join(str(key) for key in data).casefold()


def test_exchange_errors_do_not_echo_identity_or_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = "private.user@example.com"
    oauth = "oauth2_4/ONE-TIME-SECRET"

    def post(*_args: object, **_kwargs: object) -> object:
        raise requests.ConnectionError(f"failed for {email} {oauth}")

    monkeypatch.setattr(personal.requests, "post", post)

    with pytest.raises(personal.PersonalGoogleSessionError) as raised:
        personal.exchange_oauth_for_aas(email, oauth)

    message = str(raised.value)
    assert email not in message
    assert oauth not in message
    assert "ONE-TIME-SECRET" not in message


def test_oauth_cookie_parser_accepts_only_google_embedded_setup_token() -> None:
    cookies = [
        {
            "name": "oauth_token",
            "domain": ".example.com",
            "value": "oauth2_4/WRONG",
        },
        {
            "name": "oauth_token",
            "domain": ".accounts.google.com",
            "value": "oauth2_4/EXPECTED",
        },
    ]

    assert personal._oauth_token(cookies) == "oauth2_4/EXPECTED"


def test_profile_email_parser_returns_only_email_shaped_value() -> None:
    valid = {
        "result": {
            "result": {
                "value": "private.user@example.com",
            }
        }
    }
    invalid = {"result": {"result": {"value": "not-an-email"}}}

    assert personal._profile_email(valid) == "private.user@example.com"
    assert personal._profile_email(invalid) is None


def test_sign_in_interactive_discards_one_time_context_after_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        personal,
        "capture_browser_oauth",
        lambda **_kwargs: ("private.user@example.com", "oauth2_4/ONE-TIME"),
    )
    monkeypatch.setattr(
        personal,
        "exchange_oauth_for_aas",
        lambda email, token: (
            "aas_et/SESSION"
            if email == "private.user@example.com" and token == "oauth2_4/ONE-TIME"
            else pytest.fail("unexpected OAuth context")
        ),
    )

    status = personal.sign_in_interactive(timeout=1)

    assert status.signed_in is True
    assert personal.personal_session_credentials() == (
        "private.user@example.com",
        "aas_et/SESSION",
    )


def test_browser_capture_can_observe_email_before_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def close(self) -> None:
            pass

    class FakeProcess:
        def poll(self) -> None:
            return None

    monkeypatch.setattr(personal, "create_connection", lambda *_args, **_kwargs: FakeSocket())
    monkeypatch.setattr(
        personal,
        "_attach_page",
        lambda _websocket, request_id: (request_id + 1, "session"),
    )
    monkeypatch.setattr(personal.time, "sleep", lambda _seconds: None)

    responses = iter(
        [
            (
                "Runtime.evaluate",
                {
                    "result": {
                        "result": {
                            "value": "private.user@example.com",
                        }
                    }
                },
            ),
            ("Storage.getCookies", {"result": {"cookies": []}}),
            (
                "Runtime.evaluate",
                {"result": {"result": {"value": ""}}},
            ),
            (
                "Storage.getCookies",
                {
                    "result": {
                        "cookies": [
                            {
                                "name": "oauth_token",
                                "domain": ".accounts.google.com",
                                "value": "oauth2_4/LATER",
                            }
                        ]
                    }
                },
            ),
        ]
    )

    def fake_cdp_request(
        _websocket: object,
        request_id: int,
        method: str,
        _params: dict[str, object] | None = None,
        _session_id: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        expected_method, response = next(responses)
        assert method == expected_method
        return request_id + 1, response

    monkeypatch.setattr(personal, "_cdp_request", fake_cdp_request)

    email, token = personal._wait_for_oauth_credentials(
        "ws://127.0.0.1/devtools/browser/test",
        "http://127.0.0.1:9222",
        FakeProcess(),  # type: ignore[arg-type]
        timeout=5,
    )

    assert email == "private.user@example.com"
    assert token == "oauth2_4/LATER"


def test_email_capture_expression_covers_current_google_sign_in_shapes() -> None:
    expression = personal._EMAIL_CAPTURE_EXPRESSION

    assert "data-email" in expression
    assert "data-identifier" in expression
    assert 'input[type="email"]' in expression
    assert "identifierId" in expression
    assert "aria-label" in expression
