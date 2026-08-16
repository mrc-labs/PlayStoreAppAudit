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
        "playstore_app_audit/services/persistence.py",
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
