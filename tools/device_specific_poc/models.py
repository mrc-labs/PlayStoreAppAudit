"""Structured results for the isolated Device Specific resolver PoC."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Literal

type ResolverStatus = Literal[
    "resolved",
    "unavailable_for_profile",
    "auth_failed",
    "rate_limited",
    "transport_error",
    "malformed_response",
    "inconclusive",
]


RESOLVER_STATUSES = frozenset(
    {
        "resolved",
        "unavailable_for_profile",
        "auth_failed",
        "rate_limited",
        "transport_error",
        "malformed_response",
        "inconclusive",
    }
)


@dataclass(
    frozen=True,
    slots=True,
)
class ResolverResult:
    """One profile-specific Google Play metadata result."""

    package_name: str
    profile_id: str
    profile_hash: str
    auth_mode: str
    status: ResolverStatus

    version_name: str | None = None
    version_code: int | None = None

    requested_country: str = "US"
    requested_language: str = "en"

    fetched_at: str = field(
        default_factory=lambda: (
            datetime.now(UTC).isoformat()
        )
    )

    diagnostics: str = ""

    def __post_init__(self) -> None:
        if not self.package_name.strip():
            raise ValueError(
                "package_name is required"
            )

        if not self.profile_id.strip():
            raise ValueError(
                "profile_id is required"
            )

        if not self.profile_hash.strip():
            raise ValueError(
                "profile_hash is required"
            )

        if not self.auth_mode.strip():
            raise ValueError(
                "auth_mode is required"
            )

        if self.status not in RESOLVER_STATUSES:
            raise ValueError(
                "Unsupported resolver status: "
                f"{self.status}"
            )

        if self.status == "resolved":
            if (
                self.version_name is None
                or not self.version_name.strip()
            ):
                raise ValueError(
                    "resolved results require version_name"
                )

            if (
                isinstance(
                    self.version_code,
                    bool,
                )
                or not isinstance(
                    self.version_code,
                    int,
                )
                or self.version_code <= 0
            ):
                raise ValueError(
                    "resolved results require "
                    "a positive version_code"
                )

        elif (
            self.version_name is not None
            or self.version_code is not None
        ):
            raise ValueError(
                "non-resolved results must not "
                "contain version evidence"
            )

    @property
    def resolved(self) -> bool:
        return self.status == "resolved"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
