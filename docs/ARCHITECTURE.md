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

Qt Widgets remains the production UI technology unless a demonstrated UX, maintainability or performance reason justifies migration. v1.4 uses Qt's platform/default QStyle in production. Cross-platform render evidence showed the native/default Windows and macOS styles integrate better than a forced Fusion style, while the validated Linux environment naturally resolves to Fusion. Shared QSS retains semantic application styling but no longer hard-codes the default application font or generic scrollbar presentation.

## Data and network boundaries

Input files, settings, audit cache/history, inventory history, snapshots, logs and reports are processed locally. Normal per-user data paths and portable mode are resolved by `playstore_app_audit.platform`.

Google Play audits send package IDs plus Store country/language parameters to public Play endpoints through the Store service. The update checker reads the repository's public GitHub Releases API. Managed Android Platform-Tools are downloaded from Google's platform archive host only after user approval.

ADB operations are read-only with respect to installed applications. Device integration lists packages, reads properties and package-manager metadata, and can open Android's app-details settings screen; it does not install, uninstall, enable or disable applications.

## Cross-platform policy

The application source remains cross-platform even when a particular public release profile publishes only a subset of platform binaries. Platform-specific behaviour is kept behind `playstore_app_audit.platform` or `playstore_app_audit.devices`, including:

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

Release packaging uses Python 3.13, `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3`.

Every public release is an exact-SHA assembly rather than a collection of independently built packages:

1. Cheap Quality CI passes on the final `main` commit.
2. One exact full `main` SHA is frozen.
3. Every candidate required by the selected release profile is built from that SHA.
4. Build workflows reject expected/dispatch/checkout SHA mismatches.
5. The profile-specific assembler validates candidate provenance, architecture/legal evidence and the exact public asset layout.
6. The annotated version tag is created on the frozen SHA only after artifact validation.
7. The already validated assets are published. Tag pushes do not rebuild them.

If source or release tooling changes after the SHA freeze, every candidate required by the selected profile must be rebuilt from the new exact SHA. Artifacts from different source revisions must never be mixed.

### v1.4 Windows engineering profile

v1.4 intentionally publishes only unsigned Windows x64 and Windows ARM64 engineering/test packages.

- Both packages come from one frozen SHA via `.github/workflows/build-windows-exe.yml` with `target=both`.
- Production signing is not invoked.
- Linux and macOS package workflows are not run for the v1.4 release.
- `.github/workflows/assemble-windows-engineering-release.yml` consumes only the successful unsigned Windows run from the same repository and exact SHA.
- The engineering assembler emits exactly four public assets: the two Windows ZIPs, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Strict public legal/source validation is unchanged.

This profile reduces release cost without weakening source identity, legal evidence or package validation.

### v1.5 full production profile

The existing production path is preserved for v1.5:

- Windows x64/ARM64 native packages are built, then pass through Microsoft Artifact Signing Public Trust and native post-sign verification.
- Linux x64/ARM64 packages use Nuitka standalone layout.
- macOS x64/ARM64 packages use Developer ID Application signing, hardened runtime, notarization, stapling and Gatekeeper verification.
- `.github/workflows/assemble-release.yml` validates all six final candidates from one frozen SHA and emits exactly eight public assets: six platform ZIPs, one consolidated third-party source archive and one `SHA256SUMS.txt`.

### Platform package forms

- Windows: Nuitka standalone application packaged as ZIP.
- Linux: Nuitka standalone tree packaged as ZIP, never onefile for production release packaging. Qt/PySide/Shiboken shared libraries remain replaceable.
- macOS: `.app` bundle packaged as ZIP.

Windows package validation covers native Python/PySide inputs, PE architecture, version metadata, runtime content, startup and legal material. Linux validates ELF architecture, runtime content and startup. macOS validates Mach-O architecture, bundle metadata, runtime content, signature state and startup.

At the immutable v1.3 baseline, Windows/Linux packages are unsigned and macOS uses an ad-hoc signature without Apple notarization. v1.4 deliberately remains unsigned on Windows. Production signing execution is deferred to v1.5.

Generated binaries, deployment directories and generated icon files are build outputs, not source files, and remain ignored by Git.

The detailed v1.4 engineering and v1.5 production procedures and current workflow names are documented in `BUILDING.md`.
