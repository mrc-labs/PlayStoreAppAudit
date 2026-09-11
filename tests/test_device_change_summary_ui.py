"""RC6-D2A-001: real inventory persistence and queued Qt audit finalization."""

from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from test_scan_session_phase_b import (
    _compact,
    _select_session,
    _session,
    _store_row,
)
from test_scan_session_phase_b import (
    app as app,
)
from test_scan_session_phase_b import (
    window as window,
)

from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.services import device_insights, scan_session, summary
from playstore_app_audit.ui.details_panel import device_inventory_line
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture
def inventory(window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(device_insights, "app_data_dir_v9", lambda: tmp_path)
    # These tests establish scan sessions directly and then drive explicit
    # audit generations. Auto-start is covered by its dedicated source tests.
    monkeypatch.setattr(window, "_schedule_first_audit", lambda: None)
    window.user_settings["inventory_history_enabled"] = True
    window.show()
    return device_insights.inventory_path("device-a")


def _complete(
    window: MainWindow,
    app: QApplication,
    session: scan_session.ScanSession,
    outcome: AuditRunOutcome = AuditRunOutcome.SUCCESS,
) -> AuditRunResult:
    _select_session(window, session)
    window._audit_session += 1
    window._audit_requested_outcome = None
    window._set_audit_state(AuditRunState.RUNNING)
    result = AuditRunResult(
        session=window._audit_session,
        outcome=outcome,
        rows=[_store_row(package) for package in session.packages],
        total_count=len(session.packages),
        live_completed_count=len(session.packages),
        metadata={"scan_session": session},
        error="Fixture failure" if outcome is AuditRunOutcome.FAILED else "",
    )
    window._on_controlled_done(result)
    assert window._audit_state is AuditRunState.FINALIZING
    app.processEvents()
    assert window._audit_state is AuditRunState.IDLE
    return result


def _visible(window: MainWindow, app: QApplication) -> tuple[str, str]:
    window.table.selectRow(0)
    app.processEvents()
    assert window.summary_label.isVisible()
    return window.summary_label.text(), window.details_panel.device_label.text()


def test_installer_change_then_unchanged_visible_in_same_generation(
    window: MainWindow, app: QApplication, inventory: Path
) -> None:
    baseline = _session(_compact())
    changed = _session(_compact(installer_package="com.sec.android.app.samsungapps"))
    _complete(window, app, baseline)
    _complete(window, app, changed)
    audit_n = _visible(window, app)
    _complete(window, app, changed)
    audit_next = _visible(window, app)

    assert "Installer/source changed" in audit_n[1]
    assert "No inventory change" in audit_next[1]
    assert ["Device changes 1" in audit_n[0], "Device changes" in audit_next[0]] == [True, False], (
        audit_n, audit_next
    )


@pytest.mark.parametrize("case", ["same", "version", "added", "removed", "multiple"])
def test_inventory_taxonomy_and_same_run_header(
    window: MainWindow, app: QApplication, inventory: Path, case: str
) -> None:
    original = _compact()
    other = _compact("com.example.other")
    baseline = _session(original, other) if case == "removed" else _session(original)
    current = {
        "same": _session(original),
        "version": _session(replace(original, installed_version_code="202")),
        "added": _session(original, other),
        "removed": _session(original),
        "multiple": _session(
            _compact(installer_package="com.sec.android.app.samsungapps"), other
        ),
    }[case]
    _complete(window, app, baseline)
    _complete(window, app, current)
    expected = {"same": 0, "version": 1, "added": 1, "removed": 1, "multiple": 2}[case]
    header, _details = _visible(window, app)
    assert summary.device_change_count(window._last_inventory_changes) == expected
    if expected:
        assert f"Device changes {expected}" in header
    else:
        assert "Device changes" not in header
    lines = [device_inventory_line(row) for row in window.current_rows]
    if case == "version":
        assert any("Installed version changed" in line for line in lines)
    elif case in {"added", "multiple"}:
        assert any("Newly installed" in line for line in lines)
        if case == "multiple":
            assert any("Installer/source changed" in line for line in lines)
    else:
        assert all("No inventory change" in line for line in lines)
    if case == "removed":
        # Removed packages have no current row/Details; retain overview semantics.
        assert window._last_inventory_changes["removed"] == ["com.example.other"]
        assert window._current_change_groups()
    saved = json.loads(inventory.read_text(encoding="utf-8"))
    assert set(saved["apps"]) == set(current.packages)


@pytest.mark.parametrize("outcome", [AuditRunOutcome.STOPPED, AuditRunOutcome.FAILED])
def test_incomplete_run_drops_old_count_without_promoting(
    window: MainWindow, app: QApplication, inventory: Path, outcome: AuditRunOutcome
) -> None:
    baseline = _session(_compact())
    changed = _session(_compact(installer_package="com.sec.android.app.samsungapps"))
    _complete(window, app, baseline)
    _complete(window, app, changed)
    before = inventory.read_bytes()
    _complete(window, app, baseline, outcome)
    assert inventory.read_bytes() == before
    header, details = _visible(window, app)
    assert "Device changes" not in header
    assert "Since previous phone scan:" not in details
    assert window._last_audit_outcome is outcome
    _complete(window, app, baseline)
    header, details = _visible(window, app)
    assert "Device changes 1" in header
    assert "Installer/source changed" in details


def test_clear_and_next_run_do_not_resurrect_completed_count(
    window: MainWindow, app: QApplication, inventory: Path
) -> None:
    _complete(window, app, _session(_compact()))
    changed = _session(_compact(version_code="202"))
    _complete(window, app, changed)
    window._clear_results()
    app.processEvents()
    assert "Device changes" not in window.summary_label.text()
    assert not window.current_rows
    _complete(window, app, changed)
    assert "Device changes" not in window.summary_label.text()


def test_new_run_clears_visible_previous_count_before_worker_completion(
    window: MainWindow, app: QApplication, inventory: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _complete(window, app, _session(_compact()))
    _complete(window, app, _session(_compact(version_code="202")))
    assert "Device changes 1" in window.summary_label.text()
    monkeypatch.setattr(window, "_load_fresh_cache", lambda *_args: {})
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)
    before = inventory.read_bytes()
    window._start_audit()
    assert window._audit_state is AuditRunState.RUNNING
    assert len(window.current_rows) == 1
    assert window.current_rows[0]["_audit_provisional"] is True
    assert "Device changes" not in window.summary_label.text()
    assert inventory.read_bytes() == before


def test_stale_completion_and_new_scan_cannot_replace_audit_inventory(
    window: MainWindow, app: QApplication, inventory: Path
) -> None:
    baseline = _session(_compact())
    stale = _complete(window, app, baseline)
    changed = _session(_compact(version_code="202"))
    current = _complete(window, app, changed)
    before = inventory.read_bytes()
    header = window.summary_label.text()
    _select_session(window, baseline)
    window._on_controlled_done(stale)
    window._complete_controlled_done(stale)
    window._complete_controlled_done(current)  # Already finalized callback.
    app.processEvents()
    assert inventory.read_bytes() == before
    assert window.summary_label.text() == header
    assert "Device changes 1" in header


def test_finalization_uses_bound_t1_not_newly_selected_session(
    window: MainWindow, app: QApplication, inventory: Path
) -> None:
    baseline = _session(_compact())
    _complete(window, app, baseline)
    changed = _session(_compact(version_code="202"))
    window._audit_session += 1
    result = AuditRunResult(
        session=window._audit_session,
        outcome=AuditRunOutcome.SUCCESS,
        rows=[_store_row()],
        total_count=1,
        live_completed_count=1,
        metadata={"scan_session": changed},
    )
    window._on_controlled_done(result)
    window._scan_session = baseline
    app.processEvents()
    assert "Device changes 1" in window.summary_label.text()
    assert "Installed version changed" in device_inventory_line(window.current_rows[0])
    assert json.loads(inventory.read_text(encoding="utf-8"))["apps"]["com.example.app"][
        "installed_version_code"
    ] == "202"
