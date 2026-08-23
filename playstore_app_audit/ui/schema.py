from __future__ import annotations

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
MODEL_COLUMNS = tuple(dict.fromkeys(DEVICE_MODEL_COLUMNS + INSIGHTS_EXTRA_COLUMNS))

COLUMN_LABELS = {
    "criticality": "Status",
    "change": "Change",
    "package_name": "Package Name",
    "play_title": "Play Store Title",
    "play_last_update": "Last Update",
    "age_days": "Age (Days)",
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
    "device_change": "Device Inventory Change",
    "health_score": "Health Score",
}

DEFAULT_WIDTHS = {
    "criticality": 145,
    "change": 105,
    "package_name": 300,
    "play_title": 265,
    "play_last_update": 120,
    "age_days": 92,
    "notes": 460,
    "play_status": 190,
    "updated_source": 180,
    "play_http_status": 90,
    "app_name": 220,
    "store_url": 350,
    "is_system": 90,
    "play_version": 150,
    "installed_version": 150,
    "installed_version_code": 120,
    "version_comparison": 140,
    "installer_source": 230,
    "installer_category": 150,
    "installer_package": 250,
    "compatibility_status": 150,
    "target_sdk": 90,
    "min_sdk": 80,
    "first_install_time": 155,
    "last_local_update": 155,
    "app_enabled": 100,
    "sensitive_permissions_count": 105,
    "sensitive_permissions": 360,
    "device_change": 155,
    "health_score": 90,
}

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
)
