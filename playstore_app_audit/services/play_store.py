from __future__ import annotations

from typing import Any, Callable

from playstore_audit_core import AuditConfig, fetch_app, load_apps
from playstore_audit_v8_features import audit_apps_v8

ProgressCallback = Callable[[int, int, str], None]


class PlayStoreService:
    """Stable service boundary between UI code and Store retrieval logic.

    The existing retrieval implementation is intentionally kept behind this
    interface so the scraper can be replaced later without changing the Qt UI.
    """

    def load_packages(self, path: str) -> list[dict[str, str]]:
        return load_apps(path)

    def fetch_one(self, app_name: str, package_name: str, config: AuditConfig) -> dict[str, Any]:
        return fetch_app(app_name, package_name, config)

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback: ProgressCallback | None = None,
        pause_event=None,
        cancel_event=None,
    ) -> list[dict[str, Any]]:
        return audit_apps_v8(
            apps,
            config,
            progress_callback,
            pause_event=pause_event,
            cancel_event=cancel_event,
        )
