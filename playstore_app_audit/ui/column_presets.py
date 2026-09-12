from __future__ import annotations

from collections.abc import Iterable

from playstore_app_audit.ui import schema

SOURCE_FILE = "file"
SOURCE_DEVICE = "device"
SOURCE_LOCAL_APK = "local_apk"

BUILTIN_PRESETS = ("Basic", "Source Details", "Technical")
CUSTOM_FIXED_COLUMNS = frozenset({"criticality", "package_name"})
CUSTOM_CONTEXTUAL_COLUMNS = frozenset(
    {"change", "device_change", "local_apk_version_comparison"}
)
CUSTOM_AUTOMATIC_COLUMNS = CUSTOM_FIXED_COLUMNS | CUSTOM_CONTEXTUAL_COLUMNS


_BASIC = {
    SOURCE_FILE: (
        "criticality",
        "change",
        "package_name",
        "play_title",
        "play_version",
        "play_last_update",
        "age_days",
        "health_score",
        "notes",
    ),
    SOURCE_DEVICE: (
        "criticality",
        "change",
        "device_change",
        "package_name",
        "play_title",
        "version_comparison",
        "installed_version",
        "play_version",
        "play_last_update",
        "age_days",
        "health_score",
        "notes",
    ),
    SOURCE_LOCAL_APK: (
        "local_apk_version_comparison",
        "criticality",
        "local_apk_file_name",
        "local_apk_label",
        "package_name",
        "local_apk_version_name",
        "play_version",
        "play_last_update",
        "age_days",
        "health_score",
        "notes",
    ),
}

# Source Details intentionally stays readable. Build identifiers, raw SDK
# values and package-level installer identifiers belong in Technical/Custom.
_SOURCE_DETAILS = {
    SOURCE_FILE: (
        "criticality",
        "change",
        "package_name",
        "play_title",
        "play_version",
        "play_last_update",
        "age_days",
        "app_name",
        "store_url",
        "health_score",
        "notes",
    ),
    SOURCE_DEVICE: (
        "criticality",
        "change",
        "device_change",
        "package_name",
        "play_title",
        "version_comparison",
        "installed_version",
        "play_version",
        "play_last_update",
        "age_days",
        "compatibility_status",
        "installer_source",
        "installer_category",
        "app_enabled",
        "first_install_time",
        "last_local_update",
        "health_score",
        "notes",
    ),
    SOURCE_LOCAL_APK: (
        "local_apk_version_comparison",
        "criticality",
        "local_apk_file_name",
        "local_apk_label",
        "package_name",
        "play_title",
        "local_apk_version_name",
        "play_version",
        "play_last_update",
        "age_days",
        "local_apk_location",
        "health_score",
        "notes",
    ),
}

# Technical remains source-aware while grouping verdicts, identity, versions,
# Store freshness, source metadata, raw Store evidence, score and Notes.
_TECHNICAL = {
    SOURCE_FILE: (
        "criticality",
        "change",
        "package_name",
        "play_title",
        "app_name",
        "play_version",
        "play_last_update",
        "age_days",
        "is_system",
        "store_url",
        "play_status",
        "updated_source",
        "play_http_status",
        "health_score",
        "notes",
    ),
    SOURCE_DEVICE: (
        "criticality",
        "change",
        "device_change",
        "version_comparison",
        "compatibility_status",
        "package_name",
        "play_title",
        "installed_version",
        "installed_version_code",
        "play_version",
        "play_last_update",
        "age_days",
        "target_sdk",
        "min_sdk",
        "installer_source",
        "installer_category",
        "installer_package",
        "app_enabled",
        "first_install_time",
        "last_local_update",
        "is_system",
        "sensitive_permissions_count",
        "sensitive_permissions",
        "store_url",
        "play_status",
        "updated_source",
        "play_http_status",
        "health_score",
        "notes",
    ),
    SOURCE_LOCAL_APK: (
        "local_apk_version_comparison",
        "criticality",
        "local_apk_file_name",
        "local_apk_label",
        "package_name",
        "play_title",
        "local_apk_version_name",
        "local_apk_version_code",
        "play_version",
        "play_last_update",
        "age_days",
        "local_apk_location",
        "local_apk_sha256",
        "store_url",
        "play_status",
        "updated_source",
        "play_http_status",
        "health_score",
        "notes",
    ),
}

_LAYOUTS = {
    "Basic": _BASIC,
    "Source Details": _SOURCE_DETAILS,
    "Technical": _TECHNICAL,
}


def normalise_source_mode(value: object) -> str:
    source = str(value or "").strip().casefold()
    if source == SOURCE_DEVICE:
        return SOURCE_DEVICE
    if source.startswith(SOURCE_LOCAL_APK):
        return SOURCE_LOCAL_APK
    return SOURCE_FILE


def normalise_view_preset(value: object) -> str:
    preset = str(value or "").strip()
    if preset == "Device":
        return "Source Details"
    if preset in (*BUILTIN_PRESETS, "Custom"):
        return preset
    return "Basic"


def visible_columns(
    preset: str,
    source_mode: object,
    *,
    compare_previous: bool,
    device_inventory_history: bool,
    health_score_enabled: bool,
    optional_columns: Iterable[str] = (),
) -> list[str]:
    """Return one canonical source-aware built-in layout with Notes last."""

    canonical_preset = normalise_view_preset(preset)
    if canonical_preset not in BUILTIN_PRESETS:
        raise ValueError("Custom layouts are user-controlled.")
    source = normalise_source_mode(source_mode)
    columns = list(_LAYOUTS[canonical_preset][source])

    if not compare_previous or source == SOURCE_LOCAL_APK:
        columns = [column for column in columns if column != "change"]
    if not device_inventory_history or source != SOURCE_DEVICE:
        columns = [column for column in columns if column != "device_change"]
    if canonical_preset != "Technical" and not health_score_enabled:
        columns = [column for column in columns if column != "health_score"]

    # Legacy optional technical-column preferences remain useful, but they may
    # only extend a built-in layout with fields relevant to the active source.
    applicable = set(_TECHNICAL[source])
    additions = [
        column
        for column in optional_columns
        if column in applicable and column in schema.MODEL_COLUMNS and column not in columns
    ]
    if additions:
        insertion = columns.index("notes") if "notes" in columns else len(columns)
        columns[insertion:insertion] = additions

    columns = list(dict.fromkeys(column for column in columns if column in schema.MODEL_COLUMNS))
    if "notes" in columns:
        columns.remove("notes")
    columns.append("notes")
    return columns
