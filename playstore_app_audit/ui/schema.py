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
    "play_last_update": "Last update",
    "age_days": "Age (days)",
    "notes": "Notes",
    "play_status": "Play status",
    "updated_source": "Update source",
    "play_http_status": "HTTP status",
    "app_name": "Input name",
    "store_url": "Store URL",
    "is_system": "System app",
    "play_version": "Play Store version",
    "installed_version": "Installed version",
    "installed_version_code": "Installed version code",
    "version_comparison": "Installed vs Store",
    "installer_source": "Installer source",
    "installer_category": "Installer category",
    "installer_package": "Installer package",
    "compatibility_status": "Android compatibility",
    "target_sdk": "Target SDK",
    "min_sdk": "Min SDK",
    "first_install_time": "First installed",
    "last_local_update": "Last local update",
    "app_enabled": "Enabled state",
    "sensitive_permissions_count": "Sensitive permissions count",
    "sensitive_permissions": "Sensitive permissions",
    "device_change": "Device inventory change",
    "health_score": "Health score",
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
