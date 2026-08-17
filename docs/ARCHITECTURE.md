# Architecture

Play Store App Audit is a Qt 6 / PySide6 desktop application with one shared source tree for Windows, macOS and Linux.

## Entry points and package layout

`main.py` is the repository entry point and delegates to `playstore_app_audit.app`. The installed console entry point resolves to the same `main()` function.

Production code is organized by responsibility:

- `playstore_app_audit/domain/`: typed domain models and pure business concepts.
- `playstore_app_audit/services/`: Store retrieval, audit, classification, cache/history and reporting behavior.
- `playstore_app_audit/devices/`: ADB discovery, execution and managed Platform-Tools installation.
- `playstore_app_audit/platform/`: operating-system and architecture differences.
- `playstore_app_audit/ui/`: Qt Widgets UI.
- `tests/`: regression, platform, workflow and UI tests.

Version-suffixed compatibility modules are not part of the production architecture. Historical implementations remain available through Git history and tags.

## Dependency direction

The preferred dependency flow is:

```text
UI -> services -> domain
 |       |
 +------> devices/platform
```

UI code coordinates interaction and presentation. Store parsing, audit classification and persistence belong in services; ADB and operating-system details belong in the device and platform layers. Domain and Store parsing code must not depend on Qt.

Side effects stay at the edges: network access in Store/update services, filesystem state in persistence/reporting services, subprocess work in device/platform code and user interaction in the UI.

## Qt UI structure

`playstore_app_audit.ui.main_window.MainWindow` is the public UI entry point. Internally, the window is assembled from focused layers including `base_window`, `audit_window`, `device_window`, `preferences_window`, `menu_window`, `results_window` and related presentation modules.

The layered inheritance structure preserves proven behavior but remains a maintenance caveat. Prefer small, behavior-preserving moves toward focused widgets or controllers when composition clearly improves ownership. Do not combine a broad behavioral rewrite with a structural migration.

UI customization should use explicit local hooks for classification, cache loading and device metadata collection/enrichment rather than mutating imported modules at runtime.

## Data and network boundaries

Input files, settings, audit cache/history, inventory history, snapshots, logs and reports are processed locally. Normal per-user data paths and portable mode are resolved by `playstore_app_audit.platform`.

Google Play audits send package IDs plus Store country/language parameters to public Play endpoints through the Store service. The update checker reads the repository's public GitHub Releases API. Managed Android Platform-Tools are downloaded from Google's platform archive host only after user approval.

ADB operations are read-only with respect to installed applications. Device integration lists packages, reads properties and package-manager metadata, and can open Android's app-details settings screen; it does not install, uninstall, enable or disable applications.

## Cross-platform policy

Windows, macOS and Linux build from the same commit. Platform-specific behavior is kept behind `playstore_app_audit.platform` or `playstore_app_audit.devices`, including:

- Platform-Tools URLs and executable names
- application-data directories and portable paths
- Store-country detection
- common Android SDK locations
- hidden Windows subprocess handling
- packaging, icons and architecture validation

There are no permanent operating-system branches.

## Performance principles

- Play Store retrieval is I/O-bound and uses a bounded worker pool.
- Healthy-result caching avoids unnecessary Store requests.
- Multi-country checks run only when the primary Store result is unavailable or inconclusive, or when metadata needs completion.
- ADB metadata collection first attempts one read-only bulk `dumpsys package` operation and falls back per package only where necessary.
- Device metadata collection and Store auditing can overlap where appropriate.
- Additional async, database, native-extension or QML infrastructure requires a measured bottleneck or user-facing need.

## Deployment policy

Release builds use Python 3.13 and the Qt Essentials subset. Windows packaging uses Nuitka standalone mode through the shared build helper, with the produced runtime validated for architecture, version, required components, forbidden components and startup.

The current build policy is:

- Relevant pushes to `main` automatically test and package Windows x64 only.
- Windows ARM64 is an explicit manual engineering option in the Windows workflow.
- macOS and Linux packaging is manual/on demand.
- Every target uses the same shared source revision.

Windows builds verify native Python/PySide6 inputs, PE architecture, file/product version and packaged startup. Linux builds install the small EGL/X11 runtime set required by the hosted runner and verify the produced ELF artifact. macOS builds exclude the unused Qt Virtual Keyboard platform-input-context plugin and validate bundle version, architecture, signature and startup.

Generated binaries, deployment directories and generated icon files are build outputs, not source files, and remain ignored by Git.
