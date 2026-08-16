from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    if old not in text:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    write(path, text.replace(old, new, 1))


def regex_once(path: str, pattern: str, replacement: str, flags: int = 0) -> None:
    text = read(path)
    updated, count = re.subn(pattern, replacement, text, count=1, flags=flags)
    if count != 1:
        raise RuntimeError(f"Expected exactly one regex match in {path}, got {count}: {pattern!r}")
    write(path, updated)


# 1) Canonical cross-platform + portable data paths live in platform.runtime.
runtime_path = "playstore_app_audit/platform/runtime.py"
regex_once(
    runtime_path,
    r"def app_data_dir\(\) -> Path:\n(?:    .*\n)+?    return target\n",
    '''def default_app_data_dir() -> Path:\n    """Return the normal per-user application data directory for this OS."""\n    key = platform_key()\n    if key == "windows":\n        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))\n    elif key == "macos":\n        base = Path.home() / "Library" / "Application Support"\n    else:\n        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))\n    target = base / APP_DIR_NAME\n    target.mkdir(parents=True, exist_ok=True)\n    return target\n\n\ndef portable_marker() -> Path:\n    return executable_dir() / "PlayStoreAppAudit.portable"\n\n\ndef portable_data_dir() -> Path:\n    return executable_dir() / "PlayStoreAppAudit-data"\n\n\ndef portable_mode_active() -> bool:\n    return portable_marker().is_file()\n\n\ndef app_data_dir() -> Path:\n    """Return the active data directory, honoring portable mode everywhere."""\n    target = portable_data_dir() if portable_mode_active() else default_app_data_dir()\n    target.mkdir(parents=True, exist_ok=True)\n    return target\n\n\ndef migrate_portable_mode(enable: bool) -> tuple[bool, str]:\n    """Move app data between normal and portable storage, then toggle the marker."""\n    current = app_data_dir()\n    destination = portable_data_dir() if enable else default_app_data_dir()\n    destination.mkdir(parents=True, exist_ok=True)\n    try:\n        probe = destination / ".write_test"\n        probe.write_text("ok", encoding="utf-8")\n        probe.unlink(missing_ok=True)\n        if current.resolve() != destination.resolve():\n            for item in current.iterdir():\n                target = destination / item.name\n                if item.is_dir():\n                    if target.exists():\n                        shutil.rmtree(target)\n                    shutil.copytree(item, target)\n                else:\n                    shutil.copy2(item, target)\n        if enable:\n            portable_marker().write_text("Play Store App Audit portable mode\\n", encoding="utf-8")\n        else:\n            portable_marker().unlink(missing_ok=True)\n        return True, "Portable mode changed. Restart the app to use the new data location."\n    except Exception as exc:\n        return False, f"Could not change portable mode: {exc}"\n''',
    flags=re.MULTILINE,
)

# 2) Platform behaviour is consumed directly instead of monkey-patched by MainWindow.
base_path = "playstore_app_audit/ui/base_window.py"
replace_once(
    base_path,
    "from playstore_app_audit.services.audit_engine import OUTPUT_FIELDS, AuditConfig, audit_apps, load_apps\n",
    "from playstore_app_audit.platform import runtime\nfrom playstore_app_audit.services.audit_engine import OUTPUT_FIELDS, AuditConfig, audit_apps, load_apps\n",
)
replace_once(
    base_path,
    'PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"\nPLATFORM_TOOLS_PAGE = "https://developer.android.com/tools/releases/platform-tools"\n',
    "PLATFORM_TOOLS_URL = runtime.platform_tools_url()\nPLATFORM_TOOLS_PAGE = runtime.PLATFORM_TOOLS_PAGE\n",
)
regex_once(
    base_path,
    r"def detect_windows_country\(\) -> str:\n.*?\n\ndef managed_platform_tools_dir\(\) -> Path:\n.*?\n    return base / APP_NAME / \"platform-tools\"\n",
    '''def detect_windows_country() -> str:\n    """Compatibility name for the canonical cross-platform Store-country detector."""\n    return runtime.detect_store_country()\n\n\ndef managed_platform_tools_dir() -> Path:\n    return runtime.managed_platform_tools_dir()\n''',
    flags=re.DOTALL,
)

# 3) Service versions come from the package version, never historical module literals.
for service_path, literal in (
    ("playstore_app_audit/services/device_insights.py", 'APP_VERSION = "0.9.0"'),
    ("playstore_app_audit/services/presentation.py", 'APP_VERSION = "0.9.2"'),
    ("playstore_app_audit/services/summary.py", 'APP_VERSION = "0.9.3"'),
):
    text = read(service_path)
    if "from playstore_app_audit import __version__" not in text:
        marker = "from typing import Any\n"
        if marker in text:
            text = text.replace(marker, marker + "\nfrom playstore_app_audit import __version__\n", 1)
        else:
            marker = "from pathlib import Path\n"
            if marker not in text:
                raise RuntimeError(f"Could not place __version__ import in {service_path}")
            text = text.replace(marker, marker + "\nfrom playstore_app_audit import __version__\n", 1)
    if literal not in text:
        raise RuntimeError(f"Expected version literal missing in {service_path}")
    text = text.replace(literal, "APP_VERSION = __version__", 1)
    write(service_path, text)

summary_path = "playstore_app_audit/services/summary.py"
replace_once(summary_path, "import playstore_app_audit.services.presentation as v92\n", "import playstore_app_audit.services.presentation as presentation\n")
replace_once(summary_path, "summary = v92.concise_summary(rows, visible_count)", "summary = presentation.concise_summary(rows, visible_count)")

# 4) Portable-mode functions in device_insights delegate to platform.runtime.
insights_service = "playstore_app_audit/services/device_insights.py"
replace_once(
    insights_service,
    "import requests\n\nimport playstore_app_audit.services.device_metadata as v8\n",
    "import requests\n\nfrom playstore_app_audit.platform import runtime\nimport playstore_app_audit.services.device_metadata as v8\n",
)
regex_once(
    insights_service,
    r"def _exe_dir\(\) -> Path:\n.*?\n\ndef install_v9_state_extensions\(\) -> None:\n",
    '''def portable_marker() -> Path:\n    return runtime.portable_marker()\n\n\ndef portable_data_dir() -> Path:\n    return runtime.portable_data_dir()\n\n\ndef local_data_dir() -> Path:\n    return runtime.default_app_data_dir()\n\n\ndef app_data_dir_v9() -> Path:\n    return runtime.app_data_dir()\n\n\ndef portable_mode_active() -> bool:\n    return runtime.portable_mode_active()\n\n\ndef migrate_portable_mode(enable: bool) -> tuple[bool, str]:\n    return runtime.migrate_portable_mode(enable)\n\n\ndef install_v9_state_extensions() -> None:\n''',
    flags=re.DOTALL,
)
replace_once(insights_service, "    user_state.app_data_dir = app_data_dir_v9\n", "")

# 5) MainWindow no longer mutates imported modules at import time.
main_path = "playstore_app_audit/ui/main_window.py"
regex_once(
    main_path,
    r"# Compatibility imports above are a tested transition layer.*?device_insights\.APP_VERSION = __version__\n\n",
    "",
    flags=re.DOTALL,
)

# 6) Remove the most visible historical alias names from the top-level result/menu layer.
results_path = "playstore_app_audit/ui/results_window.py"
text = read(results_path)
text = text.replace("from app_icon import ensure_runtime_icon\n", "from playstore_app_audit.resources import ensure_runtime_icon\n")
text = text.replace("import playstore_app_audit.services.summary as summary_service\n", "import playstore_app_audit.services.device_insights as device_insights\nimport playstore_app_audit.services.presentation as presentation\nimport playstore_app_audit.services.summary as summary_service\n")
text = re.sub(
    r"\n# Surface the new product version.*?preferences_ui\.v9\.features\.APP_VERSION = summary_service\.APP_VERSION\n",
    "\n",
    text,
    count=1,
    flags=re.DOTALL,
)
text = re.sub(r"\n# Transitional aliases for the final results/UX layer\.\n.*?v93 = summary_service\n", "\n", text, count=1, flags=re.DOTALL)
text = text.replace("preferences_ui.v92.rows_for_output", "presentation.rows_for_output")
text = text.replace("preferences_ui.v9.features.write_html_report", "device_insights.write_html_report")
write(results_path, text)

menu_path = "playstore_app_audit/ui/menu_window.py"
text = read(menu_path)
text = text.replace("from app_icon import ensure_runtime_icon\n", "from playstore_app_audit.resources import ensure_runtime_icon\n")
text = text.replace("import playstore_app_audit.services.presentation as presentation\n", "import playstore_app_audit.services.device_insights as device_insights\nimport playstore_app_audit.services.presentation as presentation\nimport playstore_app_audit.ui.base_window as base_ui\n")
text = re.sub(r"\n# Transitional aliases for the menu layer\.\n.*?user_state = persistence\n", "\n", text, count=1, flags=re.DOTALL)
text = text.replace("preferences_ui.v9.features.ADB_SETUP_GUIDE", "device_insights.ADB_SETUP_GUIDE")
text = text.replace("preferences_ui.v9.features.HEALTH_SCORE_GUIDE", "device_insights.HEALTH_SCORE_GUIDE")
text = text.replace("preferences_ui.v9.v8.v7.qt_base.CRITICALITY", "base_ui.CRITICALITY")
text = text.replace("preferences_ui.v9.v8.v7.qt_base.APP_NAME", "base_ui.APP_NAME")
write(menu_path, text)

# 7) Stop building the source card twice in the final inheritance chain.
replace_once(results_path, "        self._rebuild_source_area()\n", "")

# 8) Bump this architectural milestone to 0.12.0.
replace_once("playstore_app_audit/__init__.py", '__version__ = "0.11.0"', '__version__ = "0.12.0"')
replace_once("pyproject.toml", 'version = "0.11.0"', 'version = "0.12.0"')

# 9) Expand regression tests around the service boundaries we are cleaning up.
(ROOT / "tests/test_device_services.py").write_text(
    '''from __future__ import annotations\n\nfrom playstore_app_audit.services.device_insights import (\n    calculate_health_score,\n    compatibility_label,\n    row_matches_filter,\n)\nfrom playstore_app_audit.services.device_metadata import compare_versions, parse_country_list\n\n\ndef test_country_parser_deduplicates_and_accepts_uk_alias() -> None:\n    valid, invalid = parse_country_list("CH, it; uk ch bad-code", selected_country="it")\n    assert valid == ["ch", "gb"]\n    assert invalid == ["bad-code"]\n\n\ndef test_version_comparison_is_conservative() -> None:\n    assert compare_versions("v1.2.3", "1.2.3") == "Match"\n    assert compare_versions("1.2.3", "1.2.4") == "Different"\n    assert compare_versions("1.2.3", "Varies with device") == "Device-specific"\n    assert compare_versions("", "1.2.3") == "Unknown"\n\n\ndef test_compatibility_buckets() -> None:\n    assert compatibility_label(34, 35) == "Modern"\n    assert compatibility_label(31, 35) == "Aging target"\n    assert compatibility_label(28, 35) == "Legacy target"\n    assert compatibility_label("", 35) == "Unknown"\n\n\ndef test_health_score_penalties_are_transparent() -> None:\n    row = {\n        "criticality_key": "orange",\n        "compatibility_status": "Legacy target",\n        "version_comparison": "Different",\n    }\n    assert calculate_health_score(row) == 55\n\n\ndef test_builtin_filters() -> None:\n    assert row_matches_filter({"criticality_key": "red"}, "Problems")\n    assert row_matches_filter({"criticality_key": "yellow"}, "Old apps")\n    assert row_matches_filter({"installer_source": "Sideload / package installer"}, "Sideloaded")\n    assert row_matches_filter({"version_comparison": "Different"}, "Version mismatch")\n    assert row_matches_filter({"app_enabled": "Disabled"}, "Disabled")\n    assert row_matches_filter({"sensitive_permissions_count": "2"}, "Sensitive permissions")\n''',
    encoding="utf-8",
)

(ROOT / "tests/test_paths.py").write_text(
    '''from __future__ import annotations\n\nfrom pathlib import Path\n\nfrom playstore_app_audit.platform import runtime\n\n\ndef test_default_data_path_is_platform_specific(monkeypatch, tmp_path: Path) -> None:\n    monkeypatch.setattr(runtime, "platform_key", lambda: "linux")\n    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))\n    assert runtime.default_app_data_dir() == tmp_path / runtime.APP_DIR_NAME\n\n\ndef test_portable_marker_switches_active_data_dir(monkeypatch, tmp_path: Path) -> None:\n    monkeypatch.setattr(runtime, "executable_dir", lambda: tmp_path)\n    normal = tmp_path / "normal"\n    monkeypatch.setattr(runtime, "default_app_data_dir", lambda: normal)\n    assert runtime.app_data_dir() == normal\n    runtime.portable_marker().write_text("portable", encoding="utf-8")\n    assert runtime.app_data_dir() == tmp_path / "PlayStoreAppAudit-data"\n''',
    encoding="utf-8",
)

# Add an architecture guard against reintroducing import-time patching in MainWindow.
architecture = read("tests/test_architecture.py")
addition = '''\n\ndef test_main_window_does_not_patch_other_modules_at_import_time() -> None:\n    root = Path(__file__).resolve().parents[1]\n    text = (root / "playstore_app_audit/ui/main_window.py").read_text(encoding="utf-8")\n    forbidden = (\n        "base_ui.detect_windows_country =",\n        "base_ui.managed_platform_tools_dir =",\n        "state_service.app_data_dir =",\n        ".APP_VERSION = __version__",\n    )\n    assert not [marker for marker in forbidden if marker in text]\n'''
if "test_main_window_does_not_patch_other_modules_at_import_time" not in architecture:
    write("tests/test_architecture.py", architecture + addition)

# Update architecture text to describe the new boundary.
arch_path = "docs/ARCHITECTURE.md"
arch = read(arch_path)
arch = arch.replace(
    "Future refactors should reduce inheritance/monkey-patching where it improves clarity, but must not reintroduce versioned modules.",
    "The first v0.12 cleanup removes import-time platform/version patching from MainWindow and centralises portable/app-data paths in the platform layer. Future refactors should continue reducing the remaining UI inheritance/legacy configuration patching where it improves clarity, but must not reintroduce versioned modules.",
)
write(arch_path, arch)

print("v0.12 foundation refactor prepared successfully.")
