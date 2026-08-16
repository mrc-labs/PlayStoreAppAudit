from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "playstore_app_audit"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel: str, old: str, new: str) -> None:
    text = read(rel)
    if old not in text:
        raise RuntimeError(f"Expected text missing in {rel}: {old[:120]!r}")
    write(rel, text.replace(old, new, 1))


# 1) The state module is canonical. Remove the compatibility re-export layer.
for path in PKG.rglob("*.py"):
    text = path.read_text(encoding="utf-8")
    text = text.replace("playstore_app_audit.services.persistence", "playstore_app_audit.services.state")
    path.write_text(text, encoding="utf-8")

persistence = PKG / "services" / "persistence.py"
if not persistence.exists():
    raise RuntimeError("Expected persistence compatibility module is already missing")
persistence.unlink()

# 2) Compact UI no longer exposes a qt_base historical alias.
compact_rel = "playstore_app_audit/ui/compact_window.py"
compact = read(compact_rel)
compact = compact.replace(
    "\n# Transitional internal alias for inherited code that still follows the old layer graph.\nqt_base = base_ui\n",
    "\n",
)
compact = compact.replace("qt_base.", "base_ui.")
write(compact_rel, compact)

# 3) Device layer uses descriptive modules directly.
device_rel = "playstore_app_audit/ui/device_window.py"
device = read(device_rel)
device = device.replace("import playstore_app_audit.services.state as persistence\n", "import playstore_app_audit.services.state as state\n")
device = device.replace(
    "\n# Transitional aliases keep the proven inheritance graph stable while module ownership moves into the package.\nv7 = compact_ui\nuser_state = persistence\nfeatures = device_metadata\ndevice_insights = device_metadata\n",
    "\n",
)
device = device.replace("v7.", "compact_ui.")
device = device.replace("user_state.", "state.")
device = device.replace("features.", "device_metadata.")
device = device.replace("device_insights.", "device_metadata.")
write(device_rel, device)

# 4) Insights layer stops reaching through v8/v7/qt_base aliases.
insights_rel = "playstore_app_audit/ui/insights_window.py"
insights = read(insights_rel)
insights = insights.replace("import playstore_app_audit.services.state as persistence\n", "import playstore_app_audit.services.state as state\n")
insights = insights.replace(
    "import playstore_app_audit.ui.device_window as device_ui\n",
    "import playstore_app_audit.ui.base_window as base_ui\n"
    "import playstore_app_audit.ui.compact_window as compact_ui\n"
    "import playstore_app_audit.ui.device_window as device_ui\n",
    1,
)
insights = insights.replace(
    "\n# Transitional aliases keep nested references stable during the package migration.\nv8 = device_ui\nuser_state = persistence\nfeatures = device_insights\n",
    "\n",
)
insights = insights.replace("device_ui.v7.qt_base.", "base_ui.")
insights = insights.replace("device_ui.v7.", "compact_ui.")
insights = insights.replace("device_ui.device_insights.", "device_ui.device_metadata.")
insights = insights.replace("v8.", "device_ui.")
insights = insights.replace("user_state.", "state.")
insights = insights.replace("features.", "device_insights.")
write(insights_rel, insights)

# 5) Table model depends on canonical base/compact/device modules explicitly.
table_rel = "playstore_app_audit/ui/table_window.py"
table = read(table_rel)
table = table.replace("import playstore_app_audit.services.state as persistence\n", "import playstore_app_audit.services.state as state\n")
table = table.replace(
    "import playstore_app_audit.ui.insights_window as insights_ui\n",
    "import playstore_app_audit.ui.base_window as base_ui\n"
    "import playstore_app_audit.ui.compact_window as compact_ui\n"
    "import playstore_app_audit.ui.device_window as device_ui\n"
    "import playstore_app_audit.ui.insights_window as insights_ui\n",
    1,
)
table = table.replace(
    "\n# Transitional aliases for the inherited table layer.\nv9 = insights_ui\nuser_state = persistence\n",
    "\n",
)
table = table.replace("insights_ui.v8.v7.qt_base.", "base_ui.")
table = table.replace("insights_ui.v8.v7.", "compact_ui.")
table = table.replace("insights_ui.v8.", "device_ui.")
table = table.replace("persistence.", "state.")
table = table.replace("user_state.", "state.")
write(table_rel, table)

# 6) Preferences directly imports the services it configures.
prefs_rel = "playstore_app_audit/ui/preferences_window.py"
prefs = read(prefs_rel)
prefs = prefs.replace("import playstore_app_audit.services.state as persistence\n", "import playstore_app_audit.services.device_insights as device_insights\nimport playstore_app_audit.services.state as state\n")
prefs = prefs.replace(
    "\n# Transitional aliases for inherited settings/export behaviour.\nv9 = insights_ui\nfixed = table_ui\nuser_state = persistence\nv92 = presentation\n",
    "\n",
)
prefs = prefs.replace("insights_ui.features.", "device_insights.")
prefs = prefs.replace("persistence.", "state.")
prefs = prefs.replace("v9.", "insights_ui.")
prefs = prefs.replace("fixed.", "table_ui.")
prefs = prefs.replace("user_state.", "state.")
prefs = prefs.replace("v92.", "presentation.")
write(prefs_rel, prefs)

# 7) Menus and final results use canonical state/base imports.
menu_rel = "playstore_app_audit/ui/menu_window.py"
menu = read(menu_rel)
menu = menu.replace("import playstore_app_audit.services.state as persistence\n", "import playstore_app_audit.services.state as state\n")
menu = menu.replace("persistence.", "state.")
write(menu_rel, menu)

results_rel = "playstore_app_audit/ui/results_window.py"
results = read(results_rel)
results = results.replace(
    "import playstore_app_audit.ui.menu_window as menu_ui\nimport playstore_app_audit.ui.preferences_window as preferences_ui\n",
    "import playstore_app_audit.ui.base_window as base_ui\nimport playstore_app_audit.ui.menu_window as menu_ui\n",
    1,
)
results = results.replace("preferences_ui.v9.v8.v7.qt_base.APP_NAME", "base_ui.APP_NAME")
write(results_rel, results)

# 8) Services use descriptive names rather than version-layer aliases.
metadata_rel = "playstore_app_audit/services/device_metadata.py"
metadata = read(metadata_rel)
metadata = metadata.replace("import playstore_app_audit.services.state as user_state\n", "import playstore_app_audit.services.state as state\n")
metadata = metadata.replace("user_state.", "state.")
write(metadata_rel, metadata)

service_rel = "playstore_app_audit/services/device_insights.py"
service = read(service_rel)
service = service.replace("import playstore_app_audit.services.device_metadata as v8\n", "import playstore_app_audit.services.device_metadata as device_metadata\n")
service = service.replace("import playstore_app_audit.services.state as user_state\n", "import playstore_app_audit.services.state as state\n")
service = service.replace("v8.", "device_metadata.")
service = service.replace("user_state.", "state.")
write(service_rel, service)

presentation_rel = "playstore_app_audit/services/presentation.py"
presentation = read(presentation_rel)
presentation = presentation.replace("import playstore_app_audit.services.state as user_state\n", "import playstore_app_audit.services.state as state\n")
presentation = presentation.replace("user_state.", "state.")
write(presentation_rel, presentation)

# 9) Architecture tests prevent the shim and old alias graph from coming back.
arch_rel = "tests/test_architecture.py"
arch = read(arch_rel)
arch = arch.replace('        "persistence.py",\n', "")
addition = '''\n\ndef test_legacy_state_shim_and_version_aliases_are_gone() -> None:\n    root = Path(__file__).resolve().parents[1]\n    package = root / "playstore_app_audit"\n    assert not (package / "services/persistence.py").exists()\n\n    offenders: list[str] = []\n    forbidden = (\n        "playstore_app_audit.services.persistence",\n        "qt_base = base_ui",\n        "v7 = compact_ui",\n        "v8 = device_ui",\n        "v9 = insights_ui",\n        "user_state = persistence",\n        "features = device_insights",\n    )\n    for path in package.rglob("*.py"):\n        text = path.read_text(encoding="utf-8")\n        for marker in forbidden:\n            if marker in text:\n                offenders.append(f"{path.relative_to(root)}: {marker}")\n    assert not offenders, offenders\n'''
if "test_legacy_state_shim_and_version_aliases_are_gone" not in arch:
    arch += addition
write(arch_rel, arch)

# 10) Documentation reflects the cleanup without claiming the remaining runtime patches are gone.
arch_doc = "docs/ARCHITECTURE.md"
doc = read(arch_doc)
doc = doc.replace(
    "The first v0.12 cleanup removes import-time platform/version patching from MainWindow and centralises portable/app-data paths in the platform layer.",
    "The v0.12 cleanup removes import-time platform/version patching from MainWindow, centralises portable/app-data paths in the platform layer, and removes the persistence compatibility shim plus historical v7/v8/v9 module aliases.",
)
write(arch_doc, doc)

print("Compatibility alias cleanup prepared successfully.")
