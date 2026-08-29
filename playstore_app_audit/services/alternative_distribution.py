from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionProvider,
    AlternativeDistributionResult,
    AlternativeDistributionState,
)
from playstore_app_audit.services import state
from playstore_app_audit.services.config_secret_protection import (
    SecretDecryptionResult,
    protect_secret,
    unprotect_secret,
)

ROW_FIELD = "_alternative_distribution"
ELIGIBLE_PLAY_STATUS = "not_found_in_checked_countries"
PROVIDER_ORDER = {"fdroid_main": 0, "aptoide": 1}
STATE_LABELS = {
    AlternativeDistributionState.AVAILABLE: "Available",
    AlternativeDistributionState.NOT_FOUND: "Not found",
    AlternativeDistributionState.INCONCLUSIVE: "Inconclusive",
    AlternativeDistributionState.UNSUPPORTED: "Unsupported",
    AlternativeDistributionState.NOT_CHECKED: "Not checked",
}
ALT_CACHE_SCHEMA_VERSION = 1
ALT_MAX_WORKERS = 2
ALT_REQUEST_TIMEOUT_SECONDS = 10.0
ALT_PHASE_BUDGET_SECONDS = 20.0
ALT_CACHE_TTL_SECONDS = {
    AlternativeDistributionState.AVAILABLE: 24 * 60 * 60,
    AlternativeDistributionState.NOT_FOUND: 12 * 60 * 60,
    AlternativeDistributionState.INCONCLUSIVE: 15 * 60,
}

FDROID_API_ROOT = "https://f-droid.org/api/v1/packages"
FDROID_LISTING_ROOT = "https://f-droid.org/packages"
APTOIDE_APP_GET_ROOT = "https://ws75.aptoide.com/api/7/app/get"
APTOIDE_APPS_GET_ROOT = "https://ws75.aptoide.com/api/7/apps/get"

PROVIDER_INFORMATION = (
    {
        "name": "F-Droid",
        "status": "Built-in",
        "explanation": (
            "Official machine-readable exact-package access is available for the active "
            "main repository. No credentials required."
        ),
        "links": (("Official F-Droid API documentation", "https://f-droid.org/docs/All_our_APIs/"),),
    },
    {
        "name": "Aptoide",
        "status": "Advanced - authorization required",
        "explanation": (
            "Official API access can support exact package queries, but authorized API "
            "credentials and store access are required."
        ),
        "links": (
            ("Aptoide API documentation", "https://partners-center-be.aptoide.com/partners_api_doc/en"),
            ("Aptoide legal terms", "https://en.aptoide.com/company/legal"),
        ),
    },
    {
        "name": "Samsung Galaxy Store",
        "status": "Not supported",
        "explanation": (
            "Reviewed official APIs are oriented toward applications belonging to the "
            "authenticated seller account, not general public-catalogue lookup."
        ),
        "links": (("Samsung developer API documentation", "https://developer.samsung.com/galaxy-store/galaxy-store-developer-api.html"),),
    },
    {
        "name": "Huawei AppGallery",
        "status": "Not supported",
        "explanation": (
            "Reviewed official APIs require project/account authorization and no suitable "
            "public-catalogue lookup API has been established."
        ),
        "links": (("AppGallery Connect documentation", "https://developer.huawei.com/consumer/en/agconnect/"),),
    },
    {
        "name": "Amazon Appstore",
        "status": "Not supported",
        "explanation": (
            "Reviewed APIs focus on authenticated developer submission, testing and "
            "reporting, not general public-catalogue lookup."
        ),
        "links": (("Amazon developer API documentation", "https://developer.amazon.com/docs/app-submission-api/overview.html"),),
    },
    {
        "name": "APKMirror",
        "status": "Not supported",
        "explanation": (
            "No suitable official public catalogue API was established. HTML scraping is "
            "not used by Play Store App Audit."
        ),
        "links": (("APKMirror FAQ", "https://www.apkmirror.com/faq/"),),
    },
    {
        "name": "APKPure",
        "status": "Not supported",
        "explanation": (
            "No supported public API path suitable for this integration was established, "
            "and automated scraping is not used."
        ),
        "links": (("APKPure terms", "https://apkpure.com/terms.html"),),
    },
    {
        "name": "Uptodown",
        "status": "Not supported",
        "explanation": (
            "Automated robot or script access requires authorization; Play Store App Audit "
            "does not scrape the site."
        ),
        "links": (("Uptodown terms", "https://en.uptodown.com/aboutus/terms"),),
    },
)


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _result(
    provider_id: str,
    provider_name: str,
    package_id: str,
    state_value: AlternativeDistributionState,
    *,
    listing_url: str = "",
    version_name: str = "",
    version_code: int | str = "",
    reason: str = "",
) -> AlternativeDistributionResult:
    return AlternativeDistributionResult(
        provider_id=provider_id,
        provider_name=provider_name,
        queried_package_id=package_id,
        state=state_value,
        listing_url=listing_url,
        version_name=version_name,
        version_code=version_code,
        checked_at=_now(),
        provenance="live",
        reason=reason,
    )


def _safe_json(response: requests.Response) -> Any:
    try:
        return response.json()
    except (requests.JSONDecodeError, ValueError):
        return None


class FDroidProvider:
    provider_id = "fdroid_main"
    provider_name = "F-Droid main repository"
    cache_namespace = "fdroid-main"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()

    def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
        url = f"{FDROID_API_ROOT}/{quote(package_id, safe='')}"
        try:
            response = self._session.get(
                url,
                headers={"Accept": "application/json", "User-Agent": "PlayStoreAppAudit/1.99"},
                timeout=timeout,
            )
        except requests.Timeout:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Request timed out.")
        except requests.RequestException:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Network request failed.")

        payload = _safe_json(response)
        if response.status_code == 404:
            if isinstance(payload, dict) and payload.get("error") == "NOT_FOUND":
                return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.NOT_FOUND, reason="The active main repository returned its documented package-not-found response.")
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Unexpected F-Droid not-found response.")
        if response.status_code == 429:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="F-Droid rate limited the request.")
        if response.status_code >= 500:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="F-Droid service error.")
        if response.status_code != 200 or not isinstance(payload, dict):
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Unexpected or malformed F-Droid response.")
        if str(payload.get("packageName") or "") != package_id:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Returned package identifier did not exactly match the query.")

        version_name = ""
        version_code: int | str = ""
        suggested = payload.get("suggestedVersionCode")
        packages = payload.get("packages")
        if isinstance(packages, list):
            for entry in packages:
                if not isinstance(entry, dict) or entry.get("versionCode") != suggested:
                    continue
                candidate_name = entry.get("versionName")
                candidate_code = entry.get("versionCode")
                if isinstance(candidate_name, str) and isinstance(candidate_code, (int, str)):
                    version_name = candidate_name
                    version_code = candidate_code
                break
        return _result(
            self.provider_id,
            self.provider_name,
            package_id,
            AlternativeDistributionState.AVAILABLE,
            listing_url=f"{FDROID_LISTING_ROOT}/{quote(package_id, safe='')}/",
            version_name=version_name,
            version_code=version_code,
            reason="Exact package identifier found in the active F-Droid main repository.",
        )


@dataclass(slots=True)
class AptoideProvider:
    store_name: str
    api_key: str = field(repr=False)
    session: requests.Session | None = field(default=None, repr=False)

    provider_id = "aptoide"
    provider_name = "Aptoide"

    def __post_init__(self) -> None:
        self.store_name = self.store_name.strip().lower()
        if self.session is None:
            self.session = requests.Session()

    @property
    def cache_namespace(self) -> str:
        return f"aptoide:{self.store_name}"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"ApiKey {self.api_key}",
            "User-Agent": "PlayStoreAppAudit/1.99",
        }

    @staticmethod
    def _error_codes(payload: Any) -> set[str]:
        codes: set[str] = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key.casefold() in {"code", "error_code"} and isinstance(item, str):
                        codes.add(item.upper())
                    walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)
        return codes

    def _request(self, url: str, timeout: float) -> tuple[requests.Response | None, Any, str]:
        assert self.session is not None
        try:
            response = self.session.get(url, headers=self._headers, timeout=timeout)
        except requests.Timeout:
            return None, None, "Request timed out."
        except requests.RequestException:
            return None, None, "Network request failed."
        return response, _safe_json(response), ""

    def check(self, package_id: str, *, timeout: float) -> AlternativeDistributionResult:
        store = quote(self.store_name, safe="")
        package = quote(package_id, safe="")
        url = f"{APTOIDE_APP_GET_ROOT}/store_name={store}/package_name={package}/nodes=meta"
        response, payload, request_error = self._request(url, timeout)
        if response is None:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason=request_error)
        codes = self._error_codes(payload)
        if response.status_code == 404 and "APP-1" in codes:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.NOT_FOUND, reason="Aptoide returned its documented application-not-found response.")
        if response.status_code in {401, 403}:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Aptoide rejected the authorized API configuration.")
        if response.status_code == 429:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Aptoide rate limited the request.")
        if response.status_code >= 500:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Aptoide service error.")
        if response.status_code != 200 or not isinstance(payload, dict):
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Unexpected or malformed Aptoide response.")
        info = payload.get("info")
        nodes = payload.get("nodes")
        meta = nodes.get("meta") if isinstance(nodes, dict) else None
        data = meta.get("data") if isinstance(meta, dict) else None
        if not isinstance(info, dict) or info.get("status") != "OK" or not isinstance(data, dict):
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Aptoide response did not contain a successful metadata result.")
        if str(data.get("package") or "") != package_id:
            return _result(self.provider_id, self.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Returned package identifier did not exactly match the query.")
        file_data = data.get("file")
        version_name = str(file_data.get("vername") or "") if isinstance(file_data, dict) else ""
        raw_code = file_data.get("vercode", "") if isinstance(file_data, dict) else ""
        version_code = raw_code if isinstance(raw_code, (int, str)) else ""
        return _result(
            self.provider_id,
            self.provider_name,
            package_id,
            AlternativeDistributionState.AVAILABLE,
            version_name=version_name,
            version_code=version_code,
            reason="Exact package identifier returned by the configured authorized Aptoide store.",
        )

    def test_connection(self, *, timeout: float = ALT_REQUEST_TIMEOUT_SECONDS) -> tuple[str, str]:
        store = quote(self.store_name, safe="")
        url = f"{APTOIDE_APPS_GET_ROOT}/store_name={store}/limit=1"
        response, payload, request_error = self._request(url, timeout)
        if response is None:
            return "network_error", request_error
        if response.status_code in {401, 403}:
            return "configuration_error", "Aptoide rejected the API key or store authorization."
        if response.status_code == 429:
            return "network_error", "Aptoide rate limited the validation request."
        if response.status_code >= 500:
            return "network_error", "Aptoide service is temporarily unavailable."
        if response.status_code != 200 or not isinstance(payload, dict):
            return "configuration_error", "Aptoide returned an unexpected validation response."
        info = payload.get("info")
        datalist = payload.get("datalist")
        if isinstance(info, dict) and info.get("status") == "OK" and isinstance(datalist, dict):
            return "ok", "Authorized Aptoide API connection succeeded for this store."
        return "configuration_error", "Aptoide did not validate the API key and store configuration."


def alternative_settings(settings: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = settings.get("alternative_distribution")
    return dict(raw) if isinstance(raw, dict) else {}


def aptoide_credential(settings: Mapping[str, Any]) -> SecretDecryptionResult:
    config = alternative_settings(settings).get("aptoide")
    protected = config.get("api_key_protected") if isinstance(config, dict) else ""
    return unprotect_secret(protected)


def replace_aptoide_credential(settings: dict[str, Any], api_key: str) -> dict[str, Any]:
    updated = dict(settings)
    alternative = alternative_settings(updated)
    aptoide = dict(alternative.get("aptoide") or {})
    aptoide["api_key_protected"] = protect_secret(api_key)
    alternative["aptoide"] = aptoide
    updated["alternative_distribution"] = alternative
    return updated


def remove_aptoide_credential(settings: dict[str, Any]) -> dict[str, Any]:
    updated = dict(settings)
    alternative = alternative_settings(updated)
    aptoide = dict(alternative.get("aptoide") or {})
    aptoide["api_key_protected"] = ""
    aptoide["enabled"] = False
    alternative["aptoide"] = aptoide
    updated["alternative_distribution"] = alternative
    return updated


def configured_providers(
    settings: Mapping[str, Any],
) -> tuple[list[AlternativeDistributionProvider], list[str]]:
    config = alternative_settings(settings)
    providers: list[AlternativeDistributionProvider] = []
    issues: list[str] = []
    fdroid = config.get("fdroid_main")
    if not isinstance(fdroid, dict) or bool(fdroid.get("enabled", True)):
        providers.append(FDroidProvider())
    aptoide = config.get("aptoide")
    if isinstance(aptoide, dict) and bool(aptoide.get("enabled", False)):
        store_name = str(aptoide.get("store_name") or "").strip().lower()
        if not store_name:
            issues.append("Aptoide checks skipped: an authorized store name is required.")
        elif not valid_aptoide_store_name(store_name):
            issues.append("Aptoide checks skipped: the store name is not a valid domain label.")
        else:
            credential = unprotect_secret(aptoide.get("api_key_protected"))
            if not credential.available:
                issues.append(credential.message)
            else:
                providers.append(AptoideProvider(store_name, credential.value))
    return providers, issues


def _read_cache(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _cache_key(provider: AlternativeDistributionProvider, package_id: str) -> str:
    return f"alt-v{ALT_CACHE_SCHEMA_VERSION}|{provider.cache_namespace}|{package_id.strip().lower()}"


def _fresh_cached_result(
    cache: Mapping[str, Any], provider: AlternativeDistributionProvider, package_id: str
) -> AlternativeDistributionResult | None:
    entry = cache.get(_cache_key(provider, package_id))
    if not isinstance(entry, dict) or not isinstance(entry.get("result"), dict):
        return None
    result = AlternativeDistributionResult.from_mapping(entry["result"])
    if (
        result.provider_id != provider.provider_id
        or result.queried_package_id != package_id
    ):
        return None
    ttl = ALT_CACHE_TTL_SECONDS.get(result.state)
    if ttl is None:
        return None
    try:
        fetched = datetime.fromisoformat(str(entry.get("fetched_at") or "").replace("Z", "+00:00"))
        age = (datetime.now(UTC) - fetched.astimezone(UTC)).total_seconds()
    except (TypeError, ValueError):
        return None
    if age < 0 or age > ttl:
        return None
    return replace(result, provenance="cache")


def _cache_result(
    cache: dict[str, Any], provider: AlternativeDistributionProvider, result: AlternativeDistributionResult
) -> None:
    if result.state not in ALT_CACHE_TTL_SECONDS:
        return
    cache[_cache_key(provider, result.queried_package_id)] = {
        "fetched_at": _now(),
        "result": result.to_mapping(),
    }


def provider_results(row: Mapping[str, Any]) -> list[AlternativeDistributionResult]:
    raw = row.get(ROW_FIELD)
    if not isinstance(raw, list):
        return []
    results = [
        AlternativeDistributionResult.from_mapping(item)
        for item in raw
        if isinstance(item, dict)
    ]
    return sorted(results, key=lambda item: (PROVIDER_ORDER.get(item.provider_id, 99), item.provider_id))


def serialize_provider_results(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [result.to_mapping() for result in provider_results(row)]


def provider_evidence_text(row: Mapping[str, Any]) -> str:
    blocks: list[str] = []
    for result in provider_results(row):
        lines = [result.provider_name, f"Status: {STATE_LABELS[result.state]}"]
        if result.version_name:
            lines.append(f"Version: {result.version_name}")
        if result.version_code != "":
            lines.append(f"Version code: {result.version_code}")
        if result.checked_at:
            lines.append(f"Checked: {result.checked_at}")
        if result.provenance:
            lines.append(f"Source: {result.provenance.title()}")
        if result.reason:
            lines.append(f"Reason: {result.reason}")
        blocks.append("\n".join(lines))
    if not blocks:
        return ""
    blocks.append(
        "Availability here means only that this provider returned an active listing for the "
        "exact package identifier; it does not establish publisher identity or binary equivalence."
    )
    return "\n\n".join(blocks)


def run_alternative_distribution_phase(
    rows: list[dict[str, Any]],
    settings: Mapping[str, Any],
    *,
    pause_event: threading.Event,
    cancel_event: threading.Event,
    force_refresh: bool = False,
    providers: list[AlternativeDistributionProvider] | None = None,
    cache_file: Path | None = None,
    max_workers: int = ALT_MAX_WORKERS,
    phase_budget: float = ALT_PHASE_BUDGET_SECONDS,
    request_timeout: float = ALT_REQUEST_TIMEOUT_SECONDS,
    phase_callback: Callable[[int], None] | None = None,
) -> list[str]:
    eligible = [row for row in rows if str(row.get("play_status") or "") == ELIGIBLE_PLAY_STATUS]
    if providers is None:
        providers, issues = configured_providers(settings)
    else:
        issues = []
    if not eligible or not providers:
        return issues
    if phase_callback is not None:
        phase_callback(len(eligible))

    cache_path = cache_file or state.alternative_distribution_cache_path()
    cache = _read_cache(cache_path)
    results_by_package: dict[str, list[AlternativeDistributionResult]] = {}
    pending: list[tuple[dict[str, Any], AlternativeDistributionProvider]] = []
    for row in eligible:
        package_id = str(row.get("package_name") or "").strip()
        if not package_id:
            continue
        for provider in providers:
            cached = None if force_refresh else _fresh_cached_result(cache, provider, package_id)
            if cached is not None:
                results_by_package.setdefault(package_id, []).append(cached)
            else:
                pending.append((row, provider))

    started = time.monotonic()
    active: dict[Future[AlternativeDistributionResult], tuple[dict[str, Any], AlternativeDistributionProvider]] = {}
    unfinished_active: list[tuple[dict[str, Any], AlternativeDistributionProvider]] = []
    executor = ThreadPoolExecutor(max_workers=max(1, min(ALT_MAX_WORKERS, max_workers)), thread_name_prefix="alternative-provider")
    try:
        while pending or active:
            budget_expired = time.monotonic() - started >= phase_budget
            if cancel_event.is_set() or budget_expired:
                break
            while pending and len(active) < max(1, min(ALT_MAX_WORKERS, max_workers)) and pause_event.is_set() and not cancel_event.is_set():
                row, provider = pending.pop(0)
                package_id = str(row.get("package_name") or "").strip()
                future = executor.submit(provider.check, package_id, timeout=request_timeout)
                active[future] = (row, provider)
            if not active:
                time.sleep(0.05)
                continue
            done, _not_done = wait(tuple(active), timeout=0.05, return_when=FIRST_COMPLETED)
            for future in done:
                row, provider = active.pop(future)
                package_id = str(row.get("package_name") or "").strip()
                try:
                    result = future.result()
                except Exception:
                    result = _result(provider.provider_id, provider.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Provider check failed unexpectedly.")
                results_by_package.setdefault(package_id, []).append(result)
                _cache_result(cache, provider, result)
        for future, (row, provider) in list(active.items()):
            if not future.done():
                future.cancel()
                unfinished_active.append((row, provider))
                continue
            package_id = str(row.get("package_name") or "").strip()
            try:
                result = future.result()
            except Exception:
                result = _result(provider.provider_id, provider.provider_name, package_id, AlternativeDistributionState.INCONCLUSIVE, reason="Provider check failed unexpectedly.")
            results_by_package.setdefault(package_id, []).append(result)
            _cache_result(cache, provider, result)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    pending_reason = "Check was not submitted because Stop was requested." if cancel_event.is_set() else "Check was not submitted before the provider-phase time budget expired."
    for row, provider in [*pending, *unfinished_active]:
        package_id = str(row.get("package_name") or "").strip()
        results_by_package.setdefault(package_id, []).append(
            _result(provider.provider_id, provider.provider_name, package_id, AlternativeDistributionState.NOT_CHECKED, reason=pending_reason)
        )
    for row in eligible:
        package_id = str(row.get("package_name") or "").strip()
        row[ROW_FIELD] = [
            result.to_mapping()
            for result in sorted(
                results_by_package.get(package_id, []),
                key=lambda item: (PROVIDER_ORDER.get(item.provider_id, 99), item.provider_id),
            )
        ]
    try:
        _write_cache(cache_path, cache)
    except OSError:
        issues.append("Alternative-distribution evidence cache could not be updated.")
    return issues


_STORE_NAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def valid_aptoide_store_name(value: str) -> bool:
    return bool(_STORE_NAME_PATTERN.fullmatch(str(value or "").strip().lower()))
