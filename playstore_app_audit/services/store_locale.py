from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass

# Deterministic primary Store language used when no device language or explicit
# user override is available. Multilingual countries intentionally have one
# stable default; ADB audits prefer the actual Android system language instead.
PRIMARY_LANGUAGE_BY_COUNTRY: dict[str, str] = {
    "at": "de",
    "au": "en",
    "be": "nl",
    "br": "pt",
    "ca": "en",
    "ch": "de",
    "de": "de",
    "dk": "da",
    "es": "es",
    "fi": "fi",
    "fr": "fr",
    "gb": "en",
    "ie": "en",
    "it": "it",
    "jp": "ja",
    "kr": "ko",
    "mx": "es",
    "nl": "nl",
    "no": "no",
    "nz": "en",
    "pl": "pl",
    "pt": "pt",
    "se": "sv",
    "us": "en",
}


@dataclass(frozen=True, slots=True)
class StoreLocale:
    language: str
    country: str
    locale: str
    source: str


def primary_language_for_country(country: object) -> str:
    code = str(country or "").strip().lower()
    return PRIMARY_LANGUAGE_BY_COUNTRY.get(code, "en")


def resolve_store_language(language: object, country: object) -> str:
    value = str(language or "").strip().lower().replace("_", "-")
    if not value or value == "auto":
        return primary_language_for_country(country)
    return value.split("-", 1)[0] or primary_language_for_country(country)


def _normalise_android_locale(value: object) -> tuple[str, str, str] | None:
    text = str(value or "").strip()
    if not text or text.casefold() in {"null", "none", "undefined"}:
        return None
    # Android settings may contain an ordered locale list. The first locale is
    # the effective primary system language for the normal UI.
    text = text.split(",", 1)[0].strip().replace("_", "-")
    text = re.sub(r"-r(?=[A-Za-z]{2}(?:-|$))", "-", text)
    match = re.match(r"^(?P<language>[A-Za-z]{2,3})(?:-(?P<country>[A-Za-z]{2}|\d{3}))?", text)
    if not match:
        return None
    language = match.group("language").lower()
    country_raw = match.group("country") or ""
    country = country_raw.lower() if len(country_raw) == 2 else ""
    locale = f"{language}-{country.upper()}" if country else language
    return language, country, locale


def locale_from_android_properties(properties: Mapping[str, str]) -> StoreLocale | None:
    for key in (
        "persist.sys.locale",
        "persist.sys.locales",
        "ro.product.locale",
    ):
        parsed = _normalise_android_locale(properties.get(key, ""))
        if parsed:
            language, country, locale = parsed
            return StoreLocale(language, country, locale, f"android_getprop:{key}")

    language = str(
        properties.get("persist.sys.language")
        or properties.get("ro.product.locale.language")
        or ""
    ).strip()
    country = str(
        properties.get("persist.sys.country")
        or properties.get("ro.product.locale.region")
        or ""
    ).strip()
    combined = f"{language}-{country}" if country else language
    parsed = _normalise_android_locale(combined)
    if parsed:
        parsed_language, parsed_country, locale = parsed
        return StoreLocale(parsed_language, parsed_country, locale, "android_getprop:legacy_locale")
    return None


def parse_getprop_output(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in str(text or "").splitlines():
        match = re.match(r"\[([^]]+)\]: \[([^]]*)\]", line.strip())
        if match:
            values[match.group(1)] = match.group(2)
    return values


def detect_android_store_locale(adb: str) -> StoreLocale | None:
    """Read the Android system locale without modifying the connected device."""
    if not adb:
        return None
    try:
        result = subprocess.run(
            [adb, "shell", "getprop"],
            check=True,
            capture_output=True,
            text=True,
            timeout=25,
        )
        detected = locale_from_android_properties(parse_getprop_output(result.stdout))
        if detected:
            return detected
    except Exception:
        pass

    # Some Android builds expose the ordered locale list through Settings even
    # when the corresponding getprop keys are absent. `settings get` is read-only.
    try:
        result = subprocess.run(
            [adb, "shell", "settings", "get", "system", "system_locales"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        parsed = _normalise_android_locale(result.stdout)
        if parsed:
            language, country, locale = parsed
            return StoreLocale(language, country, locale, "android_settings:system_locales")
    except Exception:
        pass
    return None
