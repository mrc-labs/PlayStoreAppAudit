"""Stable separation between user-facing product identity and technical identifiers."""

from __future__ import annotations

DISPLAY_NAME = "Store App Audit"
TECHNICAL_NAME = "PlayStoreAppAudit"
LEGACY_DISPLAY_NAME = "Play Store App Audit"
PREVIOUS_DISPLAY_NAMES = ("Store App Package Audit", LEGACY_DISPLAY_NAME)
ABOUT_TITLE = f"About {DISPLAY_NAME}"


def is_known_display_name(value: str) -> bool:
    """Recognize current and previous UI labels during the visible rename."""
    return value in (DISPLAY_NAME, *PREVIOUS_DISPLAY_NAMES)
