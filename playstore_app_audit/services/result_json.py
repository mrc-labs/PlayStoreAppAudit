from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playstore_app_audit import __version__
from playstore_app_audit.services import alternative_distribution

FORMAT_ID = "play-store-app-audit/results"
SCHEMA_VERSION = 2


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_json_safe(item) for item in value), key=lambda item: str(item))
    if isinstance(value, datetime):
        dt = value.astimezone(UTC) if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return dt.isoformat().replace("+00:00", "Z")
    if isinstance(value, Path):
        return str(value)
    return str(value)


def build_results_document(
    rows: list[dict[str, Any]],
    *,
    scope: str = "all",
    context: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    app_version: str | None = None,
) -> dict[str, Any]:
    """Build the stable machine-readable audit-results envelope.

    Row dictionaries are intentionally preserved rather than reduced to CSV
    fields. This keeps structured v1.7 evidence/change records available to
    downstream automation while the top-level schema can evolve explicitly.
    """
    created = generated_at or datetime.now(UTC)
    if created.tzinfo is None:
        created = created.replace(tzinfo=UTC)
    created = created.astimezone(UTC)
    export_scope = "visible" if str(scope).casefold() == "visible" else "all"
    safe_rows: list[dict[str, Any]] = []
    for row in rows:
        exported = dict(row)
        exported.pop("local_apk_location", None)
        providers = alternative_distribution.serialize_provider_results(exported)
        exported.pop(alternative_distribution.ROW_FIELD, None)
        if providers:
            exported["alternative_distribution"] = {"providers": providers}
        safe_rows.append(_json_safe(exported))
    safe_context = _json_safe(dict(context or {}))
    return {
        "format": FORMAT_ID,
        "schema_version": SCHEMA_VERSION,
        "app_version": str(app_version or __version__),
        "generated_at_utc": created.isoformat().replace("+00:00", "Z"),
        "scope": export_scope,
        "result_count": len(safe_rows),
        "context": safe_context,
        "results": safe_rows,
    }


def write_results_json(
    path: str | Path,
    rows: list[dict[str, Any]],
    *,
    scope: str = "all",
    context: dict[str, Any] | None = None,
) -> Path:
    target = Path(path)
    document = build_results_document(rows, scope=scope, context=context)
    target.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return target
