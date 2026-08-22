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
        view_preset=str(settings.get("view_preset") or "Basic"),
    )


def _sync_view_actions(window: object, view_preset: str) -> None:
    for action in getattr(window, "view_preset_actions", []) or []:
        if hasattr(action, "text") and hasattr(action, "setChecked"):
            action.setChecked(action.text() == view_preset)


def apply_window_profile(window: object, profile: dict[str, Any]) -> None:
    country, expected_source, view_preset, settings = audit_profiles.apply_profile_to_settings(
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

    set_view = getattr(window, "_set_view_preset", None)
    if callable(set_view):
        set_view(view_preset)
        _sync_view_actions(window, view_preset)

    device_metadata.set_fallback_countries(
        saved.get("fallback_countries", device_metadata.DEFAULT_FALLBACK_COUNTRIES),
        country,
    )

    current_source = str(getattr(window, "source_mode", "") or "")
    source_mismatch = expected_source != "any" and current_source != expected_source
    status = getattr(window, "status_label", None)
    if status is not None and hasattr(status, "setText"):
        message = "Audit profile applied; settings will be used by the next audit"
        if source_mismatch:
            expected_label = _SOURCE_LABELS.get(expected_source, expected_source)
            message += f"; profile expects source: {expected_label}"
        status.setText(message)


def _save_current(window: object, menu: QMenu) -> None:
    name, ok = QInputDialog.getText(window, "Save audit profile", "Profile name")
    name = name.strip()
    if not ok or not name:
        return

    existing = audit_profiles.load_profiles()
    if name in existing:
        answer = QMessageBox.question(
            window,
            "Replace audit profile?",
            f"An audit profile named '{name}' already exists. Replace it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

    audit_profiles.save_profile(name, capture_window_profile(window))
    populate_audit_profiles_menu(window, menu)
    status = getattr(window, "status_label", None)
    if status is not None and hasattr(status, "setText"):
        status.setText(f"Saved audit profile: {name}")


def _apply_named(window: object, menu: QMenu, name: str) -> None:
    profile = audit_profiles.load_profiles().get(name)
    if profile is None:
        QMessageBox.warning(window, "Audit profile", f"Audit profile '{name}' no longer exists.")
        populate_audit_profiles_menu(window, menu)
        return
    apply_window_profile(window, profile)


def _delete_named(window: object, menu: QMenu, name: str) -> None:
    answer = QMessageBox.question(
        window,
        "Delete audit profile?",
        f"Delete the audit profile '{name}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        return
    audit_profiles.delete_profile(name)
    populate_audit_profiles_menu(window, menu)


def _profile_tooltip(profile: dict[str, Any]) -> str:
    source = _SOURCE_LABELS.get(str(profile.get("source_mode") or "any"), "Any source")
    country = str(profile.get("store_country") or "us").upper()
    view = str(profile.get("view_preset") or "Basic")
    language = str((profile.get("settings") or {}).get("store_language") or "auto")
    return f"Source: {source} | Store: {country}/{language} | View: {view}"


def populate_audit_profiles_menu(window: object, menu: QMenu) -> None:
    menu.clear()
    menu.addAction("Save current audit settings as profile…", lambda: _save_current(window, menu))

    profiles = audit_profiles.load_profiles()
    if not profiles:
        menu.addSeparator()
        empty = menu.addAction("No saved audit profiles")
        empty.setEnabled(False)
        return

    menu.addSeparator()
    for name, profile in profiles.items():
        action = menu.addAction(name, lambda _checked=False, n=name: _apply_named(window, menu, n))
        action.setToolTip(_profile_tooltip(profile))

    delete_menu = menu.addMenu("Delete profile")
    for name in profiles:
        delete_menu.addAction(name, lambda _checked=False, n=name: _delete_named(window, menu, n))
