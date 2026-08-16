"""Compatibility shim for the canonical state service.

New code should import from ``playstore_app_audit.services.state`` directly.
"""

from playstore_app_audit.services.state import (
    DEFAULT_SETTINGS,
    TECHNICAL_COLUMNS,
    _cache_key,
    _read_json,
    _write_json,
    app_data_dir,
    cache_path,
    clear_cache,
    compare_with_history,
    history_path,
    load_fresh_cache,
    load_history,
    load_settings,
    reset_settings,
    save_history,
    save_settings,
    settings_path,
    update_cache,
)

__all__ = [
    "DEFAULT_SETTINGS",
    "TECHNICAL_COLUMNS",
    "app_data_dir",
    "settings_path",
    "cache_path",
    "history_path",
    "load_settings",
    "save_settings",
    "reset_settings",
    "clear_cache",
    "load_fresh_cache",
    "update_cache",
    "load_history",
    "compare_with_history",
    "save_history",
]
