"""Canonical CSV field order and presentation shared by GUI and CLI."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Any, TextIO

from playstore_app_audit.services import presentation, result_json

_BASE_FIELDS = (
    "app_name", "package_name", "play_status", "play_http_status",
    "play_title", "play_category", "play_last_update", "play_version", "updated_source",
    "store_url", "notes",
)

EXPORT_EXTRA_FIELDS = (
    "is_system", "criticality", "age_days", "change", "cache_hit",
    "play_version", "installed_version", "installed_version_code",
    "version_comparison", "resolved_play_version", "resolved_play_version_code",
    "device_specific_profile", "device_specific_resolver_status",
    "device_specific_profile_id", "installer_source", "installer_package", "compatibility_status", "target_sdk", "min_sdk",
    "first_install_time", "last_local_update", "app_enabled",
    "sensitive_permissions_count", "sensitive_permissions", "device_change",
    "health_score", "source_mode", "local_apk_file_name", "local_apk_label",
    "local_apk_version_name", "local_apk_version_code",
    "local_apk_version_comparison", "local_apk_sha256",
    "local_apk_long_version_code", "local_apk_file_size",
    "local_apk_modified_at", "local_apk_min_sdk", "local_apk_target_sdk",
    "local_apk_compile_sdk", "local_apk_debuggable",
    "local_apk_permissions", "local_apk_features", "local_apk_warnings",
)
EXPORT_FIELDS = tuple(dict.fromkeys((*_BASE_FIELDS, *EXPORT_EXTRA_FIELDS)))


def write_csv(handle: TextIO, rows: Iterable[dict[str, Any]], *, date_style: str) -> None:
    writer = csv.DictWriter(handle, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in presentation.rows_for_output(list(rows), date_style):
        writer.writerow(result_json.privacy_filter_row(row))
