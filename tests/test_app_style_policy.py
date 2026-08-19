from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "playstore_app_audit"
BASE_WINDOW = PACKAGE_ROOT / "ui" / "base_window.py"


def test_first_party_code_does_not_force_a_qt_style() -> None:
    unexpected: list[str] = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        count = text.count(".setStyle(")
        if count:
            unexpected.append(f"{relative}: setStyle call count={count}")

    assert not unexpected, (
        "Qt platform/default QStyle ownership was bypassed by first-party code:\n"
        + "\n".join(unexpected)
    )


def test_shared_qss_leaves_font_family_and_scrollbars_to_qt_style() -> None:
    text = BASE_WINDOW.read_text(encoding="utf-8")

    assert 'font-family: "Segoe UI"' not in text
    assert "QScrollBar:vertical" not in text
    assert "QScrollBar:horizontal" not in text
