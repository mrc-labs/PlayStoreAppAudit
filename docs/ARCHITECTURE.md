# Architecture

## Target architecture

Play Store App Audit is a single Qt 6 / PySide6 desktop application with one shared source tree for Windows, macOS and Linux.

The canonical application entry point is `main.py`, which delegates to `playstore_app_audit.app`.

New code is organised as follows:

- `playstore_app_audit/domain/`: typed application/domain objects.
- `playstore_app_audit/services/`: platform-independent audit and Play Store service boundaries.
- `playstore_app_audit/devices/`: Android/ADB integration.
- `playstore_app_audit/platform/`: operating-system detection, application data paths, Platform-Tools URLs and subprocess details.
- `playstore_app_audit/ui/`: Qt Widgets UI.
- `tests/`: regression and platform-abstraction tests.

## Current architecture

The migration away from version-suffixed top-level modules is complete. Production code now lives under `playstore_app_audit/`; the repository no longer depends on `playstore_audit_qt_v*.py`, `*_fixed.py` or `*_stable.py` compatibility files.

The Qt window is organised into focused internal layers (`base_window`, `audit_window`, `compact_window`, `device_window`, `insights_window`, `table_window`, `preferences_window`, `menu_window`, `results_window`) with `main_window.py` as the only public UI entry point. Services and platform code are likewise inside the package. The v0.12 cleanup removes import-time platform/version patching from MainWindow, centralises portable/app-data paths in the platform layer, and removes the persistence compatibility shim plus historical v7/v8/v9 module aliases. Table columns, labels, widths and export extras now come from `ui/schema.py`, so importing child windows no longer changes the table schema. Future refactors should continue reducing the remaining behavioural audit/classification patching and UI inheritance where it improves clarity, but must not reintroduce versioned modules.

## Dependency direction

Preferred direction:

`UI -> application/services -> domain`

`UI/services -> devices/platform` only at the edges where OS/device interaction is required.

The domain and Play Store parsing logic must not import Qt.

## Platform policy

There are no Windows/macOS/Linux source branches. All three targets build the same commit.

Platform-specific concerns are abstracted behind `playstore_app_audit.platform` and `playstore_app_audit.devices`, including:

- Android Platform-Tools download URL and ADB executable name
- application-data directories
- Store-country detection
- hiding Windows subprocess consoles
- common Android SDK locations
- packaging/icon differences

## Performance policy

- Play Store retrieval remains I/O-bound and uses bounded worker threads.
- Healthy-result caching avoids unnecessary Store requests.
- Multi-country checks run only when the primary Store market is unavailable/inconclusive.
- ADB metadata collection is bounded and runs in parallel with the Store audit where possible.
- Do not introduce async/Rust/database/QML infrastructure unless profiling identifies a real bottleneck it solves.

## Deployment

Runtime uses the Qt Essentials subset, not the full PySide6 Addons meta-package.

`pyside6-deploy` / Nuitka is the preferred release deployment path. Windows builds automatically in CI. macOS and Linux packaging is manually dispatched only.
