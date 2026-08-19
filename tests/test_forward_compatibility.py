from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# This is intentionally a curated regression list, not a claim that static text
# matching can discover every future deprecation. Each pattern corresponds to an
# API reviewed during the v1.4 forward-compatibility sweep and should be removed
# only when the replacement policy is deliberately revisited.
DEPRECATED_API_PATTERNS: dict[str, re.Pattern[str]] = {
    "Python datetime.utcnow": re.compile(r"\bdatetime(?:\.datetime)?\.utcnow\("),
    "Python datetime.utcfromtimestamp": re.compile(
        r"\bdatetime(?:\.datetime)?\.utcfromtimestamp\("
    ),
    "Python locale.getdefaultlocale": re.compile(r"\blocale\.getdefaultlocale\("),
    "Python logging.warn": re.compile(r"\blogging\.warn\("),
    "PySide legacy exec_ alias": re.compile(r"\.exec_\("),
    "Qt QCheckBox.stateChanged": re.compile(r"\.stateChanged\.connect\("),
    "Qt QSortFilterProxyModel legacy filter invalidation": re.compile(
        r"\.invalidate(?:Rows|Columns)?Filter\("
    ),
    "Qt legacy pointer-event position accessors": re.compile(
        r"\.(?:globalPos|localPos|screenPos|windowPos)\("
    ),
    "Qt QApplication deprecated static member": re.compile(
        r"\bQApplication\.(?:fontMetrics|setActiveWindow)\("
    ),
    "Qt QDesktopWidget": re.compile(r"\bQDesktopWidget\b"),
    "Qt QRegExp": re.compile(r"\bQRegExp\b"),
}


def _first_party_python_files() -> list[Path]:
    files = sorted((ROOT / "playstore_app_audit").rglob("*.py"))
    files.extend(sorted((ROOT / ".github" / "scripts").glob("*.py")))
    files.append(ROOT / "main.py")
    return files


def test_audited_deprecated_apis_are_not_reintroduced() -> None:
    failures: list[str] = []

    for path in _first_party_python_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        for label, pattern in DEPRECATED_API_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                failures.append(f"{relative}:{line}: {label}")

    assert not failures, (
        "Audited deprecated/superseded APIs were found. Use the documented "
        "replacement when semantics are equivalent, or update this guard only "
        "with explicit compatibility evidence:\n" + "\n".join(failures)
    )
