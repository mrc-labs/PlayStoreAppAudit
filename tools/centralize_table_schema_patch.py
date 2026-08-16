from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Run after centralize_table_schema.py has transformed the tree.
compact = ROOT / "playstore_app_audit/ui/compact_window.py"
text = compact.read_text(encoding="utf-8")
text = text.replace("MODEL_COLUMNS = schema.COMPACT_MODEL_COLUMNS", "MODEL_COLUMNS = schema.MODEL_COLUMNS")
compact.write_text(text, encoding="utf-8")

# TableWindow still uses the shared LinkedIn URL in its About text. Keep that
# presentation dependency explicit; it does not mutate schema state.
table = ROOT / "playstore_app_audit/ui/table_window.py"
text = table.read_text(encoding="utf-8")
if "import playstore_app_audit.ui.compact_window as compact_ui\n" not in text:
    marker = "import playstore_app_audit.ui.base_window as base_ui\n"
    if marker not in text:
        raise RuntimeError("Could not place compact_ui import")
    text = text.replace(marker, marker + "import playstore_app_audit.ui.compact_window as compact_ui\n", 1)
table.write_text(text, encoding="utf-8")

print("Canonical schema follow-up fixes applied.")
