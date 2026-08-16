from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MOVE_MAP = {
    "playstore_audit_core.py": "playstore_app_audit/services/audit_engine.py",
    "playstore_audit_multicountry.py": "playstore_app_audit/services/countries.py",
    "playstore_audit_user_state.py": "playstore_app_audit/services/persistence.py",
    "playstore_audit_v8_features.py": "playstore_app_audit/services/device_metadata.py",
    "playstore_audit_v9_features.py": "playstore_app_audit/services/device_insights.py",
    "playstore_audit_v9_2_features.py": "playstore_app_audit/services/presentation.py",
    "playstore_audit_v9_3_features.py": "playstore_app_audit/services/summary.py",
    "playstore_audit_process.py": "playstore_app_audit/platform/subprocesses.py",
    "playstore_audit_qt.py": "playstore_app_audit/ui/base_window.py",
    "playstore_audit_qt_branch.py": "playstore_app_audit/ui/audit_window.py",
    "playstore_audit_qt_compact.py": "playstore_app_audit/ui/compact_window.py",
    "playstore_audit_qt_v8.py": "playstore_app_audit/ui/device_window.py",
    "playstore_audit_qt_v9.py": "playstore_app_audit/ui/insights_window.py",
    "playstore_audit_qt_v9_fixed.py": "playstore_app_audit/ui/table_window.py",
    "playstore_audit_qt_v9_2.py": "playstore_app_audit/ui/preferences_window.py",
    "playstore_audit_qt_v9_2_stable.py": "playstore_app_audit/ui/menu_window.py",
    "playstore_audit_qt_v9_3.py": "playstore_app_audit/ui/results_window.py",
    "playstore_audit_cli.py": "playstore_app_audit/cli.py",
}

DELETE_FILES = {
    "playstore_audit_qt_v8_stable.py",  # superseded and not imported by the production chain
    "playstore_audit_gui.py",           # retired Tkinter implementation
    "playstore_audit_windows.py",       # retired Tkinter/Windows launcher
}

MODULE_REPLACEMENTS = {
    "playstore_audit_qt_v9_2_stable": "playstore_app_audit.ui.menu_window",
    "playstore_audit_qt_v9_fixed": "playstore_app_audit.ui.table_window",
    "playstore_audit_qt_v9_3": "playstore_app_audit.ui.results_window",
    "playstore_audit_qt_v9_2": "playstore_app_audit.ui.preferences_window",
    "playstore_audit_qt_v9": "playstore_app_audit.ui.insights_window",
    "playstore_audit_qt_v8": "playstore_app_audit.ui.device_window",
    "playstore_audit_qt_compact": "playstore_app_audit.ui.compact_window",
    "playstore_audit_qt_branch": "playstore_app_audit.ui.audit_window",
    "playstore_audit_qt": "playstore_app_audit.ui.base_window",
    "playstore_audit_v9_3_features": "playstore_app_audit.services.summary",
    "playstore_audit_v9_2_features": "playstore_app_audit.services.presentation",
    "playstore_audit_v9_features": "playstore_app_audit.services.device_insights",
    "playstore_audit_v8_features": "playstore_app_audit.services.device_metadata",
    "playstore_audit_user_state": "playstore_app_audit.services.persistence",
    "playstore_audit_multicountry": "playstore_app_audit.services.countries",
    "playstore_audit_process": "playstore_app_audit.platform.subprocesses",
    "playstore_audit_core": "playstore_app_audit.services.audit_engine",
    "playstore_audit_cli": "playstore_app_audit.cli",
}

CLASS_REPLACEMENTS = {
    "PlayStoreAuditQtV92Stable": "MenuWindow",
    "PlayStoreAuditQtV9Fixed": "TableWindow",
    "PlayStoreAuditQtV93": "ResultsWindow",
    "PlayStoreAuditQtV92": "PreferencesWindow",
    "PlayStoreAuditQtV9": "InsightsWindow",
    "PlayStoreAuditQtV8": "DeviceWindow",
    "PlayStoreAuditQtCompact": "CompactWindow",
    "PlayStoreAuditQtBranch": "AuditWindow",
    "PlayStoreAuditQt": "BaseWindow",
    "StableV9TableModel": "AuditTableModel",
    "V92TableModel": "FormattedAuditTableModel",
    "V92FilterProxy": "AuditFilterProxy",
    "V9FilterProxy": "AdvancedFilterProxy",
}

TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".bat", ".ps1"}


def move_files() -> None:
    for old_name, new_name in MOVE_MAP.items():
        old = ROOT / old_name
        new = ROOT / new_name
        if not old.exists():
            raise FileNotFoundError(f"Expected migration source is missing: {old_name}")
        new.parent.mkdir(parents=True, exist_ok=True)
        if new.exists():
            raise FileExistsError(f"Migration target already exists: {new_name}")
        shutil.move(str(old), str(new))

    for name in DELETE_FILES:
        path = ROOT / name
        if path.exists():
            path.unlink()


def replace_text() -> None:
    replacements = sorted(MODULE_REPLACEMENTS.items(), key=lambda pair: len(pair[0]), reverse=True)
    class_replacements = sorted(CLASS_REPLACEMENTS.items(), key=lambda pair: len(pair[0]), reverse=True)

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        original = text
        for old, new in replacements:
            text = text.replace(old, new)
        if path.suffix == ".py":
            for old, new in class_replacements:
                text = text.replace(old, new)
        if text != original:
            path.write_text(text, encoding="utf-8")


def clean_aliases() -> None:
    replacements_by_file = {
        "playstore_app_audit/ui/device_window.py": {
            "import playstore_app_audit.ui.compact_window as v7": "import playstore_app_audit.ui.compact_window as compact_ui",
            "import playstore_app_audit.services.persistence as user_state": "import playstore_app_audit.services.persistence as persistence",
            "import playstore_app_audit.services.device_metadata as features": "import playstore_app_audit.services.device_metadata as device_metadata",
            "v7.": "compact_ui.",
            "user_state.": "persistence.",
            "features.": "device_metadata.",
        },
        "playstore_app_audit/ui/insights_window.py": {
            "import playstore_app_audit.ui.device_window as v8": "import playstore_app_audit.ui.device_window as device_ui",
            "import playstore_app_audit.services.persistence as user_state": "import playstore_app_audit.services.persistence as persistence",
            "import playstore_app_audit.services.device_insights as features": "import playstore_app_audit.services.device_insights as device_insights",
            "v8.": "device_ui.",
            "user_state.": "persistence.",
            "features.": "device_insights.",
        },
        "playstore_app_audit/ui/table_window.py": {
            "import playstore_app_audit.ui.insights_window as v9": "import playstore_app_audit.ui.insights_window as insights_ui",
            "import playstore_app_audit.services.persistence as user_state": "import playstore_app_audit.services.persistence as persistence",
            "v9.": "insights_ui.",
            "user_state.": "persistence.",
        },
        "playstore_app_audit/ui/preferences_window.py": {
            "import playstore_app_audit.ui.insights_window as v9": "import playstore_app_audit.ui.insights_window as insights_ui",
            "import playstore_app_audit.ui.table_window as fixed": "import playstore_app_audit.ui.table_window as table_ui",
            "import playstore_app_audit.services.persistence as user_state": "import playstore_app_audit.services.persistence as persistence",
            "import playstore_app_audit.services.presentation as v92": "import playstore_app_audit.services.presentation as presentation",
            "v9.": "insights_ui.",
            "fixed.": "table_ui.",
            "user_state.": "persistence.",
            "v92.": "presentation.",
        },
        "playstore_app_audit/ui/menu_window.py": {
            "import playstore_app_audit.ui.preferences_window as v92ui": "import playstore_app_audit.ui.preferences_window as preferences_ui",
            "import playstore_app_audit.services.presentation as v92": "import playstore_app_audit.services.presentation as presentation",
            "import playstore_app_audit.services.persistence as user_state": "import playstore_app_audit.services.persistence as persistence",
            "v92ui.": "preferences_ui.",
            "v92.": "presentation.",
            "user_state.": "persistence.",
        },
        "playstore_app_audit/ui/results_window.py": {
            "import playstore_app_audit.ui.preferences_window as v92ui": "import playstore_app_audit.ui.preferences_window as preferences_ui",
            "import playstore_app_audit.ui.menu_window as stable": "import playstore_app_audit.ui.menu_window as menu_ui",
            "import playstore_app_audit.services.summary as v93": "import playstore_app_audit.services.summary as summary_service",
            "v92ui.": "preferences_ui.",
            "stable.": "menu_ui.",
            "v93.": "summary_service.",
        },
        "playstore_app_audit/ui/compact_window.py": {
            "import playstore_app_audit.ui.base_window as qt_base": "import playstore_app_audit.ui.base_window as base_ui",
            "qt_base.": "base_ui.",
        },
        "playstore_app_audit/ui/main_window.py": {
            "import playstore_app_audit.ui.base_window as qt_base": "import playstore_app_audit.ui.base_window as base_ui",
            "import playstore_app_audit.ui.audit_window as qt_branch": "import playstore_app_audit.ui.audit_window as audit_ui",
            "import playstore_app_audit.ui.compact_window as qt_compact": "import playstore_app_audit.ui.compact_window as compact_ui",
            "import playstore_app_audit.ui.preferences_window as v92ui": "import playstore_app_audit.ui.preferences_window as preferences_ui",
            "import playstore_app_audit.ui.results_window as legacy_ui": "import playstore_app_audit.ui.results_window as results_ui",
            "import playstore_app_audit.services.presentation as v92_features": "import playstore_app_audit.services.presentation as presentation",
            "import playstore_app_audit.services.summary as v93_features": "import playstore_app_audit.services.summary as summary_service",
            "import playstore_app_audit.services.device_insights as v9_features": "import playstore_app_audit.services.device_insights as device_insights",
            "qt_base.": "base_ui.",
            "qt_branch.": "audit_ui.",
            "qt_compact.": "compact_ui.",
            "v92ui.": "preferences_ui.",
            "legacy_ui.": "results_ui.",
            "v92_features.": "presentation.",
            "v93_features.": "summary_service.",
            "v9_features.": "device_insights.",
        },
    }

    for relative, replacements in replacements_by_file.items():
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")


def update_metadata_and_docs() -> None:
    init = ROOT / "playstore_app_audit/__init__.py"
    init.write_text(init.read_text(encoding="utf-8").replace('0.10.0', '0.11.0'), encoding="utf-8")

    pyproject = ROOT / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8").replace('version = "0.10.0"', 'version = "0.11.0"')
    text = re.sub(
        r'\nexclude = \[\n\s*"playstore_app_audit/ui/base_window\.py",.*?\n\]\n',
        "\n",
        text,
        flags=re.S,
    )
    # The pre-refactor exclusions are obsolete after migration into the package.
    text = re.sub(
        r'\nexclude = \[\n\s*"playstore_app_audit/ui/base_window_v\*\.py",.*?\n\]\n',
        "\n",
        text,
        flags=re.S,
    )
    text = text.replace(
        'exclude = [\n    "playstore_app_audit/ui/base_window_v*.py",\n    "playstore_audit_customtkinter*.py",\n]\n',
        '',
    )
    text = text.replace(
        'exclude = [\n    "playstore_app_audit.ui.base_window_v*.py",\n    "playstore_audit_customtkinter*.py",\n]\n',
        '',
    )
    text = text.replace(
        'exclude = [\n    "playstore_app_audit/ui/base_window_v*.py",\n    "playstore_audit_customtkinter*.py",\n]\n',
        '',
    )
    # Handle the original exact Ruff/mypy legacy exclusions after module-name replacement.
    text = re.sub(r'\nexclude = \[\n\s*"playstore_app_audit/ui/base_window_v\*\.py",\n\s*"playstore_audit_customtkinter\*\.py",\n\]\n', '\n', text)
    text = re.sub(r'\nexclude = "\^\(playstore_app_audit/ui/base_window_v\.\*\|playstore_audit_customtkinter\.\*\)\\\\\.py\$"\n', '\n', text)
    if 'ignore = ["E501"]' not in text:
        text = text.replace('[tool.ruff.lint]\nselect = ["E", "F", "I", "UP", "B", "SIM"]', '[tool.ruff.lint]\nselect = ["E", "F", "I", "UP", "B", "SIM"]\nignore = ["E501"]')
    pyproject.write_text(text, encoding="utf-8")

    architecture = ROOT / "docs/ARCHITECTURE.md"
    arch = architecture.read_text(encoding="utf-8")
    start = arch.find("## Current migration state")
    end = arch.find("## Dependency direction")
    if start != -1 and end != -1 and end > start:
        replacement = (
            "## Current architecture\n\n"
            "The migration away from version-suffixed top-level modules is complete. Production code now lives under "
            "`playstore_app_audit/`; the repository no longer depends on `playstore_audit_qt_v*.py`, `*_fixed.py` or "
            "`*_stable.py` compatibility files.\n\n"
            "The Qt window is organised into focused internal layers (`base_window`, `audit_window`, `compact_window`, "
            "`device_window`, `insights_window`, `table_window`, `preferences_window`, `menu_window`, `results_window`) "
            "with `main_window.py` as the only public UI entry point. Services and platform code are likewise inside the "
            "package. Future refactors should reduce inheritance/monkey-patching where it improves clarity, but must not "
            "reintroduce versioned modules.\n\n"
        )
        arch = arch[:start] + replacement + arch[end:]
    architecture.write_text(arch, encoding="utf-8")

    agents = ROOT / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    text = re.sub(
        r'The older top-level `playstore_app_audit/ui/base_window_v\*\.py`.*?gradually deleting legacy wrappers\.\n\n',
        '',
        text,
        flags=re.S,
    )
    text = text.replace(
        "- `qt6-working` and `customtkinter` are legacy branches and should be retired after the Qt package refactor is validated and the final useful differences have been reconciled.\n",
        "- `main` is the single canonical permanent branch; use short-lived feature/fix/refactor branches and delete them after merge.\n",
    )
    agents.write_text(text, encoding="utf-8")

    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(
        r'The old top-level version-suffixed Qt modules.*?See `docs/ARCHITECTURE\.md` and `AGENTS\.md`\.\n',
        "The application code is fully contained under `playstore_app_audit/`; version-suffixed compatibility modules have been removed. See `docs/ARCHITECTURE.md` and `AGENTS.md`.\n",
        text,
        flags=re.S,
    )
    readme.write_text(text, encoding="utf-8")


def add_architecture_test() -> None:
    path = ROOT / "tests/test_architecture.py"
    path.write_text(
        '''from __future__ import annotations\n\nfrom pathlib import Path\n\n\ndef test_no_legacy_versioned_modules_at_repository_root() -> None:\n    root = Path(__file__).resolve().parents[1]\n    forbidden = list(root.glob("playstore_audit_qt_v*.py"))\n    forbidden += list(root.glob("playstore_audit_*_features.py"))\n    forbidden += [root / "playstore_audit_gui.py", root / "playstore_audit_windows.py"]\n    assert not [path for path in forbidden if path.exists()]\n\n\ndef test_canonical_package_owns_core_layers() -> None:\n    root = Path(__file__).resolve().parents[1]\n    required = [\n        "playstore_app_audit/services/audit_engine.py",\n        "playstore_app_audit/services/countries.py",\n        "playstore_app_audit/services/persistence.py",\n        "playstore_app_audit/services/device_metadata.py",\n        "playstore_app_audit/services/device_insights.py",\n        "playstore_app_audit/ui/base_window.py",\n        "playstore_app_audit/ui/main_window.py",\n        "playstore_app_audit/platform/subprocesses.py",\n    ]\n    assert all((root / item).is_file() for item in required)\n\n\ndef test_source_does_not_import_retired_module_names() -> None:\n    root = Path(__file__).resolve().parents[1]\n    retired = (\n        "playstore_audit_qt_v",\n        "playstore_audit_v8_features",\n        "playstore_audit_v9_features",\n        "playstore_audit_v9_2_features",\n        "playstore_audit_v9_3_features",\n    )\n    offenders: list[str] = []\n    for path in (root / "playstore_app_audit").rglob("*.py"):\n        text = path.read_text(encoding="utf-8")\n        if any(name in text for name in retired):\n            offenders.append(str(path.relative_to(root)))\n    assert not offenders\n''',
        encoding="utf-8",
    )


def main() -> None:
    move_files()
    replace_text()
    clean_aliases()
    update_metadata_and_docs()
    add_architecture_test()
    print("Architecture migration prepared successfully.")


if __name__ == "__main__":
    main()
