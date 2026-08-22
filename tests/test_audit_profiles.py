from __future__ import annotations

from typing import Any

import pytest

import playstore_app_audit.services.audit_profiles as audit_profiles
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.audit_profiles as audit_profiles_ui


def _profile() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "source_mode": "device",
        "view_preset": "Technical",
        "store_country": "ch",
        "settings": {
            "store_language": "it",
            "fallback_countries": "de, fr, us",
            "store_workers": 12,
            "cache_enabled": True,
            "cache_ttl_hours": 48,
            "collect_device_metadata": True,
            "permissions_audit_enabled": False,
            "inventory_history_enabled": True,
            "compare_previous": True,
            "exclude_system_source": False,
        },
    }


def test_profile_normalisation_is_bounded_and_excludes_filter_state() -> None:
    profile = audit_profiles.normalise_profile(
        {
            "source_mode": "DEVICE",
            "view_preset": "Technical",
            "store_country": "CH",
            "settings": {
                "store_language": "IT",
                "fallback_countries": "de, invalid, us",
                "store_workers": 999,
                "cache_ttl_hours": 9999,
                "cache_enabled": 1,
                "collect_device_metadata": True,
                "inventory_history_enabled": True,
                "exclude_system_source": False,
                "search": "legacy",
                "active_filter_preset": "Sideloaded",
                "technical_columns": ["target_sdk"],
            },
        }
    )

    assert profile is not None
    assert profile["source_mode"] == "device"
    assert profile["view_preset"] == "Technical"
    assert profile["store_country"] == "ch"
    assert profile["settings"]["store_language"] == "it"
    assert profile["settings"]["store_workers"] == state.MAX_STORE_WORKERS
    assert profile["settings"]["cache_ttl_hours"] == 720
    assert "search" not in profile["settings"]
    assert "active_filter_preset" not in profile["settings"]
    assert "technical_columns" not in profile["settings"]


def test_capture_profile_keeps_source_view_and_audit_settings_only() -> None:
    settings = {
        "store_language": "auto",
        "fallback_countries": "gb, de",
        "store_workers": 16,
        "cache_enabled": True,
        "cache_ttl_hours": 72,
        "collect_device_metadata": True,
        "permissions_audit_enabled": True,
        "inventory_history_enabled": False,
        "compare_previous": False,
        "exclude_system_source": True,
        "search": "must not persist",
        "active_filter_preset": "Alternative stores",
    }

    profile = audit_profiles.capture_profile(
        settings,
        "de",
        source_mode="file",
        view_preset="Device",
    )

    assert profile["source_mode"] == "file"
    assert profile["view_preset"] == "Device"
    assert profile["store_country"] == "de"
    assert profile["settings"]["permissions_audit_enabled"] is True
    assert "search" not in profile["settings"]
    assert "active_filter_preset" not in profile["settings"]


def test_profile_store_round_trip_and_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: dict[str, Any] = {"show_app_icons": True}

    def load() -> dict[str, Any]:
        return dict(stored)

    def save(values: dict[str, Any]) -> dict[str, Any]:
        stored.clear()
        stored.update(values)
        return dict(stored)

    monkeypatch.setattr(state, "load_settings", load)
    monkeypatch.setattr(state, "save_settings", save)

    audit_profiles.save_profile("  Phone   audit  ", _profile())
    profiles = audit_profiles.load_profiles()
    assert list(profiles) == ["Phone audit"]
    assert profiles["Phone audit"]["source_mode"] == "device"
    assert stored["show_app_icons"] is True

    assert audit_profiles.delete_profile("Phone audit") is True
    assert audit_profiles.load_profiles() == {}
    assert audit_profiles.delete_profile("Phone audit") is False


def test_apply_profile_preserves_unrelated_settings_and_sets_view() -> None:
    country, source, view, merged = audit_profiles.apply_profile_to_settings(
        _profile(),
        {
            "show_app_icons": True,
            "view_preset": "Basic",
            "store_language": "de",
        },
    )

    assert country == "ch"
    assert source == "device"
    assert view == "Technical"
    assert merged["view_preset"] == "Technical"
    assert merged["store_language"] == "it"
    assert merged["show_app_icons"] is True


class _Text:
    def __init__(self, value: str = "") -> None:
        self.value = value
        self.tooltip = ""

    def text(self) -> str:
        return self.value

    def setText(self, value: str) -> None:
        self.value = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


class _Spin:
    def __init__(self) -> None:
        self.value = 0

    def setValue(self, value: int) -> None:
        self.value = value


class _Check:
    def __init__(self) -> None:
        self.checked = True

    def setChecked(self, value: bool) -> None:
        self.checked = value


class _Action:
    def __init__(self, text: str) -> None:
        self._text = text
        self.checked = False

    def text(self) -> str:
        return self._text

    def setChecked(self, value: bool) -> None:
        self.checked = value


class _Window:
    source_mode = "file"
    _device_store_locale = None
    _store_country_manual_override = False

    def __init__(self) -> None:
        self.country_edit = _Text("de")
        self.workers_spin = _Spin()
        self.exclude_system_source_check = _Check()
        self.status_label = _Text()
        self.view_preset_actions = [_Action("Basic"), _Action("Technical")]
        self.country_resolution_calls: list[object] = []
        self.view_calls: list[str] = []
        self.user_settings: dict[str, Any] = {}

    def _apply_store_country_resolution(self, locale: object) -> None:
        self.country_resolution_calls.append(locale)

    def _set_view_preset(self, name: str) -> None:
        self.view_calls.append(name)


def test_apply_window_profile_updates_runtime_controls_without_switching_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_state: dict[str, Any] = {"show_app_icons": True, "view_preset": "Basic"}
    fallback_calls: list[tuple[object, str]] = []

    monkeypatch.setattr(state, "load_settings", lambda: dict(saved_state))

    def save(values: dict[str, Any]) -> dict[str, Any]:
        saved_state.clear()
        saved_state.update(values)
        return dict(saved_state)

    monkeypatch.setattr(state, "save_settings", save)
    monkeypatch.setattr(
        device_metadata,
        "set_fallback_countries",
        lambda countries, primary: fallback_calls.append((countries, primary)),
    )

    window = _Window()
    audit_profiles_ui.apply_window_profile(window, _profile())

    assert window.source_mode == "file"
    assert window.country_edit.text() == "ch"
    assert window._store_country_manual_override is True
    assert window.country_resolution_calls == [None]
    assert window.workers_spin.value == 12
    assert window.exclude_system_source_check.checked is False
    assert window.view_calls == ["Technical"]
    assert [action.checked for action in window.view_preset_actions] == [False, True]
    assert fallback_calls == [("de, fr, us", "ch")]
    assert saved_state["show_app_icons"] is True
    assert "profile expects source: Android phone" in window.status_label.text()
