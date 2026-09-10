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
