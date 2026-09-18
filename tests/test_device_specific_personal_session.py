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


def test_exchange_oauth_for_aas_uses_placeholder_and_returns_google_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class Response:
        status_code = 200
        text = "Email=private.user@example.com\nToken=aas_et/RESULT\n"

        def raise_for_status(self) -> None:
            return None

    def post(url: str, **kwargs: object) -> Response:
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(personal.requests, "post", post)

    email, token = personal.exchange_oauth_for_aas(
        "oauth2_4/ONE-TIME",
    )

    assert email == "private.user@example.com"
    assert token == "aas_et/RESULT"
    data = captured["data"]
    assert isinstance(data, dict)
    assert data["Email"] == personal.OAUTH_EMAIL_HINT
    assert data["Token"] == "oauth2_4/ONE-TIME"
    assert captured["allow_redirects"] is False
    assert "EncryptedPasswd" not in data
    assert "Passwd" not in data
    assert "password" not in " ".join(str(key) for key in data).casefold()


def test_exchange_errors_do_not_echo_oauth_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oauth = "oauth2_4/ONE-TIME-SECRET"

    def post(*_args: object, **_kwargs: object) -> object:
        raise requests.ConnectionError(f"failed for {oauth}")

    monkeypatch.setattr(personal.requests, "post", post)

    with pytest.raises(personal.PersonalGoogleSessionError) as raised:
        personal.exchange_oauth_for_aas(oauth)

    message = str(raised.value)
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


def test_sign_in_interactive_discards_one_time_context_after_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        personal,
        "capture_browser_oauth",
        lambda **_kwargs: "oauth2_4/ONE-TIME",
    )
    monkeypatch.setattr(
        personal,
        "exchange_oauth_for_aas",
        lambda token: (
            ("private.user@example.com", "aas_et/SESSION")
            if token == "oauth2_4/ONE-TIME"
            else pytest.fail("unexpected OAuth context")
        ),
    )

    status = personal.sign_in_interactive(timeout=1)

    assert status.signed_in is True
    assert personal.personal_session_credentials() == (
        "private.user@example.com",
        "aas_et/SESSION",
    )


def test_browser_capture_completes_from_oauth_cookie_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSocket:
        def close(self) -> None:
            pass

    class FakeProcess:
        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        personal,
        "create_connection",
        lambda *_args, **_kwargs: FakeSocket(),
    )
    monkeypatch.setattr(
        personal,
        "_attach_page",
        lambda _websocket, request_id: (request_id + 1, "session"),
    )

    def fake_cdp_request(
        _websocket: object,
        request_id: int,
        method: str,
        _params: dict[str, object] | None = None,
        _session_id: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        assert method == "Storage.getCookies"
        return request_id + 1, {
            "result": {
                "cookies": [
                    {
                        "name": "oauth_token",
                        "domain": ".accounts.google.com",
                        "value": "oauth2_4/EXPECTED",
                    }
                ]
            }
        }

    monkeypatch.setattr(personal, "_cdp_request", fake_cdp_request)

    token = personal._wait_for_oauth_token(
        "ws://127.0.0.1/devtools/browser/test",
        "http://127.0.0.1:9222",
        FakeProcess(),  # type: ignore[arg-type]
        timeout=5,
    )

    assert token == "oauth2_4/EXPECTED"


def test_exchange_rejects_placeholder_when_google_does_not_return_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        status_code = 200
        text = (
            f"Email={personal.OAUTH_EMAIL_HINT}\n"
            "Token=aas_et/RESULT\n"
        )

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(
        personal.requests,
        "post",
        lambda *_args, **_kwargs: Response(),
    )

    with pytest.raises(
        personal.PersonalGoogleSessionError,
        match="no account identity",
    ):
        personal.exchange_oauth_for_aas("oauth2_4/ONE-TIME")

