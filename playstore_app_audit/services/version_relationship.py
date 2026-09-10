from __future__ import annotations

import re

VERSION_MISMATCH_STATES = frozenset({"Outdated", "Newer", "Different"})
DEVICE_SPECIFIC_VALUES = frozenset({"varies with device", "varies by device", "varies"})


def _normalise(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in {"none", "null", "n/a"} else text


def _canonical(value: str) -> str:
    return re.sub(r"\s+", "", value.lstrip("vV")).casefold()


def compare_versions(local: object, store: object) -> str:
    """Return a conservative local/installed-to-Store version relationship."""

    local_text = _normalise(local)
    store_text = _normalise(store)
    if not local_text or not store_text:
        return "Unknown"
    if store_text.casefold() in DEVICE_SPECIFIC_VALUES:
        return "Device-specific"
    if _canonical(local_text) == _canonical(store_text):
        return "Match"

    local_match = re.match(r"^[vV]?\s*(\d+(?:\.\d+)*)", local_text)
    store_match = re.match(r"^[vV]?\s*(\d+(?:\.\d+)*)", store_text)
    if local_match is None or store_match is None:
        return "Different"
    local_parts = tuple(int(part) for part in local_match.group(1).split("."))
    store_parts = tuple(int(part) for part in store_match.group(1).split("."))
    for local_part, store_part in zip(local_parts, store_parts, strict=False):
        if local_part < store_part:
            return "Outdated"
        if local_part > store_part:
            return "Newer"
    return "Different"
