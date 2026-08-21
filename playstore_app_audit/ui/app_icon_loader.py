from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl, Signal
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


class AppIconLoader(QObject):
    """Lazy icon loader with bounded RAM plus long-lived disk reuse.

    Decoded QIcon objects remain bounded to the current session. Raw image bytes
    are persisted separately and reused until a later Store fetch reports a
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

        persisted = load_cached_icon_bytes(package, url, update)
        if persisted:
            pixmap = QPixmap()
            if pixmap.loadFromData(persisted) and not pixmap.isNull():
                icon = QIcon(pixmap)
                self._remember_in_memory(item.key, icon)
                return icon

        if item.key in self._failed or item.key in self._pending:
            return None
        self._pending.add(item.key)
        self._queued.append(item)
        self._pump()
        return None

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
                        icon = QIcon(pixmap)
                        self._remember_in_memory(item.key, icon)
                        try:
                            store_cached_icon_bytes(
                                item.package_name,
                                item.url,
                                item.play_last_update,
                                data,
                            )
                        except OSError:
                            # Disk persistence is an optimization. A valid icon
                            # should still render even if local storage fails.
                            pass
                        self.icon_ready.emit(item.url)
                        return
            self._failed.add(item.key)
        finally:
            self._pending.discard(item.key)
            self._active = max(0, self._active - 1)
            reply.deleteLater()
            self._pump()
