from __future__ import annotations

from typing import Any

import pytest
import requests

import playstore_app_audit.services.alternative_distribution as alternative
from playstore_app_audit.domain.alternative_distribution import AlternativeDistributionState


class FakeResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class FakeSession:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((url, kwargs))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_fdroid_available_requires_exact_id_and_derives_suggested_version() -> None:
    session = FakeSession(
        FakeResponse(
            200,
            {
                "packageName": "org.example.app",
                "suggestedVersionCode": 42,
                "packages": [
                    {"versionName": "4.2", "versionCode": 42},
                    {"versionName": "4.1", "versionCode": 41},
                ],
            },
        )
    )

    result = alternative.FDroidProvider(session).check("org.example.app", timeout=10)

    assert result.state is AlternativeDistributionState.AVAILABLE
    assert result.version_name == "4.2"
    assert result.version_code == 42
    assert result.listing_url == "https://f-droid.org/packages/org.example.app/"
    assert session.calls[0][0].endswith("/org.example.app")


def test_fdroid_does_not_guess_version_without_exact_suggested_entry() -> None:
    session = FakeSession(
        FakeResponse(
            200,
            {
                "packageName": "org.example.app",
                "suggestedVersionCode": 42,
                "packages": [{"versionName": "4.1", "versionCode": 41}],
            },
        )
    )

    result = alternative.FDroidProvider(session).check("org.example.app", timeout=10)

    assert result.state is AlternativeDistributionState.AVAILABLE
    assert result.version_name == ""
    assert result.version_code == ""


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse(404, {"error": "NOT_FOUND"}), AlternativeDistributionState.NOT_FOUND),
        (FakeResponse(404, {"error": "different"}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(429, {}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(503, {}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(200, ValueError("bad json")), AlternativeDistributionState.INCONCLUSIVE),
        (requests.Timeout(), AlternativeDistributionState.INCONCLUSIVE),
    ],
)
def test_fdroid_error_contracts(
    response: FakeResponse | Exception, expected: AlternativeDistributionState
) -> None:
    result = alternative.FDroidProvider(FakeSession(response)).check(
        "org.example.app", timeout=10
    )
    assert result.state is expected


def test_fdroid_id_mismatch_is_inconclusive() -> None:
    result = alternative.FDroidProvider(
        FakeSession(FakeResponse(200, {"packageName": "org.other.app", "packages": []}))
    ).check("org.example.app", timeout=10)
    assert result.state is AlternativeDistributionState.INCONCLUSIVE


def _aptoide_success(package: str = "org.example.app") -> dict[str, Any]:
    return {
        "info": {"status": "OK"},
        "nodes": {
            "meta": {
                "info": {"status": "OK"},
                "data": {
                    "package": package,
                    "updated": "2026-08-01 10:00:00",
                    "file": {"vername": "7.8", "vercode": 78},
                    "urls": {},
                },
            }
        },
    }


def test_aptoide_available_uses_authorization_header_store_and_exact_metadata() -> None:
    synthetic_key = "synthetic-aptoide-key"
    session = FakeSession(FakeResponse(200, _aptoide_success()))

    result = alternative.AptoideProvider(
        "authorized-store", synthetic_key, session
    ).check("org.example.app", timeout=10)

    url, kwargs = session.calls[0]
    assert result.state is AlternativeDistributionState.AVAILABLE
    assert result.version_name == "7.8"
    assert result.version_code == 78
    assert result.listing_url == ""
    assert "/store_name=authorized-store/package_name=org.example.app/" in url
    assert kwargs["headers"]["Authorization"] == f"ApiKey {synthetic_key}"
    assert synthetic_key not in url
    assert synthetic_key not in result.reason


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (
            FakeResponse(404, {"info": {"status": "FAIL", "error": {"code": "APP-1"}}}),
            AlternativeDistributionState.NOT_FOUND,
        ),
        (FakeResponse(404, {"info": {"error": {"code": "APP-14"}}}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(401, {"info": {"error": {"code": "AUTH-13"}}}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(429, {}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(500, {}), AlternativeDistributionState.INCONCLUSIVE),
        (FakeResponse(200, ValueError("bad json")), AlternativeDistributionState.INCONCLUSIVE),
        (requests.Timeout(), AlternativeDistributionState.INCONCLUSIVE),
    ],
)
def test_aptoide_error_contracts(
    response: FakeResponse | Exception, expected: AlternativeDistributionState
) -> None:
    result = alternative.AptoideProvider(
        "authorized-store", "synthetic-key", FakeSession(response)
    ).check("org.example.app", timeout=10)
    assert result.state is expected


def test_aptoide_exact_id_mismatch_is_inconclusive() -> None:
    result = alternative.AptoideProvider(
        "authorized-store",
        "synthetic-key",
        FakeSession(FakeResponse(200, _aptoide_success("org.other.app"))),
    ).check("org.example.app", timeout=10)
    assert result.state is AlternativeDistributionState.INCONCLUSIVE


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (FakeResponse(200, {"info": {"status": "OK"}, "datalist": {"list": []}}), "ok"),
        (FakeResponse(401, {}), "configuration_error"),
        (FakeResponse(503, {}), "network_error"),
        (requests.Timeout(), "network_error"),
    ],
)
def test_aptoide_connection_test_is_small_and_distinguishes_failures(
    response: FakeResponse | Exception, expected: str
) -> None:
    session = FakeSession(response)
    provider = alternative.AptoideProvider("authorized-store", "synthetic-key", session)

    status, _message = provider.test_connection()

    assert status == expected
    url, kwargs = session.calls[0]
    assert url.endswith("/store_name=authorized-store/limit=1")
    assert "package_name" not in url
    assert "synthetic-key" not in url
    assert kwargs["headers"]["Authorization"] == "ApiKey synthetic-key"
