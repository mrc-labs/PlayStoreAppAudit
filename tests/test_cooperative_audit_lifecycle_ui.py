from __future__ import annotations

import os
import threading

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.device_window as device_ui
import playstore_app_audit.ui.insights_window as insights_ui
from playstore_app_audit.domain.models import AuditRunOutcome, AuditRunResult, AuditRunState
from playstore_app_audit.services.audit_engine import AuditConfig
from playstore_app_audit.ui.main_window import MainWindow


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
        "changes_history_enabled": True,
        "compare_previous": False,
        "inventory_history_enabled": True,
    }
    monkeypatch.setattr(state, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(state, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    monkeypatch.setattr(compact_ui.QMessageBox, "critical", lambda *_args, **_kwargs: None)
    created = MainWindow()
    created.source_mode = "file"
    created.file_apps = [{"app_name": "Example", "package_name": "com.example.app"}]
    created.current_system_packages = set()
    created._sync_action_availability()
    yield created
    created.close()
    app.processEvents()


def _available_row(package: str, title: str = "Example") -> dict[str, object]:
    return {
        "app_name": title,
        "package_name": package,
        "play_status": "available",
        "play_title": title,
        "play_last_update": "2026-08-01",
        "play_version": "1.0",
    }


def test_lifecycle_action_availability_and_clear_guard(window: MainWindow) -> None:
    row = _available_row("com.example.app")
    window.current_rows = [row]
    window.model.set_rows([row])
    window._set_audit_state(AuditRunState.IDLE)

    assert window.run_button.isEnabled()
    assert not window.stop_button.isEnabled()
    assert window.clear_button.isEnabled()
    assert window.export_button.isEnabled()
    assert window.audit_result_actions.clear.isEnabled()
    assert window.audit_result_actions.exports.menu.menuAction().isEnabled()

    for state_value in (
        AuditRunState.RUNNING,
        AuditRunState.PAUSED,
        AuditRunState.STOPPING,
        AuditRunState.FINALIZING,
    ):
        window._set_audit_state(state_value)
        assert not window.clear_button.isEnabled()
        assert not window.export_button.isEnabled()
        assert not window.audit_result_actions.clear.isEnabled()
        assert not window.audit_result_actions.exports.menu.menuAction().isEnabled()
        before = list(window.current_rows)
        window._clear_results()
        assert window.current_rows == before

    window._set_audit_state(AuditRunState.IDLE)
    assert window.clear_button.isEnabled()
    assert window.export_button.isEnabled()
    assert window.audit_result_actions.clear.isEnabled()
    assert window.audit_result_actions.exports.menu.menuAction().isEnabled()


def test_stop_unpauses_and_enters_visible_drain_state(window: MainWindow) -> None:
    window._audit_session = 7
    window._audit_pause_event.clear()
    window._audit_cancel_event.clear()
    window._last_progress = (37, 120, "com.example.app")
    window._set_audit_state(AuditRunState.PAUSED)

    window._stop_audit()

    assert window._audit_state is AuditRunState.STOPPING
    assert window._audit_requested_outcome is AuditRunOutcome.STOPPED
    assert window._audit_cancel_event.is_set()
    assert window._audit_pause_event.is_set()
    assert window.status_label.text() == "Stopping… 37/120 completed"
    assert not window.run_button.isEnabled()
    assert not window.stop_button.isEnabled()
    assert not window.clear_button.isEnabled()


def test_stopped_run_finalizes_partial_rows_without_baseline_promotion(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    monkeypatch.setattr(state, "save_history", lambda _rows: promotions.append("history"))
    monkeypatch.setattr(
        device_metadata,
        "save_history_merged",
        lambda _rows: promotions.append("history-merged"),
    )
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: promotions.append("inventory") or {},
    )
    window._audit_session = 8
    window._audit_requested_outcome = AuditRunOutcome.STOPPED
    window._set_audit_state(AuditRunState.STOPPING)
    rows = [_available_row("com.example.cached"), _available_row("com.example.live")]

    window._on_controlled_done(
        AuditRunResult(
            session=8,
            outcome=AuditRunOutcome.STOPPED,
            rows=rows,
            cached_count=1,
            live_completed_count=1,
            total_count=3,
        )
    )

    assert window._audit_state is AuditRunState.FINALIZING
    app.processEvents()
    assert window._audit_state is AuditRunState.IDLE
    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert [row["package_name"] for row in window.current_rows] == [
        "com.example.cached",
        "com.example.live",
    ]
    assert window.status_label.text().startswith("Audit stopped • 2/3 completed")
    assert not window.export_button.isEnabled()
    assert window.clear_button.isEnabled()
    assert window.run_button.isEnabled()
    assert promotions == []


def test_targeted_stop_replaces_only_completed_rows_and_preserves_device_metadata(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    window.user_settings["compare_previous"] = True
    monkeypatch.setattr(
        device_metadata,
        "save_history_merged",
        lambda _rows: promotions.append("history"),
    )
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: promotions.append("inventory") or {},
    )
    old_one = {
        **_available_row("com.example.one", "Old one"),
        "installed_version": "7.0",
        "target_sdk": "34",
    }
    old_two = _available_row("com.example.two", "Old two")
    window.current_rows = [old_one, old_two]
    window.model.set_rows(window.current_rows)
    window._merge_base_rows = [dict(old_one), dict(old_two)]
    window._subset_label = "Problematic-app recheck"
    window._v9_targeted_active = True
    window._audit_session = 9
    window._set_audit_state(AuditRunState.STOPPING)
    refreshed = _available_row("com.example.one", "New one")
    refreshed["installed_version"] = ""
    refreshed["target_sdk"] = ""

    window._on_controlled_done(
        AuditRunResult(
            session=9,
            outcome=AuditRunOutcome.STOPPED,
            rows=[refreshed],
            live_completed_count=1,
            total_count=2,
        )
    )
    app.processEvents()

    by_package = {str(row["package_name"]): row for row in window.current_rows}
    assert by_package["com.example.one"]["play_title"] == "New one"
    assert by_package["com.example.one"]["installed_version"] == "7.0"
    assert by_package["com.example.one"]["target_sdk"] == "34"
    assert by_package["com.example.two"]["play_title"] == "Old two"
    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert promotions == []


def test_cancelled_optional_device_metadata_keeps_valid_store_row(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata_cancelled = threading.Event()
    store_row = _available_row("com.example.app")
    window.source_mode = "device"
    window._audit_session = 24
    window._audit_requested_outcome = None
    window._audit_cancel_event.clear()
    window._audit_pause_event.set()
    window._set_audit_state(AuditRunState.RUNNING)
    monkeypatch.setattr(window, "_get_authorised_adb", lambda: "adb")

    def cancel_metadata(_adb, _packages, cancel_event):
        cancel_event.set()
        metadata_cancelled.set()
        return {}

    def complete_store_row(
        _apps,
        _config,
        _progress,
        *,
        pause_event,
        cancel_event,
        row_completed_callback,
    ):
        del pause_event
        assert metadata_cancelled.wait(2.0)
        assert cancel_event.is_set()
        row_completed_callback(0, store_row)
        return [store_row]

    monkeypatch.setattr(window, "_collect_device_metadata", cancel_metadata)
    monkeypatch.setattr(device_metadata, "audit_apps_v8", complete_store_row)
    apps = [{"app_name": "Example", "package_name": "com.example.app"}]

    device_ui.DeviceWindow._controlled_audit_worker(
        window,
        apps,
        apps,
        {},
        AuditConfig(country="us", language="en", max_workers=1),
        24,
        window._audit_pause_event,
        window._audit_cancel_event,
        False,
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert len(window.current_rows) == 1
    assert window.current_rows[0]["package_name"] == "com.example.app"
    assert window.current_rows[0]["play_status"] == "available"


def test_post_success_baseline_persistence_succeeds_in_order(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    warnings: list[str] = []
    window.user_settings["compare_previous"] = True
    window.source_mode = "device"
    window.device_apps_all = [{"app_name": "Example", "package_name": "com.example.app"}]
    window._device_summary = {"device_id": "device-1"}
    monkeypatch.setattr(state, "save_history", lambda _rows: promotions.append("history"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: promotions.append("inventory") or {"had_previous": False},
    )
    monkeypatch.setattr(
        insights_ui.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    window._audit_session = 10
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=10,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.app")],
            live_completed_count=1,
            total_count=1,
        )
    )

    assert promotions == []
    app.processEvents()
    assert promotions == ["history", "inventory"]
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert window._audit_state is AuditRunState.IDLE
    assert warnings == []


def test_result_finalization_failure_is_failed_before_baseline_persistence(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    window.user_settings["compare_previous"] = True
    monkeypatch.setattr(state, "save_history", lambda _rows: promotions.append("history"))
    monkeypatch.setattr(
        window,
        "_classify_row",
        lambda _row: (_ for _ in ()).throw(RuntimeError("classification failed")),
    )
    window._audit_session = 11
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=11,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.app")],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.FAILED
    assert window._audit_state is AuditRunState.IDLE
    assert window.status_label.text() == "Audit failed during finalization"
    assert promotions == []


def test_post_success_history_persistence_failure_keeps_audit_successful(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_calls: list[str] = []
    warnings: list[tuple[str, str]] = []
    criticals: list[str] = []
    logs: list[str] = []
    window.user_settings.update(
        {"compare_previous": True, "inventory_history_enabled": True}
    )
    window.source_mode = "device"
    window.device_apps_all = [{"app_name": "Example", "package_name": "com.example.app"}]
    window._device_summary = {"device_id": "device-1"}

    def fail_history(_rows) -> None:
        persistence_calls.append("history")
        raise OSError("history write denied")

    monkeypatch.setattr(state, "save_history", fail_history)
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: persistence_calls.append("inventory") or {},
    )
    monkeypatch.setattr(device_insights, "log_event", logs.append)
    monkeypatch.setattr(
        insights_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "critical",
        lambda _parent, _title, message: criticals.append(message),
    )
    window._audit_session = 20
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=20,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.app")],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert persistence_calls == ["history"]
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert window._audit_state is AuditRunState.IDLE
    assert window.current_rows[0]["package_name"] == "com.example.app"
    assert window.export_button.isEnabled()
    assert window.status_label.text() == "Audit completed • local history baseline not saved"
    assert len(warnings) == 1
    assert warnings[0][0] == "Audit completed with a local save warning"
    assert "history baseline could not be saved" in warnings[0][1]
    assert "inventory baseline was not updated" in warnings[0][1]
    assert criticals == []
    assert len(logs) == 1
    assert "stage=history history=failed inventory=skipped" in logs[0]


def test_post_success_inventory_persistence_failure_keeps_audit_successful(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_calls: list[str] = []
    warnings: list[tuple[str, str]] = []
    criticals: list[str] = []
    logs: list[str] = []
    window.user_settings.update(
        {"compare_previous": True, "inventory_history_enabled": True}
    )
    window.source_mode = "device"
    window.device_apps_all = [{"app_name": "Example", "package_name": "com.example.app"}]
    window._device_summary = {"device_id": "device-1"}
    monkeypatch.setattr(
        state,
        "save_history",
        lambda _rows: persistence_calls.append("history"),
    )

    def fail_inventory(*_args) -> dict[str, object]:
        persistence_calls.append("inventory")
        raise OSError("inventory write denied")

    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        fail_inventory,
    )
    monkeypatch.setattr(device_insights, "log_event", logs.append)
    monkeypatch.setattr(
        insights_ui.QMessageBox,
        "warning",
        lambda _parent, title, message: warnings.append((title, message)),
    )
    monkeypatch.setattr(
        compact_ui.QMessageBox,
        "critical",
        lambda _parent, _title, message: criticals.append(message),
    )
    window._audit_session = 21
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=21,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.app")],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert persistence_calls == ["history", "inventory"]
    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert window._audit_state is AuditRunState.IDLE
    assert window.current_rows[0]["package_name"] == "com.example.app"
    assert window.export_button.isEnabled()
    assert window.status_label.text() == (
        "Audit completed • device inventory baseline not saved"
    )
    assert len(warnings) == 1
    assert "local history was saved" in warnings[0][1]
    assert "inventory baseline could not be saved" in warnings[0][1]
    assert criticals == []
    assert len(logs) == 1
    assert "stage=inventory history=saved inventory=failed" in logs[0]


def test_failed_audit_result_never_persists_baselines(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_calls: list[str] = []
    window.user_settings.update(
        {"compare_previous": True, "inventory_history_enabled": True}
    )
    window.source_mode = "device"
    window._device_summary = {"device_id": "device-1"}
    monkeypatch.setattr(
        state,
        "save_history",
        lambda _rows: persistence_calls.append("history"),
    )
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: persistence_calls.append("inventory") or {},
    )
    window._audit_session = 22
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=22,
            outcome=AuditRunOutcome.FAILED,
            rows=[_available_row("com.example.partial")],
            live_completed_count=1,
            total_count=2,
            error="worker failed",
        )
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.FAILED
    assert persistence_calls == []


def test_successful_targeted_recheck_persists_merged_history_only(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    persistence_calls: list[str] = []
    old = _available_row("com.example.app", "Old")
    window.user_settings.update(
        {"compare_previous": True, "inventory_history_enabled": True}
    )
    window.source_mode = "device"
    window.current_rows = [old]
    window.model.set_rows(window.current_rows)
    window._merge_base_rows = [dict(old)]
    window._subset_label = "App recheck"
    window._v9_targeted_active = True
    window._device_summary = {"device_id": "device-1"}
    monkeypatch.setattr(
        device_metadata,
        "save_history_merged",
        lambda _rows: persistence_calls.append("history-merged"),
    )
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: persistence_calls.append("inventory") or {},
    )
    window._audit_session = 23
    window._set_audit_state(AuditRunState.RUNNING)

    window._on_controlled_done(
        AuditRunResult(
            session=23,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.app", "New")],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.SUCCESS
    assert window.current_rows[0]["play_title"] == "New"
    assert persistence_calls == ["history-merged"]


def test_close_abandons_and_late_result_is_ignored(window: MainWindow) -> None:
    original_rows = [_available_row("com.example.previous")]
    window.current_rows = list(original_rows)
    window.model.set_rows(window.current_rows)
    window._audit_session = 12
    window._audit_cancel_event.clear()
    window._audit_pause_event.clear()
    window._set_audit_state(AuditRunState.RUNNING)

    window.close()

    assert window._audit_session == 13
    assert window._last_audit_outcome is AuditRunOutcome.ABANDONED
    assert window._audit_cancel_event.is_set()
    assert window._audit_pause_event.is_set()
    assert window._audit_state is AuditRunState.IDLE

    window._on_controlled_done(
        AuditRunResult(
            session=12,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.late")],
            live_completed_count=1,
            total_count=1,
        )
    )
    assert window.current_rows == original_rows


def test_stop_accepted_before_queued_success_prevents_promotion(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    monkeypatch.setattr(state, "save_history", lambda _rows: promotions.append("history"))
    window.user_settings["compare_previous"] = True
    window._audit_session = 18
    window._audit_requested_outcome = AuditRunOutcome.STOPPED
    window._set_audit_state(AuditRunState.STOPPING)

    window._on_controlled_done(
        AuditRunResult(
            session=18,
            outcome=AuditRunOutcome.SUCCESS,
            rows=[_available_row("com.example.completed")],
            live_completed_count=1,
            total_count=1,
        )
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert window.status_label.text().startswith("Audit stopped")
    assert promotions == []


def test_abandoned_run_never_promotes_baselines(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    promotions: list[str] = []
    monkeypatch.setattr(state, "save_history", lambda _rows: promotions.append("history"))
    monkeypatch.setattr(
        device_insights,
        "annotate_inventory_changes_and_save",
        lambda *_args: promotions.append("inventory") or {},
    )
    window._audit_session = 13
    window._set_audit_state(AuditRunState.RUNNING)

    window._abandon_active_audit()

    assert window._last_audit_outcome is AuditRunOutcome.ABANDONED
    assert promotions == []


def test_fatal_failure_wins_over_concurrent_stop(
    window: MainWindow,
    app: QApplication,
) -> None:
    window._audit_session = 14
    window._audit_requested_outcome = AuditRunOutcome.STOPPED
    window._set_audit_state(AuditRunState.STOPPING)

    window._on_controlled_done(
        AuditRunResult(
            session=14,
            outcome=AuditRunOutcome.FAILED,
            rows=[_available_row("com.example.partial")],
            live_completed_count=1,
            total_count=2,
            error="fatal worker failure",
        )
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.FAILED
    assert window._audit_state is AuditRunState.IDLE
    assert window.status_label.text() == "Audit failed • 1/2 completed"


def test_stopped_worker_caches_only_canonical_positive_rows_and_excludes_unfinished(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    cache_file = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_file)
    cached = _available_row("com.example.cached", "Cached")
    positive = _available_row("com.example.positive", "Positive")
    inconclusive = {
        **_available_row("com.example.inconclusive", "Inconclusive"),
        "play_status": "check_failed",
        "play_last_update": "",
    }
    all_apps = [
        {"app_name": "Cached", "package_name": "com.example.cached"},
        {"app_name": "Positive", "package_name": "com.example.positive"},
        {"app_name": "Inconclusive", "package_name": "com.example.inconclusive"},
        {"app_name": "Unfinished", "package_name": "com.example.unfinished"},
    ]
    live_apps = all_apps[1:]

    def stopped_audit(
        _apps,
        _config,
        _progress,
        *,
        pause_event,
        cancel_event,
        row_completed_callback,
    ):
        del pause_event
        row_completed_callback(0, positive)
        row_completed_callback(1, inconclusive)
        cancel_event.set()
        return []

    monkeypatch.setattr(compact_ui, "audit_apps_multicountry", stopped_audit)
    window._audit_session = 16
    window._audit_requested_outcome = AuditRunOutcome.STOPPED
    window._set_audit_state(AuditRunState.STOPPING)
    pause_event = window._audit_pause_event
    pause_event.set()
    cancel_event = window._audit_cancel_event
    cancel_event.clear()

    compact_ui.CompactWindow._controlled_audit_worker(
        window,
        all_apps,
        live_apps,
        {"com.example.cached": cached},
        AuditConfig(country="us", language="en", max_workers=1),
        16,
        pause_event,
        cancel_event,
        True,
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.STOPPED
    assert [row["package_name"] for row in window.current_rows] == [
        "com.example.cached",
        "com.example.positive",
        "com.example.inconclusive",
    ]
    fresh = state.load_fresh_cache(live_apps, "us", "en", 72)
    assert set(fresh) == {"com.example.positive"}
    assert "com.example.unfinished" not in fresh
    assert not window.export_button.isEnabled()


def test_worker_exception_before_any_result_is_failed(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compact_ui,
        "audit_apps_multicountry",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("worker failed")),
    )
    apps = [{"app_name": "Example", "package_name": "com.example.app"}]
    window._audit_session = 17
    window._audit_requested_outcome = None
    window._set_audit_state(AuditRunState.RUNNING)
    cancel_event = window._audit_cancel_event
    cancel_event.clear()
    pause_event = window._audit_pause_event
    pause_event.set()

    compact_ui.CompactWindow._controlled_audit_worker(
        window,
        apps,
        apps,
        {},
        AuditConfig(country="us", language="en", max_workers=1),
        17,
        pause_event,
        cancel_event,
        False,
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.FAILED
    assert window.current_rows == []
    assert window.status_label.text() == "Audit failed"
    assert window._audit_state is AuditRunState.IDLE


def test_worker_exception_after_partial_result_preserves_completed_row(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = _available_row("com.example.completed")

    def failing_audit(
        _apps,
        _config,
        _progress,
        *,
        pause_event,
        cancel_event,
        row_completed_callback,
    ):
        del pause_event, cancel_event
        row_completed_callback(0, completed)
        raise RuntimeError("worker failed after row")

    monkeypatch.setattr(compact_ui, "audit_apps_multicountry", failing_audit)
    apps = [
        {"app_name": "Completed", "package_name": "com.example.completed"},
        {"app_name": "Unfinished", "package_name": "com.example.unfinished"},
    ]
    window._audit_session = 19
    window._audit_requested_outcome = None
    window._set_audit_state(AuditRunState.RUNNING)
    cancel_event = window._audit_cancel_event
    cancel_event.clear()
    pause_event = window._audit_pause_event
    pause_event.set()

    compact_ui.CompactWindow._controlled_audit_worker(
        window,
        apps,
        apps,
        {},
        AuditConfig(country="us", language="en", max_workers=1),
        19,
        pause_event,
        cancel_event,
        False,
    )
    app.processEvents()

    assert window._last_audit_outcome is AuditRunOutcome.FAILED
    assert [row["package_name"] for row in window.current_rows] == [
        "com.example.completed"
    ]
    assert window.status_label.text() == "Audit failed • 1/2 completed"
