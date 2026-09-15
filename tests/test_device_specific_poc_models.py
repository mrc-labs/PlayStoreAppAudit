from __future__ import annotations

import pytest

from tools.device_specific_poc.models import (
    RESOLVER_STATUSES,
    ResolverResult,
)


def _base(
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "package_name":
            "com.example.test",
        "profile_id":
            "android13_api33_s20plus",
        "profile_hash":
            "abc123",
        "auth_mode":
            "anonymous",
        "status":
            "resolved",
        "version_name":
            "1.2.3",
        "version_code":
            123,
        "requested_country":
            "CH",
        "requested_language":
            "en",
    }

    values.update(
        overrides
    )

    return values


def test_resolved_result_keeps_version_name_and_code() -> None:
    result = ResolverResult(
        **_base()
    )

    assert result.resolved is True
    assert (
        result.version_name
        == "1.2.3"
    )
    assert (
        result.version_code
        == 123
    )


@pytest.mark.parametrize(
    (
        "version_name",
        "version_code",
    ),
    [
        (None, 123),
        ("", 123),
        ("1.2.3", None),
        ("1.2.3", 0),
        ("1.2.3", -1),
    ],
)
def test_resolved_result_requires_complete_version_evidence(
    version_name: str | None,
    version_code: int | None,
) -> None:
    with pytest.raises(
        ValueError
    ):
        ResolverResult(
            **_base(
                version_name=(
                    version_name
                ),
                version_code=(
                    version_code
                ),
            )
        )


@pytest.mark.parametrize(
    "status",
    sorted(
        RESOLVER_STATUSES
        - {
            "resolved",
        }
    ),
)
def test_failed_results_cannot_carry_version_evidence(
    status: str,
) -> None:
    with pytest.raises(
        ValueError
    ):
        ResolverResult(
            **_base(
                status=status,
            )
        )

    result = ResolverResult(
        **_base(
            status=status,
            version_name=None,
            version_code=None,
        )
    )

    assert result.resolved is False
    assert result.version_name is None
    assert result.version_code is None
