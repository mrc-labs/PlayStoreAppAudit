from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATCHES: dict[str, tuple[str, str]] = {
    "playstore_app_audit/ui/compact_window.py": (
        "\n\nFIXED_WORKERS = 16\n",
        "\n\n# Transitional internal alias for inherited code that still follows the old layer graph.\nqt_base = base_ui\n\nFIXED_WORKERS = 16\n",
    ),
    "playstore_app_audit/ui/device_window.py": (
        "\n\n# Extend the v7 table model in-place.",
        "\n\n# Transitional aliases keep the proven inheritance graph stable while module ownership moves into the package.\nv7 = compact_ui\nuser_state = persistence\nfeatures = device_metadata\ndevice_insights = device_metadata\n\n# Extend the v7 table model in-place.",
    ),
    "playstore_app_audit/ui/insights_window.py": (
        "\n\nV9_EXTRA_COLUMNS = (",
        "\n\n# Transitional aliases keep nested references stable during the package migration.\nv8 = device_ui\nuser_state = persistence\nfeatures = device_insights\n\nV9_EXTRA_COLUMNS = (",
    ),
    "playstore_app_audit/ui/table_window.py": (
        "\n\nTABLE_SCHEMA_VERSION =",
        "\n\n# Transitional aliases for the inherited table layer.\nv9 = insights_ui\nuser_state = persistence\n\nTABLE_SCHEMA_VERSION =",
    ),
    "playstore_app_audit/ui/preferences_window.py": (
        "\n\ninsights_ui.features.VIEW_PRESETS",
        "\n\n# Transitional aliases for inherited settings/export behaviour.\nv9 = insights_ui\nfixed = table_ui\nuser_state = persistence\nv92 = presentation\n\ninsights_ui.features.VIEW_PRESETS",
    ),
    "playstore_app_audit/ui/menu_window.py": (
        "\n\nclass MenuWindow",
        "\n\n# Transitional aliases for the menu layer.\nv92ui = preferences_ui\nv92 = presentation\nuser_state = persistence\n\nclass MenuWindow",
    ),
    "playstore_app_audit/ui/results_window.py": (
        "\n\nclass ResultsWindow",
        "\n\n# Transitional aliases for the final results/UX layer.\nv92ui = preferences_ui\nstable = menu_ui\nv93 = summary_service\n\nclass ResultsWindow",
    ),
}


def main() -> None:
    for relative, (needle, replacement) in PATCHES.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        if needle not in text:
            raise RuntimeError(f"Expected patch point not found in {relative}: {needle!r}")
        path.write_text(text.replace(needle, replacement, 1), encoding="utf-8")
    print("Applied transitional alias fixes.")


if __name__ == "__main__":
    main()
