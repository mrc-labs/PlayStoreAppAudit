from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    (ROOT / rel).write_text(text, encoding="utf-8")


def regex_once(rel: str, pattern: str, replacement: str, flags: int = 0) -> None:
    text = read(rel)
    updated, count = re.subn(pattern, lambda _m: replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected one match in {rel}, found {count}: {pattern[:100]!r}")
    write(rel, updated)


schema = '''from __future__ import annotations

# Canonical table schema for every UI layer. Older releases progressively
# mutated module globals while importing successive window classes. Keeping one
# immutable source of truth prevents import order from changing the model.
PRIMARY_COLUMNS = (
    "criticality",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
)

COMPACT_MODEL_COLUMNS = (
    "criticality",
    "change",
    "package_name",
    "play_title",
    "play_last_update",
    "age_days",
    "notes",
    "play_status",
    "updated_source",
    "play_http_status",
    "app_name",
    "store_url",
    "is_system",
)

DEVICE_EXTRA_COLUMNS = (
    "play_version",
    "installed_version",
    "version_comparison",
    "installer_source",
)
DEVICE_MODEL_COLUMNS = tuple(dict.fromkeys(COMPACT_MODEL_COLUMNS + DEVICE_EXTRA_COLUMNS))

INSIGHTS_EXTRA_COLUMNS = (
    "compatibility_status",
    "target_sdk",
    "min_sdk",
    "first_install_time",
    "last_local_update",
    "app_enabled",
    "sensitive_permissions_count",
    "sensitive_permissions",
    "device_change",
    "health_score",
)
MODEL_COLUMNS = tuple(dict.fromkeys(DEVICE_MODEL_COLUMNS + INSIGHTS_EXTRA_COLUMNS))

COLUMN_LABELS = {
    "criticality": "Status",
    "change": "Change",
    "package_name": "Package Name",
    "play_title": "Play Store Title",
    "play_last_update": "Last update",
    "age_days": "Age (days)",
    "notes": "Notes",
    "play_status": "Play status",
    "updated_source": "Update source",
    "play_http_status": "HTTP status",
    "app_name": "Input name",
    "store_url": "Store URL",
    "is_system": "System app",
    "play_version": "Play Store version",
    "installed_version": "Installed version",
    "installed_version_code": "Installed version code",
    "version_comparison": "Installed vs Store",
    "installer_source": "Installer source",
    "compatibility_status": "Android compatibility",
    "target_sdk": "Target SDK",
    "min_sdk": "Min SDK",
    "first_install_time": "First installed",
    "last_local_update": "Last local update",
    "app_enabled": "Enabled state",
    "sensitive_permissions_count": "Sensitive permissions count",
    "sensitive_permissions": "Sensitive permissions",
    "device_change": "Device inventory change",
    "health_score": "Health score",
}

DEFAULT_WIDTHS = {
    "criticality": 145,
    "change": 105,
    "package_name": 300,
    "play_title": 265,
    "play_last_update": 120,
    "age_days": 92,
    "notes": 460,
    "play_status": 190,
    "updated_source": 180,
    "play_http_status": 90,
    "app_name": 220,
    "store_url": 350,
    "is_system": 90,
    "play_version": 150,
    "installed_version": 150,
    "installed_version_code": 120,
    "version_comparison": 140,
    "installer_source": 230,
    "compatibility_status": 150,
    "target_sdk": 90,
    "min_sdk": 80,
    "first_install_time": 155,
    "last_local_update": 155,
    "app_enabled": 100,
    "sensitive_permissions_count": 105,
    "sensitive_permissions": 360,
    "device_change": 155,
    "health_score": 90,
}

EXPORT_EXTRA_FIELDS = (
    "is_system",
    "criticality",
    "age_days",
    "change",
    "cache_hit",
    "play_version",
    "installed_version",
    "installed_version_code",
    "version_comparison",
    "installer_source",
    *INSIGHTS_EXTRA_COLUMNS,
)
'''
write("playstore_app_audit/ui/schema.py", schema)

# Base model starts with the final immutable schema instead of waiting for
# import-time mutations from child modules.
base = "playstore_app_audit/ui/base_window.py"
text = read(base)
marker = "from playstore_app_audit.services.audit_engine import OUTPUT_FIELDS, AuditConfig, audit_apps, load_apps\n"
if "from playstore_app_audit.ui import schema\n" not in text:
    if marker not in text:
        raise RuntimeError("Could not place schema import in base_window")
    text = text.replace(marker, marker + "from playstore_app_audit.ui import schema\n", 1)
write(base, text)
regex_once(
    base,
    r"COLUMNS = \(.*?\nEXPORT_FIELDS = list\(OUTPUT_FIELDS\) \+ \[\"is_system\", \"criticality\", \"age_days\"\]\n",
    '''COLUMNS = schema.MODEL_COLUMNS
COLUMN_LABELS = dict(schema.COLUMN_LABELS)
EXPORT_FIELDS = list(dict.fromkeys(list(OUTPUT_FIELDS) + list(schema.EXPORT_EXTRA_FIELDS)))
''',
    flags=re.DOTALL,
)

# Compact layer owns presentation defaults, not the base model's globals.
compact = "playstore_app_audit/ui/compact_window.py"
text = read(compact)
if "from playstore_app_audit.ui import schema\n" not in text:
    marker = "import playstore_app_audit.ui.base_window as base_ui\n"
    text = text.replace(marker, marker + "from playstore_app_audit.ui import schema\n", 1)
write(compact, text)
regex_once(
    compact,
    r"PRIMARY_COLUMNS = \(.*?\nPROJECT_URL = ",
    '''PRIMARY_COLUMNS = schema.PRIMARY_COLUMNS
MODEL_COLUMNS = schema.COMPACT_MODEL_COLUMNS
DEFAULT_WIDTHS = dict(schema.DEFAULT_WIDTHS)
PROJECT_URL = ''',
    flags=re.DOTALL,
)
# The regex above leaves the quoted URL in place after the replacement prefix.
text = read(compact)
text = re.sub(r"\nbase_ui\.COLUMNS = MODEL_COLUMNS\nbase_ui\.COLUMN_LABELS\.update\(.*?\n\)\nbase_ui\.EXPORT_FIELDS = list\(dict\.fromkeys\(base_ui\.EXPORT_FIELDS \+ \[\"change\", \"cache_hit\"\]\)\)\n", "\n", text, count=1, flags=re.DOTALL)
write(compact, text)

# Device and insights layers expose semantic subsets for existing methods but
# do not mutate parents while being imported.
device = "playstore_app_audit/ui/device_window.py"
text = read(device)
if "from playstore_app_audit.ui import schema\n" not in text:
    marker = "import playstore_app_audit.ui.base_window as base_ui\n"
    text = text.replace(marker, marker + "from playstore_app_audit.ui import schema\n", 1)
write(device, text)
regex_once(
    device,
    r"# Extend the v7 table model in-place\..*?\n# Use the enhanced v8 audit path and merge-safe history writer\.",
    '''# Stable device-layer schema aliases. The canonical definitions live in ui.schema.
V8_EXTRA_COLUMNS = schema.DEVICE_EXTRA_COLUMNS
V8_MODEL_COLUMNS = schema.DEVICE_MODEL_COLUMNS

# Use the enhanced v8 audit path and merge-safe history writer.''',
    flags=re.DOTALL,
)

insights = "playstore_app_audit/ui/insights_window.py"
text = read(insights)
if "from playstore_app_audit.ui import schema\n" not in text:
    marker = "import playstore_app_audit.ui.base_window as base_ui\n"
    text = text.replace(marker, marker + "from playstore_app_audit.ui import schema\n", 1)
write(insights, text)
regex_once(
    insights,
    r"V9_EXTRA_COLUMNS = \(.*?\n# v8 imports the feature module object, so replacing these functions upgrades",
    '''V9_EXTRA_COLUMNS = schema.INSIGHTS_EXTRA_COLUMNS
V9_MODEL_COLUMNS = schema.MODEL_COLUMNS

# v8 imports the feature module object, so replacing these functions upgrades''',
    flags=re.DOTALL,
)

# The stable table model consumes the schema directly and no longer rewrites
# module globals before construction.
table = "playstore_app_audit/ui/table_window.py"
text = read(table)
if "from playstore_app_audit.ui import schema\n" not in text:
    marker = "import playstore_app_audit.ui.base_window as base_ui\n"
    text = text.replace(marker, marker + "from playstore_app_audit.ui import schema\n", 1)
text = text.replace('TABLE_SCHEMA_VERSION = "v9-fixed-1"', 'TABLE_SCHEMA_VERSION = "v12-schema-1"')
text = text.replace("self.columns = tuple(insights_ui.V9_MODEL_COLUMNS)", "self.columns = schema.MODEL_COLUMNS")
text = re.sub(
    r"\n        # Keep every Qt layer on the same schema before constructing widgets\.\n        device_ui\.V8_MODEL_COLUMNS = tuple\(insights_ui\.V9_MODEL_COLUMNS\)\n        compact_ui\.MODEL_COLUMNS = tuple\(insights_ui\.V9_MODEL_COLUMNS\)\n        base_ui\.COLUMNS = tuple\(insights_ui\.V9_MODEL_COLUMNS\)\n",
    "\n",
    text,
    count=1,
)
write(table, text)

# Remove imports that became unused only because schema mutation disappeared;
# Ruff will handle the rest, but these two are explicit architecture edges.
text = read(table)
text = text.replace("import playstore_app_audit.ui.compact_window as compact_ui\n", "")
text = text.replace("import playstore_app_audit.ui.device_window as device_ui\n", "")
write(table, text)

# Regression tests: schema is complete and no UI module may rewrite another
# module's table schema during import.
(ROOT / "tests/test_ui_schema.py").write_text(
    '''from __future__ import annotations

from playstore_app_audit.ui import schema


def test_final_schema_is_unique_and_contains_each_layer() -> None:
    assert len(schema.MODEL_COLUMNS) == len(set(schema.MODEL_COLUMNS))
    assert set(schema.COMPACT_MODEL_COLUMNS) <= set(schema.MODEL_COLUMNS)
    assert set(schema.DEVICE_EXTRA_COLUMNS) <= set(schema.MODEL_COLUMNS)
    assert set(schema.INSIGHTS_EXTRA_COLUMNS) <= set(schema.MODEL_COLUMNS)


def test_schema_has_labels_and_widths_for_visible_model_columns() -> None:
    missing_labels = [column for column in schema.MODEL_COLUMNS if column not in schema.COLUMN_LABELS]
    missing_widths = [column for column in schema.MODEL_COLUMNS if column not in schema.DEFAULT_WIDTHS]
    assert not missing_labels
    assert not missing_widths


def test_export_extras_are_unique() -> None:
    assert len(schema.EXPORT_EXTRA_FIELDS) == len(set(schema.EXPORT_EXTRA_FIELDS))
''',
    encoding="utf-8",
)

arch = "tests/test_architecture.py"
text = read(arch)
addition = '''\n\ndef test_ui_modules_do_not_mutate_table_schema_across_imports() -> None:\n    root = Path(__file__).resolve().parents[1]\n    ui = root / "playstore_app_audit/ui"\n    forbidden = (\n        "base_ui.COLUMNS =",\n        "base_ui.COLUMN_LABELS.update",\n        "base_ui.EXPORT_FIELDS =",\n        "compact_ui.MODEL_COLUMNS =",\n        "compact_ui.DEFAULT_WIDTHS.update",\n        "device_ui.V8_MODEL_COLUMNS =",\n    )\n    offenders: list[str] = []\n    for path in ui.glob("*.py"):\n        if path.name == "schema.py":\n            continue\n        source = path.read_text(encoding="utf-8")\n        for marker in forbidden:\n            if marker in source:\n                offenders.append(f"{path.name}: {marker}")\n    assert not offenders, offenders\n'''
if "test_ui_modules_do_not_mutate_table_schema_across_imports" not in text:
    text += addition
write(arch, text)

# Documentation.
doc = "docs/ARCHITECTURE.md"
text = read(doc)
old = "Future refactors should continue reducing the remaining UI inheritance/legacy configuration patching where it improves clarity, but must not reintroduce versioned modules."
new = "Table columns, labels, widths and export extras now come from `ui/schema.py`, so importing child windows no longer changes the table schema. Future refactors should continue reducing the remaining behavioural audit/classification patching and UI inheritance where it improves clarity, but must not reintroduce versioned modules."
if old in text:
    text = text.replace(old, new, 1)
write(doc, text)

print("Canonical table schema migration prepared successfully.")
