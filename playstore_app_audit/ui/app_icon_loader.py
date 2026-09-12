from __future__ import annotations

import logging
from collections import OrderedDict, deque
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import cast

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from playstore_app_audit.services.app_icon_disk_cache import (
    MAX_CACHED_ICON_BYTES,
    clear_icon_cache,
    load_cached_icon_bytes,
    store_cached_icon_bytes,
)

logger = logging.getLogger(__name__)

MAX_ICON_BYTES = MAX_CACHED_ICON_BYTES
DEFAULT_ICON_CACHE_SIZE = 96
DEFAULT_ICON_CONCURRENCY = 4
DEFAULT_MAX_PENDING = 256
ICON_TIMEOUT_MS = 10_000
ICON_CACHE_CLEAR_TIMEOUT_MS = 5_000


def _normalise_icon_url(value: object) -> str:
    text = str(value or "").strip()
    url = QUrl(text)
    if not text or not url.isValid() or url.scheme().lower() != "https":
        return ""
    return url.toString()


@dataclass(slots=True, frozen=True)
class _IconRequest:
    package_name: str
    url: str
    play_last_update: str
    generation: int = 0

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.package_name, self.url, self.play_last_update)


class _DiskSignals(QObject):
    loaded = Signal(object, object)
    stored = Signal()


class _DiskLoadTask(QRunnable):
    def __init__(self, item: _IconRequest, signals: _DiskSignals) -> None:
        super().__init__()
        self._item = item
        self._signals = signals

    def run(self) -> None:
        data: bytes | None = None
        try:
            data = load_cached_icon_bytes(
                self._item.package_name,
                self._item.url,
                self._item.play_last_update,
            )
        except Exception:
            # Disk cache is an optional acceleration layer. Even an unexpected
            # backend failure must complete this task so the request can fall
            # through to the bounded network queue instead of staying pending.
            data = None
        self._signals.loaded.emit(self._item, data)


class _DiskStoreTask(QRunnable):
    def __init__(
        self,
        item: _IconRequest,
        data: bytes,
        signals: _DiskSignals,
        generation_is_current: Callable[[int], bool],
    ) -> None:
        super().__init__()
        self._item = item
        self._data = data
        self._signals = signals
        self._generation_is_current = generation_is_current

    def run(self) -> None:
        try:
            if self._generation_is_current(self._item.generation):
                with suppress(OSError):
                    store_cached_icon_bytes(
                        self._item.package_name,
                        self._item.url,
                        self._item.play_last_update,
                        self._data,
                    )
        finally:
            self._signals.stored.emit()


class AppIconLoader(QObject):
    """Lazy icon loader with bounded RAM, work queues and disk reuse.

    The table never waits for icon I/O. Decoded QIcon objects remain bounded to
    the current session, while raw image bytes are loaded/stored on a dedicated
    single-thread disk queue and reused until a later Store fetch reports a
    different play_last_update value. If no update marker exists, URL equality
    is used as the conservative fallback invalidation rule.
    """

    icon_ready = Signal(str, int)
    busy_changed = Signal(bool)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_active: int = DEFAULT_ICON_CONCURRENCY,
        max_cache: int = DEFAULT_ICON_CACHE_SIZE,
        max_pending: int = DEFAULT_MAX_PENDING,
    ) -> None:
        super().__init__(parent)
        self._manager: QNetworkAccessManager | None = None
        self._max_active = max(1, int(max_active))
        self._max_cache = max(1, int(max_cache))
        self._max_pending = max(1, int(max_pending))
        self._active = 0
        self._queued: deque[_IconRequest] = deque()
        self._pending: set[tuple[str, str, str]] = set()
        self._request_generations: dict[tuple[str, str, str], int] = {}
        self._failed: set[tuple[str, str, str]] = set()
        self._cache: OrderedDict[tuple[str, str, str], QIcon] = OrderedDict()
        self._generation = 0
        self._active_replies: dict[QNetworkReply, _IconRequest] = {}
        self._reported_busy = False

        # A single worker keeps index.json reads/writes serialized while making
        # all persistent-cache file I/O independent from Qt table painting.
        self._disk_pool = QThreadPool(self)
        self._disk_pool.setMaxThreadCount(1)
        self._disk_signals = _DiskSignals(self)
        self._disk_signals.loaded.connect(self._on_disk_loaded)
        self._disk_signals.stored.connect(self._on_disk_store_finished)

    @property
    def generation(self) -> int:
        return self._generation

    def has_active_work(self) -> bool:
        active_thread_count = getattr(self._disk_pool, "activeThreadCount", None)
        disk_active = bool(active_thread_count()) if callable(active_thread_count) else False
        return bool(
            self._queued
            or self._pending
            or self._active_replies
            or disk_active
        )

    def _notify_busy_if_changed(self) -> None:
        busy = self.has_active_work()
        if busy == self._reported_busy:
            return
        self._reported_busy = busy
        self.busy_changed.emit(busy)

    def _notify_busy_after_worker_return(self) -> None:
        # Worker signals are emitted just before QRunnable.run() returns. Defer
        # the pool-state check one event-loop turn so activeThreadCount() cannot
        # leave the maintenance action stuck in a false-busy state.
        QTimer.singleShot(0, self._notify_busy_if_changed)

    def _generation_is_current(self, generation: int) -> bool:
        return generation == self._generation

    def begin_generation(self) -> int:
        """Retire I/O for an obsolete logical result set while preserving caches."""

        self._generation += 1
        self._queued.clear()
        self._pending.clear()
        self._request_generations.clear()
        self._failed.clear()
        self._disk_pool.clear()
        for reply in tuple(self._active_replies):
            if reply.isRunning():
                reply.abort()
        self._notify_busy_if_changed()
        return self._generation

    def clear_cache(self, timeout_ms: int = ICON_CACHE_CLEAR_TIMEOUT_MS) -> int:
        """Retire RAM/network work and safely clear the persistent icon cache.

        The disk pool has one worker. Queued work is discarded and a bounded
        wait drains any task that was already running before disk deletion. A
        timeout is reported instead of risking a stale write after the clear.
        """

        self.begin_generation()
        self._cache.clear()
        if not self._disk_pool.waitForDone(max(0, int(timeout_ms))):
            self._notify_busy_if_changed()
            raise TimeoutError(
                "App icon disk work did not stop within the safety timeout; "
                "the cache was not cleared."
            )
        removed = clear_icon_cache()
        self._notify_busy_if_changed()
        return removed

    def icon_for_row(
        self,
        package_name: object,
        icon_url: object,
        play_last_update: object,
    ) -> QIcon | None:
        package = str(package_name or "").strip()
        url = _normalise_icon_url(icon_url)
        update = str(play_last_update or "").strip()
        if not package or not url:
            return None

        item = _IconRequest(package, url, update, self._generation)
        icon = self._cache.get(item.key)
        if icon is not None:
            self._cache.move_to_end(item.key)
            return icon

        if item.key in self._failed or item.key in self._pending:
            return None
        if len(self._pending) >= self._max_pending:
            return None

        # Return immediately so the table can paint and remain interactive.
        # Disk lookup happens asynchronously; only a cache miss reaches network.
        self._pending.add(item.key)
        self._request_generations[item.key] = item.generation
        self._disk_pool.start(_DiskLoadTask(item, self._disk_signals))
        self._notify_busy_if_changed()
        return None

    def _on_disk_loaded(self, item: _IconRequest, data: bytes | None) -> None:
        if (
            item.generation != self._generation
            or item.key not in self._pending
            or self._request_generations.get(item.key, item.generation) != item.generation
        ):
            self._notify_busy_after_worker_return()
            return

        if data:
            pixmap = QPixmap()
            if pixmap.loadFromData(data) and not pixmap.isNull():
                logger.debug("App icon disk cache hit: package=%s", item.package_name)
                self._remember_in_memory(item.key, QIcon(pixmap))
                self._pending.discard(item.key)
                self._request_generations.pop(item.key, None)
                self.icon_ready.emit(item.package_name, item.generation)
                self._notify_busy_after_worker_return()
                return
            logger.debug("App icon disk decode failed: package=%s", item.package_name)
        else:
            logger.debug("App icon disk cache miss: package=%s", item.package_name)

        # Cache miss, unreadable image or disk failure. Keep the request marked
        # pending while it continues asynchronously through the network queue.
        self._queued.append(item)
        self._pump()
        self._notify_busy_if_changed()

    def _on_disk_store_finished(self) -> None:
        self._notify_busy_after_worker_return()

    def _remember_in_memory(self, key: tuple[str, str, str], icon: QIcon) -> None:
        self._cache[key] = icon
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)

    def _pump(self) -> None:
        while self._active < self._max_active and self._queued:
            item = self._queued.popleft()
            if (
                item.generation != self._generation
                or self._request_generations.get(item.key) != item.generation
            ):
                continue
            request = QNetworkRequest(QUrl(item.url))
            request.setTransferTimeout(ICON_TIMEOUT_MS)
            request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
            reply = self._network_manager().get(request)
            self._active += 1
            self._active_replies[reply] = item
            reply.downloadProgress.connect(
                lambda received, _total, r=reply: self._abort_oversized(r, received)
            )
            reply.finished.connect(lambda r=reply, i=item: self._finish(i, r))
        self._notify_busy_if_changed()

    def _network_manager(self) -> QNetworkAccessManager:
        if self._manager is None:
            self._manager = QNetworkAccessManager(self)
        return self._manager

    @staticmethod
    def _abort_oversized(reply: QNetworkReply, received: int) -> None:
        if received > MAX_ICON_BYTES and reply.isRunning():
            reply.abort()

    def _finish(self, item: _IconRequest, reply: QNetworkReply) -> None:
        try:
            if item.generation != self._generation:
                return
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = cast(bytes, reply.readAll().data())
                if data and len(data) <= MAX_ICON_BYTES:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(data) and not pixmap.isNull():
                        self._remember_in_memory(item.key, QIcon(pixmap))
                        self._disk_pool.start(
                            _DiskStoreTask(
                                item,
                                data,
                                self._disk_signals,
                                self._generation_is_current,
                            )
                        )
                        self.icon_ready.emit(item.package_name, item.generation)
                        return
                    logger.debug(
                        "App icon network decode failed: package=%s bytes=%d",
                        item.package_name,
                        len(data),
                    )
            logger.debug(
                "App icon download failed: package=%s error=%s",
                item.package_name,
                reply.errorString(),
            )
            self._failed.add(item.key)
        finally:
            if self._request_generations.get(item.key) == item.generation:
                self._pending.discard(item.key)
                self._request_generations.pop(item.key, None)
            self._active = max(0, self._active - 1)
            self._active_replies.pop(reply, None)
            reply.deleteLater()
            self._pump()
            self._notify_busy_if_changed()
