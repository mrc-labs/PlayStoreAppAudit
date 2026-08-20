from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_store_workers_default_and_bounds() -> None:
    assert state.DEFAULT_SETTINGS["store_workers"] == 16
    assert state.normalise_store_workers(None) == 16
    assert state.normalise_store_workers(1) == 4
    assert state.normalise_store_workers(12) == 12
    assert state.normalise_store_workers(99) == 32


def test_store_workers_are_normalised_when_saved(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr(state, "settings_path", lambda: path)

    saved = state.save_settings({"store_workers": 99})

    assert saved["store_workers"] == 32
    assert json.loads(path.read_text(encoding="utf-8"))["store_workers"] == 32


def test_compact_audit_uses_persisted_worker_count(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings: dict[str, object] = {
        "store_language": "en",
        "store_workers": 12,
        "cache_enabled": False,
        "cache_ttl_hours": 72,
        "compare_previous": False,
        "exclude_system_source": True,
        "technical_columns": [],
        "qt_header_state": "",
    }
    monkeypatch.setattr(compact_ui, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(compact_ui, "save_settings", lambda values: dict(values))

    captured: dict[str, object] = {}

    class FakeThread:
        def __init__(self, *, target, args, daemon):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self) -> None:
            captured["started"] = True

    monkeypatch.setattr(compact_ui.threading, "Thread", FakeThread)

    window = compact_ui.CompactWindow()
    monkeypatch.setattr(
        window,
        "_get_apps_to_audit",
        lambda: ([{"app_name": "Example", "package_name": "com.example.app"}], set(), "test"),
    )

    window._start_audit()

    args = captured["args"]
    assert isinstance(args, tuple)
    config = args[3]
    assert config.max_workers == 12
    assert window.workers_spin.value() == 12
    assert captured["started"] is True

    window.close()
    app.processEvents()
