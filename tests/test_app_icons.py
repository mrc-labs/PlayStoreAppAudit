from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.app_icon_disk_cache as disk_cache
import playstore_app_audit.services.app_icon_metadata as metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.app_icon_loader as icon_loader_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.ui.app_icon_loader import AppIconLoader, _normalise_icon_url


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_app_icons_are_off_by_default() -> None:
    assert state.DEFAULT_SETTINGS["show_app_icons"] is False


def test_icon_metadata_accepts_only_https_urls() -> None:
    metadata.clear_icon_metadata()
    metadata._remember_result_icon(
        {"appId": "com.example.good", "icon": "https://example.invalid/icon.png"}
    )
    metadata._remember_result_icon(
        {"appId": "com.example.bad", "icon": "http://example.invalid/icon.png"}
    )

    assert metadata.icon_url_for_package("com.example.good") == "https://example.invalid/icon.png"
    assert metadata.icon_url_for_package("com.example.bad") == ""


def test_live_available_rows_receive_icon_url_for_normal_cache_write() -> None:
    metadata.clear_icon_metadata()
    metadata._remember_result_icon(
        {"appId": "com.example.app", "icon": "https://example.invalid/icon.png"}
    )
    rows = [
        {
            "package_name": "com.example.app",
            "play_status": "available",
            "play_last_update": "2026-08-01",
        }
    ]

    result = metadata._enrich_rows_with_icon_urls(rows)

    assert result is rows
    assert rows[0]["play_icon_url"] == "https://example.invalid/icon.png"


def test_unavailable_rows_do_not_receive_captured_icon_url() -> None:
    metadata.clear_icon_metadata()
    metadata._remember_result_icon(
        {"appId": "com.example.removed", "icon": "https://example.invalid/icon.png"}
    )
    rows = [
        {
            "package_name": "com.example.removed",
            "play_status": "not_found_in_checked_countries",
        }
    ]

    metadata._enrich_rows_with_icon_urls(rows)

    assert "play_icon_url" not in rows[0]


def test_existing_https_icon_metadata_is_preserved() -> None:
    metadata.clear_icon_metadata()
    metadata._remember_result_icon(
        {"appId": "com.example.app", "icon": "https://example.invalid/new.png"}
    )
    rows = [
        {
            "package_name": "com.example.app",
            "play_status": "available",
            "play_icon_url": "https://example.invalid/cached.png",
        }
    ]

    metadata._enrich_rows_with_icon_urls(rows)

    assert rows[0]["play_icon_url"] == "https://example.invalid/cached.png"


def test_loader_url_normalisation_rejects_non_https() -> None:
    assert _normalise_icon_url("https://example.invalid/icon.png")
    assert _normalise_icon_url("http://example.invalid/icon.png") == ""
    assert _normalise_icon_url("") == ""


def test_icon_lookup_schedules_disk_io_without_blocking_ui(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = AppIconLoader()
    scheduled: list[object] = []

    def fail_if_called_synchronously(*_args: object) -> bytes | None:
        raise AssertionError("persistent icon cache read ran synchronously on the UI path")

    monkeypatch.setattr(icon_loader_ui, "load_cached_icon_bytes", fail_if_called_synchronously)
    loader._disk_pool = SimpleNamespace(start=lambda task: scheduled.append(task))  # type: ignore[assignment]

    result = loader.icon_for_row(
        "com.example.lazy",
        "https://example.invalid/icon.png",
        "2026-08-20",
    )

    assert result is None
    assert len(scheduled) == 1
    loader.deleteLater()
    app.processEvents()


def test_disk_backend_error_falls_through_to_network_queue(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    loader = AppIconLoader()
    pumped: list[bool] = []

    def fail_disk_read(*_args: object) -> bytes | None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(icon_loader_ui, "load_cached_icon_bytes", fail_disk_read)
    monkeypatch.setattr(loader, "_pump", lambda: pumped.append(True))
    loader._disk_pool = SimpleNamespace(start=lambda task: task.run())  # type: ignore[assignment]

    try:
        result = loader.icon_for_row(
            "com.example.disk-failure",
            "https://example.invalid/icon.png",
            "2026-08-20",
        )

        assert result is None
        assert pumped == [True]
        assert len(loader._queued) == 1
        queued = loader._queued[0]
        assert queued.key in loader._pending
    finally:
        loader.deleteLater()
        app.processEvents()


def test_persisted_icon_is_reused_while_app_update_is_unchanged(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    package = "com.example.persisted"
    first_url = "https://example.invalid/icon-v1.png"
    changed_cdn_url = "https://cdn.example.invalid/icon-v1.png"
    update = "2026-08-01"
    image_bytes = b"fake-image-bytes"

    disk_cache.store_cached_icon_bytes(package, first_url, update, image_bytes)

    assert disk_cache.load_cached_icon_bytes(package, first_url, update) == image_bytes
    assert disk_cache.load_cached_icon_bytes(package, changed_cdn_url, update) == image_bytes
    record = disk_cache.cached_icon_metadata(package)
    assert record["play_last_update"] == update


def test_persisted_icon_is_invalidated_when_app_update_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    package = "com.example.updated"
    url = "https://example.invalid/icon.png"
    disk_cache.store_cached_icon_bytes(package, url, "2026-08-01", b"old-icon")

    assert disk_cache.load_cached_icon_bytes(package, url, "2026-08-20") is None
    assert disk_cache.cached_icon_metadata(package) == {}


def test_persisted_icon_without_update_marker_requires_same_url(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    package = "com.example.unknown-update"
    url = "https://example.invalid/icon.png"
    disk_cache.store_cached_icon_bytes(package, url, "", b"icon")

    assert disk_cache.load_cached_icon_bytes(package, url, "") == b"icon"
    assert (
        disk_cache.load_cached_icon_bytes(
            package,
            "https://example.invalid/different.png",
            "",
        )
        is None
    )


def test_disk_cache_directory_failure_degrades_to_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("blocked", encoding="utf-8")
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: blocker)

    disk_cache.store_cached_icon_bytes(
        "com.example.blocked",
        "https://example.invalid/icon.png",
        "2026-08-20",
        b"icon",
    )

    assert (
        disk_cache.load_cached_icon_bytes(
            "com.example.blocked",
            "https://example.invalid/icon.png",
            "2026-08-20",
        )
        is None
    )
    assert disk_cache.cached_icon_metadata("com.example.blocked") == {}


def test_index_write_failure_does_not_leave_orphan_icon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    original_write_text = Path.write_text

    def fail_index_write(path: Path, *args: object, **kwargs: object) -> int:
        if path.name == "index.json.tmp":
            raise OSError("index is not writable")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_index_write)
    disk_cache.store_cached_icon_bytes(
        "com.example.index-failure",
        "https://example.invalid/icon.png",
        "2026-08-20",
        b"icon",
    )

    assert disk_cache.cached_icon_metadata("com.example.index-failure") == {}
    assert not list((tmp_path / disk_cache.ICON_CACHE_DIRNAME).glob("*.img"))


def test_table_icons_are_opt_in_and_use_captured_metadata(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": False})
    monkeypatch.setattr(
        metadata,
        "icon_url_for_package",
        lambda package: "https://example.invalid/icon.png" if package == "com.example.app" else "",
    )

    model = table_ui.AuditTableModel()
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "criticality_key": "green",
    }
    model.set_rows([row])
    assert model.rows[0]["play_icon_url"] == "https://example.invalid/icon.png"

    package_column = model.columns.index("package_name")
    index = model.index(0, package_column)
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is None

    expected = QIcon()
    model._icon_loader = SimpleNamespace(  # type: ignore[assignment]
        icon_for_row=lambda _package, _url, _update: expected
    )
    model.set_app_icons_enabled(True)
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is expected

    model.deleteLater()
    app.processEvents()


def test_unavailable_rows_do_not_show_stale_icons(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    monkeypatch.setattr(
        metadata,
        "icon_url_for_package",
        lambda _package: "https://example.invalid/icon.png",
    )

    model = table_ui.AuditTableModel()
    model.set_rows(
        [
            {
                "package_name": "com.example.removed",
                "play_status": "not_found_in_checked_countries",
                "criticality_key": "red",
            }
        ]
    )
    package_column = model.columns.index("package_name")
    index = model.index(0, package_column)
    assert "play_icon_url" not in model.rows[0]
    assert model.data(index, Qt.ItemDataRole.DecorationRole) is None

    model.deleteLater()
    app.processEvents()
