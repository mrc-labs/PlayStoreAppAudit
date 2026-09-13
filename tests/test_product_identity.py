from __future__ import annotations

from playstore_app_audit.platform import runtime
from playstore_app_audit.product_identity import (
    ABOUT_TITLE,
    DISPLAY_NAME,
    LEGACY_DISPLAY_NAME,
    TECHNICAL_NAME,
)


def test_visible_brand_is_separate_from_technical_slug() -> None:
    assert DISPLAY_NAME == "Store App Package Audit"
    assert ABOUT_TITLE == "About Store App Package Audit"
    assert LEGACY_DISPLAY_NAME == "Play Store App Audit"
    assert TECHNICAL_NAME == "PlayStoreAppAudit"


def test_rebrand_does_not_move_application_data_or_portable_paths() -> None:
    assert runtime.APP_DIR_NAME == TECHNICAL_NAME
    assert runtime.portable_marker().name == f"{TECHNICAL_NAME}.portable"
    assert runtime.portable_data_dir().name == f"{TECHNICAL_NAME}-data"
