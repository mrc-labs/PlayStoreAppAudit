from __future__ import annotations

from collections import OrderedDict, deque

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

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


class AppIconLoader(QObject):
    """Lazy, bounded icon loader with session-only memory caching."""

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
        self._queued: deque[str] = deque()
        self._pending: set[str] = set()
        self._failed: set[str] = set()
        self._cache: OrderedDict[str, QIcon] = OrderedDict()

    def icon_for_url(self, value: object) -> QIcon | None:
        url = _normalise_icon_url(value)
        if not url:
            return None
        icon = self._cache.get(url)
        if icon is not None:
            self._cache.move_to_end(url)
            return icon
        if url in self._failed or url in self._pending:
            return None
        self._pending.add(url)
        self._queued.append(url)
        self._pump()
        return None

    def _pump(self) -> None:
        while self._active < self._max_active and self._queued:
            url = self._queued.popleft()
            request = QNetworkRequest(QUrl(url))
            request.setTransferTimeout(ICON_TIMEOUT_MS)
            request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)
            reply = self._manager.get(request)
            self._active += 1
            reply.finished.connect(lambda r=reply, u=url: self._finish(u, r))

    def _finish(self, url: str, reply: QNetworkReply) -> None:
        try:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = bytes(reply.readAll())
                if data and len(data) <= MAX_ICON_BYTES:
                    pixmap = QPixmap()
                    if pixmap.loadFromData(data) and not pixmap.isNull():
                        self._cache[url] = QIcon(pixmap)
                        self._cache.move_to_end(url)
                        while len(self._cache) > self._max_cache:
                            self._cache.popitem(last=False)
                        self.icon_ready.emit(url)
                        return
            self._failed.add(url)
        finally:
            self._pending.discard(url)
            self._active = max(0, self._active - 1)
            reply.deleteLater()
            self._pump()
