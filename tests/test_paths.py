from __future__ import annotations

from pathlib import Path

from playstore_app_audit.platform import runtime


def test_default_data_path_is_platform_specific(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime, "platform_key", lambda: "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert runtime.default_app_data_dir() == tmp_path / runtime.APP_DIR_NAME


def test_portable_marker_switches_active_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(runtime, "executable_dir", lambda: tmp_path)
    normal = tmp_path / "normal"
    monkeypatch.setattr(runtime, "default_app_data_dir", lambda: normal)
    assert runtime.app_data_dir() == normal
    runtime.portable_marker().write_text("portable", encoding="utf-8")
    assert runtime.app_data_dir() == tmp_path / "PlayStoreAppAudit-data"
