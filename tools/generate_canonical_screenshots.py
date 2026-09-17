#!/usr/bin/env python3
"""Generate deterministic synthetic screenshots for README and in-app help."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import requests
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import QApplication, QWidget

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.main_window as main_window_ui
from playstore_app_audit.ui.changes_history import (
    ChangesHistoryAvailability,
    ChangesHistoryDialog,
)
from playstore_app_audit.ui.local_apk_mass_rename_dialog import (
    LocalApkMassRenameDialog,
)
from playstore_app_audit.ui.main_window import MainWindow

CANONICAL_SCREENSHOTS: tuple[str, ...] = (
    "store-app-audit-phone-maintenance.png",
    "store-app-audit-changes-history.png",
    "store-app-audit-local-apk.png",
    "store-app-audit-mass-rename.png",
)

CANONICAL_DIMENSIONS: dict[str, tuple[int, int]] = {
    "store-app-audit-phone-maintenance.png": (1560, 900),
    "store-app-audit-local-apk.png": (1560, 900),
    "store-app-audit-changes-history.png": (820, 720),
    "store-app-audit-mass-rename.png": (1080, 640),
}


def _forbid_network(*_args: object, **_kwargs: object) -> object:
    raise RuntimeError(
        "Canonical screenshot generation must not use the network."
    )


def _install_no_external_dependency_guards() -> None:
    requests.sessions.Session.request = _forbid_network

    device_insights.check_for_updates = lambda: {
        "status": "error",
        "message": "disabled during screenshot generation",
    }

    device_insights.get_recent_sources = lambda: []

    # MainWindow may perform background ADB executable discovery while it is
    # created. The documentation generator must not depend on local SDK/device
    # state, so deliberately report no ADB executable.
    main_window_ui.find_adb = lambda: None


def _documentation_palette() -> QPalette:
    palette = QPalette()

    values = (
        (QPalette.ColorRole.Window, "#F5F7FA"),
        (QPalette.ColorRole.WindowText, "#20252B"),
        (QPalette.ColorRole.Base, "#FFFFFF"),
        (QPalette.ColorRole.AlternateBase, "#FAFBFC"),
        (QPalette.ColorRole.Text, "#20252B"),
        (QPalette.ColorRole.Button, "#FFFFFF"),
        (QPalette.ColorRole.ButtonText, "#20252B"),
        (QPalette.ColorRole.Highlight, "#DDEBF7"),
        (QPalette.ColorRole.HighlightedText, "#18212A"),
        (QPalette.ColorRole.PlaceholderText, "#66737D"),
    )

    for role, value in values:
        palette.setColor(
            role,
            QColor(value),
        )

    return palette


def _process_events(
    app: QApplication,
    cycles: int = 12,
) -> None:
    for _ in range(cycles):
        app.processEvents()


def _save_widget(
    widget: QWidget,
    output: Path,
    *,
    width: int,
    height: int,
    app: QApplication,
) -> None:
    widget.resize(width, height)
    widget.show()
    widget.raise_()

    _process_events(app)

    pixmap = widget.grab()

    if pixmap.isNull():
        raise RuntimeError(
            f"Qt returned a null pixmap for {output.name}"
        )

    if not pixmap.save(str(output), "PNG"):
        raise RuntimeError(
            f"Could not save screenshot: {output}"
        )

    image = QImage(str(output))

    if image.isNull():
        raise RuntimeError(
            f"Could not reopen generated PNG: {output}"
        )

    # Visual fidelity is not judged on Qt's offscreen platform because
    # available fonts and rendering backends vary across CI environments.
    # This generator-level invariant is intentionally structural: the PNG
    # must decode and have the exact requested geometry. The committed
    # canonical Windows assets receive the stronger size and human-visual
    # acceptance gates separately.

    if (image.width(), image.height()) != (
        width,
        height,
    ):
        raise RuntimeError(
            f"Unexpected PNG dimensions for {output.name}: "
            f"{image.width()}x{image.height()} "
            f"!= {width}x{height}"
        )


def _settings() -> dict[str, object]:
    values = dict(state.DEFAULT_SETTINGS)

    values.update(
        {
            "view_preset": "Source Details",
            "recent_sources": [],
            "show_app_icons": False,
            "details_panel_position": "right",
            "active_filter_preset": "All",
            "health_score_enabled": True,
            "compare_previous": True,
            "inventory_history_enabled": True,
            "changes_history_enabled": True,
            "auto_update_check": False,
        }
    )

    return values


def _install_ephemeral_settings(
    values: dict[str, object],
) -> None:
    def load_settings() -> dict[str, object]:
        return dict(values)

    def save_settings(
        updated: dict[str, object],
    ) -> dict[str, object]:
        values.clear()
        values.update(updated)
        return dict(values)

    state.load_settings = load_settings
    state.save_settings = save_settings

    # Older layered UI modules import these functions directly.
    compact_ui.load_settings = load_settings
    compact_ui.save_settings = save_settings


def phone_rows() -> list[dict[str, object]]:
    return [
        {
            "source_mode": "device",
            "criticality_key": "green",
            "criticality": "Recent",
            "package_name": "com.example.juniper.notes",
            "app_name": "Juniper Notes",
            "play_title": "Juniper Notes",
            "play_last_update": "2026-09-02",
            "age_days": 14,
            "play_status": "available",
            "play_version": "5.4.2",
            "installed_version": "5.4.2",
            "installed_version_code": 5040200,
            "version_comparison": "Match",
            "installer_source": "Google Play",
            "installer_package": "com.android.vending",
            "compatibility_status": "Modern target",
            "target_sdk": 35,
            "min_sdk": 26,
            "device_change": "No change",
            "health_score": 96,
            "notes": "Current Store listing and installed version.",
        },
        {
            "source_mode": "device",
            "criticality_key": "yellow",
            "criticality": "Aging",
            "package_name": "com.example.orbit.tasks",
            "app_name": "Orbit Tasks",
            "play_title": "Orbit Tasks",
            "play_last_update": "2025-08-04",
            "age_days": 408,
            "play_status": "available",
            "play_version": "7.5.0",
            "installed_version": "7.2.0",
            "installed_version_code": 7020000,
            "version_comparison": "Outdated",
            "installer_source": "Google Play",
            "installer_package": "com.android.vending",
            "compatibility_status": "Modern target",
            "target_sdk": 34,
            "min_sdk": 26,
            "device_change": "Version changed",
            "health_score": 74,
            "notes": "Installed version trails available Store evidence.",
        },
        {
            "source_mode": "device",
            "criticality_key": "orange",
            "criticality": "Stale",
            "package_name": "com.example.cedar.maps",
            "app_name": "Cedar Maps",
            "play_title": "Cedar Maps",
            "play_last_update": "2023-05-19",
            "age_days": 1216,
            "play_status": "available",
            "play_version": "3.9.1",
            "installed_version": "3.9.1",
            "installed_version_code": 3090100,
            "version_comparison": "Match",
            "installer_source": "Google Play",
            "installer_package": "com.android.vending",
            "compatibility_status": "Legacy target",
            "target_sdk": 29,
            "min_sdk": 23,
            "device_change": "No change",
            "health_score": 58,
            "notes": "Old listing and legacy Android target deserve review.",
        },
        {
            "source_mode": "device",
            "criticality_key": "red",
            "criticality": "Not Found",
            "package_name": "com.example.lumen.reader",
            "app_name": "Lumen Reader",
            "play_title": "",
            "play_last_update": "",
            "age_days": "",
            "play_status": "not_found_in_checked_countries",
            "play_version": "",
            "installed_version": "2.6.4",
            "installed_version_code": 2060400,
            "version_comparison": "Unknown",
            "installer_source": "Package installer",
            "installer_package": "",
            "compatibility_status": "Aging target",
            "target_sdk": 32,
            "min_sdk": 24,
            "device_change": "New on device",
            "health_score": 31,
            "notes": "No listing found in the configured Store markets.",
        },
        {
            "source_mode": "device",
            "criticality_key": "green",
            "criticality": "Recent",
            "package_name": "com.example.harbor.weather",
            "app_name": "Harbor Weather",
            "play_title": "Harbor Weather",
            "play_last_update": "2026-08-30",
            "age_days": 17,
            "play_status": "available",
            "play_version": "Varies with device",
            "resolved_play_version": "20.5.1",
            "resolved_play_version_code": 2050104,
            "device_specific_profile": (
                "Samsung Galaxy S20+ • Android 13 / API 33"
            ),
            "device_specific_resolver_status": "resolved",
            "installed_version": "20.4.0",
            "installed_version_code": 2040001,
            "version_comparison": "Outdated",
            "installer_source": "Google Play",
            "installer_package": "com.android.vending",
            "compatibility_status": "Modern target",
            "target_sdk": 35,
            "min_sdk": 26,
            "device_change": "No change",
            "health_score": 88,
            "notes": "Device Specific Store version resolved separately.",
        },
        {
            "source_mode": "device",
            "criticality_key": "blue",
            "criticality": "Anomaly",
            "package_name": "com.example.mosaic.vault",
            "app_name": "Mosaic Vault",
            "play_title": "Mosaic Vault",
            "play_last_update": "",
            "age_days": "",
            "play_status": "multi_country_check_inconclusive",
            "play_version": "",
            "installed_version": "1.8.0",
            "installed_version_code": 1080000,
            "version_comparison": "Unknown",
            "installer_source": "Package installer",
            "installer_package": "",
            "compatibility_status": "Modern target",
            "target_sdk": 35,
            "min_sdk": 28,
            "device_change": "Installer changed",
            "health_score": 71,
            "notes": "Store verification remained inconclusive.",
        },
    ]


def local_apk_rows() -> list[dict[str, object]]:
    return [
        {
            "source_mode": "local_apk",
            "criticality_key": "green",
            "criticality": "Recent",
            "package_name": "com.example.juniper.notes",
            "play_title": "Juniper Notes",
            "play_last_update": "2026-09-02",
            "age_days": 14,
            "play_status": "available",
            "play_version": "5.4.2",
            "local_apk_file_name": "JuniperNotes_5.1.0.apk",
            "local_apk_label": "Juniper Notes",
            "local_apk_version_name": "5.1.0",
            "local_apk_version_code": 5010000,
            "local_apk_version_comparison": "Outdated",
            "local_apk_sha256": "1a" * 32,
            "health_score": 86,
            "notes": "Archived APK is older than current Store evidence.",
        },
        {
            "source_mode": "local_apk",
            "criticality_key": "yellow",
            "criticality": "Aging",
            "package_name": "com.example.orbit.tasks",
            "play_title": "Orbit Tasks",
            "play_last_update": "2025-08-04",
            "age_days": 408,
            "play_status": "available",
            "play_version": "7.5.0",
            "local_apk_file_name": "OrbitTasks_7.5.0.apkm",
            "local_apk_label": "Orbit Tasks",
            "local_apk_version_name": "7.5.0",
            "local_apk_version_code": 7050000,
            "local_apk_version_comparison": "Match",
            "local_apk_sha256": "2b" * 32,
            "health_score": 81,
            "notes": "Local package matches current Store evidence.",
        },
        {
            "source_mode": "local_apk",
            "criticality_key": "green",
            "criticality": "Recent",
            "package_name": "com.example.harbor.weather",
            "play_title": "Harbor Weather",
            "play_last_update": "2026-08-30",
            "age_days": 17,
            "play_status": "available",
            "play_version": "Varies with device",
            "resolved_play_version": "20.5.1",
            "resolved_play_version_code": 2050104,
            "device_specific_profile": (
                "Samsung Galaxy S20+ • Android 13 / API 33"
            ),
            "device_specific_resolver_status": "resolved",
            "local_apk_file_name": "HarborWeather_20.4.0.xapk",
            "local_apk_label": "Harbor Weather",
            "local_apk_version_name": "20.4.0",
            "local_apk_version_code": 2040001,
            "local_apk_version_comparison": "Device-specific",
            "local_apk_sha256": "3c" * 32,
            "health_score": 90,
            "notes": "Store relationship depends on the reference profile.",
        },
        {
            "source_mode": "local_apk",
            "criticality_key": "orange",
            "criticality": "Stale",
            "package_name": "com.example.cedar.maps",
            "play_title": "Cedar Maps",
            "play_last_update": "2023-05-19",
            "age_days": 1216,
            "play_status": "available",
            "play_version": "3.9.1",
            "local_apk_file_name": "CedarMaps_4.0-beta.apk",
            "local_apk_label": "Cedar Maps",
            "local_apk_version_name": "4.0-beta",
            "local_apk_version_code": 4000000,
            "local_apk_version_comparison": "Newer",
            "local_apk_sha256": "4d" * 32,
            "health_score": 66,
            "notes": "Local build is newer than public Store evidence.",
        },
        {
            "source_mode": "local_apk",
            "criticality_key": "red",
            "criticality": "Not Found",
            "package_name": "com.example.lumen.reader",
            "play_title": "",
            "play_last_update": "",
            "age_days": "",
            "play_status": "not_found_in_checked_countries",
            "play_version": "",
            "local_apk_file_name": "LumenReader_2.6.4.apk",
            "local_apk_label": "Lumen Reader",
            "local_apk_version_name": "2.6.4",
            "local_apk_version_code": 2060400,
            "local_apk_version_comparison": "Unknown",
            "local_apk_sha256": "5e" * 32,
            "health_score": 34,
            "notes": "Local artifact retained despite uncertain Store availability.",
        },
    ]


def mass_rename_rows(
    directory: Path,
) -> list[dict[str, object]]:
    specs = (
        (
            "JN_5.1.0.apk",
            "com.example.juniper.notes",
            "Juniper Notes",
            "5.1.0",
            "Productivity",
        ),
        (
            "Orbit Tasks_7.5.0.apkm",
            "com.example.orbit.tasks",
            "Orbit Tasks",
            "7.5.0",
            "Productivity",
        ),
        (
            "HW_20.4.0.xapk",
            "com.example.harbor.weather",
            "Harbor Weather",
            "20.4.0",
            "Weather",
        ),
        (
            "CM_4.0-beta.apk",
            "com.example.cedar.maps",
            "Cedar Maps",
            "4.0-beta",
            "Maps & Navigation",
        ),
    )

    rows: list[dict[str, object]] = []

    for (
        filename,
        package_name,
        app_name,
        version,
        category,
    ) in specs:
        source = directory / filename
        source.write_bytes(
            b"Store App Audit synthetic screenshot fixture\n"
        )

        rows.append(
            {
                "source_mode": "local_apk",
                "local_apk_location": str(source),
                "package_name": package_name,
                "local_apk_label": app_name,
                "play_title": app_name,
                "play_category": category,
                "local_apk_version_name": version,
            }
        )

    return rows


def _prepare_window(
    app: QApplication,
    settings: dict[str, object],
    *,
    source_mode: str,
    rows: list[dict[str, object]],
    source_label: str,
    selected_row: int,
) -> MainWindow:
    settings["view_preset"] = "Source Details"

    window = MainWindow()
    window.resize(1560, 900)

    window.source_mode = source_mode
    window.current_rows = list(rows)
    window.model.set_rows(rows)

    window.country_edit.setText("CH")
    window.source_label.setText(source_label)

    if source_mode == "local_apk":
        window._local_apk_candidates = tuple(
            Path(
                str(
                    row.get("local_apk_file_name")
                    or f"fixture-{index}.apk"
                )
            )
            for index, row in enumerate(rows)
        )

    if hasattr(window.proxy, "invalidate"):
        window.proxy.invalidate()

    window._apply_column_visibility(
        reset_order=True
    )
    window._sync_action_availability()
    window._update_summary()

    selected_row = max(
        0,
        min(
            selected_row,
            len(rows) - 1,
        ),
    )

    window.table.selectRow(selected_row)

    if hasattr(window, "details_panel"):
        window.details_panel.set_row(
            rows[selected_row]
        )
        window.details_panel.show()

    if hasattr(window, "details_splitter"):
        window.details_splitter.setSizes(
            [1030, 500]
        )

    _process_events(app)

    return window


def generate(
    output_dir: Path,
) -> tuple[Path, ...]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    _install_no_external_dependency_guards()

    app = (
        QApplication.instance()
        or QApplication([])
    )

    assert isinstance(app, QApplication)

    app.setApplicationName(
        "Store App Audit Canonical Documentation Capture"
    )
    app.setPalette(
        _documentation_palette()
    )

    settings = _settings()
    _install_ephemeral_settings(settings)

    outputs: list[Path] = []

    phone_window = _prepare_window(
        app,
        settings,
        source_mode="device",
        rows=phone_rows(),
        source_label=(
            "Demo Android phone inventory • 6 packages loaded • "
            "Store country CH"
        ),
        selected_row=2,
    )

    try:
        target = (
            output_dir
            / "store-app-audit-phone-maintenance.png"
        )

        _save_widget(
            phone_window,
            target,
            width=1560,
            height=900,
            app=app,
        )
        outputs.append(target)

        availability = ChangesHistoryAvailability(
            automatic_tracking=True,
            store_tracking=True,
            store_review=True,
            store_had_baseline=True,
            device_tracking=True,
            device_review=True,
            snapshots_available=True,
        )

        changes = ChangesHistoryDialog(
            phone_window,
            availability,
            review_store_changes=lambda: None,
            review_device_changes=lambda: None,
            save_snapshot=lambda: None,
            compare_snapshot=lambda: None,
            save_tracking_settings=(
                lambda automatic, store, device: (
                    ChangesHistoryAvailability(
                        automatic_tracking=automatic,
                        store_tracking=store,
                        store_review=True,
                        store_had_baseline=True,
                        device_tracking=device,
                        device_review=True,
                        snapshots_available=True,
                    )
                )
            ),
        )

        try:
            target = (
                output_dir
                / "store-app-audit-changes-history.png"
            )

            _save_widget(
                changes,
                target,
                width=820,
                height=720,
                app=app,
            )
            outputs.append(target)
        finally:
            changes.close()
            changes.deleteLater()
            _process_events(app, cycles=3)

    finally:
        phone_window.close()
        phone_window.deleteLater()
        _process_events(app, cycles=4)

    local_window = _prepare_window(
        app,
        settings,
        source_mode="local_apk",
        rows=local_apk_rows(),
        source_label=(
            "Demo Local APK collection • 5 package files loaded • "
            "Store country CH"
        ),
        selected_row=0,
    )

    try:
        target = (
            output_dir
            / "store-app-audit-local-apk.png"
        )

        _save_widget(
            local_window,
            target,
            width=1560,
            height=900,
            app=app,
        )
        outputs.append(target)

        with tempfile.TemporaryDirectory(
            prefix="StoreAppAudit-screenshot-mass-rename-"
        ) as temp:
            rows = mass_rename_rows(
                Path(temp)
            )

            rename = LocalApkMassRenameDialog(
                local_window,
                rows,
            )

            rename.template_edit.setText(
                "{appname}_{localversion}"
            )

            try:
                target = (
                    output_dir
                    / "store-app-audit-mass-rename.png"
                )

                _save_widget(
                    rename,
                    target,
                    width=1080,
                    height=640,
                    app=app,
                )
                outputs.append(target)
            finally:
                rename.close()
                rename.deleteLater()
                _process_events(app, cycles=3)

    finally:
        local_window.close()
        local_window.deleteLater()
        _process_events(app, cycles=4)

    generated_names = tuple(
        path.name
        for path in outputs
    )

    if generated_names != CANONICAL_SCREENSHOTS:
        raise RuntimeError(
            "Canonical screenshot set/order changed unexpectedly: "
            f"{generated_names!r}"
        )

    return tuple(outputs)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/images"),
        help=(
            "Destination directory. "
            "Default: docs/images"
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    paths = generate(
        args.output_dir
    )

    print(
        "Canonical Store App Audit screenshots generated:"
    )

    for path in paths:
        image = QImage(str(path))

        print(
            f"  {path} "
            f"({image.width()}x{image.height()}, "
            f"{path.stat().st_size} bytes)"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
