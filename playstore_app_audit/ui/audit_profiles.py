from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QInputDialog, QMenu, QMessageBox

import playstore_app_audit.services.audit_profiles as audit_profiles
import playstore_app_audit.services.device_metadata as device_metadata
import playstore_app_audit.services.state as state

_SOURCE_LABELS = {
    "any": "Any source",
    "file": "File",
    "device": "Android phone",
}


def _current_country(window: object) -> str:
    edit = getattr(window, "country_edit", None)
    if edit is not None and hasattr(edit, "text"):
        return str(edit.text() or "").strip().lower()
    return "us"


def capture_window_profile(window: object) -> dict[str, Any]:
    settings = state.load_settings()
    return audit_profiles.capture_profile(
        settings,
        _current_country(window),
        source_mode=str(getattr(window, "source_mode", "") or "any"),
    )


def apply_window_profile(window: object, profile: dict[str, Any]) -> None:
    country, expected_source, settings = audit_profiles.apply_profile_to_settings(
        profile, state.load_settings()
    )
    saved = state.save_settings(settings)
    window.user_settings = saved  # type: ignore[attr-defined]

    country_edit = getattr(window, "country_edit", None)
    if country_edit is not None and hasattr(country_edit, "setText"):
        country_edit.setText(country)
        window._store_country_manual_override = True  # type: ignore[attr-defined]
        apply_country = getattr(window, "_apply_store_country_resolution", None)
        if callable(apply_country):
            source_mode = str(getattr(window, "source_mode", "") or "")
            android_locale = (
                getattr(window, "_device_store_locale", None) if source_mode == "device" else None
            )
            apply_country(android_locale)

    workers = getattr(window, "workers_spin", None)
    if workers is not None and hasattr(workers, "setValue"):
        workers.setValue(state.normalise_store_workers(saved.get("store_workers")))

    exclude_system = getattr(window, "exclude_system_source_check", None)
    if exclude_system is not None and hasattr(exclude_system, "setChecked"):
        exclude_system.setChecked(bool(saved.get("exclude_system_source", True)))

    device_metadata.set_fallback_countries(
        saved.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),
        country,
    )

    current_source = str(getattr(window, "source_mode", "") or "")
    source_mismatch = expected_source != "any" and current_source != expected_source
    status = getattr(window, "status_label", None)
    if status is not None and hasattr(status, "setText"):
        message = "Audit preset applied; settings will be used by the next audit"
        if source_mismatch:
            expected_label = _SOURCE_LABELS.get(expected_source, expected_source)
            message += f"; preset expects source: {expected_label}"
        status.setText(message)


def _save_current(window: object, menu: QMenu) -> None:
    name, ok = QInputDialog.getText(window, "Save Audit Preset", "Preset name")
    name = name.strip()
    if not ok or not name:
        return

    existing = audit_profiles.load_profiles()
    if name in existing:
        answer = QMessageBox.question(
            window,
            "Replace Audit Preset?",
            f"An Audit Preset named '{name}' already exists. Replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

    audit_profiles.save_profile(name, capture_window_profile(window))
    populate_audit_profiles_menu(window, menu)
    status = getattr(window, "status_label", None)
    if status is not None and hasattr(status, "setText"):
        status.setText(f"Saved Audit Preset: {name}")


def _apply_named(window: object, menu: QMenu, name: str) -> None:
    profile = audit_profiles.load_profiles().get(name)
    if profile is None:
        QMessageBox.warning(window, "Audit Preset", f"Audit Preset '{name}' no longer exists.")
        populate_audit_profiles_menu(window, menu)
        return
    apply_window_profile(window, profile)


def _delete_named(window: object, menu: QMenu, name: str) -> None:
    answer = QMessageBox.question(
        window,
        "Delete Audit Preset?",
        f"Delete the Audit Preset '{name}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    audit_profiles.delete_profile(name)
    populate_audit_profiles_menu(window, menu)


def _manage_presets(window: object, menu: QMenu) -> None:
    profiles = audit_profiles.load_profiles()
    if not profiles:
        return
    name, ok = QInputDialog.getItem(
        window,
        "Manage Audit Presets",
        "Preset to delete",
        list(profiles),
        0,
        False,
    )
    if ok and name:
        _delete_named(window, menu, name)


def _profile_tooltip(profile: dict[str, Any]) -> str:
    source = _SOURCE_LABELS.get(str(profile.get("source_mode") or "any"), "Any source")
    country = str(profile.get("store_country") or "us").upper()
    language = str((profile.get("settings") or {}).get("store_language") or "auto")
    return f"Source: {source} | Store: {country}/{language}"


def populate_audit_profiles_menu(window: object, menu: QMenu) -> None:
    menu.clear()
    menu.addAction("Save Current as Preset…", lambda: _save_current(window, menu))

    profiles = audit_profiles.load_profiles()
    manage = menu.addAction("Manage Presets…", lambda: _manage_presets(window, menu))
    manage.setEnabled(bool(profiles))
    if not profiles:
        menu.addSeparator()
        empty = menu.addAction("No Saved Audit Presets")
        empty.setEnabled(False)
        return

    menu.addSeparator()
    for name, profile in profiles.items():
        action = menu.addAction(name, lambda _checked=False, n=name: _apply_named(window, menu, n))
        action.setToolTip(_profile_tooltip(profile))
