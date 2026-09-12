from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app: QApplication) -> MainWindow:
    value = MainWindow()
    yield value
    value.close()
    app.processEvents()


def _drain(app: QApplication) -> None:
    app.processEvents()
    app.processEvents()


def test_valid_local_source_auto_starts_once(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    package = tmp_path / "app.apkm"
    package.write_bytes(b"candidate")
    starts: list[bool] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append(True))

    window._begin_local_apk_parse([package, package])
    _drain(app)

    assert starts == [True]


def test_empty_or_cancelled_local_source_does_not_auto_start(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts: list[bool] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append(True))
    monkeypatch.setattr(
        "playstore_app_audit.ui.main_window.QFileDialog.getOpenFileNames",
        lambda *_args, **_kwargs: ([], ""),
    )

    window._choose_local_apks()
    window._establish_local_apk_candidates((), "selected")
    _drain(app)

    assert starts == []


def test_valid_app_list_auto_starts_once_but_invalid_file_does_not(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "apps.csv"
    source.write_text("package_name\ncom.example.one\n", encoding="utf-8")
    starts: list[bool] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append(True))
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args, **_kwargs: None)

    window._load_input_file(str(source))
    _drain(app)
    window._load_input_file(str(tmp_path / "missing.csv"))
    _drain(app)

    assert starts == [True]


def test_successful_phone_capture_auto_starts_once(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    starts: list[bool] = []
    monkeypatch.setattr(window, "_start_audit", lambda: starts.append(True))
    monkeypatch.setattr(window, "_find_adb", lambda: None)
    monkeypatch.setattr(window, "_get_authorised_adb", lambda: None)

    window._on_adb_scan_done(
        [{"app_name": "Example", "package_name": "com.example.one"}],
        set(),
    )
    _drain(app)

    assert starts == [True]


def test_progressive_rows_replace_by_physical_key_and_remain_unexportable(
    window: MainWindow,
) -> None:
    window._audit_session = 7
    window._set_audit_state(AuditRunState.RUNNING)
    first = {
        "source_mode": "local_apk",
        "package_name": "com.example.one",
        "local_apk_file_name": "one.apkm",
        "local_apk_location": "C:/private/one.apkm",
        "_audit_provisional": True,
        "_provisional_key": "C:/private/one.apkm",
    }
    resolved = {
        **first,
        "play_status": "available",
        "play_version": "2.0",
    }

    window._on_progressive_row(7, first)
    window._on_progressive_row(7, resolved)

    assert len(window.current_rows) == 1
    assert window.current_rows[0]["play_version"] == "2.0"
    assert "criticality_key" not in window.current_rows[0]
    assert "health_score" not in window.current_rows[0]
    assert not window.export_button.isEnabled()
    assert all(button.text().endswith("0") for button in window.criticality_buttons.values())


def test_progressive_rows_use_key_index_and_coalesce_model_refreshes(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TrackingRows(list[dict[str, object]]):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    rows = TrackingRows(
        [
            {
                "source_mode": "file",
                "package_name": "com.example.one",
                "_audit_provisional": True,
                "_provisional_key": "com.example.one",
            }
        ]
    )
    window._audit_session = 30
    window._set_audit_state(AuditRunState.RUNNING)
    window.current_rows = rows
    window._begin_progressive_presentation(30, rows)
    icon_generation = window.model._icon_generation
    rows.iterations = 0
    refreshes: list[list[dict[str, object]]] = []
    monkeypatch.setattr(window.model, "set_rows", lambda value: refreshes.append(value))

    window._on_progressive_row(
        30,
        {
            "source_mode": "file",
            "package_name": "com.example.one",
            "play_version": "2",
            "_audit_provisional": True,
            "_provisional_key": "com.example.one",
        },
    )
    window._on_progressive_row(
        30,
        {
            "source_mode": "file",
            "package_name": "com.example.two",
            "_audit_provisional": True,
            "_provisional_key": "com.example.two",
        },
    )
    window._on_progressive_row(
        30,
        {
            "source_mode": "file",
            "package_name": "com.example.one",
            "play_version": "3",
            "_audit_provisional": True,
            "_provisional_key": "com.example.one",
        },
    )

    assert rows.iterations == 0
    assert len(window.current_rows) == 2
    assert window.current_rows[0]["play_version"] == "3"
    assert window._provisional_row_indexes == {
        "com.example.one": 0,
        "com.example.two": 1,
    }
    assert window._progressive_payload_count == 3
    assert window._progressive_refresh_count == 0
    assert 50 <= window._progressive_refresh_timer.interval() <= 100
    assert refreshes == []

    window._flush_progressive_rows()

    assert len(refreshes) == 1
    assert window._progressive_refresh_count == 1
    assert window._progressive_payload_count > window._progressive_refresh_count
    assert window.model._icon_generation == icon_generation


@pytest.mark.parametrize(
    "outcome",
    [AuditRunOutcome.SUCCESS, AuditRunOutcome.STOPPED, AuditRunOutcome.FAILED],
)
def test_final_outcome_invalidates_pending_progressive_refresh(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    outcome: AuditRunOutcome,
) -> None:
    from playstore_app_audit.ui.compact_window import CompactWindow

    monkeypatch.setattr(QMessageBox, "critical", lambda *_args, **_kwargs: None)
    window._audit_session = 31
    window._set_audit_state(AuditRunState.RUNNING)
    window.current_rows = []
    window._begin_progressive_presentation(31, [])
    window._on_progressive_row(
        31,
        {
            "source_mode": "file",
            "package_name": "com.example.provisional",
            "_audit_provisional": True,
            "_provisional_key": "com.example.provisional",
        },
    )
    authoritative = {
        "source_mode": "file",
        "package_name": "com.example.final",
        "play_status": "available",
        "play_last_update": "2026-08-01",
    }

    CompactWindow._on_controlled_done(
        window,
        AuditRunResult(
            session=31,
            outcome=outcome,
            rows=[authoritative],
            live_completed_count=1,
            total_count=1,
            error="synthetic failure" if outcome is AuditRunOutcome.FAILED else "",
        ),
    )
    window._flush_progressive_rows()

    assert not window._progressive_refresh_pending
    assert window._progressive_refresh_session is None
    assert [row["package_name"] for row in window.current_rows] == ["com.example.final"]
    assert window.model.rowCount() == 1
    assert window.export_button.isEnabled() is (outcome is AuditRunOutcome.SUCCESS)


def test_abandon_and_source_replacement_invalidate_pending_refresh(
    window: MainWindow,
) -> None:
    window._audit_session = 32
    window._set_audit_state(AuditRunState.RUNNING)
    window.current_rows = []
    window._begin_progressive_presentation(32, [])
    window._on_progressive_row(
        32,
        {
            "source_mode": "device",
            "package_name": "com.example.old",
            "_audit_provisional": True,
            "_provisional_key": "com.example.old",
        },
    )

    window._abandon_active_audit()
    window._clear_source_result_rows()
    window._flush_progressive_rows()

    assert window._last_audit_outcome is AuditRunOutcome.ABANDONED
    assert not window._progressive_refresh_pending
    assert window._progressive_refresh_session is None
    assert window.current_rows == []
    assert window.model.rowCount() == 0


def test_successful_final_rows_replace_provisional_rows_without_duplicates(
    window: MainWindow,
) -> None:
    window._audit_session = 8
    window._set_audit_state(AuditRunState.RUNNING)
    window.current_rows = [
        {
            "source_mode": "file",
            "package_name": "com.example.one",
            "_audit_provisional": True,
            "_provisional_key": "com.example.one",
        }
    ]
    result = AuditRunResult(
        session=8,
        outcome=AuditRunOutcome.SUCCESS,
        rows=[
            {
                "source_mode": "file",
                "package_name": "com.example.one",
                "play_status": "not_found_in_checked_countries",
            }
        ],
        live_completed_count=1,
        total_count=1,
    )

    # Exercise the shared finalizer directly; MainWindow adds deferred polish.
    from playstore_app_audit.ui.compact_window import CompactWindow

    CompactWindow._on_controlled_done(window, result)

    assert len(window.current_rows) == 1
    assert "_audit_provisional" not in window.current_rows[0]
    assert window.current_rows[0]["criticality_key"] == "red"
    assert window.export_button.isEnabled()
