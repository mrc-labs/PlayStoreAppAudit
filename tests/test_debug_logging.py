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
        for name in ("playstore_app_audit.acceptance", "pyaxmlparser.parser", "urllib3.connectionpool")
    }
    previous_levels = {name: logger.level for name, logger in loggers.items()}
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
        loggers["pyaxmlparser.parser"].debug("parser token flood")
        loggers["pyaxmlparser.parser"].warning("parser warning retained")
        loggers["pyaxmlparser.parser"].error("parser failure retained")
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
        for name, level in parent_levels.items():
            logging.getLogger(name).setLevel(level)
        sys.excepthook = previous_excepthook
        threading.excepthook = previous_threading_excepthook


def test_normal_parser_noise_filter_is_narrow() -> None:
    filter_ = debug_logging._NormalParserNoiseFilter()
    known = logging.LogRecord("x", logging.WARNING, "", 0, "res1 is not zero!", (), None)
    real = logging.LogRecord("x", logging.ERROR, "", 0, "manifest parse failed", (), None)
    assert not filter_.filter(known)
    assert filter_.filter(real)


def test_debug_mode_removes_only_the_normal_parser_noise_filter() -> None:
    logger = logging.getLogger("pyaxmlparser.axmlprinter")
    unrelated = logging.Filter()
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
    finally:
        logger.removeFilter(unrelated)
