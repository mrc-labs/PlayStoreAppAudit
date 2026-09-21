from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_specific_integration as integration
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.presentation as presentation
import playstore_app_audit.ui.details_panel as details_panel
import playstore_app_audit.ui.preferences_window as preferences_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.domain.device_specific_resolver import (
    ResolverProvider,
    ResolverResult,
    ResolverStatus,
)
from playstore_app_audit.domain.local_artifacts import LocalArtifact, LocalArtifactFormat
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.connected_device_profile import ConnectedDeviceProfile
from playstore_app_audit.services.device_specific_profiles import load_reference_profile
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService

ENDPOINT = "https://resolver.example/api/auth"
COUNTRY = "ch"
LANGUAGE = "en"
PACKAGE = "com.example.app"


class FakeStore:
    def __init__(self, play_version: str) -> None:
        self.play_version = play_version

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback=None,
        pause_event=None,
        cancel_event=None,
        row_completed_callback=None,
    ) -> list[dict[str, Any]]:
        del progress_callback, pause_event, cancel_event
        rows = [
            {
                "package_name": app["package_name"],
                "play_status": "available",
                "play_version": self.play_version,
                "store_country": config.country,
                "store_language": config.language,
            }
            for app in apps
        ]
        if row_completed_callback is not None:
            for index, row in enumerate(rows):
                row_completed_callback(index, dict(row))
        return rows


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _artifact(
    *,
    version_name: str = "1.0",
    version_code: int | str = 100,
    version_code_major: int | str | None = None,
) -> LocalArtifact:
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256="a" * 64,
        package_id=PACKAGE,
        application_label="Example App",
        application_label_reference=None,
        version_name=version_name,
        version_name_reference=None,
        version_code=version_code,
        version_code_major=version_code_major,
        min_sdk=23,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=(),
        features=(),
        icon_reference=None,
        file_name="example.apk",
        canonical_path=Path("C:/fixtures/example.apk"),
        file_size=1234,
        modified_at=datetime(2026, 9, 19, tzinfo=UTC),
    )


def _settings(
    provider: str = "custom_dispenser",
    *,
    profile_id: str = integration.DEFAULT_PROFILE_ID,
) -> dict[str, object]:
    return {
        "cache_enabled": False,
        integration.SETTING_PROVIDER: provider,
        integration.SETTING_ENDPOINT: ENDPOINT,
        integration.SETTING_PROFILE_ID: profile_id,
    }


def _service(play_version: str) -> LocalArtifactStoreService:
    return LocalArtifactStoreService(
        store_service=FakeStore(play_version),
        alternative_runner=lambda _rows, _settings, **_kwargs: [],
    )


def _disable_resolver_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        integration,
        "load_cached_result",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        integration,
        "store_resolved_result",
        lambda *_args, **_kwargs: True,
    )


def _resolved_from_call(
    call: dict[str, object],
    *,
    version_code: int,
    version_name: str = "2.0",
) -> ResolverResult:
    profile = call["profile"]
    assert hasattr(profile, "profile_id")
    return ResolverResult(
        package_name=PACKAGE,
        profile_id=profile.profile_id,
        profile_hash=profile.profile_hash,
        provider=call["provider"],
        status=ResolverStatus.RESOLVED,
        requested_country=COUNTRY,
        requested_language=LANGUAGE,
        version_name=version_name,
        version_code=version_code,
    )


def _result_row(result) -> dict[str, Any]:
    rows = local_apk_audit.association_result_rows(result.associations)
    assert len(rows) == 1
    return rows[0]


def _complete_connected_profile(*, complete: bool = True) -> ConnectedDeviceProfile:
    reference = load_reference_profile(integration.DEFAULT_PROFILE_ID)
    return ConnectedDeviceProfile(
        profile_id="connected_device_test",
        display_name="Validated Test Phone",
        android_release="16",
        api_level=36,
        profile_hash="b" * 64,
        profile=dict(reference.profile),
        complete=complete,
        missing_fields=() if complete else ("Build.FINGERPRINT",),
    )


def test_custom_dispenser_reference_profile_preserves_raw_and_adds_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    calls: list[dict[str, object]] = []

    def resolver(**kwargs: object) -> ResolverResult:
        calls.append(dict(kwargs))
        return _resolved_from_call(dict(kwargs), version_code=101)

    monkeypatch.setattr(integration, "resolve_if_device_specific", resolver)
    result = _service("Varies with device").collect(
        [_artifact(version_code=100)],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
    )
    row = _result_row(result)

    assert len(calls) == 1
    assert calls[0]["provider"] is ResolverProvider.ANONYMOUS_DISPENSER
    assert calls[0]["profile_id"] == integration.DEFAULT_PROFILE_ID
    assert row["play_version"] == "Varies with device"
    assert row[integration.RESOLVED_VERSION_FIELD] == "2.0"
    assert row[integration.RESOLVED_VERSION_CODE_FIELD] == 101
    assert row[integration.PROFILE_ID_FIELD] == integration.DEFAULT_PROFILE_ID
    assert row[integration.STATUS_FIELD] == "resolved"
    assert row["local_apk_version_comparison"] == "Outdated"


def test_personal_google_session_reuses_shared_auth_without_exposing_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    oneplus_profile = "android10_api29_oneplus8pro"
    monkeypatch.setattr(
        integration.device_specific_personal_session,
        "personal_session_status",
        lambda: type(
            "Status",
            (),
            {"signed_in": True, "context_hash": "context-secret"},
        )(),
    )
    bundle: dict[str, object] = {
        "authToken": "token-secret",
        "gsfId": "gsf-secret",
        "cookie": "cookie-secret",
        "account": "account-secret",
    }
    monkeypatch.setattr(
        integration.device_specific_personal_auth,
        "create_personal_auth_bundle",
        lambda **_kwargs: bundle,
    )
    calls: list[dict[str, object]] = []

    def resolver(**kwargs: object) -> ResolverResult:
        calls.append(dict(kwargs))
        return _resolved_from_call(dict(kwargs), version_code=100)

    monkeypatch.setattr(integration, "resolve_if_device_specific", resolver)
    result = _service("Varies by device").collect(
        [_artifact()],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings("personal_google_session", profile_id=oneplus_profile),
    )
    row = _result_row(result)

    assert len(calls) == 1
    assert calls[0]["provider"] is ResolverProvider.PERSONAL_GOOGLE_SESSION
    assert calls[0]["profile_id"] == oneplus_profile
    assert calls[0]["auth_bundle"] is bundle
    assert bundle == {}
    surfaced = repr(result) + repr(presentation.rows_for_output([row]))
    for secret in (
        "context-secret",
        "token-secret",
        "gsf-secret",
        "cookie-secret",
        "account-secret",
    ):
        assert secret not in surfaced
    assert row[integration.STATUS_FIELD] == "resolved"
    assert row["local_apk_version_comparison"] == "Match"


def test_disabled_provider_does_no_resolver_auth_or_connected_profile_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for target, name in (
        (integration, "resolve_if_device_specific"),
        (integration.device_specific_personal_session, "personal_session_status"),
        (integration.device_specific_personal_auth, "create_personal_auth_bundle"),
    ):
        monkeypatch.setattr(
            target,
            name,
            lambda *_args, **_kwargs: pytest.fail(
                "Disabled Device Specific performed provider work"
            ),
        )

    result = _service("Varies with device").collect(
        [_artifact()],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(
            "disabled",
            profile_id=integration.CONNECTED_DEVICE_PROFILE_ID,
        ),
        connected_profile=_complete_connected_profile(),
    )
    row = _result_row(result)

    assert row["play_version"] == "Varies with device"
    assert row[integration.STATUS_FIELD] == ""
    assert row["local_apk_version_comparison"] == "Device-specific"


@pytest.mark.parametrize("provider", ["personal_google_session", "custom_dispenser"])
def test_ordinary_store_row_does_no_resolver_or_personal_auth_work(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    for target, name in (
        (integration, "resolve_if_device_specific"),
        (integration.device_specific_personal_session, "personal_session_status"),
        (integration.device_specific_personal_auth, "create_personal_auth_bundle"),
    ):
        monkeypatch.setattr(
            target,
            name,
            lambda *_args, **_kwargs: pytest.fail(
                "Ordinary Store evidence performed Device Specific work"
            ),
        )

    row = _result_row(
        _service("2.0").collect(
            [_artifact(version_name="1.0")],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(provider),
        )
    )

    assert row["play_version"] == "2.0"
    assert row[integration.RESOLVED_VERSION_FIELD] == ""
    assert row[integration.STATUS_FIELD] == ""
    assert row["local_apk_version_comparison"] == "Outdated"


def test_complete_process_local_connected_profile_reaches_shared_coordinator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    connected = _complete_connected_profile()
    calls: list[dict[str, object]] = []

    def resolver(**kwargs: object) -> ResolverResult:
        calls.append(dict(kwargs))
        return _resolved_from_call(dict(kwargs), version_code=101)

    monkeypatch.setattr(integration, "resolve_if_device_specific", resolver)
    row = _result_row(
        _service("Varies").collect(
            [_artifact()],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(profile_id=integration.CONNECTED_DEVICE_PROFILE_ID),
            connected_profile=connected,
        )
    )

    assert calls[0]["profile"] is connected
    assert calls[0]["profile_id"] == connected.profile_id
    assert row[integration.PROFILE_ID_FIELD] == connected.profile_id
    assert "Validated Test Phone" in row[integration.PROFILE_FIELD]


@pytest.mark.parametrize(
    "connected_profile",
    [None, _complete_connected_profile(complete=False)],
)
def test_unusable_connected_profile_fails_conservatively_without_fabrication(
    monkeypatch: pytest.MonkeyPatch,
    connected_profile: ConnectedDeviceProfile | None,
) -> None:
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **_kwargs: pytest.fail("Unavailable Connected Device profile resolved"),
    )
    row = _result_row(
        _service("Varies with device").collect(
            [_artifact()],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(profile_id=integration.CONNECTED_DEVICE_PROFILE_ID),
            connected_profile=connected_profile,
        )
    )

    assert row["play_version"] == "Varies with device"
    assert row[integration.PROFILE_FIELD] == ""
    assert row[integration.PROFILE_ID_FIELD] == ""
    assert row[integration.STATUS_FIELD] == ""
    assert row["local_apk_version_comparison"] == "Device-specific"


@pytest.mark.parametrize(
    ("local_code", "resolved_code", "expected"),
    [(99, 100, "Outdated"), (100, 100, "Match"), (101, 100, "Newer")],
)
def test_positive_resolved_version_code_drives_canonical_relationship(
    monkeypatch: pytest.MonkeyPatch,
    local_code: int,
    resolved_code: int,
    expected: str,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **kwargs: _resolved_from_call(
            dict(kwargs),
            version_code=resolved_code,
        ),
    )
    row = _result_row(
        _service("Varies with device").collect(
            [_artifact(version_code=local_code)],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(),
        )
    )

    assert row["local_apk_version_comparison"] == expected
    assert local_apk_audit.local_apk_relationship_display_value(row) == f"{expected} (Dev. Sp.)"


def test_long_version_code_precedes_manifest_version_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **kwargs: _resolved_from_call(dict(kwargs), version_code=100),
    )
    artifact = _artifact(version_code=5, version_code_major=1)
    assert artifact.long_version_code == (1 << 32) | 5

    row = _result_row(
        _service("Varies").collect(
            [artifact],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(),
        )
    )

    assert row["local_apk_version_code"] == 5
    assert row["local_apk_long_version_code"] == (1 << 32) | 5
    assert row["local_apk_version_comparison"] == "Newer"


def test_string_version_code_falls_back_when_long_version_code_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **kwargs: _resolved_from_call(dict(kwargs), version_code=100),
    )

    row = _result_row(
        _service("Varies").collect(
            [_artifact(version_code="99")],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(),
        )
    )

    assert row["local_apk_long_version_code"] is None
    assert row["local_apk_version_comparison"] == "Outdated"


def test_resolver_failure_preserves_successful_public_and_local_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)

    def failing_resolver(**_kwargs: object) -> ResolverResult:
        raise RuntimeError("synthetic resolver failure")

    monkeypatch.setattr(integration, "resolve_if_device_specific", failing_resolver)
    row = _result_row(
        _service("Varies by device").collect(
            [_artifact()],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings(),
        )
    )

    assert row["play_status"] == "available"
    assert row["play_version"] == "Varies by device"
    assert row["local_apk_version_name"] == "1.0"
    assert row[integration.RESOLVED_VERSION_FIELD] == ""
    assert row[integration.STATUS_FIELD] == "inconclusive"
    assert row["local_apk_version_comparison"] == "Device-specific"


def test_personal_auth_failure_preserves_successful_public_and_local_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration.device_specific_personal_session,
        "personal_session_status",
        lambda: type(
            "Status",
            (),
            {"signed_in": True, "context_hash": "context"},
        )(),
    )

    def failing_auth(**_kwargs: object) -> dict[str, object]:
        raise integration.device_specific_personal_auth.PersonalGoogleAuthError(
            "auth_failed"
        )

    monkeypatch.setattr(
        integration.device_specific_personal_auth,
        "create_personal_auth_bundle",
        failing_auth,
    )
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **_kwargs: pytest.fail("Resolver ran after auth failure"),
    )
    row = _result_row(
        _service("Varies").collect(
            [_artifact()],
            AuditConfig(country=COUNTRY, language=LANGUAGE),
            _settings("personal_google_session"),
        )
    )

    assert row["play_version"] == "Varies"
    assert row[integration.STATUS_FIELD] == "auth_failed"
    assert row["local_apk_version_comparison"] == "Device-specific"


def test_progressive_callback_receives_raw_then_resolved_device_specific_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _disable_resolver_cache(monkeypatch)
    monkeypatch.setattr(
        integration,
        "resolve_if_device_specific",
        lambda **kwargs: _resolved_from_call(dict(kwargs), version_code=101),
    )
    callback_rows: list[dict[str, Any]] = []

    _service("Varies with device").collect(
        [_artifact()],
        AuditConfig(country=COUNTRY, language=LANGUAGE),
        _settings(),
        row_completed_callback=lambda _package, row: callback_rows.append(dict(row)),
    )

    assert len(callback_rows) == 2
    assert callback_rows[0]["play_version"] == "Varies with device"
    assert callback_rows[0].get(integration.STATUS_FIELD, "") == ""
    assert callback_rows[1]["play_version"] == "Varies with device"
    assert callback_rows[1][integration.STATUS_FIELD] == "resolved"
    progressive = local_apk_audit.artifact_result_row(
        _artifact(),
        callback_rows[1],
        provisional=True,
    )
    assert progressive["local_apk_version_comparison"] == "Outdated"
    assert local_apk_audit.local_apk_relationship_display_value(progressive) == (
        "Outdated (Dev. Sp.)"
    )


def test_ds_suffix_is_presentation_only_for_table_details_filter_and_score(
    app: QApplication,
) -> None:
    del app
    row = local_apk_audit.artifact_result_row(
        _artifact(version_code=99),
        {
            "package_name": PACKAGE,
            "play_status": "available",
            "play_version": "Varies with device",
            integration.RESOLVED_VERSION_FIELD: "2.0",
            integration.RESOLVED_VERSION_CODE_FIELD: 100,
            integration.PROFILE_FIELD: "Samsung Galaxy S20+",
            integration.PROFILE_ID_FIELD: integration.DEFAULT_PROFILE_ID,
            integration.STATUS_FIELD: "resolved",
        },
    )
    assert row["local_apk_version_comparison"] == "Outdated"

    ordinary_row = dict(row)
    ordinary_row[integration.RESOLVED_VERSION_FIELD] = ""
    ordinary_row[integration.RESOLVED_VERSION_CODE_FIELD] = ""
    ordinary_row[integration.STATUS_FIELD] = ""
    model = table_ui.AuditTableModel()
    model.set_rows([row, ordinary_row])
    column = model.columns.index("local_apk_version_comparison")
    index = model.index(0, column)
    ordinary_index = model.index(1, column)
    assert model.data(index, Qt.ItemDataRole.DisplayRole) == "Outdated (Dev. Sp.)"
    assert model.data(ordinary_index, Qt.ItemDataRole.DisplayRole) == "Outdated"
    assert model.data(index, Qt.ItemDataRole.UserRole)[
        "local_apk_version_comparison"
    ] == "Outdated"
    assert model.data(index, Qt.ItemDataRole.BackgroundRole) == model.data(
        ordinary_index,
        Qt.ItemDataRole.BackgroundRole,
    )
    assert model.data(index, Qt.ItemDataRole.ForegroundRole) == model.data(
        ordinary_index,
        Qt.ItemDataRole.ForegroundRole,
    )
    assert "Local APK vs Store: Outdated (Dev. Sp.)" in details_panel.local_apk_details_lines(
        row
    )

    proxy = preferences_ui.AuditFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_relationship_filters({"Outdated"})
    assert proxy.rowCount() == 2
    proxy.set_relationship_filters({"Outdated (Dev. Sp.)"})
    assert proxy.rowCount() == 0

    breakdown = device_insights.calculate_health_score_breakdown(row)
    assert breakdown.version_comparison_penalty == -10


def test_ds_suffix_requires_matching_positive_version_code_evidence() -> None:
    row = {
        "local_apk_version_comparison": "Outdated",
        "local_apk_version_code": 99,
        "local_apk_long_version_code": 99,
        integration.RESOLVED_VERSION_CODE_FIELD: 0,
        integration.STATUS_FIELD: "resolved",
    }

    assert local_apk_audit.local_apk_relationship_display_value(row) == "Outdated"

    row[integration.RESOLVED_VERSION_CODE_FIELD] = 100
    row["local_apk_version_comparison"] = "Match"
    assert local_apk_audit.local_apk_relationship_display_value(row) == "Match"


@pytest.mark.parametrize(
    ("installed_code", "resolved_code", "relationship"),
    [(99, 100, "Outdated"), (100, 100, "Match"), (101, 100, "Newer")],
)
def test_phone_relationship_provenance_is_reproduced_from_strict_evidence(
    installed_code: int,
    resolved_code: int,
    relationship: str,
) -> None:
    row = {
        "play_version": "Varies with device",
        "installed_version_code": installed_code,
        "resolved_play_version_code": resolved_code,
        "device_specific_resolver_status": "resolved",
        "version_comparison": relationship,
    }

    assert presentation.relationship_display_value(row, "version_comparison") == (
        f"{relationship} (Dev. Sp.)"
    )
    assert row["version_comparison"] == relationship

    model = table_ui.AuditTableModel()
    model.set_rows([row])
    index = model.index(0, model.columns.index("version_comparison"))
    assert model.data(index, Qt.ItemDataRole.DisplayRole) == f"{relationship} (Dev. Sp.)"
    assert model.data(index, Qt.ItemDataRole.UserRole)["version_comparison"] == relationship


@pytest.mark.parametrize(
    "updates",
    [
        {"play_version": "2.0"},
        {"device_specific_resolver_status": "inconclusive"},
        {"resolved_play_version_code": 0},
        {"installed_version_code": ""},
        {"version_comparison": "Match"},
    ],
)
def test_phone_relationship_provenance_is_not_fabricated(
    updates: dict[str, object],
) -> None:
    row: dict[str, object] = {
        "play_version": "Varies with device",
        "installed_version_code": 99,
        "resolved_play_version_code": 100,
        "device_specific_resolver_status": "resolved",
        "version_comparison": "Outdated",
    }
    row.update(updates)

    assert presentation.relationship_display_value(row, "version_comparison") == str(
        row["version_comparison"]
    )


def test_phone_relationship_details_use_row_aware_provenance_and_canonical_style() -> None:
    row = {
        "play_version": "Varies with device",
        "installed_version_code": 99,
        "resolved_play_version_code": 100,
        "device_specific_resolver_status": "resolved",
        "version_comparison": "Outdated",
    }

    rendered = details_panel._joined_semantic_fields(
        row,
        [("Installed vs Store", "version_comparison")],
    )

    assert "Outdated (Dev. Sp.)" in rendered
    assert presentation.semantic_value_presentation(
        "version_comparison", row["version_comparison"]
    ).status_key == "orange"
