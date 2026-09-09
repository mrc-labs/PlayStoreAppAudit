from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class AlternativeDistributionState(StrEnum):
    AVAILABLE = "available"
    NOT_FOUND = "not_found"
    INCONCLUSIVE = "inconclusive"
    UNSUPPORTED = "unsupported"
    NOT_CHECKED = "not_checked"


@dataclass(frozen=True, slots=True)
class AlternativeDistributionResult:
    provider_id: str
    provider_name: str
    queried_package_id: str
    state: AlternativeDistributionState
    listing_url: str = ""
    version_name: str = ""
    version_code: int | str = ""
    checked_at: str = ""
    provenance: str = "live"
    reason: str = ""

    def to_mapping(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value
        return data

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AlternativeDistributionResult:
        try:
            state = AlternativeDistributionState(str(value.get("state") or ""))
        except ValueError:
            state = AlternativeDistributionState.INCONCLUSIVE
        version_code = value.get("version_code", "")
        if not isinstance(version_code, (int, str)):
            version_code = ""
        return cls(
            provider_id=str(value.get("provider_id") or ""),
            provider_name=str(value.get("provider_name") or ""),
            queried_package_id=str(value.get("queried_package_id") or ""),
            state=state,
            listing_url=str(value.get("listing_url") or ""),
            version_name=str(value.get("version_name") or ""),
            version_code=version_code,
            checked_at=str(value.get("checked_at") or ""),
            provenance=str(value.get("provenance") or ""),
            reason=str(value.get("reason") or ""),
        )


@runtime_checkable
class AlternativeDistributionProvider(Protocol):
    provider_id: str
    provider_name: str
    cache_namespace: str

    def check(
        self, package_id: str, *, timeout: float
    ) -> AlternativeDistributionResult: ...
