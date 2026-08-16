from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The initial migration intentionally used narrow replacements. Clean up any
# remaining canonical-state references that were written using the old local
# variable name.
for rel in (
    "playstore_app_audit/ui/device_window.py",
    "playstore_app_audit/ui/insights_window.py",
    "playstore_app_audit/ui/table_window.py",
    "playstore_app_audit/ui/preferences_window.py",
    "playstore_app_audit/ui/menu_window.py",
):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "import playstore_app_audit.services.state as persistence",
        "import playstore_app_audit.services.state as state",
    )
    text = text.replace("persistence.", "state.")
    path.write_text(text, encoding="utf-8")

# DeviceWindow still had a few direct references to the compact compatibility
# alias rather than the earlier v7 alias.
device = ROOT / "playstore_app_audit/ui/device_window.py"
text = device.read_text(encoding="utf-8")
if "import playstore_app_audit.ui.base_window as base_ui\n" not in text:
    marker = "import playstore_app_audit.ui.compact_window as compact_ui\n"
    if marker not in text:
        raise RuntimeError("Could not place base_ui import in device_window")
    text = text.replace(marker, "import playstore_app_audit.ui.base_window as base_ui\n" + marker, 1)
text = text.replace("compact_ui.qt_base.", "base_ui.")
text = text.replace("compact_ui.qt_base", "base_ui")
device.write_text(text, encoding="utf-8")

# Preferences still referenced nested attributes that existed only because
# InsightsWindow used to export its parent modules as v8/features aliases.
prefs = ROOT / "playstore_app_audit/ui/preferences_window.py"
text = prefs.read_text(encoding="utf-8")
if "import playstore_app_audit.services.device_metadata as device_metadata\n" not in text:
    marker = "import playstore_app_audit.services.device_insights as device_insights\n"
    if marker not in text:
        raise RuntimeError("Could not place device_metadata import in preferences_window")
    text = text.replace(marker, marker + "import playstore_app_audit.services.device_metadata as device_metadata\n", 1)
if "import playstore_app_audit.ui.base_window as base_ui\n" not in text:
    marker = "import playstore_app_audit.ui.insights_window as insights_ui\n"
    if marker not in text:
        raise RuntimeError("Could not place base_ui import in preferences_window")
    text = text.replace(marker, "import playstore_app_audit.ui.base_window as base_ui\n" + marker, 1)
text = text.replace("insights_ui.v8.v7.qt_base.", "base_ui.")
text = text.replace("insights_ui.v8.features.", "device_metadata.")
text = text.replace("insights_ui.features.", "device_insights.")
text = text.replace("insights_ui.v8.v7.qt_base", "base_ui")
prefs.write_text(text, encoding="utf-8")

# Tests should follow the canonical names too.
adb_test = ROOT / "tests/test_adb_bulk_metadata.py"
text = adb_test.read_text(encoding="utf-8").replace("insights.user_state", "insights.state")
adb_test.write_text(text, encoding="utf-8")

arch_test = ROOT / "tests/test_architecture.py"
text = arch_test.read_text(encoding="utf-8")
text = text.replace('        "playstore_app_audit/services/persistence.py",\n', "")
arch_test.write_text(text, encoding="utf-8")

# Fail early if obvious compatibility chains survived the migration.
for path in (ROOT / "playstore_app_audit").rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    leftovers = [
        marker
        for marker in (
            "playstore_app_audit.services.persistence",
            "compact_ui.qt_base",
            "device_ui.v7",
            "insights_ui.v8",
            "preferences_ui.v9",
        )
        if marker in text
    ]
    if leftovers:
        raise RuntimeError(f"Compatibility references remain in {path.relative_to(ROOT)}: {leftovers}")

print("Residual compatibility references cleaned up.")
