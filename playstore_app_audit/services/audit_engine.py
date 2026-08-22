from __future__ import annotations

import csv
import re
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

PLAY_URL = "https://play.google.com/store/apps/details"

PACKAGE_HEADERS = {
    "package",
    "packageid",
    "packagename",
    "package_name",
    "appid",
    "app_id",
    "id",
}
APP_NAME_HEADERS = {
    "app",
    "appname",
    "app_name",
    "name",
    "title",
    "label",
}

_thread_local = threading.local()


@dataclass(frozen=True)
class AuditConfig:
    country: str = "us"
    language: str = "en"
    fallback_country: str = "us"
    fallback_language: str = "en"
    max_workers: int = 16
    timeout_seconds: int = 25
    max_retries: int = 2
    retry_sleep_base: float = 1.0


def _normalise_header(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", value.strip().lower().replace(" ", "_"))


def _looks_like_package(value: str) -> bool:
    value = value.strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+", value))


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


def load_apps(input_path: str | Path) -> list[dict[str, str]]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    if not raw.strip():
        raise ValueError("The input file is empty.")

    delimiter = _detect_delimiter(raw[:5000])
    parsed = list(csv.reader(raw.splitlines(), delimiter=delimiter))
    parsed = [[cell.strip() for cell in row] for row in parsed if any(cell.strip() for cell in row)]
    if not parsed:
        raise ValueError("The file does not contain usable rows.")

    first = parsed[0]
    normalised_headers = [_normalise_header(v) for v in first]
    package_index: int | None = None
    name_index: int | None = None
    has_header = False

    for index, header in enumerate(normalised_headers):
        if header in PACKAGE_HEADERS:
            package_index = index
            has_header = True
            break

    for index, header in enumerate(normalised_headers):
        if header in APP_NAME_HEADERS:
            name_index = index
            has_header = True
            break

    data_rows = parsed[1:] if has_header else parsed

    if package_index is None:
        max_columns = max(len(row) for row in data_rows)
        scores: list[tuple[int, int]] = []
        for index in range(max_columns):
            score = sum(
                1 for row in data_rows[:100] if index < len(row) and _looks_like_package(row[index])
            )
            scores.append((score, index))
        best_score, package_index = max(scores)
        if best_score == 0:
            raise ValueError(
                "No Android package column was found. Use a column named package_name or one package per row."
            )

    if name_index is None:
        for index in range(max(len(row) for row in data_rows)):
            if index != package_index:
                name_index = index
                break

    apps: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in data_rows:
        if package_index >= len(row):
            continue

        package_name = row[package_index].strip()
        package_name = re.sub(r"^package:", "", package_name, flags=re.IGNORECASE).strip()

        if not _looks_like_package(package_name) or package_name in seen:
            continue

        seen.add(package_name)
        app_name = ""
        if name_index is not None and name_index < len(row):
            app_name = row[name_index].strip()

        apps.append({"app_name": app_name or package_name, "package_name": package_name})

    if not apps:
        raise ValueError("No valid Android packages were found in the file.")

    return apps


def normalise_updated(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return str(value)
    text = str(value).strip()
    if re.fullmatch(r"\d{10,13}", text):
        timestamp = float(text)
        if len(text) == 13:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return text
    return text


def _get_session(language: str) -> requests.Session:
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
                "Accept-Language": f"{language}-{language.upper()},{language};q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        _thread_local.session = session
    return session


def _parse_updated_from_html(html: str) -> str:
    """Extract only update-specific dates from a Play Store HTML response.

    `datePublished` is intentionally not accepted: it can be the original app
    publication date and therefore must never be used as the latest-update date.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    visible_patterns = [
        r"Aggiornata il\s+([0-9]{1,2}\s+[A-Za-zÀ-ÿ]+\s+[0-9]{4})",
        r"Ultimo aggiornamento\s+([0-9]{1,2}\s+[A-Za-zÀ-ÿ]+\s+[0-9]{4})",
        r"Updated on\s+([A-Za-z]{3,9}\s+[0-9]{1,2},\s+[0-9]{4})",
        r"Updated\s+([A-Za-z]{3,9}\s+[0-9]{1,2},\s+[0-9]{4})",
    ]
    for pattern in visible_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    embedded_patterns = [
        r'"dateModified"\s*:\s*"([^"]+)"',
        r'"updated"\s*:\s*"([^"]+)"',
    ]
    for pattern in embedded_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _scraper_request(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
) -> dict[str, Any]:
    try:
        from google_play_scraper import app as play_app
    except ImportError as exc:
        return {
            "ok": False,
            "title": "",
            "updated": "",
            "error": f"google_play_scraper is not installed: {exc}",
        }

    last_error = ""
    for attempt in range(config.max_retries + 1):
        try:
            data = play_app(package_name, lang=language, country=country)
            return {
                "ok": True,
                "title": str(data.get("title") or "").strip(),
                "updated": normalise_updated(data.get("updated")),
                "error": "",
            }
        except Exception as exc:
            last_error = str(exc)[:300]
            if attempt < config.max_retries:
                time.sleep(config.retry_sleep_base * (attempt + 1))
    return {
        "ok": False,
        "title": "",
        "updated": "",
        "error": last_error or "Unknown Google Play scraper error",
    }


def _html_request(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
) -> dict[str, Any]:
    params = {"id": package_name, "hl": language, "gl": country}
    session = _get_session(language)
    last_error = ""
    attempts = 0
    for attempt in range(config.max_retries + 1):
        attempts = attempt + 1
        try:
            response = session.get(PLAY_URL, params=params, timeout=config.timeout_seconds)
            if response.status_code in {429, 500, 502, 503, 504} and attempt < config.max_retries:
                time.sleep(config.retry_sleep_base * (attempt + 1))
                continue
            break
        except requests.RequestException as exc:
            last_error = str(exc)[:300]
            if attempt < config.max_retries:
                time.sleep(config.retry_sleep_base * (attempt + 1))
            else:
                return {
                    "ok": False,
                    "status": "request_error",
                    "http_status": "",
                    "title": "",
                    "updated": "",
                    "url": f"{PLAY_URL}?id={package_name}&hl={language}&gl={country}",
                    "error": last_error,
                    "attempts": attempts,
                    "retry_count": max(0, attempts - 1),
                }
    else:
        return {
            "ok": False,
            "status": "request_error",
            "http_status": "",
            "title": "",
            "updated": "",
            "url": f"{PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "error": last_error or "Request not completed",
            "attempts": attempts,
            "retry_count": max(0, attempts - 1),
        }

    html = response.text
    store_url = response.url
    if response.status_code == 404:
        return {
            "ok": False,
            "status": "not_found_or_unavailable",
            "http_status": 404,
            "title": "",
            "updated": "",
            "url": store_url,
            "error": "404",
            "attempts": attempts,
            "retry_count": max(0, attempts - 1),
        }
    if response.status_code != 200:
        return {
            "ok": False,
            "status": "http_error",
            "http_status": response.status_code,
            "title": "",
            "updated": "",
            "url": store_url,
            "error": f"HTTP {response.status_code}",
            "attempts": attempts,
            "retry_count": max(0, attempts - 1),
        }

    unavailable_signals = (
        "Siamo spiacenti, l'URL richiesto non è stato trovato",
        "L'URL richiesto non è stato trovato",
        "Item not found",
        "We're sorry, the requested URL was not found",
    )
    if any(signal in html for signal in unavailable_signals):
        return {
            "ok": False,
            "status": "not_found_or_unavailable",
            "http_status": 200,
            "title": "",
            "updated": "",
            "url": store_url,
            "error": "The page indicates that the listing is unavailable.",
            "attempts": attempts,
            "retry_count": max(0, attempts - 1),
        }

    soup = BeautifulSoup(html, "html.parser")
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = str(og_title["content"]).strip()
    return {
        "ok": True,
        "status": "available",
        "http_status": response.status_code,
        "title": title,
        "updated": _parse_updated_from_html(html),
        "url": store_url,
        "error": "",
        "attempts": attempts,
        "retry_count": max(0, attempts - 1),
    }


def _fetch_locale(
    package_name: str,
    language: str,
    country: str,
    config: AuditConfig,
) -> dict[str, Any]:
    scraper = _scraper_request(package_name, language, country, config)
    if scraper["ok"] and scraper["updated"]:
        return {
            "status": "available",
            "http_status": 200,
            "title": scraper["title"],
            "updated": scraper["updated"],
            "source": "google_play_scraper",
            "url": f"{PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "notes": "",
        }

    html = _html_request(package_name, language, country, config)
    if scraper["ok"]:
        title = scraper["title"] or html.get("title", "")
        updated = scraper["updated"] or html.get("updated", "")
        return {
            "status": "available",
            "http_status": html.get("http_status", 200),
            "title": title,
            "updated": updated,
            "source": "google_play_scraper"
            if scraper["updated"]
            else ("html_fallback" if updated else ""),
            "url": html.get("url")
            or f"{PLAY_URL}?id={package_name}&hl={language}&gl={country}",
            "notes": "" if updated else "update_date_not_found",
        }

    return {
        "status": html.get("status", "check_failed"),
        "http_status": html.get("http_status", ""),
        "title": html.get("title", ""),
        "updated": html.get("updated", ""),
        "source": "html_fallback" if html.get("updated") else "",
        "url": html.get("url")
        or f"{PLAY_URL}?id={package_name}&hl={language}&gl={country}",
        "notes": " | ".join(
            value
            for value in [
                f"scraper: {scraper['error']}" if scraper["error"] else "",
                f"html: {html.get('error', '')}" if html.get("error") else "",
            ]
            if value
        ),
    }


def fetch_app(app_name: str, package_name: str, config: AuditConfig) -> dict[str, Any]:
    primary = _fetch_locale(package_name, config.language, config.country, config)
    needs_fallback = not primary["updated"] or primary["status"] in {
        "not_found_or_unavailable",
        "request_error",
        "http_error",
        "check_failed",
    }
    fallback: dict[str, Any] | None = None
    if needs_fallback:
        fallback = _fetch_locale(
            package_name,
            config.fallback_language,
            config.fallback_country,
            config,
        )

    final = dict(primary)
    if fallback:
        if not final["updated"] and fallback["updated"]:
            final["updated"] = fallback["updated"]
            final["source"] = f"{fallback['source']}_fallback_locale"
            final["notes"] = " | ".join(
                filter(None, [final["notes"], "data_used_from_fallback_locale"])
            )
        if not final["title"] and fallback["title"]:
            final["title"] = fallback["title"]
        if final["status"] == "not_found_or_unavailable" and fallback["status"] == "available":
            final["status"] = "available_in_fallback_locale_only"
            final["http_status"] = fallback["http_status"]
            final["url"] = fallback["url"]
            final["notes"] = " | ".join(
                filter(None, [final["notes"], "primary_locale_unavailable_fallback_available"])
            )
        if (
            final["status"] in {"request_error", "http_error", "check_failed"}
            and fallback["status"] == "available"
        ):
            final["status"] = "available"
            final["http_status"] = fallback["http_status"]
            final["url"] = fallback["url"]
            final["notes"] = " | ".join(
                filter(None, [final["notes"], "fallback_locale_check_succeeded"])
            )

    return {
        "app_name": app_name,
        "package_name": package_name,
        "play_status": final["status"],
        "play_http_status": final["http_status"],
        "play_title": final["title"],
        "play_last_update": final["updated"],
        "updated_source": final["source"],
        "store_url": final["url"],
        "notes": final["notes"],
    }


def audit_apps(
    apps: list[dict[str, str]],
    config: AuditConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any] | None] = [None] * len(apps)
    with ThreadPoolExecutor(max_workers=max(1, config.max_workers)) as executor:
        futures = {
            executor.submit(fetch_app, app["app_name"], app["package_name"], config): index
            for index, app in enumerate(apps)
        }
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            app = apps[index]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = {
                    "app_name": app["app_name"],
                    "package_name": app["package_name"],
                    "play_status": "unexpected_error",
                    "play_http_status": "",
                    "play_title": "",
                    "play_last_update": "",
                    "updated_source": "",
                    "store_url": f"{PLAY_URL}?id={app['package_name']}",
                    "notes": str(exc)[:500],
                }
            completed += 1
            if progress_callback:
                progress_callback(completed, len(apps), app["package_name"])

    return [result for result in results if result is not None]


def iter_packages(apps: Iterable[dict[str, str]]) -> Iterable[str]:
    for app in apps:
        yield app["package_name"]


OUTPUT_FIELDS = [
    "app_name",
    "package_name",
    "play_status",
    "play_http_status",
    "play_title",
    "play_last_update",
    "updated_source",
    "store_url",
    "notes",
]
