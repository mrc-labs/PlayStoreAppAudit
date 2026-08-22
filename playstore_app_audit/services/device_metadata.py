from __future__ import annotations

import re
import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import playstore_app_audit.services.audit_engine as core
import playstore_app_audit.services.state as state

DEFAULT_FALLBACK_COUNTRIES = "us, gb, de, fr, it, ch, es, ca, au, jp"
DEFAULT_DEVICE_INFO_ENABLED = True

_FALLBACK_COUNTRIES: tuple[str, ...] = tuple(token.strip() for token in DEFAULT_FALLBACK_COUNTRIES.split(","))


def install_user_state_extensions() -> None:
    """Extend v7 settings/technical-column dictionaries in place."""
    state.DEFAULT_SETTINGS.setdefault("fallback_countries", DEFAULT_FALLBACK_COUNTRIES)
    state.DEFAULT_SETTINGS.setdefault("collect_device_metadata", DEFAULT_DEVICE_INFO_ENABLED)
    state.TECHNICAL_COLUMNS.update(
        {
            "play_version": "Play Store version",
            "installed_version": "Installed version",
            "version_comparison": "Installed vs Store",
            "installer_source": "Installer source",
        }
    )


def parse_country_list(value: object, selected_country: str = "") -> tuple[list[str], list[str]]:
    """Parse an expert comma/space separated country list.

    Returns (valid, invalid). Values are ISO-style 2-letter market codes.
    'uk' is accepted as a convenience alias for Google Play's 'gb'.
    """
    raw = str(value or "")
    tokens = [token for token in re.split(r"[,;\s]+", raw) if token]
    valid: list[str] = []
    invalid: list[str] = []
    selected = selected_country.strip().lower()
    for token in tokens:
        code = token.strip().lower()
        if code == "uk":
            code = "gb"
        if not re.fullmatch(r"[a-z]{2}", code):
            invalid.append(token)
            continue
        if code == selected or code in valid:
            continue
        valid.append(code)
    return valid, invalid


def normalise_country_string(value: object) -> tuple[str, list[str]]:
    valid, invalid = parse_country_list(value)
    return ", ".join(valid), invalid


def set_fallback_countries(value: object, selected_country: str = "") -> tuple[str, ...]:
    global _FALLBACK_COUNTRIES
    valid, _invalid = parse_country_list(value, selected_country)
    _FALLBACK_COUNTRIES = tuple(valid)
    return _FALLBACK_COUNTRIES


def get_fallback_countries(selected_country: str = "") -> tuple[str, ...]:
    selected = selected_country.strip().lower()
    return tuple(country for country in _FALLBACK_COUNTRIES if country != selected)


def clear_history() -> None:
    try:
        state.history_path().write_text("{}", encoding="utf-8")
    except Exception:
        pass


def save_history_merged(rows: list[dict[str, Any]]) -> None:
    """Compatibility adapter for targeted rechecks using the canonical history schema."""
    state.save_history_merged(rows)


def _normalise_version(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in {"none", "null", "n/a"}:
        return ""
    return text


def compare_versions(installed: object, store: object) -> str:
    installed_text = _normalise_version(installed)
    store_text = _normalise_version(store)
    if not installed_text or not store_text:
        return "Unknown"
    if store_text.casefold() in {"varies with device", "varies by device", "varies"}:
        return "Device-specific"

    def canonical(value: str) -> str:
        return re.sub(r"\s+", "", value.strip().lstrip("vV")).casefold()

    return "Match" if canonical(installed_text) == canonical(store_text) else "Different"


def _friendly_installer(package: str) -> str:
    package = str(package or "").strip()
    if not package or package.lower() in {"null", "none"}:
        return "Unknown / preinstalled"
    labels = {
        "com.android.vending": "Google Play",
        "com.sec.android.app.samsungapps": "Galaxy Store",
        "com.amazon.venezia": "Amazon Appstore",
        "com.huawei.appmarket": "Huawei AppGallery",
        "com.android.packageinstaller": "Sideload / package installer",
        "com.google.android.packageinstaller": "Sideload / package installer",
    }
    label = labels.get(package)
    return f"{label} ({package})" if label else package


def _parse_installer_map(output: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        match = re.match(r"package:(\S+)(?:\s+installer=(\S+))?", line)
        if match:
            mapping[match.group(1)] = match.group(2) or ""
    return mapping


def _read_package_version(adb: str, package_name: str) -> tuple[str, str]:
    try:
        result = subprocess.run(
            [adb, "shell", "dumpsys", "package", package_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=25,
        )
        text = result.stdout
        version_name_match = re.search(r"\bversionName=([^\r\n]+)", text)
        version_code_match = re.search(r"\bversionCode=(\d+)", text)
        version_name = _normalise_version(version_name_match.group(1) if version_name_match else "")
        version_code = version_code_match.group(1) if version_code_match else ""
        return version_name, version_code
    except Exception:
        return "", ""


def collect_device_metadata(
    adb: str,
    packages: list[str],
    cancel_event: threading.Event | None = None,
    max_workers: int = 6,
) -> dict[str, dict[str, str]]:
    """Collect installed version + installer source from the connected Android device."""
    packages = list(dict.fromkeys(str(package).strip() for package in packages if str(package).strip()))
    if not adb or not packages:
        return {}

    installer_map: dict[str, str] = {}
    try:
        result = subprocess.run(
            [adb, "shell", "pm", "list", "packages", "-i"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        installer_map = _parse_installer_map(result.stdout)
    except Exception:
        installer_map = {}

    metadata: dict[str, dict[str, str]] = {
        package: {
            "installed_version": "",
            "installed_version_code": "",
            "installer_source": _friendly_installer(installer_map.get(package, "")),
        }
        for package in packages
    }

    def read_one(package: str) -> tuple[str, str, str]:
        if cancel_event is not None and cancel_event.is_set():
            return package, "", ""
        version_name, version_code = _read_package_version(adb, package)
        return package, version_name, version_code

    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 8))) as executor:
        futures = {executor.submit(read_one, package): package for package in packages}
        for future in as_completed(futures):
            if cancel_event is not None and cancel_event.is_set():
                for pending in futures:
                    pending.cancel()
                break
            package, version_name, version_code = future.result()
            metadata[package]["installed_version"] = version_name
            metadata[package]["installed_version_code"] = version_code
    return metadata


def install_core_version_support() -> None:
    """Patch the existing core fetchers to carry Play Store version without extra Store requests."""
    if getattr(core, "_playstore_audit_v8_version_support", False):
        return

    def scraper_request(
        package_name: str, language: str, country: str, config: core.AuditConfig
    ) -> dict[str, Any]:
        try:
            from google_play_scraper import app as play_app
            from google_play_scraper.exceptions import NotFoundError
        except ImportError as exc:
            return {
                "ok": False,
                "title": "",
                "updated": "",
                "version": "",
                "error": f"google_play_scraper not installed: {exc}",
            }

        last_error = ""
        for attempt in range(config.max_retries + 1):
            try:
                data = play_app(package_name, lang=language, country=country)
                return {
                    "ok": True,
                    "title": str(data.get("title") or "").strip(),
                    "updated": core.normalise_updated(data.get("updated")),
                    "version": _normalise_version(data.get("version")),
                    "error": "",
                }
            except NotFoundError as exc:
                last_error = str(exc)[:300]
                break
            except Exception as exc:
                last_error = str(exc)[:300]
                if attempt < config.max_retries:
                    time.sleep(config.retry_sleep_base * (attempt + 1))
        return {
            "ok": False,
            "title": "",
            "updated": "",
            "version": "",
            "error": last_error or "Unknown Google Play scraper error",
        }

    def fetch_locale(
        package_name: str, language: str, country: str, config: core.AuditConfig
    ) -> dict[str, Any]:
        scraper = scraper_request(package_name, language, country, config)
        if scraper["ok"] and scraper["updated"]:
            return {
                "status": "available",
                "http_status": 200,
                "title": scraper["title"],
                "updated": scraper["updated"],
                "version": scraper["version"],
                "source": "google_play_scraper",
                "url": f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
                "notes": "",
            }

        html = core._html_request(package_name, language, country, config)
        if scraper["ok"]:
            title = scraper["title"] or html.get("title", "")
            updated = scraper["updated"] or html.get("updated", "")
            return {
                "status": "available",
                "http_status": html.get("http_status", 200),
                "title": title,
                "updated": updated,
                "version": scraper["version"],
                "source": "google_play_scraper"
                if scraper["updated"]
                else ("html_fallback" if updated else ""),
                "url": html.get("url") or f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
                "notes": "" if updated else "update_date_not_found",
            }

        return {
            "status": html.get("status", "check_failed"),
            "http_status": html.get("http_status", ""),
            "title": html.get("title", ""),
            "updated": html.get("updated", ""),
            "version": "",
            "source": "html_fallback" if html.get("updated") else "",
            "url": html.get("url") or f"{core.PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "notes": " | ".join(
                value
                for value in [
                    f"scraper: {scraper['error']}" if scraper["error"] else "",
                    f"html: {html.get('error', '')}" if html.get("error") else "",
                ]
                if value
            ),
        }

    core._scraper_request = scraper_request
    core._fetch_locale = fetch_locale
    if "play_version" not in core.OUTPUT_FIELDS:
        core.OUTPUT_FIELDS.insert(core.OUTPUT_FIELDS.index("play_last_update") + 1, "play_version")
    core._playstore_audit_v8_version_support = True


def _append_note(existing: object, note: str) -> str:
    parts = [str(existing or "").strip(), note.strip()]
    return " | ".join(part for part in parts if part)


def _wait_until_running(
    pause_event: threading.Event | None,
    cancel_event: threading.Event | None,
) -> bool:
    if cancel_event is not None and cancel_event.is_set():
        return False
    if pause_event is None:
        return True
    while not pause_event.wait(0.10):
        if cancel_event is not None and cancel_event.is_set():
            return False
    return cancel_event is None or not cancel_event.is_set()


def fetch_app_v8(
    app_name: str,
    package_name: str,
    config: core.AuditConfig,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any] | None:
    if not _wait_until_running(pause_event, cancel_event):
        return None

    selected = (config.country or "").lower()
    primary = core._fetch_locale(package_name, config.language, selected, config)
    if cancel_event is not None and cancel_event.is_set():
        return None

    result: dict[str, Any] = {
        "app_name": app_name,
        "package_name": package_name,
        "play_status": primary.get("status", "check_failed"),
        "play_http_status": primary.get("http_status", ""),
        "play_title": primary.get("title", ""),
        "play_last_update": primary.get("updated", ""),
        "play_version": primary.get("version", ""),
        "updated_source": primary.get("source", ""),
        "store_url": primary.get("url", f"{core.PLAY_URL}?id={package_name}"),
        "notes": primary.get("notes", ""),
    }

    primary_status = str(primary.get("status") or "")
    markets = get_fallback_countries(selected)

    # Healthy listing: only use an alternative market to fill missing metadata.
    if primary_status == "available":
        if result["play_last_update"] and result["play_version"]:
            return result
        for country in markets:
            if not _wait_until_running(pause_event, cancel_event):
                return None
            alternative = core._fetch_locale(package_name, "en", country, config)
            if str(alternative.get("status") or "") != "available":
                continue
            if not result["play_last_update"] and alternative.get("updated"):
                result["play_last_update"] = alternative.get("updated", "")
                result["updated_source"] = f"{alternative.get('source', '')}_fallback_locale".strip("_")
            if not result["play_version"] and alternative.get("version"):
                result["play_version"] = alternative.get("version", "")
            if not result["play_title"] and alternative.get("title"):
                result["play_title"] = alternative.get("title", "")
            result["notes"] = _append_note(
                result["notes"], "missing_metadata_completed_from_fallback_market"
            )
            break
        return result

    checked: list[str] = []
    failed: list[str] = []
    for country in markets:
        if not _wait_until_running(pause_event, cancel_event):
            return None
        checked.append(country)
        alternative = core._fetch_locale(package_name, "en", country, config)
        if cancel_event is not None and cancel_event.is_set():
            return None
        alt_status = str(alternative.get("status") or "")
        if alt_status == "available":
            if primary_status == "not_found_or_unavailable":
                result["play_status"] = "available_in_other_country"
                note = (
                    f"selected_country_unavailable:{selected}; available_in:{country}; "
                    f"multi_country_checked:{','.join(checked)}"
                )
            else:
                result["play_status"] = "available"
                note = (
                    f"primary_country_check_failed:{selected}; fallback_available:{country}; "
                    f"multi_country_checked:{','.join(checked)}"
                )
            result["play_http_status"] = alternative.get("http_status", "")
            result["play_title"] = alternative.get("title", "") or result["play_title"]
            result["play_last_update"] = alternative.get("updated", "") or result["play_last_update"]
            result["play_version"] = alternative.get("version", "") or result["play_version"]
            source = str(alternative.get("source") or "")
            result["updated_source"] = f"{source}_multi_country" if source else result["updated_source"]
            result["store_url"] = alternative.get("url", "") or result["store_url"]
            result["notes"] = _append_note(result["notes"], note)
            return result
        if alt_status != "not_found_or_unavailable":
            failed.append(f"{country}:{alt_status or 'unknown'}")

    checked_text = ",".join(checked)
    if not checked:
        result["play_status"] = "multi_country_check_inconclusive"
        result["notes"] = _append_note(result["notes"], "no_fallback_countries_configured")
    elif primary_status == "not_found_or_unavailable" and not failed:
        result["play_status"] = "not_found_in_checked_countries"
        result["notes"] = _append_note(
            result["notes"],
            f"selected_country_unavailable:{selected}; also_not_found_in:{checked_text}; likely_removed_or_region_restricted",
        )
    else:
        result["play_status"] = "multi_country_check_inconclusive"
        result["notes"] = _append_note(
            result["notes"],
            f"primary_country_status:{primary_status or 'unknown'}; multi_country_checked:{checked_text}; check_errors:{','.join(failed)}",
        )
    return result


def audit_apps_v8(
    apps: list[dict[str, str]],
    config: core.AuditConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    install_core_version_support()
    results: list[dict[str, Any] | None] = [None] * len(apps)

    def run_one(app: dict[str, str]) -> dict[str, Any] | None:
        if not _wait_until_running(pause_event, cancel_event):
            return None
        return fetch_app_v8(
            app["app_name"],
            app["package_name"],
            config,
            pause_event=pause_event,
            cancel_event=cancel_event,
        )

    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        futures = {executor.submit(run_one, app): index for index, app in enumerate(apps)}
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            app = apps[index]
            if cancel_event is not None and cancel_event.is_set():
                for pending in futures:
                    pending.cancel()
            try:
                row = future.result()
                if row is None:
                    continue
                results[index] = row
            except Exception as exc:
                if cancel_event is not None and cancel_event.is_set():
                    continue
                results[index] = {
                    "app_name": app["app_name"],
                    "package_name": app["package_name"],
                    "play_status": "unexpected_error",
                    "play_http_status": "",
                    "play_title": "",
                    "play_last_update": "",
                    "play_version": "",
                    "updated_source": "",
                    "store_url": f"{core.PLAY_URL}?id={app['package_name']}",
                    "notes": str(exc)[:500],
                }
            completed += 1
            if progress_callback:
                progress_callback(completed, len(apps), app["package_name"])
    return [row for row in results if row is not None]


def enrich_rows_with_device_metadata(
    rows: list[dict[str, Any]],
    metadata: dict[str, dict[str, str]],
) -> None:
    for row in rows:
        package_name = str(row.get("package_name") or "")
        info = metadata.get(package_name, {})
        installed = info.get("installed_version", "")
        row["installed_version"] = installed
        row["installed_version_code"] = info.get("installed_version_code", "")
        row["installer_source"] = info.get("installer_source", "")
        row["version_comparison"] = compare_versions(installed, row.get("play_version"))


def is_problematic(row: dict[str, Any]) -> bool:
    return str(row.get("criticality_key") or "") in {"red", "blue", "purple"}


def dashboard_summary(rows: list[dict[str, Any]], visible_count: int | None = None) -> str:
    total = len(rows)
    if not total:
        return "No results yet"
    counts = {
        key: sum(1 for row in rows if str(row.get("criticality_key") or "") == key)
        for key in ("green", "yellow", "orange", "red", "blue", "purple")
    }
    parts = []
    if visible_count is not None and visible_count != total:
        parts.append(f"{visible_count}/{total} shown")
    else:
        parts.append(f"{total} apps")
    parts.extend(
        [
            f"Current {counts['green']}",
            f"Aging {counts['yellow']}",
            f"Stale {counts['orange']}",
            f"Removed {counts['red']}",
            f"Anomaly {counts['blue']}",
            f"Other {counts['purple']}",
        ]
    )
    aged = []
    for row in rows:
        try:
            age = int(row.get("age_days", ""))
        except (TypeError, ValueError):
            continue
        aged.append((age, str(row.get("play_title") or row.get("package_name") or "")))
    if aged:
        age, title = max(aged)
        short_title = title if len(title) <= 28 else title[:27] + "…"
        parts.append(f"Oldest {short_title} {age}d")
    differences = sum(1 for row in rows if row.get("version_comparison") == "Different")
    if differences:
        parts.append(f"Version differences {differences}")
    return "  •  ".join(parts)


install_user_state_extensions()
install_core_version_support()
