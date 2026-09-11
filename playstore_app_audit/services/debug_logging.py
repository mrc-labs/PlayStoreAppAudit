from __future__ import annotations

import logging
import platform
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

import PySide6
from PySide6.QtCore import qVersion

from playstore_app_audit import __version__
from playstore_app_audit.platform import runtime

_NOISY_MESSAGES = (
    "starts with 'android:' prefix! The Manifest seems to be broken? Removing prefix.",
    "res1 is not zero!",
)


class _NormalParserNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(noise in message for noise in _NOISY_MESSAGES)


def configure_parser_logging(*, debug: bool) -> None:
    """Filter two known recoverable pyaxmlparser warnings only in normal mode."""

    for name in ("pyaxmlparser.axmlprinter", "pyaxmlparser.arscutil"):
        logger = logging.getLogger(name)
        if debug:
            logger.filters[:] = [
                item
                for item in logger.filters
                if not isinstance(item, _NormalParserNoiseFilter)
            ]
        elif not any(isinstance(item, _NormalParserNoiseFilter) for item in logger.filters):
            logger.addFilter(_NormalParserNoiseFilter())


def start_debug_logging() -> Path:
    started = datetime.now(UTC)
    logs_dir = runtime.app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"debug-{started.strftime('%Y%m%d-%H%M%S-%f')}.log"
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Keep first-party diagnostics detailed without recording every internal
    # parser token/resource or urllib3 connection event. Third-party warnings
    # and errors still reach the debug session and real parser failures remain
    # visible.
    logging.getLogger("playstore_app_audit").setLevel(logging.DEBUG)
    logging.getLogger("pyaxmlparser").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    if sys.stderr is not None and not any(
        isinstance(item, logging.StreamHandler) and not isinstance(item, logging.FileHandler)
        for item in root.handlers
    ):
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)

    def log_uncaught(exc_type, exc_value, exc_traceback) -> None:
        if exc_value is None:
            logging.getLogger("playstore_app_audit").critical("Uncaught exception")
            return
        logging.getLogger("playstore_app_audit").critical(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    def log_thread_uncaught(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None:
            logging.getLogger("playstore_app_audit").critical(
                "Uncaught thread exception in %s",
                args.thread.name if args.thread is not None else "unknown",
            )
            return
        logging.getLogger("playstore_app_audit").critical(
            "Uncaught thread exception in %s",
            args.thread.name if args.thread is not None else "unknown",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = log_uncaught
    threading.excepthook = log_thread_uncaught
    logging.getLogger("playstore_app_audit").info(
        "Debug session started | app=%s | python=%s | Qt=%s | PySide=%s | platform=%s | started=%s",
        __version__,
        platform.python_version(),
        qVersion(),
        PySide6.__version__,
        platform.platform(),
        started.isoformat(),
    )
    configure_parser_logging(debug=True)
    return path
