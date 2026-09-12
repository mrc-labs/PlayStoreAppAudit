from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

# Canonical table schema for every UI layer. Older releases progressively
# mutated module globals while importing successive window classes. Keeping one
# immutable source of truth prevents import order from changing the model.
PRIMARY_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
)

COMPACT_MODEL_COLUMNS = (
    "criticality",
    "change",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
    "play_status",
    "updated_source",
    "play_http_status",
    "app_name",
    "store_url",
    "is_system",
)

DEVICE_EXTRA_COLUMNS = (
    "play_version",
    "installed_version",
    "installed_version_code",
    "version_comparison",
    "installer_source",
    "installer_category",
    "installer_package",
)
DEVICE_MODEL_COLUMNS = tuple(dict.fromkeys(COMPACT_MODEL_COLUMNS + DEVICE_EXTRA_COLUMNS))

INSIGHTS_EXTRA_COLUMNS = (
    "compatibility_status",
    "target_sdk",
    "min_sdk",
    "first_install_time",
    "last_local_update",
    "app_enabled",
    "sensitive_permissions_count",
    "sensitive_permissions",
    "device_change",
    "health_score",
)
LOCAL_APK_EXTRA_COLUMNS = (
    "local_apk_file_name",
    "local_apk_location",
    "local_apk_label",
    "local_apk_version_name",
    "local_apk_version_code",
    "local_apk_version_comparison",
    "local_apk_sha256",
)
MODEL_COLUMNS = tuple(
    dict.fromkeys(DEVICE_MODEL_COLUMNS + INSIGHTS_EXTRA_COLUMNS + LOCAL_APK_EXTRA_COLUMNS)
)

COLUMN_LABELS = {
    "criticality": "Store Status",
    "change": "Play Store Listing Change",
    "package_name": "Package Name",
    "play_title": "Play Store Title",
    "play_last_update": "Last Store Update",
    "age_days": "Store Age (Days)",
    "notes": "Notes",
    "play_status": "Play Status",
    "updated_source": "Update Source",
    "play_http_status": "HTTP Status",
    "app_name": "Input Name",
    "store_url": "Store URL",
    "is_system": "System App",
    "play_version": "Play Store Version",
    "installed_version": "Installed Version",
    "installed_version_code": "Installed Version Code",
    "version_comparison": "Installed vs Store",
    "installer_source": "Installer Source",
    "installer_category": "Installer Category",
    "installer_package": "Installer Package",
    "compatibility_status": "Android Compatibility",
    "target_sdk": "Target SDK",
    "min_sdk": "Min SDK",
    "first_install_time": "First Installed",
    "last_local_update": "Last Local Update",
    "app_enabled": "Enabled State",
    "sensitive_permissions_count": "Sensitive Permissions Count",
    "sensitive_permissions": "Sensitive Permissions",
    "device_change": "Device App Inventory Change",
    "health_score": "Maintenance Score",
    "local_apk_file_name": "APK Filename",
    "local_apk_location": "Location",
    "local_apk_label": "Local App Label",
    "local_apk_version_name": "Local APK Version",
    "local_apk_version_code": "Local Version Code",
    "local_apk_version_comparison": "Local APK vs Store",
    "local_apk_sha256": "APK SHA-256",
}

TABLE_HEADER_LABELS = {
    **COLUMN_LABELS,
    "change": "Play Store Listing\nChange",
    "play_last_update": "Last Store\nUpdate",
    "age_days": "Store Age\n(Days)",
    "play_http_status": "HTTP\nStatus",
    "is_system": "System\nApp",
    "version_comparison": "Installed vs\nStore",
    "compatibility_status": "Android\nCompatibility",
    "sensitive_permissions_count": "Sensitive Permissions\nCount",
    "device_change": "Device App Inventory\nChange",
    "health_score": "Maintenance\nScore",
    "local_apk_version_comparison": "Local APK vs\nStore",
    "local_apk_version_code": "Local Version\nCode",
}


class ColumnWidthCategory(StrEnum):
    COMPACT = "compact"
    MEDIUM = "medium"
    PRIMARY = "primary"
    LONG_TEXT = "long_text"


@dataclass(frozen=True, slots=True)
class ColumnWidthPolicy:
    category: ColumnWidthCategory
    preferred: int
    minimum: int
    maximum: int


def _width(
    category: ColumnWidthCategory,
    preferred: int,
    minimum: int,
    maximum: int,
) -> ColumnWidthPolicy:
    return ColumnWidthPolicy(category, preferred, minimum, maximum)


# Default widths describe the meaning and normal value shape of each column.
# They deliberately do not inspect body values: long URLs and notes remain
# bounded while primary identity columns receive useful reading space.
COLUMN_WIDTH_POLICIES = {
    "criticality": _width(ColumnWidthCategory.MEDIUM, 145, 120, 180),
    "change": _width(ColumnWidthCategory.MEDIUM, 145, 125, 165),
    "package_name": _width(ColumnWidthCategory.PRIMARY, 300, 240, 340),
    "play_title": _width(ColumnWidthCategory.PRIMARY, 280, 220, 340),
    "play_last_update": _width(ColumnWidthCategory.COMPACT, 104, 96, 108),
    "age_days": _width(ColumnWidthCategory.COMPACT, 78, 70, 82),
    "notes": _width(ColumnWidthCategory.LONG_TEXT, 360, 280, 400),
    "play_status": _width(ColumnWidthCategory.MEDIUM, 180, 145, 210),
    "updated_source": _width(ColumnWidthCategory.MEDIUM, 170, 140, 200),
    "play_http_status": _width(ColumnWidthCategory.COMPACT, 78, 70, 82),
    "app_name": _width(ColumnWidthCategory.PRIMARY, 220, 180, 280),
    "store_url": _width(ColumnWidthCategory.LONG_TEXT, 250, 220, 280),
    "is_system": _width(ColumnWidthCategory.COMPACT, 78, 70, 82),
    "play_version": _width(ColumnWidthCategory.MEDIUM, 150, 125, 190),
    "installed_version": _width(ColumnWidthCategory.MEDIUM, 150, 125, 190),
    "installed_version_code": _width(ColumnWidthCategory.COMPACT, 125, 105, 140),
    "version_comparison": _width(ColumnWidthCategory.MEDIUM, 116, 104, 120),
    "installer_source": _width(ColumnWidthCategory.LONG_TEXT, 220, 180, 280),
    "installer_category": _width(ColumnWidthCategory.MEDIUM, 155, 130, 185),
    "installer_package": _width(ColumnWidthCategory.LONG_TEXT, 240, 200, 300),
    "compatibility_status": _width(ColumnWidthCategory.MEDIUM, 120, 108, 124),
    "target_sdk": _width(ColumnWidthCategory.COMPACT, 74, 66, 78),
    "min_sdk": _width(ColumnWidthCategory.COMPACT, 70, 64, 74),
    "first_install_time": _width(ColumnWidthCategory.MEDIUM, 155, 135, 185),
    "last_local_update": _width(ColumnWidthCategory.MEDIUM, 155, 135, 185),
    "app_enabled": _width(ColumnWidthCategory.COMPACT, 88, 80, 92),
    "sensitive_permissions_count": _width(ColumnWidthCategory.COMPACT, 124, 112, 128),
    "sensitive_permissions": _width(ColumnWidthCategory.LONG_TEXT, 320, 260, 380),
    "device_change": _width(ColumnWidthCategory.MEDIUM, 155, 135, 175),
    "health_score": _width(ColumnWidthCategory.COMPACT, 86, 78, 90),
    "local_apk_file_name": _width(ColumnWidthCategory.PRIMARY, 230, 180, 300),
    "local_apk_location": _width(ColumnWidthCategory.LONG_TEXT, 360, 260, 480),
    "local_apk_label": _width(ColumnWidthCategory.PRIMARY, 220, 170, 280),
    "local_apk_version_name": _width(ColumnWidthCategory.MEDIUM, 150, 125, 190),
    "local_apk_version_code": _width(ColumnWidthCategory.COMPACT, 125, 105, 140),
    "local_apk_version_comparison": _width(ColumnWidthCategory.MEDIUM, 120, 108, 135),
    "local_apk_sha256": _width(ColumnWidthCategory.LONG_TEXT, 280, 220, 360),
}

DEFAULT_WIDTHS = {
    column: policy.preferred for column, policy in COLUMN_WIDTH_POLICIES.items()
}


def semantic_default_width(
    column: str,
    measure_text: Callable[[str], int] | None = None,
    *,
    header_chrome_width: int = 0,
) -> int:
    """Return a bounded semantic default, optionally fitting explicit header lines."""

    policy = COLUMN_WIDTH_POLICIES.get(
        column,
        ColumnWidthPolicy(ColumnWidthCategory.MEDIUM, 140, 110, 190),
    )
    semantic_width = max(policy.minimum, min(policy.maximum, policy.preferred))
    if measure_text is not None:
        header = TABLE_HEADER_LABELS.get(column, COLUMN_LABELS.get(column, column))
        line_width = max((measure_text(line) for line in header.splitlines()), default=0)
        header_width = line_width + max(0, int(header_chrome_width))
        # Explicit header lines may grow a default within its semantic range,
        # but never turn an accessibility/font difference into an unbounded
        # table-width change.
        return max(semantic_width, min(policy.maximum, header_width))
    return semantic_width

EXPORT_EXTRA_FIELDS = (
    "is_system",
    "criticality",
    "age_days",
    "change",
    "cache_hit",
    "play_version",
    "installed_version",
    "installed_version_code",
    "version_comparison",
    "installer_source",
    "installer_category",
    "installer_package",
    *INSIGHTS_EXTRA_COLUMNS,
    "source_mode",
    *(column for column in LOCAL_APK_EXTRA_COLUMNS if column != "local_apk_location"),
    "local_apk_long_version_code",
    "local_apk_file_size",
    "local_apk_modified_at",
    "local_apk_min_sdk",
    "local_apk_target_sdk",
    "local_apk_compile_sdk",
    "local_apk_debuggable",
    "local_apk_permissions",
    "local_apk_features",
    "local_apk_warnings",
)
