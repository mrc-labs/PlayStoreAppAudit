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

## Current migration state

The package structure above is now the public/canonical entry layer. The existing top-level `playstore_audit_qt_v*.py` modules are still used internally as a compatibility layer so that the refactor does not replace a large amount of proven UI/audit behaviour in one risky change.

No new product feature should be added to version-suffixed UI modules. The next architectural cleanup is to migrate their remaining methods into focused package modules and then delete the compatibility chain.

This is intentionally a strangler-style refactor: stable behaviour remains working while ownership moves module by module behind clean boundaries.

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
