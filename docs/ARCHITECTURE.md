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

The v2.0 Local APK foundation follows the same dependency direction:
`domain.local_artifacts` owns the immutable SHA-256 artifact identity and typed
parse outcomes, while `services.local_apk` owns bounded filesystem/ZIP and
binary-manifest/resource parsing. Local APK parsing has no Qt or ADB dependency.
Package ID remains a Store fan-out key rather than artifact identity.

`services.local_artifact_store` is the package-evidence coordination boundary.
One call has one `AuditConfig`, provider/settings context and refresh policy; it
deduplicates exact `package_lookup_key` values in first-seen order, submits the
unique batch through the existing Play Store/cache/provider services, and fans
one immutable `domain.local_artifact_store.PackageStoreEvidence` object back to
every corresponding artifact. It creates no cache or worker pool of its own.
Different lookup contexts require separate calls and retain the existing Store
and provider cache-key semantics.

`domain.local_apk_library` and `services.local_apk_library` form the persistent
Library core. The version-1 `local_apk_library.json` document, stored through the
active platform app-data directory, separates registered roots, SHA-256 artifact
records and physical path-to-SHA associations. Explicit deterministic scans do
not follow directory links, reuse `parse_local_apk()` for every candidate, and
merge partial successes conservatively. Only a fully completed root scan can
mark an unseen known location not present; failed, partial and cancelled roots
retain prior presence knowledge. Atomic writes and typed load/save/scan outcomes
keep this boundary independent from settings, history, inventories and Store or
provider caches. The projection for later Library audits chooses one present
location per exact SHA while preserving every location in Library state. See
`LOCAL_APK_LIBRARY.md`.

The canonical `ui.main_window.MainWindow` owns the transient Local APK source
interaction. It uses a small background parsing worker with cooperative
between-file cancellation and a monotonically increasing request guard, then
passes immutable artifacts to `LocalArtifactStoreService`. The UI conversion in
`services.local_apk_audit` emits one shared-schema row per completed artifact
without its canonical path. Local APK rows reuse table, Details and export
surfaces but are explicitly excluded from installed-device enrichment,
ScanSession/Device Inventory promotion and package-keyed audit history.

`ui.local_apk_library.LocalApkLibraryDialog` is the focused phase 5b Library
surface. It loads and writes only through `LocalApkLibraryService`, presents
registered roots separately from one artifact row per SHA-256, and runs explicit
rescans on a small cooperative background worker with request-generation guards.
Completed, partial and failed scan results are saved atomically; cancelled
results are discarded and the last persisted Library is reloaded. The dialog
emits only the core's one-representative-per-SHA audit projection to
`MainWindow`, which establishes the distinct `local_apk_library` source mode and
reuses the existing Local APK Store/provider, result, Details and export path.
Both Local APK source modes bypass package history and Device Inventory; local
paths remain confined to Library management Details and never enter result rows
or remote lookup input.

## Dependency direction

The preferred dependency flow is:

```text
UI -> services -> domain
 |       |
 +------> devices/platform
```

UI code coordinates interaction and presentation. Store parsing, audit classification and persistence belong in services; ADB and operating-system details belong in the device and platform layers. Domain and Store parsing code must not depend on Qt.

Side effects stay at the edges: network access in Store/update services, filesystem state in persistence/reporting services, subprocess work in device/platform code and user interaction in the UI.

Local APKs are untrusted filesystem input. The parser captures a bounded
temporary snapshot and SHA-256 in one streaming pass, parses only that snapshot,
then re-hashes the source before success. It preflights ZIP structure and
resource limits, decompresses only bounded metadata members in memory, and never
extracts archive paths. It currently accepts only standalone `.apk`; split APKs,
`.apks`, `.aab` and signature verification are explicitly outside the boundary.
See `LOCAL_APK_PARSER.md`.

## Qt UI structure

`playstore_app_audit.ui.main_window.MainWindow` is the public UI entry point. Internally, the window is assembled from focused layers including `base_window`, `audit_window`, `device_window`, `preferences_window`, `menu_window`, `results_window` and related presentation modules.

The layered inheritance structure preserves proven behaviour but remains a maintenance caveat. Prefer small, behaviour-preserving moves toward focused widgets or controllers when composition clearly improves ownership. Do not combine a broad behavioural rewrite with a structural migration.

UI customization should use explicit local hooks for classification, cache loading and device metadata collection/enrichment rather than mutating imported modules at runtime.

The main window has one operational status channel. The existing `status_label` is hosted by the native `QStatusBar`; callers continue updating that canonical label rather than mirroring state. The same canonical progress widget occupies the first results-header row between the grouped Run/Stop controls and Export/Clear. It remains geometrically present at idle as a neutral empty track and retains established determinate/busy behavior during source, audit and finalization work. Source/device identity remains on its established surfaces. The second results-header row owns chips, Hide System Apps, search and the single Details selector synchronized with the View menu; no duplicate status, progress or Details state is introduced.

Column layouts use immutable Basic, Device and Technical definitions plus one separately persisted Custom state. Custom contains only visible columns, full visual order and per-column widths; global display preferences such as app icons and date format remain independent. Manual header changes and Customize View column changes capture Custom, while built-in application and result refresh paths suppress capture so they cannot mutate it. The legacy Qt header-state blob remains only as a compatibility bridge for existing saved widths/order and is not a second active layout model.

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

### v1.4 Windows x64 Engineering Test Build (ETB) profile

v1.4 intentionally publishes only one unsigned Windows x64 Engineering Test Build (ETB) package.

- The package comes from one frozen SHA via `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Windows ARM64, Linux and macOS release jobs are not run for v1.4.
- Production signing is not invoked.
- `.github/workflows/assemble-windows-engineering-release.yml` consumes only the successful unsigned Windows x64 run from the same repository and exact SHA and rejects ARM64 source input.
- The engineering assembler emits exactly three public assets: the Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Strict public legal/source validation is unchanged.

This profile reduces release cost without weakening source identity, legal evidence or package validation.

### v1.5 Windows x64 Engineering Test Build (ETB) profile

v1.5.0 keeps the same reduced public profile as v1.4: one unsigned Windows x64 package from one frozen SHA.

- Build with `.github/workflows/build-windows-exe.yml` using `target=x64`.
- Do not run Windows ARM64, Linux or macOS v1.5 release jobs.
- Do not invoke production signing.
- `.github/workflows/assemble-windows-engineering-release.yml` validates the Windows x64 candidate and emits exactly three public assets: `PlayStoreAppAudit-v1.5.0-windows-x64.zip`, `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`.
- The GitHub Release uses title suffix `(ETB Win x64)` and the Windows x64-only ETB body heading.

### v1.6-v1.9 Windows x64 Engineering Test Build profiles

v1.6.0, v1.7.0 and v1.8.0 were published as unsigned Windows x64-only Engineering Test Builds. v1.9 retains the same distribution profile:

- one Windows x64 candidate is built from the frozen SHA with `.github/workflows/build-windows-exe.yml`;
- Windows signing, Windows ARM64, Linux and macOS release candidates are not invoked;
- `.github/workflows/assemble-windows-engineering-release.yml` validates exact-SHA provenance and emits exactly three public assets: the Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.

The full six-platform production path remains maintained for the v2.0-or-later milestone. It requires Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 candidates from one frozen SHA, with production signing/notarization only after provider, credential, cost and end-to-end validation succeed.

### Platform package forms

- Windows: Nuitka standalone application packaged as ZIP.
- Linux: Nuitka standalone tree packaged as ZIP, never onefile for production release packaging. Qt/PySide/Shiboken shared libraries remain replaceable.
- macOS: `.app` bundle packaged as ZIP.

Windows package validation covers native Python/PySide inputs, PE architecture, version metadata, runtime content, startup and legal material. Linux validates ELF architecture, runtime content and startup. macOS validates Mach-O architecture, bundle metadata, runtime content, signature state and startup.

At the immutable v1.3 baseline, Windows/Linux packages are unsigned and macOS uses an ad-hoc signature without Apple notarization. The v1.4-v1.9 release line deliberately uses unsigned Windows x64 Engineering Test Builds. Production signing and the full six-platform release are deferred to v2.0 or later and remain conditional on real validation.

Generated binaries, deployment directories and generated icon files are build outputs, not source files, and remain ignored by Git.

The detailed Windows x64 ETB and future v2.0 production procedures and current workflow names are documented in `BUILDING.md`.
