from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

import playstore_app_audit.services.app_icon_metadata as app_icon_metadata

logger = logging.getLogger(__name__)

DEFAULT_METADATA_CONCURRENCY = 2


@dataclass(frozen=True, slots=True)
class StoreMetadataRequest:
    package_name: str
    country: str
    language: str
    generation: int = 0


class _BackfillSignals(QObject):
    completed = Signal(object, object)


class _BackfillTask(QRunnable):
    def __init__(
        self,
        request: StoreMetadataRequest,
        signals: _BackfillSignals,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._request = request
        self._signals = signals
        self._cancel_event = cancel_event

    def run(self) -> None:
        metadata = app_icon_metadata.fetch_store_metadata(
            self._request.package_name,
            self._request.country,
            self._request.language,
            cancel_event=self._cancel_event,
        )
        self._signals.completed.emit(self._request, metadata)


class StoreMetadataBackfill(QObject):
    """Deduplicated, bounded Store metadata completion for legacy cache rows."""

    completed = Signal(object, object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        max_active: int = DEFAULT_METADATA_CONCURRENCY,
    ) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(max(1, int(max_active)))
        self._signals = _BackfillSignals(self)
        self._signals.completed.connect(self._on_completed)
        self._attempted: set[StoreMetadataRequest] = set()
        self._cancel_event = threading.Event()
        self._generation = 0

    def schedule(self, package_name: object, country: object, language: object) -> bool:
        if self._cancel_event.is_set():
            return False
        request = StoreMetadataRequest(
            str(package_name or "").strip(),
            str(country or "us").strip().lower() or "us",
            str(language or "en").strip().lower() or "en",
            self._generation,
        )
        if not request.package_name or request in self._attempted:
            return False
        self._attempted.add(request)
        logger.debug(
            "Store icon metadata backfill scheduled: package=%s country=%s language=%s",
            request.package_name,
            request.country,
            request.language,
        )
        self._pool.start(_BackfillTask(request, self._signals, self._cancel_event))
        return True

    def begin_generation(self) -> int:
        self._cancel_event.set()
        self._pool.clear()
        self._generation += 1
        self._cancel_event = threading.Event()
        self._attempted.clear()
        return self._generation

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pool.clear()

    def _on_completed(self, request: object, metadata: object) -> None:
        if self._cancel_event.is_set():
            return
        if (
            isinstance(request, StoreMetadataRequest)
            and request.generation == self._generation
            and isinstance(metadata, dict)
        ):
            self.completed.emit(request, metadata)
