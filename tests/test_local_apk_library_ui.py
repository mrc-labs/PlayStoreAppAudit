from __future__ import annotations

import csv
import json
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_library as library_service_module
import playstore_app_audit.services.result_json as result_json
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.local_apk_library as library_ui
from playstore_app_audit.domain.local_apk_library import (
    LibraryRootScanStatus,
    LocalApkLibrary,
    LocalApkLibraryScanResult,
)
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFormat,
    LocalArtifactParseResult,
)
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.services.local_apk_library import LocalApkLibraryService
from playstore_app_audit.services.local_artifact_store import LocalArtifactStoreService
from playstore_app_audit.ui import details_panel
from playstore_app_audit.ui.local_apk_library import LocalApkLibraryDialog
from playstore_app_audit.ui.main_window import MainWindow

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _artifact(path: Path, sha: str, package: str = "com.example.shared") -> LocalArtifact:
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
        file_size=path.stat().st_size,
        modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
    )


def _parser(path: Path) -> LocalArtifactParseResult:
    data = path.read_bytes()
    sha = (data.hex() * 64)[:64]
    return LocalArtifactParseResult(artifact=_artifact(path, sha))


def _service(tmp_path: Path) -> LocalApkLibraryService:
    return LocalApkLibraryService(
        tmp_path / "local_apk_library.json",
        parser=_parser,
        clock=lambda: NOW,
    )


def _persisted_library(
    service: LocalApkLibraryService,
    roots: list[Path],
) -> LocalApkLibrary:
    library = service.register_roots(service.empty_library(), roots)
    library = service.rescan(library).library
    assert service.save(library).succeeded
    return library


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


def test_empty_library_dialog_opens_safely(app: QApplication, tmp_path: Path) -> None:
    dialog = LocalApkLibraryDialog(service=_service(tmp_path))

    assert dialog.library == LocalApkLibrary()
    assert dialog.roots_table.rowCount() == 0
    assert dialog.artifacts_table.rowCount() == 0
    assert dialog.add_folder_button.isEnabled()
    assert not dialog.audit_button.isEnabled()
    dialog.close()


def test_valid_persisted_library_loads_one_artifact_row(app: QApplication, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"1")
    service = _service(tmp_path)
    _persisted_library(service, [root])

    dialog = LocalApkLibraryDialog(service=service)

    assert dialog.roots_table.rowCount() == 1
    assert dialog.artifacts_table.rowCount() == 1
    assert dialog.roots_table.item(0, 0).text() == str(root.resolve())
    dialog.close()


def test_invalid_library_load_disables_writes_without_overwrite(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    invalid = b'{"schema_version": 99}'
    service.path.write_bytes(invalid)
    messages: list[str] = []
    monkeypatch.setattr(
        library_ui.QMessageBox,
        "critical",
        lambda _parent, _title, message: messages.append(message),
    )

    dialog = LocalApkLibraryDialog(service=service)

    assert dialog.library is None
    assert dialog.error_label.isVisibleTo(dialog)
    assert not dialog.add_folder_button.isEnabled()
    assert not dialog.rescan_all_button.isEnabled()
    assert not dialog.audit_button.isEnabled()
    assert service.path.read_bytes() == invalid
    assert messages and "Writing is disabled" in messages[0]
    dialog.close()


def test_add_folder_saves_registration_then_launches_async_scan(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"1")
    service = _service(tmp_path)
    dialog = LocalApkLibraryDialog(service=service)
    jobs: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        library_ui.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(root),
    )
    monkeypatch.setattr(dialog, "_launch_scan_worker", lambda *args: jobs.append(args))

    dialog.add_folder_button.click()

    persisted_before_scan = service.load().library
    assert persisted_before_scan is not None
    assert [item.path for item in persisted_before_scan.roots] == [root.resolve()]
    assert persisted_before_scan.artifacts == ()
    assert len(jobs) == 1
    dialog._scan_worker(*jobs[0])
    persisted_after_scan = service.load().library
    assert persisted_after_scan is not None
    assert len(persisted_after_scan.artifacts) == 1
    assert persisted_after_scan.roots[0].last_scan_status is LibraryRootScanStatus.COMPLETED
    dialog.close()


def test_duplicate_and_overlapping_roots_are_rejected_explicitly(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = tmp_path / "parent"
    registered = parent / "registered"
    nested = registered / "nested"
    nested.mkdir(parents=True)
    service = _service(tmp_path)
    library = service.register_roots(service.empty_library(), [registered])
    assert library_ui.root_overlap_message(library, registered)
    assert "covered" in str(library_ui.root_overlap_message(library, nested))
    assert "contains" in str(library_ui.root_overlap_message(library, parent))
    assert service.save(library).succeeded
    dialog = LocalApkLibraryDialog(service=service)
    messages: list[str] = []
    jobs: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        library_ui.QFileDialog,
        "getExistingDirectory",
        lambda *_args, **_kwargs: str(registered),
    )
    monkeypatch.setattr(
        library_ui.QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )
    monkeypatch.setattr(dialog, "_launch_scan_worker", lambda *args: jobs.append(args))

    dialog.add_folder_button.click()

    assert len(dialog.library.roots) == 1  # type: ignore[union-attr]
    assert messages and "already registered" in messages[0]
    assert jobs == []
    dialog.close()


def test_existing_nested_roots_load_and_display_safely(app: QApplication, tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    service = _service(tmp_path)
    library = service.register_roots(service.empty_library(), [parent, child])
    assert service.save(library).succeeded

    dialog = LocalApkLibraryDialog(service=service)

    assert dialog.roots_table.rowCount() == 2
    assert {dialog.roots_table.item(row, 0).text() for row in range(2)} == {
        str(parent.resolve()),
        str(child.resolve()),
    }
    dialog.close()


def test_remove_folder_removes_only_library_metadata(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    apk = root / "one.apk"
    apk.write_bytes(b"1")
    service = _service(tmp_path)
    _persisted_library(service, [root])
    dialog = LocalApkLibraryDialog(service=service)
    dialog.roots_table.selectRow(0)
    prompts: list[str] = []
    monkeypatch.setattr(
        library_ui.QMessageBox,
        "question",
        lambda _parent, _title, message, *_args: prompts.append(message) or QMessageBox.StandardButton.Yes,
    )

    dialog.remove_folder_button.click()

    persisted = service.load().library
    assert persisted is not None
    assert persisted.roots == ()
    assert persisted.locations == ()
    assert len(persisted.artifacts) == 1
    assert root.is_dir() and apk.read_bytes() == b"1"
    assert prompts and "will not be deleted" in prompts[0]
    dialog.close()


def test_partial_scan_is_saved_without_false_disappearance(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (nested / "one.apk").write_bytes(b"1")
    service = _service(tmp_path)
    _persisted_library(service, [root])
    dialog = LocalApkLibraryDialog(service=service)
    jobs: list[tuple[object, ...]] = []
    monkeypatch.setattr(dialog, "_launch_scan_worker", lambda *args: jobs.append(args))
    monkeypatch.setattr(library_ui.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    original_scandir = library_service_module.os.scandir

    def guarded_scandir(path: str | os.PathLike[str]):
        if Path(path) == nested:
            raise PermissionError("fixture")
        return original_scandir(path)

    monkeypatch.setattr(library_service_module.os, "scandir", guarded_scandir)
    dialog.rescan_all_button.click()
    dialog._scan_worker(*jobs[0])

    persisted = service.load().library
    assert persisted is not None
    assert persisted.roots[0].last_scan_status is LibraryRootScanStatus.PARTIAL
    assert persisted.locations[0].present
    dialog.close()


def test_failed_root_scan_status_is_saved_without_losing_known_location(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    apk = root / "one.apk"
    apk.write_bytes(b"1")
    service = _service(tmp_path)
    _persisted_library(service, [root])
    dialog = LocalApkLibraryDialog(service=service)
    jobs: list[tuple[object, ...]] = []
    monkeypatch.setattr(dialog, "_launch_scan_worker", lambda *args: jobs.append(args))
    monkeypatch.setattr(library_ui.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    apk.unlink()
    root.rmdir()

    dialog.rescan_all_button.click()
    dialog._scan_worker(*jobs[0])

    persisted = service.load().library
    assert persisted is not None
    assert persisted.roots[0].last_scan_status is LibraryRootScanStatus.FAILED
    assert persisted.locations[0].present
    dialog.close()


def test_cancelled_scan_discards_partial_mutations(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"1")
    service = _service(tmp_path)
    persisted = _persisted_library(service, [root])
    dialog = LocalApkLibraryDialog(service=service)
    mutated = service.register_roots(persisted, [tmp_path / "not-persisted"])
    cancelled = LocalApkLibraryScanResult(mutated, (), (), True)
    save_calls: list[LocalApkLibrary] = []
    original_save = service.save
    monkeypatch.setattr(
        service,
        "save",
        lambda library: save_calls.append(library) or original_save(library),
    )
    dialog._scan_generation = 4
    dialog._scan_active = True

    dialog._on_scan_done(4, cancelled)

    assert save_calls == []
    assert dialog.library == persisted
    assert service.load().library == persisted
    assert "not saved" in dialog.status_label.text()
    dialog.close()


def test_stale_scan_completion_cannot_overwrite_newer_state(
    app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    persisted = service.empty_library()
    assert service.save(persisted).succeeded
    dialog = LocalApkLibraryDialog(service=service)
    stale_library = service.register_roots(persisted, [tmp_path / "stale"])
    stale = LocalApkLibraryScanResult(stale_library, (), (), False)
    save_calls: list[LocalApkLibrary] = []
    monkeypatch.setattr(service, "save", lambda library: save_calls.append(library))
    dialog._scan_generation = 2
    dialog._scan_active = True

    dialog._on_scan_done(1, stale)

    assert dialog.library == persisted
    assert save_calls == []
    dialog.close()


def test_duplicate_locations_share_one_artifact_row_and_show_all_states(
    app: QApplication, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    present = root / "present.apk"
    missing = root / "missing.apk"
    present.write_bytes(b"1")
    missing.write_bytes(b"1")
    service = _service(tmp_path)
    library = _persisted_library(service, [root])
    missing.unlink()
    library = service.rescan(library).library
    assert service.save(library).succeeded

    dialog = LocalApkLibraryDialog(service=service)

    assert dialog.artifacts_table.rowCount() == 1
    assert dialog.artifacts_table.item(0, 4).text() == "1/2 present"
    details = dialog.artifact_details.toPlainText()
    assert f"Present: {present.resolve()}" in details
    assert f"Missing: {missing.resolve()}" in details
    assert f"Root: {root.resolve()}" in details
    dialog.close()


def test_audit_library_emits_one_representative_per_sha(app: QApplication, tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "copy-a.apk").write_bytes(b"1")
    (root / "copy-b.apk").write_bytes(b"1")
    (root / "other.apk").write_bytes(b"2")
    service = _service(tmp_path)
    _persisted_library(service, [root])
    dialog = LocalApkLibraryDialog(service=service)
    requests: list[tuple[LocalArtifact, ...]] = []
    dialog.audit_requested.connect(lambda artifacts: requests.append(tuple(artifacts)))

    dialog.audit_button.click()

    assert len(requests) == 1
    assert len(requests[0]) == 2
    assert len({artifact.artifact_sha256 for artifact in requests[0]}) == 2
    assert {artifact.package_lookup_key for artifact in requests[0]} == {"com.example.shared"}


def test_main_window_exposes_file_and_compact_library_entry_points(window: MainWindow) -> None:
    assert window.file_local_apk_library_action.text() == "Local APK Library…"
    assert [action.text() for action in window.local_apk_options_menu.actions()] == ["Local APK Library…"]
    controls = window.local_apk_options_button.parentWidget().layout()
    assert controls.itemAt(0).widget() is window.choose_apk_button
    assert controls.itemAt(1).widget() is window.local_apk_options_button
    assert window.choose_apk_button.text() == "Choose APK(s)"
    assert window.choose_button.text() == "Choose File"
    assert window.scan_button.text() == "Scan Phone"


def test_opening_library_manager_preserves_current_results(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    current_rows = [{"package_name": "com.example.current", "criticality_key": "green"}]
    window.current_rows = current_rows
    window.model.set_rows(current_rows)
    window.source_mode = "file"
    monkeypatch.setattr(window, "_local_apk_library_service", lambda: service)

    window.file_local_apk_library_action.trigger()
    app.processEvents()

    assert window._local_apk_library_dialog is not None
    assert window._local_apk_library_dialog.isVisible()
    assert window.current_rows == current_rows
    assert window.source_mode == "file"
    window._local_apk_library_dialog.close()


def test_library_audit_establishes_explicit_source_without_persistence_write(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "one.apk"
    path.write_bytes(b"1")
    artifact = _artifact(path, "1" * 64)
    starts: list[str] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append("audit"))

    window._begin_local_apk_library_audit((artifact,))
    app.processEvents()

    assert window.source_mode == local_apk_audit.LIBRARY_SOURCE_MODE
    assert window._local_apk_artifacts == (artifact,)
    assert starts == ["audit"]
    assert "Local APK Library" in window.source_label.text()
    assert not window.exclude_system_source_check.isEnabled()


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
        for index, app in enumerate(apps, start=1):
            package = app["package_name"]
            rows.append(
                {
                    "app_name": package,
                    "package_name": package,
                    "play_status": "available",
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


def test_library_audit_reuses_package_fanout_and_bypasses_history(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.apk"
    second_path = tmp_path / "second.apk"
    first_path.write_bytes(b"1")
    second_path.write_bytes(b"2")
    first = _artifact(first_path, "1" * 64)
    second = _artifact(second_path, "2" * 64)
    store = FakeStore()
    fanout = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    )
    persistence: list[str] = []
    monkeypatch.setattr(window, "_local_artifact_store_service", lambda: fanout)
    monkeypatch.setattr(state, "save_history", lambda _rows: persistence.append("history"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: persistence.append("inventory") or {},
    )
    window.source_mode = local_apk_audit.LIBRARY_SOURCE_MODE
    window._local_apk_artifacts = (first, second)
    window._audit_session = 30
    window._set_audit_state(AuditRunState.RUNNING)

    window._local_apk_audit_worker(
        (first, second),
        AuditConfig(country="us", language="en"),
        {"cache_enabled": False, "compare_previous": True},
        30,
        threading.Event(),
        threading.Event(),
        False,
        local_apk_audit.LIBRARY_SOURCE_MODE,
    )
    app.processEvents()

    assert store.calls == [[{"app_name": "com.example.shared", "package_name": "com.example.shared"}]]
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert len(window.current_rows) == 2
    assert all(row["source_mode"] == local_apk_audit.LIBRARY_SOURCE_MODE for row in window.current_rows)
    serialized = json.dumps(window.current_rows)
    assert str(tmp_path.resolve()) not in serialized
    assert "canonical_path" not in serialized
    assert persistence == []

    panel = details_panel.AppDetailsPanel()
    panel.set_row(window.current_rows[0])
    assert not panel.local_apk_section.isHidden()
    assert panel.device_section.isHidden()
    panel.deleteLater()

    csv_path = tmp_path / "library-results.csv"
    monkeypatch.setattr(
        compact_ui.QFileDialog,
        "getSaveFileName",
        lambda *_args, **_kwargs: (str(csv_path), "CSV (*.csv)"),
    )
    monkeypatch.setattr(compact_ui.QMessageBox, "information", lambda *_args: None)
    window._export_results()
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    json_document = result_json.build_results_document(window.current_rows)
    html_path = device_insights.write_html_report(tmp_path / "library-results.html", window.current_rows)
    exported_text = csv_path.read_text(encoding="utf-8-sig") + html_path.read_text(encoding="utf-8")
    assert [row["local_apk_sha256"] for row in csv_rows] == ["1" * 64, "2" * 64]
    assert [row["local_apk_sha256"] for row in json_document["results"]] == [
        "1" * 64,
        "2" * 64,
    ]
    assert "APK SHA-256" in html_path.read_text(encoding="utf-8")
    assert str(tmp_path.resolve()) not in exported_text


def test_library_source_switching_does_not_modify_persistent_library(
    window: MainWindow, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"1")
    service = _service(tmp_path)
    library = _persisted_library(service, [root])
    original = service.path.read_bytes()
    window.source_mode = local_apk_audit.LIBRARY_SOURCE_MODE
    window._local_apk_artifacts = service.auditable_artifacts(library)
    window.current_rows = [{"source_mode": local_apk_audit.LIBRARY_SOURCE_MODE}]
    source = tmp_path / "packages.csv"
    source.write_text("package_name\ncom.example.file\n", encoding="utf-8")

    window._load_input_file(str(source))

    assert window.source_mode == "file"
    assert window._local_apk_artifacts == ()
    assert service.path.read_bytes() == original


def test_library_mapper_sets_distinct_source_without_path_leak(tmp_path: Path) -> None:
    path = tmp_path / "private" / "one.apk"
    path.parent.mkdir()
    path.write_bytes(b"1")
    artifact = _artifact(path, "1" * 64)
    store = FakeStore()
    result = LocalArtifactStoreService(
        store_service=store,
        alternative_runner=_no_alternatives,
    ).collect((artifact,), AuditConfig(), {"cache_enabled": False})

    rows = local_apk_audit.association_result_rows(
        result.associations,
        source_mode=local_apk_audit.LIBRARY_SOURCE_MODE,
    )

    assert rows[0]["source_mode"] == "local_apk_library"
    assert rows[0]["local_apk_sha256"] == "1" * 64
    assert str(path.parent.resolve()) not in json.dumps(rows)
    assert "canonical_path" not in rows[0]
