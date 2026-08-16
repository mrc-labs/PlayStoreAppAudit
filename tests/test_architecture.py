from __future__ import annotations

from pathlib import Path


def test_no_legacy_versioned_modules_at_repository_root() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = list(root.glob("playstore_audit_qt_v*.py"))
    forbidden += list(root.glob("playstore_audit_*_features.py"))
    forbidden += [root / "playstore_audit_gui.py", root / "playstore_audit_windows.py"]
    assert not [path for path in forbidden if path.exists()]


def test_canonical_package_owns_core_layers() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        "playstore_app_audit/services/audit_engine.py",
        "playstore_app_audit/services/countries.py",
        "playstore_app_audit/services/device_metadata.py",
        "playstore_app_audit/services/device_insights.py",
        "playstore_app_audit/ui/base_window.py",
        "playstore_app_audit/ui/main_window.py",
        "playstore_app_audit/platform/subprocesses.py",
    ]
    assert all((root / item).is_file() for item in required)


def test_source_does_not_import_retired_module_names() -> None:
    root = Path(__file__).resolve().parents[1]
    retired = (
        "playstore_audit_qt_v",
        "playstore_audit_v8_features",
        "playstore_audit_v9_features",
        "playstore_audit_v9_2_features",
        "playstore_audit_v9_3_features",
    )
    offenders: list[str] = []
    for path in (root / "playstore_app_audit").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(name in text for name in retired):
            offenders.append(str(path.relative_to(root)))
    assert not offenders


def test_main_window_does_not_patch_other_modules_at_import_time() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "playstore_app_audit/ui/main_window.py").read_text(encoding="utf-8")
    forbidden = (
        "base_ui.detect_windows_country =",
        "base_ui.managed_platform_tools_dir =",
        "state_service.app_data_dir =",
        ".APP_VERSION = __version__",
    )
    assert not [marker for marker in forbidden if marker in text]


def test_legacy_state_shim_and_version_aliases_are_gone() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "playstore_app_audit"
    assert not (package / "services/persistence.py").exists()

    offenders: list[str] = []
    forbidden = (
        "playstore_app_audit.services.persistence",
        "qt_base = base_ui",
        "v7 = compact_ui",
        "v8 = device_ui",
        "v9 = insights_ui",
        "user_state = persistence",
        "features = device_insights",
    )
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in text:
                offenders.append(f"{path.relative_to(root)}: {marker}")
    assert not offenders, offenders


def test_ui_modules_do_not_mutate_table_schema_across_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    ui = root / "playstore_app_audit/ui"
    forbidden = (
        "base_ui.COLUMNS =",
        "base_ui.COLUMN_LABELS.update",
        "base_ui.EXPORT_FIELDS =",
        "compact_ui.MODEL_COLUMNS =",
        "compact_ui.DEFAULT_WIDTHS.update",
        "device_ui.V8_MODEL_COLUMNS =",
    )
    offenders: list[str] = []
    for path in ui.glob("*.py"):
        if path.name == "schema.py":
            continue
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            if marker in source:
                offenders.append(f"{path.name}: {marker}")
    assert not offenders, offenders


def test_no_runtime_cross_module_monkey_patching() -> None:
    root = Path(__file__).resolve().parents[1]
    forbidden = (
        "base_ui.audit_apps =",
        "base_ui.classify_criticality =",
        "compact_ui.audit_apps_multicountry =",
        "compact_ui.load_fresh_cache =",
        "device_ui.device_metadata.collect_device_metadata =",
        "device_insights.VIEW_PRESETS =",
        "Development assistance: OpenAI ChatGPT",
    )
    for path in (root / "playstore_app_audit").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for snippet in forbidden:
            assert snippet not in source, f"{snippet!r} reintroduced in {path.relative_to(root)}"
