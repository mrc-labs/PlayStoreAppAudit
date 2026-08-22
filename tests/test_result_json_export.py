from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.sdk_maintenance as sdk_maintenance
import playstore_app_audit.ui.json_export as json_export
from playstore_app_audit.ui.main_window import MainWindow


def test_versioned_json_preserves_structured_v17_row_data() -> None:
    row = {
        "package_name": "com.example.app",
        "play_status": "multi_country_check_inconclusive",
        "_store_evidence": [
            {
                "role": "primary",
                "country": "ch",
                "language": "it",
                "request_path": "google_play_scraper -> html",
                "retry_count": 2,
            }
        ],
        "_audit_changes": [{"type": "store_version_changed", "previous": "1", "current": "2"}],
        "tags": {"device", "store"},
    }
    generated = datetime(2026, 8, 22, 10, 30, tzinfo=UTC)

    document = result_json.build_results_document(
        [row],
        scope="visible",
        context={"source_mode": "device"},
        generated_at=generated,
        app_version="1.7-test",
    )

    assert document["format"] == "play-store-app-audit/results"
    assert document["schema_version"] == 1
    assert document["app_version"] == "1.7-test"
    assert document["generated_at_utc"] == "2026-08-22T10:30:00Z"
    assert document["scope"] == "visible"
    assert document["result_count"] == 1
    assert document["results"][0]["_store_evidence"][0]["retry_count"] == 2
    assert document["results"][0]["_audit_changes"][0]["type"] == "store_version_changed"
    assert document["results"][0]["tags"] == ["device", "store"]


def test_json_writer_is_utf8_pretty_and_newline_terminated(tmp_path: Path) -> None:
    target = tmp_path / "results.json"

    result_json.write_results_json(
        target,
        [{"package_name": "com.example.ümlaut"}],
        context={"label": "München"},
    )

    raw = target.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    assert raw.endswith("\n")
    assert "München" in raw
    assert parsed["results"][0]["package_name"] == "com.example.ümlaut"


class _TextWidget:
    def __init__(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _CheckWidget:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _WindowStub:
    source_mode = "device"
    country_edit = _TextWidget("ch")
    search_edit = _TextWidget("legacy")
    hide_system_check = _CheckWidget(True)
    _status_filters = {"orange", "yellow"}
    _active_filter_preset = "Alternative stores"
    _device_summary = {"model": "Example Phone", "serial_masked": "••••1234"}
    current_rows = [{"store_language": "it", "package_name": "com.example.app"}]


def test_export_context_contains_filters_but_not_source_file_paths() -> None:
    sdk_maintenance.set_active_sdk_filter(
        sdk_maintenance.SdkMaintenanceFilter(target_sdk_max=32, min_sdk_max=23)
    )
    try:
        context = json_export.build_window_export_context(_WindowStub())
    finally:
        sdk_maintenance.set_active_sdk_filter(None)

    assert context["source_mode"] == "device"
    assert context["store_country"] == "ch"
    assert context["store_language"] == "it"
    assert context["filters"]["preset"] == "Alternative stores"
    assert context["filters"]["sdk"] == {
        "target_sdk_max": 32,
        "min_sdk_max": 23,
        "compatibility": "",
    }
    assert "path" not in json.dumps(context).casefold()


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_final_file_export_menu_exposes_versioned_json_actions(app: QApplication) -> None:
    window = MainWindow()
    try:
        actions = [action.text() for action in window.file_export_results_menu.actions()]
        assert "Export all results as versioned JSON…" in actions
        assert "Export visible results as versioned JSON…" in actions
    finally:
        window.close()
        app.processEvents()
