from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "playstore_app_audit"
BASE_WINDOW = PACKAGE_ROOT / "ui" / "base_window.py"

# These are standalone developer entry points only. The canonical production
# launcher and shared base no longer force a QStyle. Keep this allowlist exact
# until the remaining large modules can be mechanically normalized without
# risky whole-file rewrites through the repository connector.
LEGACY_DIRECT_ENTRYPOINT_STYLE_OVERRIDES = {
    "playstore_app_audit/ui/audit_window.py",
    "playstore_app_audit/ui/compact_window.py",
    "playstore_app_audit/ui/device_window.py",
    "playstore_app_audit/ui/insights_window.py",
    "playstore_app_audit/ui/preferences_window.py",
}


def test_qt_style_override_is_limited_to_known_legacy_direct_entrypoints() -> None:
    found: set[str] = set()
    unexpected: list[str] = []

    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        relative = str(path.relative_to(ROOT)).replace("\\", "/")
        count = text.count('.setStyle("Fusion")')
        other_count = text.count(".setStyle(") - count

        if other_count:
            unexpected.append(f"{relative}: non-Fusion setStyle call")
        if count:
            if count != 1 or relative not in LEGACY_DIRECT_ENTRYPOINT_STYLE_OVERRIDES:
                unexpected.append(f"{relative}: unexpected Fusion override count={count}")
            else:
                found.add(relative)

    assert not unexpected, (
        "Qt platform/default QStyle ownership was bypassed outside the explicit "
        "legacy standalone-entry allowlist:\n" + "\n".join(unexpected)
    )
    assert found == LEGACY_DIRECT_ENTRYPOINT_STYLE_OVERRIDES


def test_shared_qss_leaves_font_family_and_scrollbars_to_qt_style() -> None:
    text = BASE_WINDOW.read_text(encoding="utf-8")

    assert 'font-family: "Segoe UI"' not in text
    assert "QScrollBar:vertical" not in text
    assert "QScrollBar:horizontal" not in text
