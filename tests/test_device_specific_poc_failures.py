from __future__ import annotations

from pathlib import Path

import pytest

from playstore_app_audit.services.version_relationship import (
    compare_versions,
)
from tools.device_specific_poc.models import (
    ResolverResult,
)
from tools.device_specific_poc.policy import (
    merge_resolver_evidence,
    should_attempt_resolver,
)
from tools.device_specific_poc.transport import (
    AUTH_AAS_ENV,
    AUTH_EMAIL_ENV,
    resolve_package,
)


@pytest.mark.parametrize(
    "value",
    [
        "Varies with device",
        "Varies by device",
        "Varies",
        " VARIES WITH DEVICE ",
    ],
)
def test_only_recognized_device_specific_values_trigger(
    value: str,
) -> None:
    assert (
        should_attempt_resolver(
            value
        )
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "Unknown",
        "Not Found",
        "N/A",
        "HTTP 503",
        "12.4.0",
        "Device Specific",
        "Depends on device",
    ],
)
def test_unrelated_store_states_do_not_trigger(
    value: object,
) -> None:
    assert not (
        should_attempt_resolver(
            value
        )
    )


@pytest.mark.parametrize(
    "status",
    [
        "unavailable_for_profile",
        "auth_failed",
        "rate_limited",
        "transport_error",
        "malformed_response",
        "inconclusive",
    ],
)
def test_all_failures_fall_back_to_device_specific(
    status: str,
) -> None:
    result = ResolverResult(
        package_name=(
            "com.example.test"
        ),
        profile_id=(
            "android13_api33_s20plus"
        ),
        profile_hash=(
            "abc123"
        ),
        auth_mode=(
            "anonymous"
        ),
        status=status,
        diagnostics=(
            "safe_test_failure"
        ),
    )

    merged = (
        merge_resolver_evidence(
            "Varies with device",
            result,
        )
    )

    assert (
        merged.public_store_raw
        == "Varies with device"
    )

    assert (
        merged.resolved_version
        is None
    )

    assert (
        merged.resolved_version_code
        is None
    )

    assert (
        merged.relationship
        == "Device-specific"
    )


def test_successful_resolution_is_additive() -> None:
    result = ResolverResult(
        package_name=(
            "com.example.test"
        ),
        profile_id=(
            "android13_api33_s20plus"
        ),
        profile_hash=(
            "abc123"
        ),
        auth_mode=(
            "anonymous"
        ),
        status="resolved",
        version_name="26.09.03",
        version_code=262843364,
    )

    merged = (
        merge_resolver_evidence(
            "Varies with device",
            result,
        )
    )

    assert (
        merged.public_store_raw
        == "Varies with device"
    )

    assert (
        merged.resolved_version
        == "26.09.03"
    )

    assert (
        merged.resolved_version_code
        == 262843364
    )

    assert (
        merged.relationship
        == "device_specific_resolved"
    )


def test_ordinary_store_version_remains_authoritative() -> None:
    fake_result = (
        ResolverResult(
            package_name=(
                "com.example.test"
            ),
            profile_id=(
                "android13_api33_s20plus"
            ),
            profile_hash=(
                "abc123"
            ),
            auth_mode=(
                "anonymous"
            ),
            status="resolved",
            version_name="999",
            version_code=999,
        )
    )

    merged = (
        merge_resolver_evidence(
            "1.2.3",
            fake_result,
        )
    )

    assert (
        merged.relationship
        == "ordinary_store_flow"
    )

    assert (
        merged.resolved_version
        is None
    )

    assert (
        merged.resolved_version_code
        is None
    )


def test_missing_anonymous_dispenser_fails_closed() -> None:
    result = resolve_package(
        package_name=(
            "com.facebook.katana"
        ),
        profile_id=(
            "android13_api33_s20plus"
        ),
        auth_mode="anonymous",
        dispenser_url=None,
    )

    assert (
        result.status
        == "inconclusive"
    )

    assert (
        result.diagnostics
        == "missing_dispenser"
    )

    assert (
        result.version_name
        is None
    )

    assert (
        result.version_code
        is None
    )


def test_missing_authenticated_context_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        AUTH_EMAIL_ENV,
        raising=False,
    )

    monkeypatch.delenv(
        AUTH_AAS_ENV,
        raising=False,
    )

    result = resolve_package(
        package_name=(
            "com.facebook.katana"
        ),
        profile_id=(
            "android13_api33_s20plus"
        ),
        auth_mode=(
            "authenticated"
        ),
    )

    assert (
        result.status
        == "auth_failed"
    )

    assert (
        result.version_name
        is None
    )

    assert (
        result.version_code
        is None
    )




def test_fallback_relationship_matches_existing_core_semantics() -> None:
    merged = merge_resolver_evidence(
        "Varies with device",
        None,
    )

    existing = compare_versions(
        "1.0",
        "Varies with device",
    )

    assert existing == "Device-specific"
    assert merged.relationship == existing


def test_experimental_code_has_no_public_dispenser_default() -> None:
    root = (
        Path(__file__)
        .resolve()
        .parents[1]
        / "tools"
        / "device_specific_poc"
    )

    python_source = "\n".join(
        path.read_text(
            encoding="utf-8"
        )
        for path
        in root.glob(
            "*.py"
        )
    ).casefold()

    assert (
        ".".join(("auroraoss", "com"))
        not in python_source
    )

    assert (
        "default_dispenser_url"
        not in python_source
    )
