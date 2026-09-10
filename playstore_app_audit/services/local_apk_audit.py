from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC
from typing import Any

from playstore_app_audit.domain.local_artifact_store import LocalArtifactStoreAssociation
from playstore_app_audit.services import alternative_distribution, device_metadata

SOURCE_MODE = "local_apk"
LIBRARY_SOURCE_MODE = "local_apk_library"
LOCAL_APK_SOURCE_MODES = frozenset({SOURCE_MODE, LIBRARY_SOURCE_MODE})


def is_local_apk_source(source_mode: object) -> bool:
    return isinstance(source_mode, str) and source_mode in LOCAL_APK_SOURCE_MODES


def _mutable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _mutable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mutable_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_mutable_value(item) for item in value), key=str)
    return value


def association_result_row(
    association: LocalArtifactStoreAssociation,
    *,
    source_mode: str = SOURCE_MODE,
) -> dict[str, Any] | None:
    """Convert one completed association to the shared audit-row schema.

    The canonical path is attached only after package-level Store/provider work
    has completed, so it remains local UI evidence and never enters a request.
    """

    evidence = association.package_evidence
    if evidence is None:
        return None
    artifact = association.artifact
    row = _mutable_value(evidence.store_result)
    if evidence.alternative_distribution:
        row[alternative_distribution.ROW_FIELD] = [
            item.to_mapping() for item in evidence.alternative_distribution
        ]
    local_version = artifact.version_name or ""
    row.update(
        {
            "source_mode": source_mode,
            "app_name": artifact.application_label or artifact.file_name,
            "package_name": artifact.package_lookup_key,
            "is_system": None,
            "local_apk_file_name": artifact.file_name,
            "local_apk_location": str(artifact.canonical_path),
            "local_apk_sha256": artifact.artifact_sha256,
            "local_apk_label": artifact.application_label,
            "local_apk_version_name": artifact.version_name,
            "local_apk_version_code": artifact.version_code,
            "local_apk_long_version_code": artifact.long_version_code,
            "local_apk_file_size": artifact.file_size,
            "local_apk_modified_at": artifact.modified_at.astimezone(UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "local_apk_min_sdk": artifact.min_sdk,
            "local_apk_target_sdk": artifact.target_sdk,
            "local_apk_compile_sdk": artifact.compile_sdk,
            "local_apk_debuggable": artifact.application_debuggable,
            "local_apk_permissions": list(artifact.permissions),
            "local_apk_features": list(artifact.features),
            "local_apk_warnings": [warning.value for warning in artifact.warnings],
            "local_apk_version_comparison": device_metadata.compare_versions(
                local_version, row.get("play_version")
            ),
        }
    )
    return row


def association_result_rows(
    associations: tuple[LocalArtifactStoreAssociation, ...],
    *,
    source_mode: str = SOURCE_MODE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for association in associations:
        row = association_result_row(association, source_mode=source_mode)
        if row is not None:
            rows.append(row)
    return rows
