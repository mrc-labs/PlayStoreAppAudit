from __future__ import annotations

import logging
import sys
import threading

from playstore_app_audit import app
from playstore_app_audit.services import debug_logging


def test_debug_argument_is_consumed_without_changing_normal_arguments() -> None:
    assert app.consume_debug_argument(["main.py"]) == (["main.py"], False)
    assert app.consume_debug_argument(["main.py", "--debug", "-platform", "offscreen"]) == (
        ["main.py", "-platform", "offscreen"],
        True,
    )


def test_debug_log_is_created_with_session_metadata(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(debug_logging.runtime, "app_data_dir", lambda: tmp_path)
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    previous_excepthook = sys.excepthook
    previous_threading_excepthook = threading.excepthook
    logger_levels = {
        name: logging.getLogger(name).level
        for name in ("playstore_app_audit", "pyaxmlparser", "urllib3")
    }
    try:
        path = debug_logging.start_debug_logging()
        for handler in root.handlers:
            handler.flush()
        text = path.read_text(encoding="utf-8")
        assert path.parent == tmp_path / "logs"
        assert path.name.startswith("debug-")
        assert "Debug session started" in text
        assert "python=" in text and "Qt=" in text and "PySide=" in text
    finally:
        for handler in list(root.handlers):
            if handler not in previous_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(previous_level)
        sys.excepthook = previous_excepthook
        threading.excepthook = previous_threading_excepthook
        for name, level in logger_levels.items():
            logging.getLogger(name).setLevel(level)


def test_debug_session_keeps_first_party_detail_and_third_party_warnings(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(debug_logging.runtime, "app_data_dir", lambda: tmp_path)
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    loggers = {
        name: logging.getLogger(name)
        for name in ("playstore_app_audit.acceptance", "pyaxmlparser.arscutil", "urllib3.connectionpool")
    }
    previous_levels = {name: logger.level for name, logger in loggers.items()}
    previous_filters = {name: list(logger.filters) for name, logger in loggers.items()}
    parent_levels = {
        name: logging.getLogger(name).level
        for name in ("playstore_app_audit", "pyaxmlparser", "urllib3")
    }
    previous_excepthook = sys.excepthook
    previous_threading_excepthook = threading.excepthook
    try:
        for logger in loggers.values():
            logger.setLevel(logging.NOTSET)
        path = debug_logging.start_debug_logging()
        loggers["playstore_app_audit.acceptance"].debug("first-party phase detail")
        loggers["pyaxmlparser.arscutil"].debug("parser token flood")
        loggers["pyaxmlparser.arscutil"].warning("parser warning retained")
        loggers["pyaxmlparser.arscutil"].error("parser failure retained")
        loggers["urllib3.connectionpool"].debug("connection chatter")
        for handler in root.handlers:
            handler.flush()
        text = path.read_text(encoding="utf-8")
        assert "first-party phase detail" in text
        assert "parser token flood" not in text
        assert "connection chatter" not in text
        assert "parser warning retained" in text
        assert "parser failure retained" in text
    finally:
        for handler in list(root.handlers):
            if handler not in previous_handlers:
                handler.close()
                root.removeHandler(handler)
        root.setLevel(previous_level)
        for name, level in previous_levels.items():
            loggers[name].setLevel(level)
        for name, filters in previous_filters.items():
            loggers[name].filters[:] = filters
        for name, level in parent_levels.items():
            logging.getLogger(name).setLevel(level)
        sys.excepthook = previous_excepthook
        threading.excepthook = previous_threading_excepthook


def test_normal_parser_noise_filter_covers_known_recoverable_floods() -> None:
    filter_ = debug_logging._NormalParserNoiseFilter()
    known_messages = (
        "res1 is not zero!",
        "invalid decoded string length",
        "RES_TABLE_LIBRARY_TYPE chunk is not supported",
        "Name 'android:name' starts with 'android:' prefix! The Manifest seems to be broken? Removing prefix.",
    )
    for message in known_messages:
        record = logging.LogRecord("x", logging.WARNING, "", 0, message, (), None)
        assert not filter_.filter(record)
    known_error = logging.LogRecord("x", logging.ERROR, "", 0, known_messages[0], (), None)
    assert filter_.filter(known_error)
    real = logging.LogRecord("x", logging.ERROR, "", 0, "manifest parse failed", (), None)
    assert filter_.filter(real)


def test_debug_parser_noise_filter_keeps_one_representative_and_unknown_warnings() -> None:
    filter_ = debug_logging._DebugParserNoiseFilter()
    first = logging.LogRecord("x", logging.WARNING, "", 0, "res1 is not zero!", (), None)
    duplicate = logging.LogRecord("x", logging.WARNING, "", 0, "res1 is not zero!", (), None)
    other_known = logging.LogRecord(
        "x", logging.WARNING, "", 0, "invalid decoded string length", (), None
    )
    unknown = logging.LogRecord("x", logging.WARNING, "", 0, "unexpected parser warning", (), None)
    error = logging.LogRecord("x", logging.ERROR, "", 0, "manifest parse failed", (), None)
    known_error = logging.LogRecord("x", logging.ERROR, "", 0, "res1 is not zero!", (), None)

    assert filter_.filter(first)
    assert not filter_.filter(duplicate)
    assert filter_.filter(other_known)
    assert filter_.filter(unknown)
    assert filter_.filter(error)
    assert filter_.filter(known_error)


def test_debug_mode_replaces_only_project_parser_noise_filters() -> None:
    logger = logging.getLogger("pyaxmlparser.axmlprinter")
    unrelated = logging.Filter()
    previous_filters = list(logger.filters)
    logger.addFilter(unrelated)
    try:
        debug_logging.configure_parser_logging(debug=False)
        assert any(
            isinstance(item, debug_logging._NormalParserNoiseFilter)
            for item in logger.filters
        )
        debug_logging.configure_parser_logging(debug=True)
        assert unrelated in logger.filters
        assert not any(
            isinstance(item, debug_logging._NormalParserNoiseFilter)
            for item in logger.filters
        )
        assert any(
            isinstance(item, debug_logging._DebugParserNoiseFilter)
            for item in logger.filters
        )
    finally:
        logger.filters[:] = previous_filters
