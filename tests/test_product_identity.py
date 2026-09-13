from __future__ import annotations

from playstore_app_audit.platform import runtime
from playstore_app_audit.product_identity import (
    ABOUT_TITLE,
    DISPLAY_NAME,
    LEGACY_DISPLAY_NAME,
    PREVIOUS_DISPLAY_NAMES,
    TECHNICAL_NAME,
    is_known_display_name,
)


def test_visible_brand_is_separate_from_technical_slug() -> None:
    assert DISPLAY_NAME == "Store App Audit"
    assert ABOUT_TITLE == "About Store App Audit"
    assert LEGACY_DISPLAY_NAME == "Play Store App Audit"
    assert PREVIOUS_DISPLAY_NAMES == ("Store App Package Audit", "Play Store App Audit")
    assert all(is_known_display_name(name) for name in (DISPLAY_NAME, *PREVIOUS_DISPLAY_NAMES))
    assert not is_known_display_name(TECHNICAL_NAME)
    assert TECHNICAL_NAME == "PlayStoreAppAudit"


def test_rebrand_does_not_move_application_data_or_portable_paths() -> None:
    assert runtime.APP_DIR_NAME == TECHNICAL_NAME
    assert runtime.portable_marker().name == f"{TECHNICAL_NAME}.portable"
    assert runtime.portable_data_dir().name == f"{TECHNICAL_NAME}-data"
