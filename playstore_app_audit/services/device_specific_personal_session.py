"""Process-local Personal Google Session for Device Specific metadata lookup.

The browser OAuth capture is adapted from Villoh/goopdl 1.2.1 (MIT):
Copyright (c) 2021 Rehmat Alam
Copyright (c) 2025 Mikel Villota

Only the browser-based EmbeddedSetup token path is retained. Store App Audit
does not implement or request a raw Google password.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from subprocess import TimeoutExpired
from typing import Any

import requests
from websocket import (
    WebSocketException,
    WebSocketTimeoutException,
    create_connection,
)

EMBEDDED_SETUP_URL = "https://accounts.google.com/EmbeddedSetup"
GOOGLE_AUTH_URL = "https://android.clients.google.com/auth"


class PersonalGoogleSessionError(RuntimeError):
    """Personal Google Session failed without exposing secret material."""


@dataclass(frozen=True, slots=True)
class PersonalGoogleSessionStatus:
    signed_in: bool
    context_hash: str


@dataclass(slots=True)
class _PersonalGoogleSession:
    email: str
    aas_token: str
    context_id: str


_LOCK = threading.RLock()
_SESSION: _PersonalGoogleSession | None = None


def personal_session_status() -> PersonalGoogleSessionStatus:
    with _LOCK:
        session = _SESSION
        return PersonalGoogleSessionStatus(
            signed_in=session is not None,
            context_hash=(
                hashlib.sha256(session.context_id.encode("utf-8")).hexdigest()
                if session is not None
                else ""
            ),
        )


def personal_session_credentials() -> tuple[str, str] | None:
    """Return process-local credentials for the direct-auth adapter only."""

    with _LOCK:
        if _SESSION is None:
            return None
        return _SESSION.email, _SESSION.aas_token


def clear_personal_session() -> None:
    global _SESSION
    with _LOCK:
        if _SESSION is not None:
            _SESSION.email = ""
            _SESSION.aas_token = ""
            _SESSION.context_id = ""
        _SESSION = None


def install_personal_session(email: str, aas_token: str) -> None:
    """Install already-acquired credentials in memory; used by interactive login/tests."""

    clean_email = str(email or "").strip()
    clean_token = str(aas_token or "").strip()
    if "@" not in clean_email or not clean_token.startswith("aas_et/"):
        raise PersonalGoogleSessionError("Google session credentials were rejected.")
    session = _PersonalGoogleSession(
        email=clean_email,
        aas_token=clean_token,
        context_id=secrets.token_hex(32),
    )
    global _SESSION
    with _LOCK:
        clear_personal_session()
        _SESSION = session


def sign_in_interactive(*, timeout: float = 300.0) -> PersonalGoogleSessionStatus:
    """Acquire one browser OAuth session and keep only its AAS context in memory."""

    email = ""
    oauth_token = ""
    try:
        email, oauth_token = capture_browser_oauth(timeout=timeout)
        aas_token = exchange_oauth_for_aas(email, oauth_token)
        install_personal_session(email, aas_token)
    finally:
        oauth_token = ""
        email = ""
    return personal_session_status()


def capture_browser_oauth(*, timeout: float = 300.0) -> tuple[str, str]:
    browser = _find_browser()
    port = _free_port()
    origin = f"http://127.0.0.1:{port}"

    with tempfile.TemporaryDirectory(prefix="store-app-audit-google-") as profile:
        try:
            process = subprocess.Popen(
                [
                    str(browser),
                    f"--remote-debugging-port={port}",
                    "--remote-debugging-address=127.0.0.1",
                    f"--remote-allow-origins={origin}",
                    f"--user-data-dir={profile}",
                    "--no-first-run",
                    "--no-default-browser-check",
                    EMBEDDED_SETUP_URL,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise PersonalGoogleSessionError("Could not start a supported browser.") from exc

        try:
            websocket_url = _wait_for_debugger(port, process)
            return _wait_for_oauth_credentials(
                websocket_url,
                origin,
                process,
                timeout=timeout,
            )
        except (OSError, WebSocketException) as exc:
            raise PersonalGoogleSessionError(
                "The isolated Google sign-in browser connection failed."
            ) from exc
        finally:
            _stop_browser(process)


def exchange_oauth_for_aas(email: str, oauth_token: str) -> str:
    clean_email = str(email or "").strip()
    one_time = str(oauth_token or "").strip()
    if "@" not in clean_email or not one_time.startswith("oauth2_4/"):
        raise PersonalGoogleSessionError("Google sign-in did not return a valid one-time session.")

    try:
        response = requests.post(
            GOOGLE_AUTH_URL,
            data={
                "Email": clean_email,
                "Token": one_time,
                "ACCESS_TOKEN": "1",
                "add_account": "1",
                "callerPkg": "com.google.android.gms",
                "callerSig": "38918a453d07199354f8b19af05ec6562ced5788",
                "device_country": "us",
                "droidguard_results": "null",
                "get_accountid": "1",
                "google_play_services_version": "240913000",
                "lang": "en",
                "sdk_version": "28",
                "service": "ac2dm",
            },
            headers={
                "Accept-Encoding": "identity",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "",
                "app": "com.google.android.gms",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise PersonalGoogleSessionError("Google session exchange could not be reached.") from exc

    values: dict[str, str] = {}
    for line in response.text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values[key] = value

    token = str(values.get("Token") or "").strip()
    if token.startswith("aas_et/"):
        return token
    if response.status_code == 429:
        raise PersonalGoogleSessionError("Google session exchange is rate limited.")
    if response.status_code in {401, 403} or values.get("Error"):
        raise PersonalGoogleSessionError("Google rejected the browser session.")
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise PersonalGoogleSessionError("Google session exchange failed.") from exc
    raise PersonalGoogleSessionError("Google session exchange returned no usable session.")


def _find_browser() -> Path:
    configured = os.environ.get("STORE_APP_AUDIT_BROWSER", "").strip()
    if configured:
        path = Path(configured).expanduser()
        if path.is_file():
            return path
        raise PersonalGoogleSessionError("The configured browser executable was not found.")

    for candidate in _browser_candidates():
        if candidate.is_file():
            return candidate
    raise PersonalGoogleSessionError(
        "Chrome, Chromium, Edge or Brave is required for Personal Google Session."
    )


def _browser_candidates() -> list[Path]:
    names = (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "microsoft-edge",
        "microsoft-edge-stable",
        "brave-browser",
    )
    candidates = [Path(path) for name in names if (path := shutil.which(name))]

    if sys.platform == "win32":
        roots = [
            os.environ.get("LOCALAPPDATA"),
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
        ]
        relative_paths = (
            "Google/Chrome/Application/chrome.exe",
            "Microsoft/Edge/Application/msedge.exe",
            "BraveSoftware/Brave-Browser/Application/brave.exe",
        )
        candidates.extend(
            Path(root) / relative
            for root in roots
            if root
            for relative in relative_paths
        )
    elif sys.platform == "darwin":
        candidates.extend(
            Path(path)
            for path in (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            )
        )
    return candidates


def _free_port() -> int:
    try:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])
    except (OSError, TypeError, ValueError) as exc:
        raise PersonalGoogleSessionError("Could not allocate the local sign-in port.") from exc


def _wait_for_debugger(
    port: int,
    process: subprocess.Popen[Any],
    *,
    timeout: float = 15.0,
) -> str:
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    client = requests.Session()
    client.trust_env = False
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise PersonalGoogleSessionError("The sign-in browser closed too early.")
            try:
                response = client.get(url, timeout=1)
                websocket_url = response.json().get("webSocketDebuggerUrl")
                if websocket_url:
                    return str(websocket_url)
            except (requests.RequestException, ValueError):
                pass
            time.sleep(0.1)
    finally:
        client.close()
    raise PersonalGoogleSessionError("The sign-in browser did not become ready.")


def _wait_for_oauth_credentials(
    websocket_url: str,
    origin: str,
    process: subprocess.Popen[Any],
    *,
    timeout: float,
) -> tuple[str, str]:
    deadline = time.monotonic() + timeout
    request_id = 0
    try:
        websocket = create_connection(
            websocket_url,
            origin=origin,
            timeout=2,
            http_no_proxy=["127.0.0.1", "localhost"],
        )
    except (OSError, WebSocketException) as exc:
        raise PersonalGoogleSessionError("Could not attach to the sign-in browser.") from exc

    try:
        request_id, session_id = _attach_page(websocket, request_id)
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise PersonalGoogleSessionError("The sign-in browser closed before completion.")
            try:
                request_id, response = _cdp_request(
                    websocket,
                    request_id,
                    "Storage.getCookies",
                )
            except WebSocketTimeoutException:
                continue
            _raise_cdp_error(response)
            token = _oauth_token(response.get("result", {}).get("cookies", []))
            if token:
                request_id, response = _cdp_request(
                    websocket,
                    request_id,
                    "Runtime.evaluate",
                    {
                        "expression": (
                            "document.querySelector('[data-profile-identifier]'"
                            "[data-email]')?.getAttribute('data-email') || ''"
                        ),
                        "returnByValue": True,
                    },
                    session_id,
                )
                _raise_cdp_error(response)
                email = _profile_email(response)
                if email:
                    return email, token
            time.sleep(0.5)
    finally:
        websocket.close()
    raise PersonalGoogleSessionError("Google sign-in timed out before completion.")


def _attach_page(websocket: Any, request_id: int) -> tuple[int, str]:
    request_id, response = _cdp_request(websocket, request_id, "Target.getTargets")
    _raise_cdp_error(response)
    targets = response.get("result", {}).get("targetInfos", [])
    pages = [target for target in targets if target.get("type") == "page"]
    target = next(
        (
            target
            for target in pages
            if "accounts.google.com" in str(target.get("url") or "")
        ),
        pages[0] if pages else None,
    )
    if not target:
        raise PersonalGoogleSessionError("The Google sign-in page was not found.")
    request_id, response = _cdp_request(
        websocket,
        request_id,
        "Target.attachToTarget",
        {"targetId": target["targetId"], "flatten": True},
    )
    _raise_cdp_error(response)
    session_id = response.get("result", {}).get("sessionId")
    if not session_id:
        raise PersonalGoogleSessionError("Could not attach to the Google sign-in page.")
    return request_id, str(session_id)


def _cdp_request(
    websocket: Any,
    request_id: int,
    method: str,
    params: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> tuple[int, dict[str, Any]]:
    request_id += 1
    message: dict[str, Any] = {"id": request_id, "method": method}
    if params is not None:
        message["params"] = params
    if session_id is not None:
        message["sessionId"] = session_id
    websocket.send(json.dumps(message))
    return request_id, _receive_response(websocket, request_id)


def _receive_response(websocket: Any, request_id: int) -> dict[str, Any]:
    while True:
        try:
            message = json.loads(websocket.recv())
        except (json.JSONDecodeError, TypeError):
            continue
        if message.get("id") == request_id:
            return message


def _raise_cdp_error(response: dict[str, Any]) -> None:
    if response.get("error"):
        raise PersonalGoogleSessionError("The sign-in browser rejected a local request.")


def _oauth_token(cookies: list[dict[str, Any]]) -> str | None:
    for cookie in cookies:
        domain = str(cookie.get("domain", "")).lstrip(".")
        value = str(cookie.get("value", ""))
        if (
            cookie.get("name") == "oauth_token"
            and (
                domain == "accounts.google.com"
                or domain.endswith(".accounts.google.com")
            )
            and value.startswith("oauth2_4/")
        ):
            return value
    return None


def _profile_email(response: dict[str, Any]) -> str | None:
    value = response.get("result", {}).get("result", {}).get("value")
    if not isinstance(value, str) or "@" not in value:
        return None
    return value.strip()


def _stop_browser(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
