from __future__ import annotations

import json
import uuid
from dataclasses import replace

import pytest
from test_connected_device_profile import build_complete_profile

from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.services import device_specific_integration as integration
from playstore_app_audit.services import personal_device_library as library
from playstore_app_audit.services import state


def test_explicit_multiple_saves_round_trip_and_random_ids(tmp_path) -> None:
    path = tmp_path / "personal_device_profiles.json"
    capture = build_complete_profile()
    assert library.list_profiles(path=path) == ()
    first = library.save_capture(capture, "My phone", path=path)
    second = library.save_capture(capture, "My phone", path=path)
    assert first.profile_id != second.profile_id
    assert first.profile_id != capture.profile_id
    assert uuid.UUID(first.profile_id.removeprefix("personal:")).version == 4
    assert [item.profile_id for item in library.list_profiles(path=path)] == [first.profile_id, second.profile_id]
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["schema_version"] == 1
    assert set(data) == {"schema_version", "profiles"}
    assert set(data["profiles"][0]) == library._RECORD_KEYS
    assert "profile_hash" not in raw
    assert "ownership_token" not in raw
    assert "connected_device_" not in raw
    assert library.get_profile(first.profile_id, path=path).profile_hash == first.profile_hash
    assert first.profile_hash != second.profile_hash
    assert first.profile_hash != capture.profile_hash


def test_rename_delete_and_refresh_preserve_identity_and_content_semantics(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    capture = build_complete_profile()
    first = library.save_capture(capture, "Original", path=path)
    second = library.save_capture(capture, "Other", path=path)
    renamed = library.rename_profile(first.profile_id, "Renamed", path=path)
    assert renamed.profile_id == first.profile_id
    assert renamed.profile_hash == first.profile_hash
    assert renamed.updated_at == first.updated_at

    changed_payload = dict(capture.profile)
    changed_payload["Vending.version"] = "999999"
    changed = replace(capture, profile=changed_payload)
    refreshed = library.refresh_profile(first.profile_id, changed, path=path)
    assert refreshed.profile_id == first.profile_id
    assert refreshed.captured_at == first.captured_at
    assert refreshed.profile_hash != first.profile_hash
    assert refreshed.profile["Vending.version"] == "999999"
    assert library.get_profile(first.profile_id, path=path).display_name == "Renamed"

    library.delete_profile(first.profile_id, path=path)
    assert [profile.profile_id for profile in library.list_profiles(path=path)] == [second.profile_id]


def test_refresh_rejects_obvious_mismatch_without_writing(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    capture = build_complete_profile()
    saved = library.save_capture(capture, "Phone", path=path)
    changed = replace(capture, profile={**capture.profile, "Build.MODEL": "Different Phone"})
    before = path.read_bytes()
    assert not library.refresh_compatibility(saved, changed)
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.refresh_profile(saved.profile_id, changed, path=path)
    assert path.read_bytes() == before


def test_malformed_and_future_schema_preserved(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    capture = build_complete_profile()
    saved = library.save_capture(capture, "Phone", path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["profiles"].append({"id": "serial-secret", "profile": {"android_id": "secret"}})
    path.write_text(json.dumps(data), encoding="utf-8")
    assert [item.profile_id for item in library.list_profiles(path=path)] == [saved.profile_id]
    before = path.read_bytes()
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.rename_profile(saved.profile_id, "New", path=path)
    assert path.read_bytes() == before

    data["schema_version"] = 2
    path.write_text(json.dumps(data), encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.list_profiles(path=path)
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.save_capture(capture, "Another", path=path)
    assert path.read_bytes() == before

    path.write_text(json.dumps({"profiles": []}), encoding="utf-8")
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.list_profiles(path=path)


def test_forbidden_record_keys_cannot_enter_library(tmp_path) -> None:
    path = tmp_path / "profiles.json"
    capture = build_complete_profile()
    saved = library.save_capture(capture, "Phone", path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["profiles"][0]["raw_serial"] = "secret"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert library.list_profiles(path=path) == ()
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.delete_profile(saved.profile_id, path=path)

    path.unlink()
    secret_capture = replace(capture, profile={**capture.profile, "AndroidID": "secret"})
    with pytest.raises(library.PersonalDeviceLibraryError):
        library.save_capture(secret_capture, "Phone", path=path)
    assert not path.exists()


def test_saved_selection_uses_existing_resolver_without_connected_phone(tmp_path, monkeypatch) -> None:
    path = tmp_path / "profiles.json"
    saved = library.save_capture(build_complete_profile(), "Offline phone", path=path)
    monkeypatch.setattr(library, "library_path", lambda: path)
    rows = [{
        "package_name": "com.example.app", "play_version": "Varies with device",
        "installed_version_code": "100", "version_comparison": "Device-specific",
    }]
    seen: list[object] = []

    def resolver(**kwargs: object) -> ResolverResult:
        profile = kwargs["profile"]
        seen.append(profile)
        return ResolverResult(
            package_name="com.example.app", profile_id=saved.profile_id,
            profile_hash=saved.profile_hash, provider=ResolverProvider.ANONYMOUS_DISPENSER,
            status=ResolverStatus.RESOLVED, requested_country="CH", requested_language="en",
            version_name="5.0", version_code=101,
        )

    summary = integration.enrich_rows_with_device_specific_resolution(
        rows,
        settings={"device_specific_provider": "custom_dispenser",
                  "device_specific_resolver_endpoint": "https://resolver.example/api/auth",
                  "device_specific_resolver_profile": saved.profile_id},
        country="CH", language="en", resolver=resolver, use_cache=False,
        connected_profile=None,
    )
    assert summary.resolved == 1
    assert seen == [saved]
    assert rows[0]["play_version"] == "Varies with device"
    assert rows[0][integration.PROFILE_ID_FIELD] == "personal_device"
    assert "Offline phone" in rows[0][integration.PROFILE_FIELD]
    assert rows[0]["version_comparison"] == "Outdated"


def test_settings_reset_and_cache_cleanup_retain_separate_library(tmp_path, monkeypatch) -> None:
    library_file = tmp_path / "personal_device_profiles.json"
    saved = library.save_capture(build_complete_profile(), "Phone", path=library_file)
    monkeypatch.setattr(state, "settings_path", lambda: tmp_path / "settings.json")
    monkeypatch.setattr(state, "cache_path", lambda: tmp_path / "audit_cache.json")
    state.reset_settings()
    state.clear_cache()
    assert library.get_profile(saved.profile_id, path=library_file) == saved
    assert state.load_settings()["device_specific_resolver_profile"] == ""


def test_transient_connected_setting_does_not_create_library(tmp_path, monkeypatch) -> None:
    library_file = tmp_path / "personal_device_profiles.json"
    monkeypatch.setattr(library, "library_path", lambda: library_file)
    monkeypatch.setattr(state, "settings_path", lambda: tmp_path / "settings.json")
    state.save_settings({"device_specific_resolver_profile": "connected_device"})
    assert library.list_profiles() == ()
    assert not library_file.exists()
