from __future__ import annotations

import json
import os

import pytest
from PySide6.QtWidgets import QApplication, QDialog

import playstore_app_audit.services.alternative_distribution as alternative
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.details_panel as details_ui
from playstore_app_audit.domain.alternative_distribution import (
    AlternativeDistributionResult,
    AlternativeDistributionState,
)
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def _result(
    provider_id: str,
    provider_name: str,
    state: AlternativeDistributionState,
    *,
    listing_url: str = "",
) -> dict[str, object]:
    return AlternativeDistributionResult(
        provider_id=provider_id,
        provider_name=provider_name,
        queried_package_id="org.example.app",
        state=state,
        listing_url=listing_url,
        version_name="4.2" if state is AlternativeDistributionState.AVAILABLE else "",
        version_code=42 if state is AlternativeDistributionState.AVAILABLE else "",
        checked_at="2026-08-29T10:00:00Z",
        provenance="cache" if provider_id == "aptoide" else "live",
        reason="Synthetic exact-package evidence.",
    ).to_mapping()


@pytest.mark.parametrize(
    "state",
    [
        AlternativeDistributionState.AVAILABLE,
        AlternativeDistributionState.NOT_FOUND,
        AlternativeDistributionState.INCONCLUSIVE,
    ],
)
def test_details_panel_renders_each_fdroid_state(
    app: QApplication, state: AlternativeDistributionState
) -> None:
    panel = details_ui.AppDetailsPanel()
    row = {
        "package_name": "org.example.app",
        alternative.ROW_FIELD: [
            _result(
                "fdroid_main",
                "F-Droid main repository",
                state,
                listing_url="https://f-droid.org/packages/org.example.app/"
                if state is AlternativeDistributionState.AVAILABLE
                else "",
            )
        ],
    }

    panel.set_row(row)

    assert not panel.alternative_section.isHidden()
    assert f"Status: {alternative.STATE_LABELS[state]}" in panel.alternative_label.text()
    assert "exact package identifier" in panel.alternative_label.text()
    assert panel.alternative_buttons.isVisibleTo(panel) is (
        state is AlternativeDistributionState.AVAILABLE
    )
    panel.deleteLater()
    app.processEvents()


@pytest.mark.parametrize(
    "state",
    [
        AlternativeDistributionState.AVAILABLE,
        AlternativeDistributionState.NOT_FOUND,
        AlternativeDistributionState.INCONCLUSIVE,
    ],
)
def test_details_panel_renders_each_aptoide_state(
    app: QApplication, state: AlternativeDistributionState
) -> None:
    panel = details_ui.AppDetailsPanel()
    panel.set_row(
        {
            "package_name": "org.example.app",
            alternative.ROW_FIELD: [_result("aptoide", "Aptoide", state)],
        }
    )

    assert "Aptoide" in panel.alternative_label.text()
    assert f"Status: {alternative.STATE_LABELS[state]}" in panel.alternative_label.text()
    assert not panel.alternative_buttons.isVisibleTo(panel)
    panel.deleteLater()
    app.processEvents()


def test_two_provider_order_is_deterministic_and_disabled_provider_is_not_noise(
    app: QApplication,
) -> None:
    panel = details_ui.AppDetailsPanel()
    row = {
        "package_name": "org.example.app",
        alternative.ROW_FIELD: [
            _result("aptoide", "Aptoide", AlternativeDistributionState.AVAILABLE),
            _result("fdroid_main", "F-Droid main repository", AlternativeDistributionState.NOT_FOUND),
        ],
    }

    panel.set_row(row)

    text = panel.alternative_label.text()
    assert text.index("F-Droid") < text.index("Aptoide")
    panel.set_row({"package_name": "org.example.app"})
    assert panel.alternative_section.isHidden()
    panel.deleteLater()
    app.processEvents()


def test_details_panel_and_app_details_use_same_presentation_helper(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    original = alternative.provider_evidence_text

    def tracked(row):
        calls.append(str(row.get("package_name") or ""))
        return original(row)

    monkeypatch.setattr(alternative, "provider_evidence_text", tracked)
    monkeypatch.setattr(QDialog, "exec", lambda _dialog: QDialog.DialogCode.Rejected)
    row = {
        "package_name": "org.example.app",
        alternative.ROW_FIELD: [
            _result("fdroid_main", "F-Droid main repository", AlternativeDistributionState.AVAILABLE)
        ],
    }
    panel = details_ui.AppDetailsPanel()
    panel.set_row(row)
    window = MainWindow()
    try:
        window._show_details(row)
        assert calls == ["org.example.app", "org.example.app"]
    finally:
        panel.deleteLater()
        window.close()
        app.processEvents()


def test_html_section_is_conditional_and_uses_neutral_links(tmp_path) -> None:
    without = tmp_path / "without.html"
    with_evidence = tmp_path / "with.html"
    base = {"package_name": "org.example.app", "criticality_key": "red"}
    device_insights.write_html_report(without, [base])
    device_insights.write_html_report(
        with_evidence,
        [
            {
                **base,
                alternative.ROW_FIELD: [
                    _result(
                        "fdroid_main",
                        "F-Droid main repository",
                        AlternativeDistributionState.AVAILABLE,
                        listing_url="https://f-droid.org/packages/org.example.app/",
                    ),
                    _result("aptoide", "Aptoide", AlternativeDistributionState.NOT_FOUND),
                ],
            }
        ],
    )

    assert "Alternative distribution checks" not in without.read_text(encoding="utf-8")
    rendered = with_evidence.read_text(encoding="utf-8")
    assert "Alternative distribution checks" in rendered
    assert "F-Droid main repository" in rendered and "Aptoide" in rendered
    assert ">Open provider listing</a>" in rendered
    assert ">Download<" not in rendered and ">Install<" not in rendered


def test_json_v2_adds_ordered_provider_collection_without_secret_material() -> None:
    synthetic_key = "synthetic-secret-key"
    row = {
        "package_name": "org.example.app",
        "play_status": "not_found_in_checked_countries",
        "installer_source": "Google Play",
        "health_score": 40,
        alternative.ROW_FIELD: [
            _result("aptoide", "Aptoide", AlternativeDistributionState.AVAILABLE),
            _result("fdroid_main", "F-Droid main repository", AlternativeDistributionState.NOT_FOUND),
        ],
    }

    document = result_json.build_results_document([row])
    serialized = json.dumps(document)
    exported = document["results"][0]

    assert document["schema_version"] == 2
    assert [
        item["provider_id"]
        for item in exported["alternative_distribution"]["providers"]
    ] == ["fdroid_main", "aptoide"]
    assert alternative.ROW_FIELD not in exported
    assert synthetic_key not in serialized
    assert "api_key_protected" not in serialized
    assert exported["play_status"] == row["play_status"]
    assert exported["installer_source"] == row["installer_source"]
    assert exported["health_score"] == row["health_score"]


def test_csv_and_friendly_notes_remain_provider_independent() -> None:
    row = {
        "package_name": "org.example.app",
        "play_status": "not_found_in_checked_countries",
        alternative.ROW_FIELD: [
            _result("fdroid_main", "F-Droid main repository", AlternativeDistributionState.AVAILABLE)
        ],
    }

    assert alternative.ROW_FIELD not in base_ui.EXPORT_FIELDS
    notes_with_provider = device_insights.presentation.friendly_notes(row)
    row.pop(alternative.ROW_FIELD)
    assert device_insights.presentation.friendly_notes(row) == notes_with_provider


def test_diagnostic_bundle_excludes_protected_credential(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import zipfile

    protected = "v1:synthetic-protected-envelope"
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    monkeypatch.setattr(
        device_insights.state,
        "load_settings",
        lambda: {
            "alternative_distribution": {
                "fdroid_main": {"enabled": True},
                "aptoide": {
                    "enabled": True,
                    "store_name": "authorized-store",
                    "api_key_protected": protected,
                },
            }
        },
    )
    target = tmp_path / "diagnostics.zip"

    device_insights.create_diagnostic_bundle(target, [])

    with zipfile.ZipFile(target) as archive:
        settings_text = archive.read("settings_sanitized.json").decode("utf-8")
    assert protected not in settings_text
    assert "api_key_protected" not in settings_text


def test_c2_uses_existing_busy_progress_and_status_bar(
    app: QApplication,
) -> None:
    window = MainWindow()
    try:
        window._audit_session = 77
        window._set_audit_state(window._audit_state.RUNNING)
        geometry = (window.progress.minimumWidth(), window.progress.maximumWidth())

        window._on_alternative_phase(77, 3)

        assert (window.progress.minimum(), window.progress.maximum()) == (0, 0)
        assert (window.progress.minimumWidth(), window.progress.maximumWidth()) == geometry
        assert "alternative distribution for 3 package" in window.status_label.text()
        assert window.status_label.parentWidget() is window.status_bar
    finally:
        window._set_audit_state(window._audit_state.IDLE)
        window.close()
        app.processEvents()
