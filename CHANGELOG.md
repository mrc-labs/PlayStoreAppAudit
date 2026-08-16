# Changelog

All notable user-facing and maintenance changes to Play Store App Audit are recorded here.

## [0.12.0] - 2026-08-16

### Added

- Cross-platform runtime abstraction for application data, Store-country detection and Android Platform-Tools paths.
- Portable-mode data-path handling in the canonical platform layer.
- Bulk Android package metadata collection through one read-only `dumpsys package` request, with conservative per-package fallback.
- Canonical immutable Qt table schema in `playstore_app_audit/ui/schema.py`.
- Regression coverage for country parsing, version comparison, Android compatibility labels, Health score, filters, portable paths, ADB bulk parsing and UI schema integrity.
- Lightweight pull-request quality workflow covering compile, tests, Ruff and Qt offscreen smoke checks.

### Changed

- Application version is now 0.12.0 across the package and project metadata.
- State/settings/cache/history code now uses `services.state` directly; the temporary persistence compatibility shim has been removed.
- Historical `v7`/`v8`/`v9`, `qt_base`, `features` and `user_state` module aliases have been replaced by descriptive imports.
- Table columns, labels, widths and export extras no longer depend on UI import order.
- Device metadata collection can avoid hundreds of individual `dumpsys package <package>` subprocesses on large app inventories.
- Service/report version strings now follow the package version rather than historical 0.9.x literals.

### Fixed

- MainWindow no longer mutates platform, state or version modules at import time.
- Final source controls are no longer rebuilt twice during window construction.
- Saved Qt header state is invalidated once for the new canonical table schema.

### Compatibility

- Windows remains the primary automatic release build.
- Linux and macOS use the same Qt/PySide6 source tree and are validated as release targets.
- CustomTkinter remains retired and preserved only by the historical `legacy-customtkinter-v9.3` tag.

## [0.11.0] - 2026-08-16

### Changed

- Flattened the application into the canonical `playstore_app_audit/` package.
- Retired version-suffixed top-level Qt modules and obsolete Tkinter launchers.
- Established `main.py` / `playstore_app_audit.app` as the canonical application entry point.
- Adopted PySide6 Essentials with the Nuitka-based `pyside6-deploy` release path.
