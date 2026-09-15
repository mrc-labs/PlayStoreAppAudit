"""Qt-independent orchestration for optional Device Specific resolution."""

from __future__ import annotations

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverCacheIdentity,
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services import store_locale
from playstore_app_audit.services.device_specific_cache import (
    DEFAULT_RESOLVER_CACHE_TTL_HOURS,
    load_cached_result,
    store_resolved_result,
)
from playstore_app_audit.services.device_specific_profiles import load_reference_profile
from playstore_app_audit.services.device_specific_protocol import (
    PROTOCOL_REVISION,
    provider_context_hash,
    resolve_metadata_with_dispenser,
)
from playstore_app_audit.services.version_relationship import DEVICE_SPECIFIC_VALUES


_DEVICE_SPECIFIC_VALUES = frozenset(
    str(value).strip().casefold() for value in DEVICE_SPECIFIC_VALUES
)


def should_attempt_device_specific_resolver(public_store_version: object) -> bool:
    value = str(public_store_version or "").strip().casefold()
    return value in _DEVICE_SPECIFIC_VALUES


def build_cache_identity(
    *,
    package_name: str,
    profile_id: str,
    dispenser_url: str,
    country: str,
    language: str,
) -> ResolverCacheIdentity:
    profile = load_reference_profile(profile_id)
    effective_language = store_locale.resolve_store_language(language, country)
    return ResolverCacheIdentity(
        package_name=package_name,
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        requested_country=country,
        requested_language=effective_language,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=provider_context_hash(dispenser_url),
        protocol_revision=PROTOCOL_REVISION,
    )


def _inconclusive_result(
    *,
    package_name: str,
    profile_id: str,
    profile_hash: str,
    country: str,
    language: str,
    diagnostics: str,
) -> ResolverResult:
    return ResolverResult(
        package_name=package_name,
        profile_id=profile_id,
        profile_hash=profile_hash,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        status=ResolverStatus.INCONCLUSIVE,
        requested_country=country,
        requested_language=language,
        diagnostics=diagnostics,
    )


def resolve_if_device_specific(
    *,
    public_store_version: object,
    package_name: str,
    profile_id: str,
    dispenser_url: str | None,
    country: str,
    language: str,
    cache_ttl_hours: int = DEFAULT_RESOLVER_CACHE_TTL_HOURS,
    use_cache: bool = True,
    timeout: float = 30.0,
) -> ResolverResult | None:
    if not should_attempt_device_specific_resolver(public_store_version):
        return None

    profile = load_reference_profile(profile_id)
    effective_language = store_locale.resolve_store_language(language, country)
    endpoint = str(dispenser_url or "").strip()
    if not endpoint:
        return _inconclusive_result(
            package_name=package_name,
            profile_id=profile.profile_id,
            profile_hash=profile.profile_hash,
            country=country,
            language=effective_language,
            diagnostics="missing_dispenser",
        )

    try:
        context_hash = provider_context_hash(endpoint)
    except ValueError:
        return _inconclusive_result(
            package_name=package_name,
            profile_id=profile.profile_id,
            profile_hash=profile.profile_hash,
            country=country,
            language=effective_language,
            diagnostics="invalid_dispenser_endpoint",
        )

    identity = ResolverCacheIdentity(
        package_name=package_name,
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        requested_country=country,
        requested_language=effective_language,
        provider=ResolverProvider.ANONYMOUS_DISPENSER,
        provider_context_hash=context_hash,
        protocol_revision=PROTOCOL_REVISION,
    )

    if use_cache:
        cached = load_cached_result(identity, ttl_hours=cache_ttl_hours)
        if cached is not None:
            return cached

    result = resolve_metadata_with_dispenser(
        package_name=package_name,
        profile=profile,
        dispenser_url=endpoint,
        country=country,
        language=effective_language,
        timeout=timeout,
    )
    if use_cache and result.resolved:
        store_resolved_result(identity, result)
    return result
