"""Trigger and fallback policy for the isolated resolver PoC."""

from __future__ import annotations

from dataclasses import dataclass

from playstore_app_audit.services.version_relationship import (
    DEVICE_SPECIFIC_VALUES,
)

from .models import ResolverResult

_DEVICE_SPECIFIC_NORMALIZED = frozenset(
    str(value).strip().casefold()
    for value in DEVICE_SPECIFIC_VALUES
)


@dataclass(
    frozen=True,
    slots=True,
)
class ResolverEvidenceView:
    public_store_raw: object
    resolved_version: str | None
    resolved_version_code: int | None
    relationship: str


def should_attempt_resolver(
    public_store_version: object,
) -> bool:
    value = str(
        public_store_version
        or ""
    ).strip().casefold()

    return (
        value
        in _DEVICE_SPECIFIC_NORMALIZED
    )


def merge_resolver_evidence(
    public_store_raw: object,
    resolver_result: ResolverResult | None,
) -> ResolverEvidenceView:
    """Preserve raw Store evidence and add resolver evidence."""

    if not should_attempt_resolver(
        public_store_raw
    ):
        return ResolverEvidenceView(
            public_store_raw=public_store_raw,
            resolved_version=None,
            resolved_version_code=None,
            relationship="ordinary_store_flow",
        )

    if (
        resolver_result is not None
        and resolver_result.resolved
    ):
        return ResolverEvidenceView(
            public_store_raw=public_store_raw,
            resolved_version=(
                resolver_result.version_name
            ),
            resolved_version_code=(
                resolver_result.version_code
            ),
            relationship=(
                "device_specific_resolved"
            ),
        )

    return ResolverEvidenceView(
        public_store_raw=public_store_raw,
        resolved_version=None,
        resolved_version_code=None,
        relationship="Device-specific",
    )
