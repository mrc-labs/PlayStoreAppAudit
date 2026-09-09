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


def test_capture_profile_keeps_audit_execution_settings_only() -> None:
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
    )

    assert profile["source_mode"] == "file"
    assert "view_preset" not in profile
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


def test_apply_legacy_profile_preserves_all_presentation_and_filter_settings() -> None:
    legacy = _profile()
    legacy["settings"].update(
        {
            "search": "from-preset",
            "active_filter_preset": "Sideloaded",
            "active_smart_query": {"name": "Legacy target"},
            "sdk_filter": {"target_sdk_max": 28},
            "technical_columns": ["target_sdk"],
            "details_panel_position": "right",
            "show_app_icons": True,
            "date_format": "YYYY-MM-DD",
        }
    )
    custom_widths = {"package_name": 319}
    country, source, merged = audit_profiles.apply_profile_to_settings(
        legacy,
        {
            "show_app_icons": False,
            "date_format": "DD.MM.YYYY",
            "details_panel_position": "hidden",
            "view_preset": "Custom",
            "custom_view_exists": True,
            "custom_view_columns": ["criticality", "package_name"],
            "custom_view_order": ["package_name", "criticality"],
            "custom_view_widths": custom_widths,
            "search": "current-search",
            "active_filter_preset": "Old apps",
            "active_smart_query": {"name": "Current query"},
            "store_language": "de",
        },
    )

    assert country == "ch"
    assert source == "device"
    assert merged["store_language"] == "it"
    assert merged["view_preset"] == "Custom"
    assert merged["custom_view_widths"] is custom_widths
    assert merged["show_app_icons"] is False
    assert merged["date_format"] == "DD.MM.YYYY"
    assert merged["details_panel_position"] == "hidden"
    assert merged["search"] == "current-search"
    assert merged["active_filter_preset"] == "Old apps"
    assert merged["active_smart_query"] == {"name": "Current query"}


def test_loading_legacy_profile_does_not_rewrite_its_stored_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = _profile()
    legacy["settings"]["show_app_icons"] = True
    stored: dict[str, Any] = {"audit_profiles": {"Existing name": legacy}}
    monkeypatch.setattr(state, "load_settings", lambda: stored)

    loaded = audit_profiles.load_profiles()

    assert list(loaded) == ["Existing name"]
    assert loaded["Existing name"]["view_preset"] == "Technical"
    assert stored["audit_profiles"]["Existing name"] is legacy
    assert legacy["settings"]["show_app_icons"] is True


def test_malformed_profile_fails_without_touching_current_settings() -> None:
    current = {
        "store_language": "de",
        "view_preset": "Custom",
        "show_app_icons": False,
    }

    with pytest.raises(ValueError, match="Invalid audit preset"):
        audit_profiles.apply_profile_to_settings(
            {"schema_version": 1, "settings": "malformed"},  # type: ignore[arg-type]
            current,
        )

    assert current == {
        "store_language": "de",
        "view_preset": "Custom",
        "show_app_icons": False,
    }


def test_unknown_profile_schema_is_ignored_safely() -> None:
    future = _profile()
    future["schema_version"] = 999

    assert audit_profiles.normalise_profile(future) is None


def test_partial_profile_applies_safely_without_touching_unrelated_state() -> None:
    country, source, merged = audit_profiles.apply_profile_to_settings(
        {
            "schema_version": 1,
            "store_country": "it",
            "settings": {"store_workers": 8},
        },
        {
            "view_preset": "Custom",
            "details_panel_position": "below",
            "show_app_icons": False,
            "date_format": "DD.MM.YYYY",
        },
    )

    assert country == "it"
    assert source == "any"
    assert merged["store_workers"] == 8
    assert merged["view_preset"] == "Custom"
    assert merged["details_panel_position"] == "below"
    assert merged["show_app_icons"] is False
    assert merged["date_format"] == "DD.MM.YYYY"


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
        self.search_edit = _Text("current-search")
        self._status_filters = {"orange"}
        self._active_filter_preset = "Old apps"
        self._active_smart_query = object()
        self.view_preset_actions = [_Action("Basic"), _Action("Custom")]
        self.view_preset_actions[1].checked = True
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
    saved_state: dict[str, Any] = {
        "show_app_icons": False,
        "date_format": "DD.MM.YYYY",
        "details_panel_position": "hidden",
        "view_preset": "Custom",
        "custom_view_exists": True,
        "custom_view_columns": ["criticality", "package_name"],
        "custom_view_order": ["package_name", "criticality"],
        "custom_view_widths": {"package_name": 319},
        "store_language": "de",
    }
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
    assert window.view_calls == []
    assert [action.checked for action in window.view_preset_actions] == [False, True]
    assert fallback_calls == [("de, fr, us", "ch")]
    assert saved_state["show_app_icons"] is False
    assert saved_state["date_format"] == "DD.MM.YYYY"
    assert saved_state["details_panel_position"] == "hidden"
    assert saved_state["view_preset"] == "Custom"
    assert saved_state["custom_view_columns"] == ["criticality", "package_name"]
    assert saved_state["custom_view_order"] == ["package_name", "criticality"]
    assert saved_state["custom_view_widths"] == {"package_name": 319}
    assert window.search_edit.text() == "current-search"
    assert window._status_filters == {"orange"}
    assert window._active_filter_preset == "Old apps"
    assert window._active_smart_query is not None
    assert "preset expects source: Android phone" in window.status_label.text()
    assert window.status_label.text().startswith("Audit preset applied")
