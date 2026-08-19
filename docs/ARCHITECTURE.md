# Architecture

Play Store App Audit is a Qt 6 / PySide6 desktop application with one shared source tree for Windows, macOS and Linux.

Durable engineering constraints are recorded in `PROJECT_DECISIONS.md`. Current release state and the active maintenance queue are recorded in `PROJECT_STATUS.md`.

## Entry points and package layout

`main.py` is the repository entry point and delegates to `playstore_app_audit.app`. The installed console entry point resolves to the same `main()` function.

Production code is organized by responsibility:

- `playstore_app_audit/domain/`: typed domain models and pure business concepts.
- `playstore_app_audit/services/`: Store retrieval, audit, classification, cache/history and reporting behaviour.
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

The layered inheritance structure preserves proven behaviour but remains a maintenance caveat. Prefer small, behaviour-preserving moves toward focused widgets or controllers when composition clearly improves ownership. Do not combine a broad behavioural rewrite with a structural migration.

UI customization should use explicit local hooks for classification, cache loading and device metadata collection/enrichment rather than mutating imported modules at runtime.

Qt Widgets remains the production UI technology unless a demonstrated UX, maintainability or performance reason justifies migration. v1.3 explicitly forces the Qt Fusion style; v1.4 should test native platform style and audit custom QSS, especially scrollbar rules, before considering a theme dependency.

## Data and network boundaries

Input files, settings, audit cache/history, inventory history, snapshots, logs and reports are processed locally. Normal per-user data paths and portable mode are resolved by `playstore_app_audit.platform`.

Google Play audits send package IDs plus Store country/language parameters to public Play endpoints through the Store service. The update checker reads the repository's public GitHub Releases API. Managed Android Platform-Tools are downloaded from Google's platform archive host only after user approval.

ADB operations are read-only with respect to installed applications. Device integration lists packages, reads properties and package-manager metadata, and can open Android's app-details settings screen; it does not install, uninstall, enable or disable applications.

## Cross-platform policy

Windows, macOS and Linux production releases derive from one exact frozen `main` commit. Platform-specific behaviour is kept behind `playstore_app_audit.platform` or `playstore_app_audit.devices`, including:

- Platform-Tools URLs and executable names
- application-data directories and portable paths
- Store-country detection
- common Android SDK locations
- hidden Windows subprocess handling
- packaging, icons, signing and architecture validation

There are no permanent operating-system branches.

## Performance principles

- Play Store retrieval is I/O-bound and uses a bounded worker pool.
- Healthy-result caching avoids unnecessary Store requests.
- Multi-country checks run only when the primary Store result is unavailable or inconclusive, or when metadata needs completion.
- ADB metadata collection first attempts one read-only bulk `dumpsys package` operation and falls back per package only where necessary.
- Device metadata collection and Store auditing can overlap where appropriate.
- Additional async, database, native-extension or QML infrastructure requires a measured bottleneck or user-facing need.

## Deployment and release architecture

Release packaging uses Python 3.13 and the Qt Essentials subset. The v1.3 release baseline pins `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3`.

A production release is an exact-SHA assembly, not a collection of independently built platform packages:

1. Cheap Quality CI passes on the final `main` commit.
2. One exact full `main` SHA is frozen.
3. Six release candidates are built from that SHA: Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64.
4. Build workflows reject expected/dispatch/checkout SHA mismatches.
5. The assembler validates the six candidates and produces exactly eight public assets: six platform ZIPs, one consolidated third-party source archive and one `SHA256SUMS.txt`.
6. The annotated version tag is created on the frozen SHA after artifact validation.
7. The already validated assets are published. Tag pushes do not rebuild them.

If source or release tooling changes after the SHA freeze, all six candidates must be rebuilt from the new exact SHA. Artifacts from different source revisions must never be mixed.

### Platform package forms

- Windows: Nuitka standalone application packaged as ZIP.
- Linux: Nuitka standalone tree packaged as ZIP, never onefile for production release packaging. Qt/PySide/Shiboken shared libraries remain replaceable.
- macOS: `.app` bundle packaged as ZIP.

Windows package validation covers native Python/PySide inputs, PE architecture, version metadata, runtime content, startup and legal material. Linux validates ELF architecture, runtime content and startup. macOS validates Mach-O architecture, bundle metadata, runtime content, signature state and startup.

At the v1.3 baseline, Windows/Linux packages are unsigned and macOS uses an ad-hoc signature without Apple notarization.

Generated binaries, deployment directories and generated icon files are build outputs, not source files, and remain ignored by Git.

The detailed release procedure and current workflow names are documented in `BUILDING.md`.
