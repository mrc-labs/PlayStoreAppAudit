from __future__ import annotations

import csv
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk as local_apk
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.main_window as main_ui
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseFailure,
    LocalArtifactParseResult,
    LocalArtifactWarning,
)
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService
from playstore_app_audit.ui import details_panel
from playstore_app_audit.ui.main_window import MainWindow


def _artifact(path: Path, sha: str, package: str = "com.example.same") -> LocalArtifact:
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256=sha,
        package_id=package,
        application_label=f"Local {path.stem}",
        application_label_reference=None,
        version_name="1.0",
        version_name_reference=None,
        version_code=10,
        version_code_major=None,
        min_sdk=23,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=("android.permission.INTERNET",),
        features=("android.hardware.camera",),
        icon_reference=None,
        file_name=path.name,
        canonical_path=path.resolve(),
        file_size=1234,
        modified_at=datetime(2026, 9, 10, 10, 0, tzinfo=UTC),
        warnings=(LocalArtifactWarning.APPLICATION_LABEL_UNRESOLVED,),
    )


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "exclude_system_source": True,
        "compare_previous": True,
        "inventory_history_enabled": True,
        "cache_enabled": False,
        "store_language": "en",
        "store_workers": 4,
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(compact_ui.QMessageBox, "critical", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(compact_ui.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


def test_partial_parse_keeps_valid_artifacts_in_selection_order(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = [tmp_path / "first.apk", tmp_path / "broken.apk", tmp_path / "second.apk"]
    first = _artifact(paths[0], "a" * 64)
    second = _artifact(paths[2], "b" * 64, "com.example.other")
    failure = LocalArtifactParseFailure(
        paths[1], LocalArtifactFailureKind.MALFORMED_ARCHIVE, "broken fixture"
    )
    outcomes = {
        paths[0]: LocalArtifactParseResult(artifact=first),
        paths[1]: LocalArtifactParseResult(failure=failure),
        paths[2]: LocalArtifactParseResult(artifact=second),
    }
    warnings: list[tuple[object, ...]] = []
    monkeypatch.setattr(local_apk, "parse_local_apk", lambda path: outcomes[path])
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "warning",
        lambda *args, **_kwargs: warnings.append(args),
    )
    jobs: list[tuple[int, tuple[Path, ...], threading.Event]] = []
    monkeypatch.setattr(
        window,
        "_launch_local_apk_parse_worker",
        lambda request, selected, cancel: jobs.append((request, selected, cancel)),
    )
    window.source_mode = "device"
    window._scan_session = object()
    window._device_store_locale = main_ui.store_locale.StoreLocale(
        language="de", country="de", locale="de-DE", source="test"
    )
    window._store_country_manual_override = False
    window.country_edit.setText("de")
    monkeypatch.setattr(main_ui.runtime, "detect_host_store_country", lambda: "us")

    window._begin_local_apk_parse(paths)
    window._local_apk_parse_worker(*jobs[0])

    assert window.source_mode == "local_apk"
    assert window._local_apk_artifacts == (first, second)
    assert "2 artifact(s)" in window.source_label.text()
    assert "1 rejected" in window.source_label.text()
    assert len(warnings) == 1
    assert window.run_button.isEnabled()
    assert not window.exclude_system_source_check.isEnabled()
    assert not window.hide_system_check.isEnabled()
    assert window._scan_session is None
    assert window._device_store_locale is None
    assert window.country_edit.text() == "us"
    assert window._visible_column_order()[:5] == [
        "criticality",
        "local_apk_file_name",
        "package_name",
        "local_apk_label",
        "local_apk_version_name",
    ]


def test_choose_apks_uses_multi_file_apk_picker(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    selected = [str(tmp_path / "one.apk"), str(tmp_path / "two.apk")]
    picker_calls: list[tuple[object, ...]] = []
    captured: list[list[Path]] = []
    monkeypatch.setattr(
        main_ui.QFileDialog,
        "getOpenFileNames",
        lambda *args: picker_calls.append(args) or (selected, "Android APK files (*.apk)"),
    )
    monkeypatch.setattr(window, "_begin_local_apk_parse", lambda paths: captured.append(paths))

    window.choose_apk_button.click()

    assert captured == [[Path(selected[0]), Path(selected[1])]]
    assert picker_calls[0][-1] == "Android APK files (*.apk)"
    assert window.choose_apk_button.text() == "Choose APK(s)"


def test_zero_valid_apks_does_not_establish_source(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "broken.apk"
    failure = LocalArtifactParseFailure(
        path, LocalArtifactFailureKind.MALFORMED_ARCHIVE, "broken fixture"
    )
    monkeypatch.setattr(
        local_apk,
        "parse_local_apk",
        lambda _path: LocalArtifactParseResult(failure=failure),
    )
    jobs: list[tuple[int, tuple[Path, ...], threading.Event]] = []
    monkeypatch.setattr(
        window,
        "_launch_local_apk_parse_worker",
        lambda request, selected, cancel: jobs.append((request, selected, cancel)),
    )

    window._begin_local_apk_parse([path])
    window._local_apk_parse_worker(*jobs[0])

    assert window.source_mode is None
    assert window._local_apk_artifacts == ()
    assert not window.run_button.isEnabled()


def test_stale_parse_completion_cannot_replace_newer_selection(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    jobs: list[tuple[int, tuple[Path, ...], threading.Event]] = []
    monkeypatch.setattr(
        window,
        "_launch_local_apk_parse_worker",
        lambda request, selected, cancel: jobs.append((request, selected, cancel)),
    )
    old = _artifact(tmp_path / "old.apk", "c" * 64)
    current = _artifact(tmp_path / "current.apk", "d" * 64)

    window._begin_local_apk_parse([old.canonical_path])
    old_request = jobs[-1][0]
    window._begin_local_apk_parse([current.canonical_path])
    current_request = jobs[-1][0]
    window._on_local_apk_parse_done(old_request, (old,), ())

    assert window.source_mode is None
    assert window._local_apk_artifacts == ()

    window._on_local_apk_parse_done(current_request, (current,), ())
    assert window.source_mode == "local_apk"
    assert window._local_apk_artifacts == (current,)


def test_switching_to_file_discards_transient_local_state(
    window: MainWindow, tmp_path: Path
) -> None:
    artifact = _artifact(tmp_path / "local.apk", "e" * 64)
    window._local_apk_artifacts = (artifact,)
    window.source_mode = "local_apk"
    window.current_rows = [{"source_mode": "local_apk", "local_apk_sha256": artifact.artifact_sha256}]
    window.model.set_rows(window.current_rows)
    source = tmp_path / "packages.csv"
    source.write_text("package_name\ncom.example.file\n", encoding="utf-8")

    window._load_input_file(str(source))

    assert window.source_mode == "file"
    assert window._local_apk_artifacts == ()
    assert window.current_rows == []
    assert window.file_apps == [
        {"app_name": "com.example.file", "package_name": "com.example.file"}
    ]
    assert window._scan_session is None


@dataclass
class FakeStore:
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback=None,
        **_kwargs,
    ) -> list[dict[str, Any]]:
        self.calls.append([dict(app) for app in apps])
        rows: list[dict[str, Any]] = []
        for index, app_row in enumerate(apps, start=1):
            package = app_row["package_name"]
            rows.append(
                {
                    "app_name": package,
                    "package_name": package,
                    "play_status": "available",
                    "play_title": "Store title",
                    "play_version": "2.0",
                    "play_last_update": "2026-09-01",
                    "store_country": config.country,
                    "store_language": config.language,
                    "notes": "",
                }
            )
            if progress_callback is not None:
                progress_callback(index, len(apps), package)
        return rows


def _no_alternatives(rows, settings, **kwargs) -> list[str]:
    del rows, settings, kwargs
    return []


def test_local_audit_preserves_artifacts_deduplicates_network_and_skips_history(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _artifact(tmp_path / "first.apk", "1" * 64)
    second = _artifact(tmp_path / "second.apk", "2" * 64)
    store = FakeStore()
    service = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    )
    persistence: list[str] = []
    monkeypatch.setattr(window, "_local_artifact_store_service", lambda: service)
    monkeypatch.setattr(
        compact_ui,
        "load_history",
        lambda: (_ for _ in ()).throw(AssertionError("history must not load")),
    )
    monkeypatch.setattr(state, "save_history", lambda _rows: persistence.append("history"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: persistence.append("inventory") or {},
    )
    window.source_mode = "local_apk"
    window._local_apk_artifacts = (first, second)
    window._audit_session = 20
    window._set_audit_state(AuditRunState.RUNNING)

    window._local_apk_audit_worker(
        (first, second),
        AuditConfig(country="us", language="en"),
        {"cache_enabled": False, "compare_previous": True},
        20,
        threading.Event(),
        threading.Event(),
        False,
    )
    app.processEvents()

    assert store.calls == [
        [{"app_name": "com.example.same", "package_name": "com.example.same"}]
    ]
    assert window._audit_state is AuditRunState.IDLE
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert [row["local_apk_sha256"] for row in window.current_rows] == [
        "1" * 64,
        "2" * 64,
    ]
    assert all(row["is_system"] is None for row in window.current_rows)
    assert all("installed_version" not in row for row in window.current_rows)
    assert all(row["local_apk_version_comparison"] == "Different" for row in window.current_rows)
    assert persistence == []

    panel = details_panel.AppDetailsPanel()
    panel.set_row(window.current_rows[0])
    detail_text = panel.local_apk_label.text()
    assert "Filename: first.apk" in detail_text
    assert f"SHA-256: {'1' * 64}" in detail_text
    assert "Local version: 1.0" in detail_text
    assert "Version code: 10" in detail_text
    assert "Min SDK: 23" in detail_text
    assert "Target SDK: 35" in detail_text
    assert "Compile SDK: 35" in detail_text
    assert "Debuggable: No" in detail_text
    assert "android.permission.INTERNET" in detail_text
    assert "application_label_unresolved" in detail_text
    assert not panel.local_apk_section.isHidden()
    assert panel.device_section.isHidden()
    panel.deleteLater()


def test_exports_preserve_artifacts_without_absolute_path(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = _artifact(tmp_path / "first.apk", "7" * 64)
    second = _artifact(tmp_path / "second.apk", "8" * 64)
    store = FakeStore()
    fanout = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    ).collect(
        (first, second), AuditConfig(), {"cache_enabled": False}
    )
    rows = local_apk_audit.association_result_rows(fanout.associations)
    csv_path = tmp_path / "results.csv"
    monkeypatch.setattr(
        compact_ui.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(csv_path), "CSV (*.csv)"),
    )
    monkeypatch.setattr(compact_ui.QMessageBox, "information", lambda *_args: None)
    window.source_mode = "local_apk"
    window.current_rows = rows
    window._export_results()

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    document = result_json.build_results_document(rows)
    html_path = device_insights.write_html_report(tmp_path / "results.html", rows)
    exported_text = csv_path.read_text(encoding="utf-8-sig") + html_path.read_text(
        encoding="utf-8"
    )

    assert [row["local_apk_sha256"] for row in csv_rows] == ["7" * 64, "8" * 64]
    assert [row["local_apk_file_name"] for row in document["results"]] == [
        "first.apk",
        "second.apk",
    ]
    assert str(tmp_path.resolve()) not in exported_text
    assert all("canonical_path" not in row for row in document["results"])
