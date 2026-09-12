from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtWidgets import QApplication

import playstore_app_audit.services.app_icon_disk_cache as disk_cache
import playstore_app_audit.services.app_icon_metadata as metadata
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.app_icon_loader as icon_loader_ui
import playstore_app_audit.ui.table_window as table_ui
from playstore_app_audit.ui.app_icon_backfill import StoreMetadataRequest
from playstore_app_audit.ui.app_icon_loader import (
    AppIconLoader,
    _IconRequest,
    _normalise_icon_url,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_app_icons_are_on_by_default() -> None:
    assert metadata.DEFAULT_SHOW_APP_ICONS is True
    assert state.DEFAULT_SETTINGS["show_app_icons"] is True


@pytest.mark.parametrize(
    ("saved_value", "expected"),
    [(None, True), (True, True), (False, False)],
)
def test_app_icon_default_preserves_explicit_saved_preference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    saved_value: bool | None,
    expected: bool,
) -> None:
    path = tmp_path / "settings.json"
    if saved_value is not None:
        path.write_text(
            json.dumps({"show_app_icons": saved_value}),
            encoding="utf-8",
        )
    monkeypatch.setattr(state, "settings_path", lambda: path)

    assert state.load_settings()["show_app_icons"] is expected


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


def test_metadata_completion_uses_normalized_store_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def fetch(package: str, *, lang: str, country: str) -> dict[str, str]:
        calls.append((package, lang, country))
        return {
            "icon": "https://example.invalid/backfill.png",
            "developer": "Example Developer",
        }

    monkeypatch.setitem(sys.modules, "google_play_scraper", SimpleNamespace(app=fetch))
    monkeypatch.setattr(
        "playstore_app_audit.services.scraper_transport.install_scraper_transport_timeout",
        lambda: True,
    )
    monkeypatch.setattr(
        "playstore_app_audit.services.store_locale.resolve_store_language",
        lambda language, _country: "it" if language == "auto" else language,
    )

    result = metadata.fetch_store_metadata("com.example.app", "IT", "auto")

    assert calls == [("com.example.app", "it", "it")]
    assert result == {
        "play_icon_url": "https://example.invalid/backfill.png",
        "developer": "Example Developer",
    }


def test_loader_url_normalisation_rejects_non_https() -> None:
    assert _normalise_icon_url("https://example.invalid/icon.png")
    assert _normalise_icon_url("http://example.invalid/icon.png") == ""
    assert _normalise_icon_url("") == ""


def test_clear_icon_cache_removes_index_orphans_temps_and_resets_pruning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    cache_dir = disk_cache.icon_cache_dir()
    cache_dir.mkdir()
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    assert (
        disk_cache.load_cached_icon_bytes(
            "com.example.prime",
            "https://example.invalid/prime.png",
            "",
        )
        is None
    )
    for name in ("orphan.img", "orphan.img.tmp", "unexpected.bin"):
        (cache_dir / name).write_bytes(b"cached")

    assert disk_cache.clear_icon_cache() == 4
    assert not cache_dir.exists()
    assert disk_cache.clear_icon_cache() == 0

    cache_dir.mkdir()
    (cache_dir / "index.json").write_text("{}", encoding="utf-8")
    recreated_orphan = cache_dir / "recreated.img"
    recreated_orphan.write_bytes(b"orphan")
    disk_cache.load_cached_icon_bytes(
        "com.example.after-clear",
        "https://example.invalid/after.png",
        "",
    )
    assert not recreated_orphan.exists()


def test_loader_clear_retires_state_drains_store_and_allows_future_writes(
    app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(icon_loader_ui, "clear_icon_cache", disk_cache.clear_icon_cache)
    original_store = disk_cache.store_cached_icon_bytes
    started = threading.Event()
    release = threading.Event()

    def delayed_store(*args: object) -> None:
        started.set()
        assert release.wait(2)
        original_store(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(icon_loader_ui, "store_cached_icon_bytes", delayed_store)
    loader = AppIconLoader()
    old = _IconRequest(
        "com.example.old",
        "https://example.invalid/old.png",
        "2026-08-20",
        loader.generation,
    )
    loader._cache[old.key] = QIcon()
    loader._queued.append(old)
    loader._pending.add(old.key)
    loader._request_generations[old.key] = old.generation
    loader._failed.add(old.key)
    loader._disk_pool.start(
        icon_loader_ui._DiskStoreTask(
            old,
            b"old-icon",
            loader._disk_signals,
            loader._generation_is_current,
        )
    )
    assert started.wait(2)
    threading.Thread(target=lambda: (time.sleep(0.05), release.set()), daemon=True).start()

    removed = loader.clear_cache(timeout_ms=2_000)

    assert removed >= 1
    assert loader.generation == 1
    assert not disk_cache.icon_cache_dir().exists()
    assert not loader._cache
    assert not loader._queued
    assert not loader._pending
    assert not loader._failed

    current = _IconRequest(
        "com.example.current",
        "https://example.invalid/current.png",
        "2026-08-20",
        loader.generation,
    )
    loader._disk_pool.start(
        icon_loader_ui._DiskStoreTask(
            current,
            b"new-icon",
            loader._disk_signals,
            loader._generation_is_current,
        )
    )
    assert loader._disk_pool.waitForDone(2_000)
    assert disk_cache.cached_icon_metadata(current.package_name)
    loader.deleteLater()
    app.processEvents()


def test_loader_clear_timeout_surfaces_failure_without_deleting_disk_cache(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loader = AppIconLoader()
    monkeypatch.setattr(loader._disk_pool, "waitForDone", lambda _timeout: False)
    deleted: list[bool] = []
    monkeypatch.setattr(icon_loader_ui, "clear_icon_cache", lambda: deleted.append(True))

    with pytest.raises(TimeoutError, match="cache was not cleared"):
        loader.clear_cache(timeout_ms=1)

    assert deleted == []
    loader.deleteLater()
    app.processEvents()


def test_loader_clear_ignores_obsolete_network_completion(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeReply:
        def __init__(self) -> None:
            self.aborted = False
            self.deleted = False

        def isRunning(self) -> bool:
            return not self.aborted

        def abort(self) -> None:
            self.aborted = True

        def error(self) -> QNetworkReply.NetworkError:
            return QNetworkReply.NetworkError.NoError

        def readAll(self) -> QByteArray:
            return QByteArray(b"stale")

        def errorString(self) -> str:
            return ""

        def deleteLater(self) -> None:
            self.deleted = True

    loader = AppIconLoader()
    loader._disk_pool = SimpleNamespace(  # type: ignore[assignment]
        clear=lambda: None,
        waitForDone=lambda _timeout: True,
        activeThreadCount=lambda: 0,
    )
    monkeypatch.setattr(icon_loader_ui, "clear_icon_cache", lambda: 0)
    stale = _IconRequest(
        "com.example.stale",
        "https://example.invalid/stale.png",
        "2026-08-20",
        loader.generation,
    )
    reply = FakeReply()
    loader._pending.add(stale.key)
    loader._request_generations[stale.key] = stale.generation
    loader._active = 1
    loader._active_replies[reply] = stale  # type: ignore[index]

    loader.clear_cache()
    loader._finish(stale, reply)  # type: ignore[arg-type]

    assert reply.aborted and reply.deleted
    assert stale.key not in loader._cache
    assert stale.key not in loader._pending
    loader.deleteLater()
    app.processEvents()


def test_loader_defers_network_manager_until_a_disk_cache_miss(app: QApplication) -> None:
    loader = AppIconLoader()
    try:
        assert loader._manager is None
    finally:
        loader.deleteLater()
        app.processEvents()


def test_cached_icon_remains_available_without_creating_networking(app: QApplication) -> None:
    loader = AppIconLoader()
    item = _IconRequest(
        "com.example.offline",
        "https://example.invalid/icon.png",
        "2026-08-20",
    )
    image = QPixmap(2, 2)
    image.fill(QColor("red"))
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    ready: list[tuple[str, int]] = []
    loader.icon_ready.connect(lambda package, generation: ready.append((package, generation)))
    loader._pending.add(item.key)

    try:
        loader._on_disk_loaded(item, bytes(encoded))

        assert loader._manager is None
        assert loader._cache[item.key].isNull() is False
        assert ready == [("com.example.offline", 0)]
    finally:
        loader.deleteLater()
        app.processEvents()


def test_loader_busy_state_returns_idle_after_disk_worker_finishes(
    app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    package = "com.example.cached"
    url = "https://example.invalid/icon.png"
    image = QPixmap(2, 2)
    image.fill(QColor("blue"))
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    disk_cache.store_cached_icon_bytes(package, url, "2026-08-20", bytes(encoded.data()))

    loader = AppIconLoader()
    states: list[bool] = []
    loader.busy_changed.connect(states.append)
    assert loader.icon_for_row(package, url, "2026-08-20") is None
    deadline = time.monotonic() + 2
    while loader.has_active_work() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    app.processEvents()

    assert loader.has_active_work() is False
    assert states[0] is True and states[-1] is False
    loader.deleteLater()
    app.processEvents()


def test_loader_bounds_pending_requests_for_large_tables(
    app: QApplication,
) -> None:
    loader = AppIconLoader(max_pending=3)
    scheduled: list[object] = []
    loader._disk_pool = SimpleNamespace(start=lambda task: scheduled.append(task))  # type: ignore[assignment]

    try:
        for index in range(10):
            loader.icon_for_row(
                f"com.example.{index}",
                f"https://example.invalid/{index}.png",
                "2026-08-20",
            )

        assert len(loader._pending) == 3
        assert len(scheduled) == 3
    finally:
        loader.deleteLater()
        app.processEvents()


def test_decoded_icon_memory_cache_is_lru_bounded(app: QApplication) -> None:
    loader = AppIconLoader(max_cache=3)
    try:
        for index in range(10):
            loader._remember_in_memory(
                (f"com.example.{index}", f"https://example.invalid/{index}.png", ""),
                QIcon(),
            )

        assert len(loader._cache) == 3
        assert [key[0] for key in loader._cache] == [
            "com.example.7",
            "com.example.8",
            "com.example.9",
        ]
    finally:
        loader.deleteLater()
        app.processEvents()


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


def test_disk_cache_evicts_oldest_entries_to_stay_within_limits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(disk_cache, "MAX_ICON_CACHE_ENTRIES", 10)
    monkeypatch.setattr(disk_cache, "MAX_ICON_CACHE_BYTES", 8)

    for index in range(3):
        disk_cache.store_cached_icon_bytes(
            f"com.example.{index}",
            f"https://example.invalid/{index}.png",
            "2026-08-20",
            b"icon",
        )

    assert disk_cache.cached_icon_metadata("com.example.0") == {}
    assert disk_cache.cached_icon_metadata("com.example.1")["size_bytes"] == 4
    assert disk_cache.cached_icon_metadata("com.example.2")["size_bytes"] == 4
    assert len(list((tmp_path / disk_cache.ICON_CACHE_DIRNAME).glob("*.img"))) == 2


def test_disk_cache_rejects_oversized_images(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(disk_cache, "MAX_CACHED_ICON_BYTES", 4)

    disk_cache.store_cached_icon_bytes(
        "com.example.oversized",
        "https://example.invalid/icon.png",
        "2026-08-20",
        b"12345",
    )

    assert disk_cache.cached_icon_metadata("com.example.oversized") == {}
    assert not list((tmp_path / disk_cache.ICON_CACHE_DIRNAME).glob("*.img"))


def test_disk_cache_never_reads_paths_outside_its_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    cache_dir = tmp_path / disk_cache.ICON_CACHE_DIRNAME
    cache_dir.mkdir()
    outside = tmp_path / "outside.img"
    outside.write_bytes(b"not-an-icon")
    (cache_dir / disk_cache.ICON_INDEX_FILENAME).write_text(
        json.dumps(
            {
                "com.example.unsafe": {
                    "file": "../outside.img",
                    "icon_url": "https://example.invalid/icon.png",
                    "play_last_update": "2026-08-20",
                }
            }
        ),
        encoding="utf-8",
    )

    assert (
        disk_cache.load_cached_icon_bytes(
            "com.example.unsafe",
            "https://example.invalid/icon.png",
            "2026-08-20",
        )
        is None
    )
    assert outside.read_bytes() == b"not-an-icon"


def test_cache_prune_removes_orphans_after_index_corruption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    cache_dir = tmp_path / disk_cache.ICON_CACHE_DIRNAME
    cache_dir.mkdir()
    orphan = cache_dir / "orphan.img"
    orphan.write_bytes(b"orphan")
    (cache_dir / disk_cache.ICON_INDEX_FILENAME).write_text("{broken", encoding="utf-8")

    assert disk_cache.prune_icon_cache() == 1
    assert not orphan.exists()
    assert json.loads((cache_dir / disk_cache.ICON_INDEX_FILENAME).read_text(encoding="utf-8")) == {}


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
        "play_title": "Example App",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "criticality_key": "green",
    }
    model.set_rows([row])
    assert model.rows[0]["play_icon_url"] == "https://example.invalid/icon.png"

    package_index = model.index(0, model.columns.index("package_name"))
    title_index = model.index(0, model.columns.index("play_title"))
    assert model.data(package_index, Qt.ItemDataRole.DecorationRole) is None
    assert model.data(title_index, Qt.ItemDataRole.DecorationRole) is None

    expected = QIcon()
    model._icon_loader = SimpleNamespace(  # type: ignore[assignment]
        icon_for_row=lambda _package, _url, _update: expected
    )
    model.set_app_icons_enabled(True)
    assert model.data(package_index, Qt.ItemDataRole.DecorationRole) is None
    assert model.data(title_index, Qt.ItemDataRole.DecorationRole) is expected

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
                "play_title": "Removed App",
                "play_status": "not_found_in_checked_countries",
                "criticality_key": "red",
            }
        ]
    )
    title_index = model.index(0, model.columns.index("play_title"))
    assert "play_icon_url" not in model.rows[0]
    assert model.data(title_index, Qt.ItemDataRole.DecorationRole) is None

    model.deleteLater()
    app.processEvents()


def test_icon_ready_updates_only_rows_indexed_for_the_package(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    model = table_ui.AuditTableModel()

    class TrackingRows(list[dict[str, object]]):
        iterations = 0

        def __iter__(self):
            self.iterations += 1
            return super().__iter__()

    rows = TrackingRows(
        {
            "package_name": f"com.example.{index}",
            "play_status": "available",
            "play_icon_url": f"https://example.invalid/{index}.png",
        }
        for index in range(10_000)
    )
    model.set_rows(rows)
    rows.iterations = 0
    changed_rows: list[int] = []
    model.dataChanged.connect(lambda top, _bottom, _roles: changed_rows.append(top.row()))

    model._on_icon_ready("com.example.7777", model._icon_generation - 1)
    assert changed_rows == []
    model._on_icon_ready("com.example.7777", model._icon_generation)

    assert rows.iterations == 0
    assert changed_rows == [7777]
    model.deleteLater()
    app.processEvents()


def test_icon_generation_retires_stale_queue_and_ignores_disk_completion(
    app: QApplication,
) -> None:
    loader = AppIconLoader()
    cleared: list[bool] = []
    loader._disk_pool = SimpleNamespace(  # type: ignore[assignment]
        start=lambda _task: None,
        clear=lambda: cleared.append(True),
    )
    old = _IconRequest(
        "com.example.old",
        "https://example.invalid/old.png",
        "2026-08-20",
        loader.generation,
    )
    loader._queued.append(old)
    loader._pending.add(old.key)
    loader._request_generations[old.key] = old.generation
    image = QPixmap(2, 2)
    image.fill(QColor("red"))
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    ready: list[tuple[str, int]] = []
    loader.icon_ready.connect(lambda package, generation: ready.append((package, generation)))

    generation = loader.begin_generation()
    loader._on_disk_loaded(old, bytes(encoded))

    assert generation == 1
    assert cleared == [True]
    assert not loader._queued
    assert not loader._pending
    assert old.key not in loader._cache
    assert ready == []
    loader.deleteLater()
    app.processEvents()


def test_icon_generation_aborts_and_ignores_stale_network_but_current_completes(
    app: QApplication,
) -> None:
    class FakeReply:
        def __init__(self, data: bytes) -> None:
            self.data = data
            self.aborted = False
            self.deleted = False

        def isRunning(self) -> bool:
            return not self.aborted

        def abort(self) -> None:
            self.aborted = True

        def error(self) -> QNetworkReply.NetworkError:
            return QNetworkReply.NetworkError.NoError

        def readAll(self) -> QByteArray:
            return QByteArray(self.data)

        def errorString(self) -> str:
            return ""

        def deleteLater(self) -> None:
            self.deleted = True

    image = QPixmap(2, 2)
    image.fill(QColor("green"))
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    assert buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()

    loader = AppIconLoader()
    stored: list[object] = []
    loader._disk_pool = SimpleNamespace(  # type: ignore[assignment]
        start=stored.append,
        clear=lambda: None,
    )
    ready: list[tuple[str, int]] = []
    loader.icon_ready.connect(lambda package, generation: ready.append((package, generation)))
    old = _IconRequest(
        "com.example.old",
        "https://example.invalid/old.png",
        "2026-08-20",
        loader.generation,
    )
    old_reply = FakeReply(bytes(encoded))
    loader._pending.add(old.key)
    loader._request_generations[old.key] = old.generation
    loader._active = 1
    loader._active_replies[old_reply] = old  # type: ignore[index]

    generation = loader.begin_generation()
    assert old_reply.aborted
    loader._finish(old, old_reply)  # type: ignore[arg-type]

    current = _IconRequest(
        "com.example.current",
        "https://example.invalid/current.png",
        "2026-08-20",
        generation,
    )
    current_reply = FakeReply(bytes(encoded))
    loader._pending.add(current.key)
    loader._request_generations[current.key] = generation
    loader._active = 1
    loader._active_replies[current_reply] = current  # type: ignore[index]
    loader._finish(current, current_reply)  # type: ignore[arg-type]

    assert old.key not in loader._cache
    assert current.key in loader._cache
    assert ready == [("com.example.current", generation)]
    assert len(stored) == 1
    loader.deleteLater()
    app.processEvents()


def test_result_generation_preserves_icon_caches_and_is_not_reset_by_set_rows(
    app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    monkeypatch.setattr(disk_cache, "app_data_dir", lambda: tmp_path)
    package = "com.example.cached"
    url = "https://example.invalid/cached.png"
    update = "2026-08-20"
    disk_cache.store_cached_icon_bytes(package, url, update, b"persistent")
    model = table_ui.AuditTableModel()
    metadata_tasks: list[Any] = []
    model._metadata_backfill._pool = SimpleNamespace(  # type: ignore[assignment]
        start=metadata_tasks.append,
        clear=lambda: None,
    )
    model.set_store_context_provider(lambda: ("it", "en"))
    memory_key = (package, url, update)
    pixmap = QPixmap(2, 2)
    pixmap.fill(QColor("blue"))
    model._icon_loader._remember_in_memory(memory_key, QIcon(pixmap))

    generation = model.begin_result_generation()
    model.set_rows([{"package_name": "one"}])
    model.set_rows(
        [
            {
                "package_name": "com.example.current-generation",
                "play_status": "available",
            }
        ]
    )

    assert model._icon_generation == generation
    assert model._icon_loader.generation == generation
    assert memory_key in model._icon_loader._cache
    assert not model._icon_loader._cache[memory_key].isNull()
    assert disk_cache.load_cached_icon_bytes(package, url, update) == b"persistent"
    assert len(metadata_tasks) == 1
    assert metadata_tasks[0]._request.generation == model._metadata_backfill._generation
    model.deleteLater()
    app.processEvents()


def test_available_rows_schedule_one_metadata_backfill_per_package(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    model = table_ui.AuditTableModel()
    tasks: list[object] = []
    model._metadata_backfill._pool = SimpleNamespace(  # type: ignore[assignment]
        start=lambda task: tasks.append(task),
        clear=lambda: None,
    )
    model.set_store_context_provider(lambda: ("it", "en"))
    model.set_rows(
        [
            {
                "package_name": "com.example.legacy",
                "play_status": "available",
                "play_last_update": "2026-08-01",
                "cache_hit": False,
            },
            {
                "package_name": "com.example.legacy",
                "play_status": "available",
                "play_last_update": "2026-08-01",
                "cache_hit": True,
            },
            {
                "package_name": "com.example.modern",
                "play_status": "available",
                "play_icon_url": "https://example.invalid/modern.png",
                "cache_hit": True,
            },
            {
                "package_name": "com.example.missing",
                "play_status": "not_found_in_checked_countries",
                "cache_hit": True,
            },
        ]
    )

    assert len(tasks) == 1
    model.deleteLater()
    app.processEvents()


def test_metadata_backfill_manager_deduplicates_without_blocking_ui(
    app: QApplication,
) -> None:
    manager = table_ui.StoreMetadataBackfill()
    tasks: list[object] = []
    manager._pool = SimpleNamespace(  # type: ignore[assignment]
        start=lambda task: tasks.append(task),
        clear=lambda: None,
    )

    try:
        assert manager.schedule("com.example.app", "IT", "auto")
        assert not manager.schedule("com.example.app", "it", "auto")
        assert len(tasks) == 1
        manager.cancel()
        assert not manager.schedule("com.example.other", "it", "auto")
    finally:
        manager.cancel()
        manager.deleteLater()
        app.processEvents()


def test_successful_metadata_backfill_updates_rows_cache_and_normal_icon_loader(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata.clear_icon_metadata()
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    persisted: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        state,
        "update_cached_store_metadata",
        lambda *args: persisted.append(args) or True,
    )
    model = table_ui.AuditTableModel()
    monkeypatch.setattr(model._metadata_backfill, "schedule", lambda *_args: False)
    model.set_rows(
        [
            {
                "package_name": "com.example.app",
                "play_status": "available",
                "play_last_update": "2026-08-01",
                "cache_hit": True,
            }
        ]
    )
    model.set_store_context_provider(lambda: ("it", "en"))
    loaded: list[tuple[object, object, object]] = []
    expected = QIcon()
    model._icon_loader = SimpleNamespace(  # type: ignore[assignment]
        icon_for_row=lambda *args: loaded.append(args) or expected
    )
    request = StoreMetadataRequest("com.example.app", "it", "en")

    model._on_metadata_backfilled(
        request,
        {
            "play_icon_url": "https://example.invalid/backfilled.png",
            "developer": "Example Developer",
        },
    )

    assert model.rows[0]["play_icon_url"] == "https://example.invalid/backfilled.png"
    assert model.rows[0]["developer"] == "Example Developer"
    assert len(persisted) == 1
    assert loaded == [
        (
            "com.example.app",
            "https://example.invalid/backfilled.png",
            "2026-08-01",
        )
    ]
    model.deleteLater()
    app.processEvents()


def test_failed_metadata_backfill_leaves_audit_row_untouched(
    app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(state, "load_settings", lambda: {"show_app_icons": True})
    model = table_ui.AuditTableModel()
    monkeypatch.setattr(model._metadata_backfill, "schedule", lambda *_args: False)
    row = {
        "package_name": "com.example.app",
        "play_status": "available",
        "play_last_update": "2026-08-01",
        "play_version": "5.0",
        "criticality": "Recent Update",
        "criticality_key": "green",
        "criticality_rank": 5,
        "local_apk_version_comparison": "Outdated",
        "health_score": 90,
        "cache_hit": True,
    }
    model.set_rows([row])
    model.set_store_context_provider(lambda: ("it", "en"))
    before = dict(row)

    model._on_metadata_backfilled(StoreMetadataRequest("com.example.app", "it", "en"), {})

    assert row == before
    model.deleteLater()
    app.processEvents()


def test_targeted_cache_metadata_update_preserves_original_fetched_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_path)
    state.update_cache(
        [
            {
                "package_name": "com.example.legacy",
                "play_status": "available",
                "play_last_update": "2026-08-01",
            }
        ],
        "it",
        "en",
    )
    before = json.loads(cache_path.read_text(encoding="utf-8"))
    fetched_at = next(iter(before.values()))["fetched_at"]

    assert state.update_cached_store_metadata(
        "com.example.legacy",
        "it",
        "en",
        {
            "play_icon_url": "https://example.invalid/backfilled.png",
            "developer": "Example Developer",
        },
    )

    after = json.loads(cache_path.read_text(encoding="utf-8"))
    entry = next(iter(after.values()))
    assert entry["fetched_at"] == fetched_at
    assert entry["row"]["play_icon_url"] == "https://example.invalid/backfilled.png"


def test_healthy_cache_roundtrip_retains_canonical_store_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_path = tmp_path / "audit_cache.json"
    monkeypatch.setattr(state, "cache_path", lambda: cache_path)
    state.update_cache(
        [
            {
                "package_name": "com.example.cached",
                "play_status": "available",
                "play_last_update": "2026-08-01",
                "play_icon_url": "https://example.invalid/canonical.png",
                "developer": "Canonical Developer",
            }
        ],
        "it",
        "en",
    )

    loaded = state.load_fresh_cache(
        [{"app_name": "Example", "package_name": "com.example.cached"}],
        "it",
        "en",
        72,
    )["com.example.cached"]

    assert loaded["play_icon_url"] == "https://example.invalid/canonical.png"
    assert loaded["developer"] == "Canonical Developer"
