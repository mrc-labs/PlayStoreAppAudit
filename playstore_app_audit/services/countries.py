from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from playstore_app_audit.services.app_icon_metadata import enrich_rows_with_store_metadata
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.play_store import PlayStoreService

# Compatibility adapter retained for older UI layers/imports. Store scheduling,
# language fallback and regional classification now live only in PlayStoreService.
_SERVICE = PlayStoreService()


def fetch_app_multicountry(
    app_name: str,
    package_name: str,
    config: AuditConfig,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Any] | None:
    rows = _SERVICE.audit(
        [{"app_name": app_name, "package_name": package_name}],
        config,
        pause_event=pause_event,
        cancel_event=cancel_event,
    )
    enrich_rows_with_store_metadata(rows)
    return rows[0] if rows else None


def audit_apps_multicountry(
    apps: list[dict[str, str]],
    config: AuditConfig,
    progress_callback: Callable[[int, int, str], None] | None = None,
    pause_event: threading.Event | None = None,
    cancel_event: threading.Event | None = None,
    row_completed_callback: Callable[[int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    def completed(index: int, row: dict[str, Any]) -> None:
        enrich_rows_with_store_metadata([row])
        if row_completed_callback is not None:
            row_completed_callback(index, row)

    rows = _SERVICE.audit(
        apps,
        config,
        progress_callback,
        pause_event=pause_event,
        cancel_event=cancel_event,
        row_completed_callback=completed if row_completed_callback is not None else None,
    )
    return enrich_rows_with_store_metadata(rows)
