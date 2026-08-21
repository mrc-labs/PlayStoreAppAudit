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

Within `## What's New / Highlights`, `### Added`, `### Changed`, and `### Fixed` are the standard subheadings. Include the subheadings that contain meaningful entries; omit an empty subheading rather than adding filler such as `None` or `N/A`.

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

Do not list temporary GitHub Actions artifacts, signing/notarization intermediates, validation evidence, or files that are not attached to the public GitHub Release.

### Verification

Summarize release evidence that actually passed for the published artifacts. Depending on the release profile this can include:

- exact frozen source SHA;
- Quality CI targets;
- package architecture/version/startup validation;
- legal/source-material validation;
- signing/notarization/Gatekeeper verification;
- release-provenance and checksum validation;
- confirmation that the final public asset set came from the same frozen SHA.

Never claim a verification step that was not actually performed. For historical releases whose detailed verification evidence was not recorded in the current repository, say so rather than reconstructing an unsupported claim.

## Release title and heading

Release-profile-specific title suffixes remain separate from the four-section body standard. For example, the v1.4/v1.5 Windows x64 Engineering Test Build profile uses the title suffix `(ETB Win x64)` and must clearly identify the package as unsigned.

A short release heading may precede the four mandatory sections when a profile requires it, for example:

```markdown
## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)
```

The mandatory four sections must follow that heading unchanged.

## Historical normalized release notes

The following bodies are the canonical normalized wording for already published releases, based only on information preserved in `CHANGELOG.md` and the durable release documentation. Published tags, commits, and binary assets remain immutable. Updating prose in an existing GitHub Release does not authorize changing its tag, commit, or assets.

### v1.4.0

```markdown
## Play Store App Audit v1.4.0 (Engineering Test Build - Windows x64 Only)

## What's New / Highlights

### Changed
- Let Qt use the platform-default application style instead of forcing Fusion globally.
- Let native platform styling own the default application font and generic scrollbar presentation.
- Retained the existing semantic colours, branded actions, table treatment and layout while improving native Windows and macOS control integration.

## Compatibility and distribution
- Engineering Test Build (ETB), Windows x64 only.
- The Windows package is intentionally unsigned.
- Windows ARM64, Linux and macOS remain source-supported but were not rebuilt for v1.4.0.
- Python 3.13 is the packaging baseline; Python 3.13 and 3.14 are Quality CI targets.

## Release assets
- `PlayStoreAppAudit-v1.4.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen release commit: `6830e0c4a03e355f442070f00dd5008322f5dbc4`.
- The Windows x64 ETB release profile requires package architecture, version, startup, legal/source-material, provenance, and release-wide checksum validation from the same frozen SHA.
```

### v1.3.0

```markdown
## What's New / Highlights

### Changed
- Added prebuilt release packages for Windows, Linux and macOS on both x64 and ARM64.
- Consolidated third-party corresponding-source delivery into one release-wide source archive with one `SHA256SUMS.txt`.
- Updated the packaged Qt/PySide baseline to PySide6 Essentials 6.11.1.

### Fixed
- Improved compatibility with current Qt filtering APIs.
- Improved the reliability of third-party license/source material included with release packages.
- Preserved managed ADB support while keeping Android Platform-Tools outside the shipped application runtime.

## Compatibility and distribution
- Prebuilt packages for Windows x64/ARM64, Linux x64/ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64.
- Windows packages are unsigned.
- macOS packages use an ad-hoc signature and are not Apple-notarized.
- Linux packages use a standalone directory layout inside the ZIP.
- Python 3.13 is the packaging baseline.

## Release assets
- Six platform ZIP packages: Windows x64/ARM64, Linux x64/ARM64, macOS x64/ARM64.
- One consolidated third-party corresponding-source archive.
- One release-wide `SHA256SUMS.txt`.

## Verification
- Immutable release commit: `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`.
- The repository records architecture/package validation and improved legal/source-material validation for this release generation; do not claim later v1.4/v1.5 exact-SHA gates retroactively beyond the evidence preserved for v1.3.0.
```

### v1.2.0

```markdown
## What's New / Highlights

### Added
- Added a split **Scan phone** control with direct phone-package inventory export to CSV.
- Added a detailed in-app Health Score methodology guide.
- Added the application version to the About dialog and support diagnostics.

### Changed
- Reorganized File, Tools and Help menus.
- Changed the Windows x64 prebuilt package from a one-file executable to a standalone ZIP.
- Separated current-result clearing from persistent cache and audit-history maintenance.
- Adopted `GPL-3.0-only`, with alternative commercial licensing and a CLA-based contribution policy.

## Compatibility and distribution
- Prebuilt Windows x64 ZIP.
- The Windows package is unsigned.
- Windows ARM64, macOS and Linux remain source-supported but were not published as v1.2.0 prebuilt packages.

## Release assets
- Windows x64 standalone ZIP.

## Verification
- Historical release. The current repository does not preserve enough standardized release-note evidence to claim the later v1.4/v1.5 exact-SHA verification profile for v1.2.0.
```

### v1.1.0

```markdown
## What's New / Highlights

### Added
- Added a compact **Recent sources** menu beside **Choose file**, synchronized with the File menu.
- Added File-menu access to running an audit and exporting all or visible results as CSV or HTML.
- Added rich in-app guides for ADB setup and CSV/TSV/TXT package-list imports.

### Changed
- Made the source area more compact while retaining file and phone inputs.
- Improved application-icon presentation without changing the visible artwork.
- Simplified the About dialog by removing the LinkedIn link.

## Compatibility and distribution
- Prebuilt Windows x64 package.
- v1.0.0 remained available for the previously published Windows ARM64, Linux and macOS packages.

## Release assets
- Windows x64 prebuilt package.

## Verification
- Historical release. The current repository does not preserve enough standardized release-note evidence to claim the later v1.4/v1.5 exact-SHA verification profile for v1.1.0.
```

### v1.0.0

```markdown
## What's New / Highlights

### Added
- First stable Qt 6 / PySide6 desktop release.
- Added CSV, TSV and TXT package imports with Google Play availability and latest-update checks.
- Added multi-country fallback checks, maintenance classifications, optional Health Score guidance, previous-audit comparison and configurable technical views.
- Added read-only ADB package scanning, device metadata, inventory history, snapshots and report/export support.
- Added prebuilt packages for Windows x64/ARM64, Linux x64/ARM64 and macOS Intel/Apple Silicon.

### Changed
- Adopted the canonical `playstore_app_audit` package and `main.py` entry point.
- Improved large-device audit performance by collecting Android package metadata in bulk where available.

### Fixed
- Restricted latest-update parsing to update-specific fields and visible **Updated on** text.
- Hid ADB subprocess console windows on Windows.
- Added packaged architecture and startup validation.

## Compatibility and distribution
- Prebuilt Windows x64/ARM64, Linux x64/ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64 packages.
- Windows and Linux packages are unsigned.
- macOS packages are ad-hoc signed for bundle integrity and are not Apple-notarized.
- The former CustomTkinter implementation is retained only at the historical `legacy-customtkinter-v9.3` tag.

## Release assets
- Six prebuilt platform/architecture packages covering Windows, Linux and macOS on x64 and ARM64.

## Verification
- Packaged architecture and startup validation were part of the v1.0.0 release work.
- Historical release. Later exact-SHA/legal-source release gates must not be claimed retroactively unless supported by preserved evidence.
```

## v1.5.0 candidate template

The final v1.5.0 GitHub Release body must be generated from the actual frozen release SHA and successful build/assembly evidence, then follow this structure:

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

## Release assets
- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen source SHA: `<exact 40-character main SHA>`.
- Quality CI: Python 3.13 and 3.14.
- Windows x64 package architecture, version and startup validation passed.
- Strict legal/source-material validation passed.
- Engineering release assembler verified source workflow identity, repository, exact SHA, x64-only input, provenance and the exact three-file public asset set.
- `SHA256SUMS.txt` covers the final public release assets.
```

Replace verification placeholders only with evidence from the final successful release run. Do not publish the candidate wording unchanged before those gates pass.
