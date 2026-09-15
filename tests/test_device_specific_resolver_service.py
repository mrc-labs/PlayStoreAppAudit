from __future__ import annotations

from pathlib import Path

import pytest

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services import device_specific_resolver as resolver


@pytest.mark.parametrize(
    "value",
    [
        "Varies with device",
        "Varies by device",
        "Varies",
        " VARIES WITH DEVICE ",
    ],
)
def test_exact_device_specific_values_trigger(value: str) -> None:
    assert resolver.should_attempt_device_specific_resolver(value)


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "Unknown",
        "Not Found",
        "N/A",
        "HTTP 503",
        "1.2.3",
        "Device Specific",
        "Depends on device",
    ],
)
def test_other_store_states_do_not_trigger(value: object) -> None:
    assert not resolver.should_attempt_device_specific_resolver(value)


def test_ordinary_store_flow_never_calls_transport(monkeypatch) -> None:
    called = False

    def fail_transport(**_kwargs):
        nonlocal called
        called = True
        raise AssertionError("transport must not run")

    monkeypatch.setattr(resolver, "resolve_metadata_with_dispenser", fail_transport)
    result = resolver.resolve_if_device_specific(
        public_store_version="1.2.3",
        package_name="com.example.app",
        profile_id="android10_api29_oneplus8pro",
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
    )
    assert result is None
    assert not called


def test_device_specific_flow_keeps_core_result_separate(monkeypatch) -> None:
    profile = resolver.load_reference_profile("android10_api29_oneplus8pro")
    expected = ResolverResult(
        package_name="com.example.app",
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.RESOLVED,
        requested_country="CH",
        requested_language="en",
        version_name="1.2.3",
        version_code=123,
    )

    monkeypatch.setattr(
        resolver,
        "resolve_metadata_with_dispenser",
        lambda **_kwargs: expected,
    )
    monkeypatch.setattr(resolver, "load_cached_result", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(resolver, "store_resolved_result", lambda *_args, **_kwargs: True)

    result = resolver.resolve_if_device_specific(
        public_store_version="Varies with device",
        package_name="com.example.app",
        profile_id=profile.profile_id,
        dispenser_url="https://resolver.example/api/auth",
        country="CH",
        language="en",
    )
    assert result == expected


def test_production_configuration_does_not_add_goopdl_dependency() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8").casefold()
    assert '"goopdl' not in pyproject
