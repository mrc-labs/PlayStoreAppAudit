from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "playstore_app_audit" / "app.py"


def test_application_does_not_force_a_qt_style() -> None:
    text = APP.read_text(encoding="utf-8")

    assert ".setStyle(" not in text
    assert "QStyleFactory" not in text
