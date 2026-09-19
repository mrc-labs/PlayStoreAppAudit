"""Typed domain objects for profile-specific Google Play version evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

RESOLVER_CACHE_SCHEMA = 1


class ResolverStatus(StrEnum):
    RESOLVED = "resolved"
    UNAVAILABLE_FOR_PROFILE = "unavailable_for_profile"
    AUTH_FAILED = "auth_failed"
    RATE_LIMITED = "rate_limited"
    TRANSPORT_ERROR = "transport_error"
    MALFORMED_RESPONSE = "malformed_response"
    INCONCLUSIVE = "inconclusive"


class ResolverProvider(StrEnum):
    ANONYMOUS_DISPENSER = "anonymous_dispenser"
    PERSONAL_GOOGLE_SESSION = "personal_google_session"


def _normalise_country(value: object) -> str:
    country = str(value or "").strip().upper()
    if len(country) != 2 or not country.isalpha():
        raise ValueError("requested_country must be a two-letter country code")
    return country


def _normalise_language(value: object) -> str:
    language = str(value or "").strip().lower().replace("_", "-")
    if not language or any(char.isspace() for char in language):
        raise ValueError("requested_language is required")
    return language


def _validate_fetched_at(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("fetched_at is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("fetched_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")
    return text


@dataclass(frozen=True, slots=True)
class ResolverResult:
    package_name: str
    profile_id: str
    profile_hash: str
    provider: ResolverProvider
    status: ResolverStatus
    requested_country: str
    requested_language: str
    version_name: str | None = None
    version_code: int | None = None
    fetched_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    diagnostics: str = ""

    def __post_init__(self) -> None:
        package_name = self.package_name.strip()
        profile_id = self.profile_id.strip()
        profile_hash = self.profile_hash.strip().lower()
        diagnostics = self.diagnostics.strip()

        if not package_name:
            raise ValueError("package_name is required")
        if not profile_id:
            raise ValueError("profile_id is required")
        if not re_full_sha256(profile_hash):
            raise ValueError("profile_hash must be a SHA-256 hex digest")
        if "\n" in diagnostics or "\r" in diagnostics:
            raise ValueError("diagnostics must be single-line")

        country = _normalise_country(self.requested_country)
        language = _normalise_language(self.requested_language)
        fetched_at = _validate_fetched_at(self.fetched_at)

        if self.status is ResolverStatus.RESOLVED:
            version_name = str(self.version_name or "").strip()
            if not version_name:
                raise ValueError("resolved results require version_name")
            if (
                isinstance(self.version_code, bool)
                or not isinstance(self.version_code, int)
                or self.version_code <= 0
            ):
                raise ValueError("resolved results require a positive version_code")
            object.__setattr__(self, "version_name", version_name)
        elif self.version_name is not None or self.version_code is not None:
            raise ValueError("unresolved results must not contain version evidence")

        object.__setattr__(self, "package_name", package_name)
        object.__setattr__(self, "profile_id", profile_id)
        object.__setattr__(self, "profile_hash", profile_hash)
        object.__setattr__(self, "requested_country", country)
        object.__setattr__(self, "requested_language", language)
        object.__setattr__(self, "fetched_at", fetched_at)
        object.__setattr__(self, "diagnostics", diagnostics)

    @property
    def resolved(self) -> bool:
        return self.status is ResolverStatus.RESOLVED

    def to_mapping(self) -> dict[str, Any]:
        data = asdict(self)
        data["provider"] = self.provider.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> ResolverResult:
        version_code = value.get("version_code")
        if isinstance(version_code, bool) or (
            version_code is not None and not isinstance(version_code, int)
        ):
            raise ValueError("version_code must be an integer or null")
        return cls(
            package_name=str(value.get("package_name") or ""),
            profile_id=str(value.get("profile_id") or ""),
            profile_hash=str(value.get("profile_hash") or ""),
            provider=ResolverProvider(str(value.get("provider") or "")),
            status=ResolverStatus(str(value.get("status") or "")),
            requested_country=str(value.get("requested_country") or ""),
            requested_language=str(value.get("requested_language") or ""),
            version_name=(
                None
                if value.get("version_name") is None
                else str(value.get("version_name"))
            ),
            version_code=version_code,
            fetched_at=str(value.get("fetched_at") or ""),
            diagnostics=str(value.get("diagnostics") or ""),
        )


@dataclass(frozen=True, slots=True)
class ResolverCacheIdentity:
    package_name: str
    profile_id: str
    profile_hash: str
    requested_country: str
    requested_language: str
    provider: ResolverProvider
    provider_context_hash: str
    protocol_revision: str
    schema: int = RESOLVER_CACHE_SCHEMA

    def components(self) -> tuple[str, ...]:
        package_name = self.package_name.strip()
        profile_id = self.profile_id.strip()
        profile_hash = self.profile_hash.strip().lower()
        provider_context_hash = self.provider_context_hash.strip().lower()
        protocol_revision = self.protocol_revision.strip()

        if not package_name or not profile_id or not protocol_revision:
            raise ValueError("cache identity fields must not be blank")
        if not re_full_sha256(profile_hash):
            raise ValueError("profile_hash must be a SHA-256 hex digest")
        if not re_full_sha256(provider_context_hash):
            raise ValueError("provider_context_hash must be a SHA-256 hex digest")
        if self.schema != RESOLVER_CACHE_SCHEMA:
            raise ValueError("unsupported resolver cache schema")

        return (
            str(self.schema),
            package_name,
            profile_id,
            profile_hash,
            _normalise_country(self.requested_country),
            _normalise_language(self.requested_language),
            self.provider.value,
            provider_context_hash,
            protocol_revision,
        )

    @property
    def key(self) -> str:
        encoded = json.dumps(
            self.components(),
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def re_full_sha256(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", value))
