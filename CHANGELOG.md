# Changelog

Notable user-facing and compatibility changes to Play Store App Audit are recorded here. Internal CI/release-process decisions belong in `AGENTS.md`, `docs/PROJECT_DECISIONS.md` and `docs/BUILDING.md`.

## [1.9.0] - 2026-08-25

### Added

- Added an automatic extra-wide Details Panel layout that enters at a usable viewport width of 1180 px and exits below 1080 px, while preserving the established 760/680 px narrow/wide hysteresis and the existing outer placement modes.
- Added a native operational status bar that reuses the application's single status label and progress widget, shows progress only during active work and retains the native resize grip.

### Changed

- Unified friendly Notes presentation across the results table, Details Panel and HTML report, including a complete table tooltip while retaining the original raw Notes in machine-readable data and exports.
- Renamed the user-facing **Health Score** concept to **Maintenance Score** without changing the algorithm or the compatibility-sensitive `health_score` identifier.
- Added foreground-only warning colours for **Different**, **Aging target** and **Legacy target** table values using the existing status palette.
- Improved the About hierarchy and coordinated the Choose File, Scan Phone and Export Results iconography with one project-owned, palette-aware family.
- Grouped extra-wide Details content into Store/Notes, Installed/Changes and Store evidence/diagnostics columns, with the action row below.
- Kept the main action row focused on Run, Export Results and Clear Results while operational status and active progress use the status bar; source/device identity remains on its existing surfaces.

### Fixed

- Fixed a Display Settings crash when changing columns with populated, sorted or filtered results by replacing an invalid manual layout-change notification with a safe presentation refresh.
- Kept Custom preset persistence, checkboxes, visible columns, selection, Details content and saved column widths synchronized across repeated changes and restart, including Advanced Settings interactions.

### Compatibility

- v1.9.0 is prepared as an unsigned Windows x64 Engineering Test Build (ETB); the exact release SHA and public artifact evidence will be recorded only after release validation.
- The planned project-defined asset set is `PlayStoreAppAudit-v1.9.0-windows-x64.zip`, `PlayStoreAppAudit-v1.9.0-third-party-sources.tar.xz` and `SHA256SUMS.txt`.
- Windows ARM64, Linux and macOS remain source-supported but are not planned as v1.9.0 prebuilt targets.
- Python 3.13 remains the packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- v1.8 settings and Smart Queries remain compatible: raw Notes and the internal `health_score` field ID are unchanged.
- Managed ADB remains read-only with respect to installed Android apps.

## [1.8.0] - 2026-08-24

### Added

- Saved Smart Queries for reusable result filtering, with a curated one-level All/Any builder, session-only active state and clear separation from Quick Filters and Audit Profiles.
- A Hidden mode for the Details Panel, available from both the compact **Details** control and **View > Details Panel**.
- A focused **Display Settings** dialog for App Icons, Date Format and Custom Columns.

### Changed

- Replaced the three permanent Details Panel position buttons with one compact, synchronized menu while preserving Auto, Right and Below placement and responsive layouts.
- Reorganized Advanced Settings into Store & Cache, Device, Audit & History, and Data & Storage categories without changing existing technical-setting persistence.
- Graduated optional Play Store icons from experimental presentation and hardened their bounded disk/RAM caches, offline reuse, malformed-data handling and large-table updates.
- Unified CSV, HTML and versioned-JSON result exports across the File menu and main Export control, with centralized action-availability checks.
- Standardized command naming, tooltips and contextual help while removing permanent table guidance that occupied operational space.
- Added the informational product tagline to repository/README identity and About presentation without placing it in the main operational UI.

### Fixed

- Prevented Advanced Settings and Audit Profiles from opening during incompatible running operations.
- Preserved active operational status messages when presentation-only filters or display/layout commands are used.
- Standardized the result-clearing command as **Clear Results**.

### Compatibility

- v1.8.0 is published as an unsigned Windows x64 Engineering Test Build (ETB) from frozen source SHA `ac328f0dffddb6b70fa7600f1291377376bc05d4`.
- Public GitHub Release title: `Play Store App Audit v1.8.0 (Win x64 Only)`.
- The project-defined asset set is exactly `PlayStoreAppAudit-v1.8.0-windows-x64.zip`, `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` and `SHA256SUMS.txt`; the published SHA-256 values are recorded in `docs/PROJECT_STATUS.md` and `docs/RELEASE_NOTES.md`.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.8.0.
- Python 3.13 remains the packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Managed ADB remains read-only with respect to installed Android apps.

## [1.7.0] - 2026-08-23

### Added

- Responsive Details Panel placement with Auto, Right and Below modes plus adaptive content reflow.
- Structured Store diagnostics with concise market evidence, fallback outcomes and machine-readable raw evidence retained for export.
- Installer/source classification and filters, plus target/min SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all or visible results.
- Reusable audit profiles for audit execution settings.
- Conservative smart/incremental re-audit behavior with targeted rechecks and explicit Force full refresh.

### Changed

- Store country and Store language resolution are independent; automatic phone language follows the active Android system language while country prefers explicit override, host region, Android region only as a late fallback, then US.
- User-facing Store evidence and Notes are substantially less verbose while technical evidence remains structured underneath.
- Play Store audit history and connected-device inventory history are presented separately, including first-baseline wording.
- Health Score is now presented as an optional supported maintenance heuristic, remains disabled by default and is explicitly not a security/malware rating.
- Details Panel position controls are larger and easier to understand.

### Fixed

- File/list audits do not inherit stale phone-language context.
- First-audit rows no longer misleadingly show phone inventory changes as Store-audit changes.
- Removed or region-restricted rows no longer expose raw internal machine-note tokens in the Details Panel.
- Definitive Store not-found evidence remains separate from transient/inconclusive request failures.

### Compatibility

- v1.7.0 is an unsigned Windows x64 Engineering Test Build (ETB).
- Public GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`.
- The public asset set contains exactly one Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Frozen source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- Windows x64 ZIP SHA-256: `142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b`.
- Third-party source archive SHA-256: `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458`.
- `SHA256SUMS.txt` SHA-256: `984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9`.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.7.0.
- v1.8 and v1.9 remain Windows x64-only ETB release lines. v2.0 is the first planned return to multi-platform distribution; production signing is a target, not yet a guarantee.

## [1.6.0] - 2026-08-22

### Added

- Automatic Store-language selection that uses the connected Android device's active system language when available, while file/list audits fall back to the primary language of the selected Store country. Explicit manual language overrides remain supported.
- A selected-row details panel that can be docked on the right or below the results table and remembers the chosen position.
- Structured country/language evidence in the details panel, including the Store country/language actually queried and fallback evidence.
- Developer metadata in app details, captured from the same normal Google Play scraper response already used by the audit, without extra Store requests.
- A grouped audit-change overview covering newly installed/removed device apps, newly available/unavailable Store results, reappeared listings, Store version/update changes, maintenance-state transitions and installer/source changes.

### Changed

- Moved bounded multi-country fallback scheduling into the canonical Store service so Store retry/fallback semantics no longer depend on performance-diagnostics wrappers.
- Consolidated Store access paths around one service while preserving terminal propagated `NotFoundError`, transient retry/backoff and uncertainty semantics.
- Moved experimental Play Store icons from the package-name column to the Play Store title, matching their Store-metadata origin.
- Reused captured icon/developer Store metadata through the normal healthy-result cache path so cached audits retain the details needed by the UI.
- Previous-audit comparison now records structured change events instead of relying only on a single display string.
- The first connected-device inventory is treated as a baseline and is not presented as hundreds of newly installed apps.

### Fixed

- Hardened persistent icon-cache filesystem failure handling so local disk errors degrade to a cache miss/network fallback and cannot leave an icon permanently pending.
- Prevented conclusive same-country Store not-found results from being retried only to change language; same-country English fallback is reserved for inconclusive or metadata-incomplete cases.
- Kept file/list audits from inheriting a previously connected phone's active language context.
- Added regression coverage for details-panel layout insertion, empty-state presentation, structured evidence/change rendering and grouped change-overview behavior.

### Compatibility

- v1.6.0 is frozen as an unsigned Windows x64 Engineering Test Build (ETB).
- The public release profile contains exactly one Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Windows ARM64, Linux and macOS remain supported by the shared source tree but are not rebuilt for v1.6.0.
- Production signing, notarization and the full Windows/Linux/macOS x64/ARM64 release profile are deferred until v2.0 or later.
- Python 3.13 remains the packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.
- `PySide6-Essentials` remains 6.11.1.
- ADB behavior remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers remain 16.
- The optional dashboard/summary candidate is not included in v1.6.0.

## [1.5.0] - 2026-08-21

### Added

- Configurable concurrent Google Play workers in **Advanced settings**, with 16 retained as the default/recommended value.
- Live regional-verification progress while fallback Store countries are being checked.
- Optional experimental Play Store app icons in the results table. The feature is off by default, populates progressively without blocking the table, and persists downloaded image bytes until the app's Store update marker changes.
- Connected-device source summaries with manufacturer/model and Android version/API using metadata already collected during the phone scan.

### Changed

- Reduced negative multi-country audit latency with bounded ordered fallback batches while preserving configured country priority and final classifications.
- Treat propagated `google_play_scraper.exceptions.NotFoundError` as terminal for the outer retry loop after the scraper has already performed its own internal fallback, while retaining retry/backoff for transient failures.
- Added a 25-second default timeout to the scraper transport so a stalled network request cannot occupy an audit worker indefinitely.
- Improved audit progress to distinguish cached/live work and show a real finalization phase before completed results are presented.
- Consolidated File-menu result actions and improved numeric table sorting and native status-chip sizing.
- Defaulted source-level system-app exclusion to enabled while preserving explicit saved choices.
- Stopped installing benchmark-only detailed Store path diagnostics during normal application startup.

### Fixed

- Avoided deterministic retry delays for Store listings that are definitively not found by the scraper.
- Preserved uncertainty semantics for timeout/network failures so they are never converted into false Store not-found results.
- Kept unavailable/removed rows from displaying stale experimental app icons.

### Compatibility

- v1.5.0 is an unsigned Windows x64 Engineering Test Build (ETB).
- The public release contains exactly one Windows x64 ZIP, one consolidated third-party source archive and one `SHA256SUMS.txt`.
- Windows ARM64, Linux and macOS remain supported by the shared source tree but are not rebuilt for v1.5.0.
- Production signing and the full Windows/Linux/macOS x64/ARM64 release profile remain planned for v1.6.
- Python 3.13 remains the release-packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.

## [1.4.0] - 2026-08-19

### Changed

- Let Qt use the platform-default application style instead of forcing Fusion globally.
- Let native platform styling own the default application font and generic scrollbar presentation.
- Retained the existing semantic colours, branded actions, table treatment and layout while improving native Windows and macOS control integration.

### Compatibility

- v1.4.0 is published as an Engineering Test Build (ETB) for Windows x64 with one prebuilt x64 ZIP package.
- The Windows v1.4.0 package is intentionally unsigned. v1.5.0 remains an unsigned Windows x64 Engineering Test Build; production code signing and the full six-platform production profile move to v1.6.
- Windows ARM64, Linux and macOS remain supported by the shared source tree, but v1.4.0 does not publish new prebuilt packages for those targets.
- The release includes one consolidated third-party source archive and one release-wide `SHA256SUMS.txt` alongside the Windows x64 package.
- Python 3.13 remains the release-packaging baseline; Python 3.13 and 3.14 remain Quality CI targets.

## [1.3.0] - 2026-08-19

### Changed

- Added prebuilt release packages for Windows, Linux and macOS on both x64 and ARM64.
- Consolidated third-party corresponding-source delivery into one release-wide source archive with one `SHA256SUMS.txt`.
- Updated the packaged Qt/PySide baseline to PySide6 Essentials 6.11.1.

### Fixed

- Improved compatibility with current Qt filtering APIs.
- Improved the reliability of third-party license/source material included with release packages.
- Preserved managed ADB support while keeping Android Platform-Tools outside the shipped application runtime.

### Compatibility

- v1.3.0 provides Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 ZIP packages.
- Python 3.13 remains the release-packaging baseline.
- Windows packages are unsigned. macOS packages use an ad-hoc signature and are not Apple-notarized.
- Linux packages use a standalone directory layout inside the ZIP.

## [1.2.0] - 2026-08-17

### Added

- A split **Scan phone** control with direct access to exporting the current phone package inventory as CSV.
- A detailed rich-text guide explaining the optional Health Score methodology and its limitations.
- The application version in the About dialog and in support diagnostics.

### Changed

- Reorganized the File, Tools and Help menus so source actions, result actions, maintenance commands and guidance are easier to find.
- Changed the Windows x64 prebuilt package from a one-file executable to a standalone ZIP.
- Separated **Clear current results** from persistent cache and audit-history maintenance.
- Grouped cache and previous-audit clearing under **Tools > Data maintenance**.
- Kept phone-package export enabled only while a current phone inventory is available.
- Adopted `GPL-3.0-only` for the public project, with alternative commercial licensing available separately and a CLA-based contribution policy.

### Compatibility

- v1.2.0 provides a prebuilt Windows x64 ZIP.
- Windows v1.2.0 is unsigned.
- Windows ARM64, macOS and Linux remain supported by the shared source tree but were not published as v1.2.0 prebuilt release assets.

## [1.1.0] - 2026-08-17

### Added

- A compact **Recent sources** menu beside **Choose file**, synchronized with the File menu.
- File-menu access to running an audit and exporting all or visible results as CSV or HTML.
- Rich in-app guides for ADB setup and CSV/TSV/TXT package-list imports.

### Changed

- Made the source area more compact while retaining the two file/phone input choices and source status.
- Improved application-icon presentation without changing its artwork.
- Simplified the About dialog by removing the LinkedIn link.

### Compatibility

- v1.1.0 provides a prebuilt Windows x64 package.
- v1.0.0 remains available for the previously published Windows ARM64, Linux and macOS packages.

## [1.0.0] - 2026-08-17

### Added

- The first stable Qt 6 / PySide6 desktop release.
- CSV, TSV and TXT package-list imports with Google Play availability and latest-update checks.
- Multi-country fallback checks that distinguish regional absence from broader unavailability or inconclusive results.
- Current, Aging, Stale, Removed, Store anomaly and Other result classifications.
- Optional Health Score maintenance guidance, previous-audit comparison and configurable technical views.
- Read-only ADB package scanning, installed-device metadata, device summaries, inventory history and snapshots.
- CSV and HTML reports, phone-inventory export and portable-mode data storage.
- Prebuilt packages for Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Apple Silicon and macOS Intel.

### Changed

- Adopted the canonical `playstore_app_audit` package and `main.py` entry point for the stable application.
- Improved large-device audit performance by collecting Android package metadata in bulk where available.

### Fixed

- Restricted latest-update parsing to update-specific fields and visible **Updated on** text; original publication dates are not treated as updates.
- Hid ADB subprocess console windows on Windows.
- Added packaged architecture and startup validation.

### Compatibility

- Windows and Linux v1.0.0 packages are unsigned.
- macOS v1.0.0 packages are ad-hoc signed for bundle integrity but not Apple-notarized.
- The former CustomTkinter application was retired and retained only at the historical `legacy-customtkinter-v9.3` tag.

## [0.11.0] - 2026-08-16

### Changed

- Consolidated the application into the canonical `playstore_app_audit` package.
- Retired version-suffixed Qt modules and obsolete Tkinter launchers.
- Established `main.py` / `playstore_app_audit.app` as the application entry point.
- Adopted PySide6 Essentials and the Nuitka-based `pyside6-deploy` packaging route.
