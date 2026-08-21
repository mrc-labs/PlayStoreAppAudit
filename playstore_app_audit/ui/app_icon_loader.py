from __future__ import annotations

from collections import OrderedDict, deque
from contextlib import suppress
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QUrl, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from playstore_app_audit.services.app_icon_disk_cache import (
    load_cached_icon_bytes,
    store_cached_icon_bytes,
)

MAX_ICON_BYTES = 1_000_000
DEFAULT_ICON_CACHE_SIZE = 96
DEFAULT_ICON_CONCURRENCY = 4
ICON_TIMEOUT_MS = 10_000


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

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.package_name, self.url, self.play_last_update)


class _DiskSignals(QObject):
    loaded = Signal(object, object)


class _DiskLoadTask(QRunnable):
    def __init__(self, item: _IconRequest, signals: _DiskSignals) -> None:
        super().__init__()
        self._item = item
        self._signals = signals

    def run(self) -> None:
        data = load_cached_icon_bytes(
            self._item.package_name,
            self._item.url,
            self._item.play_last_update,
        )
        self._signals.loaded.emit(self._item, data)


class _DiskStoreTask(QRunnable):
    def __init__(self, item: _IconRequest, data: bytes) -> None:
        super().__init__()
        self._item = item
        self._data = data

    def run(self) -> None:
        with suppress(OSError):
            store_cached_icon_bytes(
                self._item.package_name,
                self._item.url,
                self._item.play_last_update,
                self._data,
            )


class AppIconLoader(QObject):
    """Lazy icon loader with bounded RAM plus long-lived disk reuse.

    The table never waits for icon I/O. Decoded QIcon objects remain bounded to
    the current session, while raw image bytes are loaded/stored on a dedicated
    single-thread disk queue and reused until a later Store fetch reports a
    different play_last_update value. If no update marker exists, URL equality
    is used as the conservative fallback invalidation rule.
    """

    icon_ready = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_active: int = DEFAULT_ICON_CONCURRENCY,
        max_cache: int = DEFAULT_ICON_CACHE_SIZE,
    ) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._max_active = max(1, int(max_active))
        self._max_cache = max(1, int(max_cache))
        self._active = 0
        self._queued: deque[_IconRequest] = deque()
        self._pending: set[tuple[str, str, str]] = set()
        self._failed: set[tuple[str, str, str]] = set()
        self._cache: OrderedDict[tuple[str, str, str], QIcon] = OrderedDict()

        # A single worker keeps index.json reads/writes serialized while making
        # all persistent-cache file I/O independent from Qt table painting.
        self._disk_pool = QThreadPool(self)
        self._disk_pool.setMaxThreadCount(1)
        self._disk_signals = _DiskSignals(self)
        self._disk_signals.loaded.connect(self._on_disk_loaded)

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

        item = _IconRequest(package, url, update)
        icon = self._cache.get(item.key)
        if icon is not None:
            self._cache.move_to_end(item.key)
            return icon

        if item.key in self._failed or item.key in self._pending:
            return None

        # Return immediately so the table can paint and remain interactive.
        # Disk lookup happens asynchronously; only a cache miss reaches network.
        self._pending.add(item.key)
        self._disk_pool.start(_DiskLoadTask(item, self._disk_signals))
        return None

    def _on_disk_loaded(self, item: _IconRequest, data: bytes | None) -> None:
        if item.key not in self._pending:
            return

        if data:
            pixmap = QPixmap()
            if pixmap.loadFromData(data) and not pixmap.isNull():
                self._remember_in_memory(item.key, QIcon(pixmap))
                self._pending.discard(item.key)
                self.icon_ready.emit(item.url)
                return

        # Cache miss or unreadable image. Keep the request marked pending and
        # continue asynchronously through the bounded network queue.
        self._queued.append(item)
        self._pump()

    def _remember_in_memory(self, key: tuple[str, str, str], icon: QIcon) -> None:
        self._cache[key] = icon
        self._cache.move_to_end(key)
        while len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)

    def _pump(self) -> None:
        while self._active < self._max_active and self._queued:
            item = self._queued.popleft()
            request = QNetworkRequest(QUrl(item.url))
            request.setTransferTimeout(ICON_TIMEOUT_MS)
            request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
            reply = self._manager.get(request)
            self._active += 1
            reply.finished.connect(lambda r=reply, i=item: self._finish(i, r))

    def _finish(self, item: _IconRequest, reply: QNetworkReply) -> None:
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = bytes(reply.readAll())
                if data and len(data) <= MAX_ICON_BYTES:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(data) and not pixmap.isNull():
                        self._remember_in_memory(item.key, QIcon(pixmap))
                        self._disk_pool.start(_DiskStoreTask(item, data))
                        self.icon_ready.emit(item.url)
                        return
            self._failed.add(item.key)
        finally:
            self._pending.discard(item.key)
            self._active = max(0, self._active - 1)
            reply.deleteLater()
            self._pump()
