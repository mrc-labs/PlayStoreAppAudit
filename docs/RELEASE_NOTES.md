# Release Notes Standard

This document defines the canonical GitHub Release notes structure for Play Store App Audit. It is a durable release invariant, not a per-release styling preference.

## Mandatory structure

Every public GitHub Release body must use these four sections, in this exact order:

```markdown
## What's New / Highlights

### Added
- ...

### Changed
- ...

### Fixed
- ...

## Compatibility and distribution
- ...

## Release assets
- ...

## Verification
- ...
```

The four `##` sections are mandatory for every release.

Within `## What's New / Highlights`, `### Added`, `### Changed`, and `### Fixed` are the standard subheadings. Include only subheadings that contain meaningful entries. Omit an empty subheading rather than adding filler such as `None` or `N/A`.

## Content rules

### What's New / Highlights

Keep this section user-facing. Describe meaningful product, UX, performance, reliability, packaging, or maintenance changes. Prefer concise bullets and avoid internal PR/workflow history unless it materially affects users.

Use:

- `Added` for new capabilities or newly exposed options.
- `Changed` for behavioural, UX, performance, distribution, or dependency changes.
- `Fixed` for defects and regressions corrected in the release.

### Compatibility and distribution

Always state the actual public distribution profile for that release, including as applicable:

- supported/prebuilt platforms and architectures;
- unsigned, ad-hoc-signed, or production-signed status;
- Engineering Test Build (ETB) status;
- important compatibility/toolchain notes that materially affect users;
- intentionally deferred platforms or signing work when relevant.

Do not imply that source support is the same as a prebuilt public package.

### Release assets

List the public release assets users should expect. Prefer exact filenames once the release asset set is frozen. The list must agree with the selected release profile and assembler output.

Do not list temporary GitHub Actions artifacts, signing/notarization intermediates, validation evidence, or GitHub's automatically generated source-code ZIP/tarball as part of the project-defined release asset set unless a historical release note explicitly treats them as release deliverables.

### Verification

Summarize release evidence that actually passed for the published artifacts. Depending on the release profile this can include:

- exact frozen source SHA;
- Quality CI targets;
- package architecture/version/startup validation;
- legal/source-material validation;
- signing/notarization/Gatekeeper verification;
- release-provenance and checksum validation;
- confirmation that the final public asset set came from the same frozen SHA.

Never claim a verification step that was not actually performed.

## Historical-source rule

When normalizing an already published release, the body that was actually published on GitHub is the primary historical source. Preserve its substantive claims and details, then reorganize them into the canonical four-section format.

`CHANGELOG.md`, release documentation, tags, commits, checksums and preserved CI evidence may supplement a historical body only where they provide clearly supported missing details. They must not silently replace, reinterpret or strengthen the claims made in the published body.

Obvious editorial mistakes may be corrected while normalizing, for example an internal heading that names the wrong version, provided the release/tag identity itself is unambiguous. Such corrections must not change the substantive historical meaning.

Published tags, source commits, binary assets and checksums remain immutable. Normalizing release-note prose never authorizes retagging, rebuilding or replacing published artifacts.

## Release title and heading

Release-profile-specific title suffixes remain separate from the four-section body standard. Current and future Windows x64 Engineering Test Build releases use the GitHub Release title suffix `(Win x64 Only)` and must clearly identify the package as unsigned. Historical titles may retain older wording where that reflects the published record.

A short release heading may precede the four mandatory sections when a profile requires it, for example:

```markdown
## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)
```

The mandatory four sections must follow that heading unchanged.

## v1.8.0 release-candidate draft

The following draft defines the intended final v1.8.0 GitHub Release body. Replace every angle-bracket placeholder only with evidence from successful runs and validated artifacts from the final frozen SHA. Do not publish unverified claims or leave placeholders in the public body.

```markdown
## Play Store App Audit v1.8.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Saved Smart Queries with a curated one-level All/Any builder, versioned persistence and session-only active state, kept separate from Quick Filters and Audit Profiles.
- A Hidden mode for the Details Panel and a focused Display Settings dialog for App Icons, Date Format and Custom Columns.

### Changed
- Replaced the permanent Details Panel position buttons with one compact **Details** control synchronized with **View > Details Panel**, while preserving Auto, Right and Below placement.
- Reorganized Advanced Settings into Store & Cache, Device, Audit & History, and Data & Storage categories.
- Graduated optional Play Store icons from experimental presentation and hardened cache bounds, offline reuse, malformed-data handling and large-table updates.
- Unified result export actions and action availability across menus, buttons and running-operation states.
- Standardized command naming, contextual help and the informational product tagline presentation.

### Fixed
- Prevented incompatible settings/profile commands from opening during active source, audit, finalization or data-maintenance operations.
- Preserved active operational messages when presentation-only filters or display/layout commands are used.
- Standardized the result-clearing command as **Clear Results**.

## Compatibility and distribution
- Engineering Test Build (ETB), Windows x64 only.
- The Windows package is intentionally unsigned; Windows may display a SmartScreen/publisher warning.
- Windows ARM64, Linux and macOS remain source-supported but are not rebuilt for v1.8.0.
- Python 3.13 is the packaging baseline; Python 3.13 and 3.14 are Quality CI targets.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Managed ADB remains read-only with respect to installed Android apps.

## Release assets
- `PlayStoreAppAudit-v1.8.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen source SHA: `<FROZEN_MAIN_SHA>`.
- Quality push run `<QUALITY_RUN_ID>` passed on Python 3.13 and 3.14.
- Windows x64 build run `<WINDOWS_BUILD_RUN_ID>` succeeded on the same frozen SHA.
- Package architecture, application/Windows version, standalone contents, startup, legal/source material and release provenance validation: `<VALIDATION_RESULT>`.
- Clean-install, v1.7-upgrade and distributed-application smoke checks: `<MANUAL_TEST_EVIDENCE>`.
- Engineering assembly run `<ASSEMBLER_RUN_ID>` validated the exact x64-only three-file set from the same frozen SHA.
- Windows x64 ZIP SHA-256: `<WINDOWS_ZIP_SHA256>`.
- Third-party source archive SHA-256: `<THIRD_PARTY_SOURCES_SHA256>`.
- `SHA256SUMS.txt` SHA-256: `<SHA256SUMS_SHA256>`.
```

## Historical normalized release notes

The following bodies are normalized from the release notes that were actually published on GitHub. Content is reorganized into the canonical structure without retroactively claiming verification steps or distribution properties that the historical body did not support.

### v1.4.0

```markdown
## Play Store App Audit v1.4.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Changed
- Qt now uses the platform-default application style instead of forcing Fusion globally.
- Native platform styling now owns the default application font and generic scrollbar presentation.
- Existing semantic colours, branded actions, table treatment and layout are retained while native Windows and macOS control integration is improved.

## Compatibility and distribution
- Prebuilt release package: Windows x64 only.
- The Windows package is intentionally unsigned.
- Production code signing is planned for a later production release.
- Windows ARM64, Linux and macOS remain supported by the shared source tree, but v1.4.0 does not publish new prebuilt packages for those targets.
- Python 3.13 remains the release-packaging baseline. Python 3.13 and 3.14 are the Quality CI targets.
- Because this package is unsigned, Windows may display a SmartScreen or publisher warning when opening it.

## Release assets
This release intentionally contains exactly three project-defined assets:
- `PlayStoreAppAudit-v1.4.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

The third-party source archive contains the corresponding source material required for the distributed runtime dependencies.

## Verification
- Frozen source commit: `6830e0c4a03e355f442070f00dd5008322f5dbc4`.
- `PlayStoreAppAudit-v1.4.0-windows-x64.zip`: `238da12f3dd5a243cbebd4b8618935a973607706fe67edad2d15e3b4be06408d`.
- `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`: `93ded83b5a15389924911cee2865cb1684efeca992e011c1d0d9a02f68c69d72`.
- Published `SHA256SUMS.txt` asset SHA-256: `41dd2d20b1fc75a19a0c318a86e28fb0072bbc8e4bac046f688d3afd13a0e9d5`.
```

### v1.3.0

```markdown
## Play Store App Audit v1.3.0

## What's New / Highlights

### Changed
- Native standalone packages for Windows, Linux and macOS.
- x64 and ARM64 builds for all three platforms.
- Qt / PySide6 6.11.1 baseline.
- Improved cross-platform packaging and runtime validation.
- Managed ADB support where available.
- Consolidated third-party source archive for release compliance.
- Release-wide SHA-256 checksums.

## Compatibility and distribution
- Choose the ZIP matching the operating system and architecture.
- Prebuilt packages cover Windows x64/ARM64, Linux x64/ARM64, macOS Apple Silicon/ARM64 and macOS Intel/x64.
- The macOS builds use an ad-hoc CI signature and are not Apple-notarized.

## Release assets
- Six platform ZIP packages covering Windows, Linux and macOS on x64 and ARM64.
- `PlayStoreAppAudit-v1.3.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- All published binary and source assets were assembled and validated from commit `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`.
```

### v1.2.0

```markdown
## Play Store App Audit v1.2.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Scan a connected Android phone directly and export its current package inventory as CSV.
- Added a detailed Health Score methodology and limitations guide.
- Added the application version to About and support diagnostics.

### Changed
- Reorganized File, Tools and Help menus and grouped data-maintenance actions more clearly.
- Separated clearing current results from cache and audit-history maintenance.
- Inventory export is available only when a current phone inventory exists.
- Windows x64 is distributed as a validated Nuitka standalone ZIP with a SHA-256 checksum sidecar.
- Play Store App Audit's own code is released under GPL-3.0-only. Alternative commercial licensing is available separately.

## Compatibility and distribution
- Windows x64: normal prebuilt release target.
- Windows ARM64: manual engineering build capability.
- macOS and Linux: supported from source, with packaging performed manually or on demand.
- The Windows build is unsigned, so Microsoft Defender SmartScreen or another reputation-based check may display a warning when the application is first run.
- Required corresponding-source archives for bundled Qt/PySide components and certifi are included with this release.

## Release assets
- Windows x64 validated Nuitka standalone ZIP.
- SHA-256 checksum sidecar for the Windows x64 ZIP.

## Verification
- Release commit: `72e2ca9`.
- Windows x64 ZIP SHA-256: `5eab727b80f8dd67a49c63e14c2ca49f229aaca6e74d5c56e8f6c92320ea982a`.
```

### v1.1.0

The originally published body contained an internal heading that incorrectly said `v1.2.0`; the normalized body below corrects that obvious editorial typo to `v1.1.0` while preserving the release's substantive content.

```markdown
## Play Store App Audit v1.1.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Added a Recent sources dropdown beside Choose file.
- Reorganized File and export actions, including Run Play Store audit in the File menu.
- Added clearer ADB setup and app-list import guides.

### Changed
- Play Store App Audit v1.1.0 makes common tasks easier to reach and the main window more compact.
- Improved application icon sizing without changing its artwork.
- Removed the LinkedIn link from About.

## Compatibility and distribution
- v1.1.0 provides a prebuilt Windows x64 package.
- v1.0.0 remains available for the previously published Windows ARM64, Linux and macOS packages.

## Release assets
- Prebuilt Windows x64 package.

## Verification
- Release commit: `af5f96b`.
- The published body did not record additional standardized verification details.
```

### v1.0.0

```markdown
## Play Store App Audit v1.0.0

## What's New / Highlights

### Added
- First stable release.
- Cross-platform runtime abstraction for application data, Store-country detection and Android Platform-Tools paths.
- Portable-mode data-path handling in the canonical platform layer.
- Bulk Android package metadata collection through one read-only `dumpsys package` request, with conservative per-package fallback.
- Canonical immutable Qt table schema in `playstore_app_audit/ui/schema.py`.
- Explicit UI behaviour hooks for row classification, cache loading and device metadata collection/enrichment.
- Regression coverage for country parsing, version comparison, Android compatibility labels, Health Score, filters, portable paths, ADB bulk parsing, architecture constraints and UI schema integrity.
- Lightweight pull-request quality workflow covering compile, tests, Ruff and Qt offscreen smoke checks.
- Manual Linux and macOS packaging workflows with platform-specific runtime validation.
- Native Windows ARM64 application packaging alongside the Windows x64 package.

### Changed
- Application version is 1.0.0 across the package and project metadata.
- State/settings/cache/history code uses `services.state` directly; the temporary persistence compatibility shim was removed.
- Historical v7/v8/v9, `qt_base`, `features` and `user_state` module aliases were replaced by descriptive imports.
- Table columns, labels, widths and export extras no longer depend on UI import order.
- Cross-module runtime monkey-patching for audit selection, classification, cache bypass and ADB enrichment was replaced by explicit overridable methods.
- Device metadata collection can avoid hundreds of individual `dumpsys package <package>` subprocesses on large app inventories.
- Service/report version strings follow the package version rather than historical 0.9.x literals.
- Linux CI installs the EGL/X11 libraries required by Qt on the hosted runner.
- macOS packaging excludes the unused Qt Virtual Keyboard platform-input-context plugin.
- macOS/Linux packaging validates the actual generated binary/app bundle so a deployment-tool false positive cannot upload an empty artifact.
- Release packaging covers Windows x64 and ARM64, Linux x64 and ARM64, and macOS Apple Silicon and Intel from the same source revision.
- Windows packaging validates native Python/PySide6 inputs; packaging asserts actual PE/ELF/Mach-O architecture, runs deterministic source and packaged smoke tests, and records release provenance in `BUILD-INFO`.
- ADB validation is architecture-aware: each supported managed or native path must execute successfully, while Windows records the downloaded `adb.exe` architecture separately from the native application package.

### Fixed
- `MainWindow` no longer mutates platform, state or version modules at import time.
- Final source controls are no longer rebuilt twice during window construction.
- Saved Qt header state is invalidated once for the canonical table schema.
- Google Play `datePublished` is not accepted as a latest-update date.
- ADB subprocesses no longer flash console windows on Windows.
- The macOS deployment path no longer attempts to bundle the unused `QtVirtualKeyboardQml` framework through platform input contexts.
- The Linux Qt smoke/build workflow provides `libEGL` and related XCB runtime libraries.

## Compatibility and distribution
- Windows x64 and Windows ARM64 packages.
- Linux x64 and Linux ARM64 packages.
- macOS Apple Silicon / ARM64 and macOS Intel / x64 packages.
- Windows remains the primary automatic release build.
- Linux and macOS use the same Qt/PySide6 source tree and are manual/on-demand release targets.
- CustomTkinter remains retired and preserved only by the historical `legacy-customtkinter-v9.3` tag.
- Windows and Linux packages are unsigned.
- macOS packages are ad-hoc signed for CI integrity but are not Apple-notarized.
- Windows ARM64 was natively built and smoke-tested on GitHub's Windows ARM64 runner, which was in public preview at release validation time.
- macOS ARM64 and Intel/x64 are separate thin packages, not universal binaries.
- macOS minimum-version Mach-O metadata is not a complete compatibility guarantee for every older macOS release.

## Release assets
- Six platform ZIP packages: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Apple Silicon/ARM64 and macOS Intel/x64.
- SHA-256 sidecars for all six packages.

## Verification
- All packages were built from exact commit `87cb259218f3acd3be38b43cd3343ef93f3d7ae6`.
- Windows ARM64 was natively built and smoke-tested on GitHub's Windows ARM64 runner.
- Linux x64 was validated on Ubuntu 22.04 CI.
- Linux ARM64 was validated on Ubuntu 24.04 ARM64 CI.
- Packaging validates actual PE/ELF/Mach-O architecture, deterministic source and packaged smoke tests, and release provenance in `BUILD-INFO`.
- SHA-256 sidecars are provided for all six packages.
```

## Published v1.5.0 release body

The body below records the final v1.5.0 release wording and the successful evidence used for publication. The published tag, source commit and assets are immutable.

```markdown
## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Configurable concurrent Google Play workers in Advanced settings, with 16 as the default/recommended value.
- Live regional-verification progress while fallback Store countries are checked.
- Optional experimental Play Store app icons with long-lived disk reuse and progressive non-blocking table population.
- Connected-device source summaries with manufacturer/model and Android version/API.

### Changed
- Reduced negative multi-country audit latency with bounded ordered fallback batches while preserving country priority and final classifications.
- Treat propagated Store `NotFoundError` as terminal for the outer retry loop while retaining retry/backoff for transient failures.
- Added a 25-second scraper transport timeout.
- Improved cached/live/finalization progress, File-menu result actions, numeric sorting and status-chip sizing.
- Defaulted source-level system-app exclusion to enabled while preserving explicit saved choices.

### Fixed
- Avoided deterministic retries for definitive Store not-found results.
- Preserved uncertainty semantics for timeout/network failures.
- Prevented unavailable/removed rows from displaying stale experimental app icons.

## Compatibility and distribution
- Engineering Test Build (ETB), Windows x64 only.
- Windows package intentionally unsigned.
- Windows ARM64, Linux and macOS remain source-supported but are not rebuilt for v1.5.0.
- Production signing and the full Windows/Linux/macOS x64/ARM64 release profile remain planned for v1.6.
- Python 3.13 is the packaging baseline; Python 3.13 and 3.14 are Quality CI targets.
- Because this package is unsigned, Windows may display a SmartScreen or publisher warning when opening it.

## Release assets
This release intentionally contains exactly three project-defined assets:
- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

The third-party source archive contains the corresponding source material required for the distributed runtime dependencies.

## Verification
- Frozen source SHA: `6f00bea0789874bc6339286a2ffc3eb9cb2891bb`.
- Quality CI push run `32438975177` passed on the frozen SHA with Python 3.13 and Python 3.14.
- Windows x64 build run `32443253472` completed successfully from the same frozen SHA.
- Native Python/PySide6 architecture, project version, static/regression tests, Qt source smoke tests, managed ADB path and Windows standalone package validation passed.
- Strict release legal/source-material preflight and packaged legal validation passed.
- Engineering release assembly run `32446825765` verified the source workflow identity, repository, exact SHA, x64-only input and exact three-file public asset set.
- `PlayStoreAppAudit-v1.5.0-windows-x64.zip` SHA-256: `942084863817852be53d63370b07b0a080728e8467f0e158deb8c2a1af354f8f`.
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz` SHA-256: `b24595b3bbf6adb77846104b246956d0f171777c8be81ef6e22b8d2b68a9a719`.
- Independent post-publication SHA-256 calculation matched the published `SHA256SUMS.txt` for both payload assets.
```


## Published v1.7.0 release body

The body below records the final v1.7.0 release wording and successful evidence. The published tag, source commit and three assets are immutable.

```markdown
## Play Store App Audit v1.7.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Added
- Responsive selected-row Details Panel controls with Auto, Right and Below placement modes and adaptive content layout.
- Structured Store request evidence and compact diagnostics for country/language checks, fallback markets and inconclusive results.
- Installer/source classification and built-in installer filters.
- SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all or visible results.
- Reusable audit profiles.
- Conservative smart/incremental re-audit behavior with targeted rechecks and Force full refresh.

### Changed
- Store country and Store language are resolved independently with explicit override/host/device fallback semantics.
- Store market evidence and Notes prioritize concise human-readable outcomes while raw evidence remains structured.
- Store audit history and phone inventory history are presented separately, including first-baseline wording.
- Health Score is an optional supported 0-100 maintenance heuristic, disabled by default and not a malware/security score.
- Details Panel position controls are larger and clearer while retaining hover tooltips.

### Fixed
- File/list audits no longer inherit stale connected-phone language context.
- First-audit rows no longer present phone inventory changes as previous Store-audit changes.
- Removed/region-restricted apps no longer expose raw machine-note tokens in the user-facing Details Panel.
- Definitive Store not-found evidence remains distinct from transient/inconclusive failures.

## Compatibility and distribution
- Engineering Test Build (ETB), Windows x64 only.
- The Windows package is intentionally unsigned; Windows may display a SmartScreen/publisher warning.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.7.0.
- Python 3.13 is the packaging baseline; Python 3.13 and 3.14 are Quality CI targets.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Managed ADB remains read-only with respect to installed Android apps.

## Release assets
- `PlayStoreAppAudit-v1.7.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- Quality push run `32609018096` passed on Python 3.13 and 3.14.
- Windows x64 build run `32609148943` succeeded on the same frozen SHA.
- Engineering assembly run `32610281618` validated the exact x64-only three-file set.
- Publish/post-publication verification run `32610914851` re-downloaded all three public assets, verified their checksums and confirmed annotated tag `v1.7.0` peels to the frozen SHA.
- Windows x64 ZIP SHA-256: `142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b`.
- Third-party source archive SHA-256: `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458`.
- `SHA256SUMS.txt` SHA-256: `984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9`.
```
