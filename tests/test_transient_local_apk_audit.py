from __future__ import annotations

import csv
import io
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

import playstore_app_audit.platform.file_locations as file_locations
import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk as local_apk
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_source as local_apk_source
import playstore_app_audit.services.local_package_container as local_package_container
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseFailure,
    LocalArtifactParseResult,
)
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService
from playstore_app_audit.ui import details_panel, schema
from playstore_app_audit.ui.base_window import EXPORT_FIELDS
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
        permissions=(),
        features=(),
        icon_reference=None,
        file_name=path.name,
        canonical_path=path.resolve(),
        file_size=1234,
        modified_at=datetime(2026, 9, 10, 10, 0, tzinfo=UTC),
    )


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "compare_previous": False,
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


def test_choose_files_establishes_candidates_without_parsing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    first = tmp_path / "one.apk"
    first.write_bytes(b"candidate")
    parser_calls: list[Path] = []
    scheduled: list[bool] = []
    monkeypatch.setattr(local_apk, "parse_local_apk", lambda path: parser_calls.append(path))
    monkeypatch.setattr(window, "_schedule_first_audit", lambda: scheduled.append(True))
    window._begin_local_apk_parse([first, first, tmp_path / "missing.apk"])
    assert window._local_apk_candidates == (first.resolve(),)
    assert window.source_mode == "local_apk"
    assert parser_calls == []
    assert scheduled == [True]
    assert window.run_button.isEnabled()


def test_folder_discovery_is_recursive_case_insensitive_and_filtered(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    first = root / "a.APK"
    second = nested / "b.apk"
    first.write_bytes(b"a")
    second.write_bytes(b"b")
    third = nested / "bundle.apks"
    third.write_bytes(b"x")
    (nested / "ignored.aab").write_bytes(b"x")
    result = local_apk_source.discover_folder_apks(root)
    expected = tuple(
        sorted(
            (first.resolve(), second.resolve(), third.resolve()),
            key=lambda p: os.path.normcase(str(p)),
        )
    )
    assert result.paths == expected
    assert not result.cancelled


def test_explicit_package_formats_are_case_insensitive_and_deduplicated(
    tmp_path: Path,
) -> None:
    paths = [
        tmp_path / name
        for name in ("one.APK", "two.APKS", "three.APKM", "four.XAPK")
    ]
    for path in paths:
        path.write_bytes(b"synthetic")

    selected = local_apk_source.normalise_explicit_apks([*paths, paths[1]])

    assert set(selected) == {path.resolve() for path in paths}


def test_folder_discovery_does_not_follow_directory_links(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (outside / "hidden.apk").write_bytes(b"x")
    link = root / "linked"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory links are unavailable in this environment")
    assert local_apk_source.discover_folder_apks(root).paths == ()


def test_folder_discovery_rejects_a_link_as_the_selected_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "hidden.apk").write_bytes(b"x")
    link = tmp_path / "selected-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Directory links are unavailable in this environment")
    assert local_apk_source.discover_folder_apks(link).paths == ()


def test_zero_folder_result_and_stale_completion_are_safe(
    window: MainWindow, tmp_path: Path
) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    result = local_apk_source.discover_folder_apks(root)
    window._local_apk_parse_generation = 4
    window._local_apk_parse_active = True
    window._on_local_apk_discovery_done(3, result, str(root))
    assert window._local_apk_candidates == ()
    window._on_local_apk_discovery_done(4, result, str(root))
    assert window.source_mode is None
    assert not window.run_button.isEnabled()


def test_folder_discovery_stop_is_cooperative(window: MainWindow) -> None:
    cancellation = threading.Event()
    window._local_apk_parse_cancel_event = cancellation
    window._local_apk_parse_active = True
    window._set_busy(True)
    window._stop_audit()
    assert cancellation.is_set()
    assert not window._local_apk_parse_active
    assert not window.stop_button.isEnabled()
    assert window.source_mode is None


@dataclass
class FakeStore:
    calls: list[list[dict[str, str]]] = field(default_factory=list)

    def audit(
        self,
        apps: list[dict[str, str]],
        config: AuditConfig,
        progress_callback=None,
        **_kwargs,
    ):
        self.calls.append([dict(app) for app in apps])
        return [
            {
                "package_name": app["package_name"],
                "play_status": "available",
                "play_version": "2.0",
                "play_last_update": "2026-08-23",
                "store_country": config.country,
            }
            for app in apps
        ]


def _no_alternatives(_rows, _settings, **_kwargs) -> list[str]:
    return []


def test_run_parses_candidates_keeps_partial_success_and_physical_rows(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    copy = tmp_path / "copy.apk"
    broken = tmp_path / "broken.apk"
    crashed = tmp_path / "crashed.apk"
    for path in (first, copy, broken, crashed):
        path.write_bytes(path.name.encode())
    outcomes = {
        first: LocalArtifactParseResult(artifact=_artifact(first, "1" * 64)),
        copy: LocalArtifactParseResult(artifact=_artifact(copy, "1" * 64)),
        broken: LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                broken, LocalArtifactFailureKind.MALFORMED_ARCHIVE, "broken"
            )
        ),
    }
    store = FakeStore()
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )

    def parse_candidate(path: Path) -> LocalArtifactParseResult:
        if path == crashed:
            raise RuntimeError("synthetic parser crash")
        return outcomes[path]

    monkeypatch.setattr(local_apk, "parse_local_apk", parse_candidate)
    monkeypatch.setattr(
        window,
        "_local_artifact_store_service",
        lambda: LocalArtifactStoreService(store_service=store, alternative_runner=_no_alternatives),
    )
    window.source_mode = "local_apk"
    window._local_apk_candidates = (first, copy, broken, crashed)
    window._audit_session = 20
    window._set_audit_state(AuditRunState.RUNNING)
    running = threading.Event()
    running.set()
    window._local_apk_audit_worker(
        window._local_apk_candidates,
        AuditConfig(),
        {"cache_enabled": False},
        20,
        running,
        threading.Event(),
        False,
    )
    app.processEvents()
    assert store.calls == [[{"app_name": "com.example.same", "package_name": "com.example.same"}]]
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert [row["local_apk_location"] for row in window.current_rows] == [
        str(first.resolve()),
        str(copy.resolve()),
    ]
    assert [row["local_apk_sha256"] for row in window.current_rows] == ["1" * 64, "1" * 64]
    assert all(row["local_apk_version_comparison"] == "Outdated" for row in window.current_rows)
    assert len(warnings) == 1
    assert warnings[0][0] == "Some package files could not be parsed"
    assert "2 package file(s) were rejected" in warnings[0][1]


def test_stop_during_parse_keeps_source_evidence_and_starts_no_store_work(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    cancel_event = threading.Event()
    store_calls: list[bool] = []

    def parse_candidate(path: Path) -> LocalArtifactParseResult:
        cancel_event.set()
        return LocalArtifactParseResult(artifact=_artifact(path, "3" * 64))

    class StoreMustNotRun:
        def collect(self, *_args, **_kwargs):
            store_calls.append(True)
            raise AssertionError("Store collection started after parse cancellation")

    monkeypatch.setattr(local_apk, "parse_local_apk", parse_candidate)
    monkeypatch.setattr(window, "_local_artifact_store_service", StoreMustNotRun)
    window.source_mode = "local_apk"
    window._audit_session = 21
    window._set_audit_state(AuditRunState.RUNNING)
    running = threading.Event()
    running.set()

    window._local_apk_audit_worker(
        (first, second),
        AuditConfig(),
        {"cache_enabled": False},
        21,
        running,
        cancel_event,
        False,
    )
    app.processEvents()
    app.processEvents()

    assert store_calls == []
    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert len(window.current_rows) == 1
    assert window.current_rows[0]["local_apk_location"] == str(first.resolve())
    assert "health_score" not in window.current_rows[0]
    assert not window.export_button.isEnabled()


def test_container_parse_cancellation_is_not_reported_as_rejection(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    cancelled = tmp_path / "cancelled.apkm"
    cancelled.write_bytes(b"synthetic container")
    cancel_event = threading.Event()
    warnings: list[tuple[str, str]] = []
    results: list[AuditRunResult] = []
    caplog.set_level(logging.INFO, logger="playstore_app_audit.ui.main_window")

    def parse_candidate(
        path: Path, *, cancel_event: threading.Event
    ) -> LocalArtifactParseResult:
        cancel_event.set()
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                path,
                LocalArtifactFailureKind.CANCELLED,
                "Container inspection was cancelled.",
            )
        )

    monkeypatch.setattr(local_package_container, "parse_local_package", parse_candidate)
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    window.audit_control_signals.done.connect(results.append)
    window.source_mode = "local_apk"
    window._audit_session = 22
    window._set_audit_state(AuditRunState.RUNNING)
    running = threading.Event()
    running.set()

    window._local_apk_audit_worker(
        (cancelled,),
        AuditConfig(),
        {"cache_enabled": False},
        22,
        running,
        cancel_event,
        False,
    )
    app.processEvents()
    app.processEvents()

    result = results[-1]
    assert result.outcome is AuditRunOutcome.STOPPED
    assert result.metadata["parse_failure_count"] == 0
    assert result.metadata["parse_failure_summary"] == ""
    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert warnings == []
    assert "local_container_rejected" not in caplog.text


def test_genuine_container_failure_before_cancellation_remains_reported(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.apks"
    cancelled = tmp_path / "cancelled.xapk"
    malformed.write_bytes(b"malformed")
    cancelled.write_bytes(b"synthetic container")
    cancel_event = threading.Event()
    warnings: list[tuple[str, str]] = []
    results: list[AuditRunResult] = []
    caplog.set_level(logging.INFO, logger="playstore_app_audit.ui.main_window")

    def parse_candidate(
        path: Path, *, cancel_event: threading.Event
    ) -> LocalArtifactParseResult:
        if path == malformed:
            return LocalArtifactParseResult(
                failure=LocalArtifactParseFailure(
                    path,
                    LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                    "Not a ZIP archive.",
                )
            )
        cancel_event.set()
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                path,
                LocalArtifactFailureKind.CANCELLED,
                "Container inspection was cancelled.",
            )
        )

    monkeypatch.setattr(local_package_container, "parse_local_package", parse_candidate)
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    window.audit_control_signals.done.connect(results.append)
    window.source_mode = "local_apk"
    window._audit_session = 23
    window._set_audit_state(AuditRunState.RUNNING)
    running = threading.Event()
    running.set()

    window._local_apk_audit_worker(
        (malformed, cancelled),
        AuditConfig(),
        {"cache_enabled": False},
        23,
        running,
        cancel_event,
        False,
    )
    app.processEvents()
    app.processEvents()

    result = results[-1]
    assert result.outcome is AuditRunOutcome.STOPPED
    assert result.metadata["parse_failure_count"] == 1
    assert result.metadata["parse_failure_summary"] == "malformed.apks: malformed archive"
    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert len(warnings) == 1
    assert warnings[0][0] == "Some package files could not be parsed"
    assert "1 package file(s) were rejected" in warnings[0][1]
    assert "malformed.apks: malformed archive" in warnings[0][1]
    assert "cancelled.xapk" not in warnings[0][1]
    rejection_logs = [
        record for record in caplog.records if record.message.startswith("local_container_rejected")
    ]
    assert len(rejection_logs) == 1
    assert "reason=malformed_archive" in rejection_logs[0].message


def test_definitive_store_absence_uses_na_local_relationship_everywhere(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    artifact = _artifact(tmp_path / "missing.apkm", "4" * 64)
    row = local_apk_audit.artifact_result_row(
        artifact,
        {"play_status": "not_found_in_checked_countries"},
    )
    row.update(criticality="Not Found", criticality_key="red")
    window.model.set_rows([row])
    relationship = window.model.index(
        0, window.model.columns.index("local_apk_version_comparison")
    )
    store_status = window.model.index(0, window.model.columns.index("criticality"))

    assert row["local_apk_version_comparison"] == "N/A"
    assert relationship.data(Qt.ItemDataRole.DisplayRole) == "N/A"
    assert store_status.data(Qt.ItemDataRole.DisplayRole) == "Not Found"
    assert store_status.data(Qt.ItemDataRole.BackgroundRole) == relationship.data(
        Qt.ItemDataRole.BackgroundRole
    )
    assert "comparison is not applicable" in relationship.data(
        Qt.ItemDataRole.ToolTipRole
    )
    assert "does not prove global absence" in relationship.data(
        Qt.ItemDataRole.ToolTipRole
    )
    assert any(
        "comparison is not applicable" in line
        for line in details_panel.local_apk_details_lines(row)
    )
    assert result_json.build_results_document([row])["results"][0][
        "local_apk_version_comparison"
    ] == "N/A"
    report = device_insights.write_html_report(tmp_path / "missing.html", [row])
    assert "<td>N/A</td>" in report.read_text(encoding="utf-8")


def test_location_schema_details_tooltip_and_private_exports(tmp_path: Path) -> None:
    path = tmp_path / "private" / "one.apk"
    path.parent.mkdir()
    path.write_bytes(b"x")
    artifact = _artifact(path, "2" * 64)
    store = FakeStore()
    fanout = LocalArtifactStoreService(store_service=store, alternative_runner=_no_alternatives).collect(
        (artifact,), AuditConfig(), {"cache_enabled": False}
    )
    row = local_apk_audit.association_result_rows(fanout.associations)[0]
    assert schema.COLUMN_LABELS["local_apk_location"] == "Location"
    assert "local_apk_location" in schema.MODEL_COLUMNS
    assert "local_apk_location" not in schema.EXPORT_EXTRA_FIELDS
    panel = details_panel.AppDetailsPanel()
    panel.set_row(row)
    assert f"Location: {path.resolve()}" in panel.local_apk_label.text()
    document = result_json.build_results_document([row])
    html_path = device_insights.write_html_report(tmp_path / "report.html", [row])
    csv_output = io.StringIO()
    writer = csv.DictWriter(csv_output, fieldnames=EXPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerow(row)
    assert "local_apk_location" not in document["results"][0]
    assert str(path.resolve()) not in json.dumps(document)
    assert str(path.resolve()) not in csv_output.getvalue()
    assert str(path.resolve()) not in html_path.read_text(encoding="utf-8")
    panel.deleteLater()


@pytest.mark.parametrize(
    ("source_mode", "expected", "excluded"),
    [
        ("file", "play_status", "installed_version"),
        ("device", "installed_version", "local_apk_location"),
        ("local_apk", "local_apk_location", "installed_version"),
    ],
)
def test_technical_view_is_source_aware(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    source_mode: str,
    expected: str,
    excluded: str,
) -> None:
    monkeypatch.setattr(
        state,
        "load_settings",
        lambda: {"view_preset": "Technical", "compare_previous": False},
    )
    window.source_mode = source_mode
    columns = window._visible_column_order()
    assert expected in columns
    assert excluded not in columns


def test_custom_view_can_include_location(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        state,
        "load_settings",
        lambda: {
            "view_preset": "Custom",
            "custom_view_columns": ["criticality", "package_name", "local_apk_location"],
        },
    )
    assert "local_apk_location" in window._visible_column_order()


def test_library_entry_points_are_removed_and_global_tooltip_is_exact(window: MainWindow) -> None:
    file_actions = [action.text() for action in window.file_menu.actions()]
    assert "Local APK Library…" not in file_actions
    assert "Choose Package Folder…" in file_actions
    assert [action.text() for action in window.local_apk_options_menu.actions()] == [
        "File(s)…",
        "Folder…",
    ]
    assert window.table.toolTip() == (
        "Double-click to open Google Play when available. Right-click for more options."
    )
    assert schema.COLUMN_LABELS["criticality"] == "Store Status"


def test_location_model_tooltip_is_full_path(tmp_path: Path) -> None:
    from playstore_app_audit.ui.table_window import AuditTableModel

    location = str((tmp_path / "one.apk").resolve())
    model = AuditTableModel()
    model.set_rows([{"local_apk_location": location}])
    index = model.index(0, model.columns.index("local_apk_location"))
    assert index.data(Qt.ItemDataRole.ToolTipRole) == location


@pytest.mark.parametrize("file_name", ["one file.apk", "one # copy.apk", "caffè_日本.apk"])
def test_windows_file_location_uses_native_shell_selection(
    file_name: str,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "folder with spaces" / file_name
    path.parent.mkdir()
    path.write_bytes(b"x")
    reveals: list[Path] = []
    monkeypatch.setattr(file_locations.runtime, "platform_key", lambda: "windows")
    monkeypatch.setattr(
        file_locations.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("Explorer subprocess must not be used on Windows"),
    )
    monkeypatch.setattr(
        file_locations,
        "_windows_reveal_file",
        lambda selected: (reveals.append(selected) is None, 0),
    )
    with caplog.at_level(logging.DEBUG, logger=file_locations.__name__):
        assert file_locations.open_file_location(path) == (True, "")
    assert reveals == [path.resolve()]
    missing = file_locations.open_file_location(tmp_path / "missing # file.apk")
    assert not missing[0]
    assert "reveal requested: platform=windows" in caplog.text
    assert "native reveal succeeded: platform=windows" in caplog.text
    assert "final outcome: platform=windows success=true" in caplog.text
    assert "reveal failed: platform=windows reason=missing" in caplog.text


def test_windows_native_reveal_failure_opens_parent_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "folder" / "one.apk"
    path.parent.mkdir()
    path.write_bytes(b"x")
    fallbacks: list[Path] = []
    monkeypatch.setattr(file_locations.runtime, "platform_key", lambda: "windows")
    monkeypatch.setattr(file_locations, "_windows_reveal_file", lambda _path: (False, -1))
    monkeypatch.setattr(
        file_locations,
        "_windows_open_folder",
        lambda parent: (fallbacks.append(parent) is None, 42),
    )

    with caplog.at_level(logging.DEBUG, logger=file_locations.__name__):
        assert file_locations.open_file_location(path) == (True, "")

    assert fallbacks == [path.parent.resolve()]
    assert "native reveal failed" in caplog.text
    assert "parent-folder fallback" in caplog.text


def test_non_windows_file_location_keeps_existing_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "one file.apk"
    path.write_bytes(b"x")
    calls: list[list[str]] = []
    monkeypatch.setattr(file_locations.runtime, "platform_key", lambda: "linux")
    monkeypatch.setattr(
        file_locations.subprocess,
        "Popen",
        lambda args, **_kwargs: calls.append(args),
    )

    assert file_locations.open_file_location(path) == (True, "")
    assert calls == [["xdg-open", str(path.parent.resolve())]]


def test_open_file_location_context_action_is_local_and_requires_a_file(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    path = tmp_path / "one.apk"
    path.write_bytes(b"x")
    assert window._local_file_location_action(
        {"source_mode": "local_apk", "local_apk_location": str(path.resolve())}
    ) == (str(path.resolve()), True)
    assert (
        window._local_file_location_action(
            {"source_mode": "file", "local_apk_location": str(path.resolve())}
        )
        is None
    )
    assert window._local_file_location_action(
        {"source_mode": "local_apk", "local_apk_location": str(tmp_path / "gone.apk")}
    ) == (str(tmp_path / "gone.apk"), False)
