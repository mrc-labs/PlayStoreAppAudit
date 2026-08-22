from __future__ import annotations

import playstore_app_audit.services.state as state
from playstore_app_audit.services.store_locale import StoreLocale, set_active_device_store_locale


def test_legacy_v15_default_english_migrates_to_auto(monkeypatch) -> None:
    monkeypatch.setattr(state, "_read_json", lambda _path, _fallback: {"store_language": "en"})

    settings = state.load_settings()

    assert settings["store_language"] == "auto"
    assert settings[state.STORE_LANGUAGE_AUTO_MIGRATION_KEY] is True


def test_explicit_english_is_preserved_after_auto_migration(monkeypatch) -> None:
    monkeypatch.setattr(
        state,
        "_read_json",
        lambda _path, _fallback: {
            "store_language": "en",
            state.STORE_LANGUAGE_AUTO_MIGRATION_KEY: True,
        },
    )

    settings = state.load_settings()

    assert settings["store_language"] == "en"


def test_cache_key_uses_effective_auto_language_for_file_source() -> None:
    set_active_device_store_locale(None)

    assert state._cache_key("ch", "auto", "com.example.app") == (
        "v2|ch|de|com.example.app"
    )
    assert state._cache_key("it", "auto", "com.example.app") == (
        "v2|it|it|com.example.app"
    )


def test_cache_key_uses_device_language_for_adb_auto_context() -> None:
    set_active_device_store_locale(StoreLocale("it", "ch", "it-CH", "test"))
    try:
        assert state._cache_key("ch", "auto", "com.example.app") == (
            "v2|ch|it|com.example.app"
        )
        assert state._cache_key("ch", "en", "com.example.app") == (
            "v2|ch|en|com.example.app"
        )
    finally:
        set_active_device_store_locale(None)
