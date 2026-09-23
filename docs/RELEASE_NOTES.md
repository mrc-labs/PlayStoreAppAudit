# Release Notes Standard

This document defines the canonical GitHub Release-note structure and records the editorially maintained public body for every published Store App Audit release.

## Mandatory structure

Every public GitHub Release body uses these four sections, in this order:

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

`Added`, `Changed`, and `Fixed` are optional subsections. Omit an empty subsection. Keep the highlights user-facing, concise, and free of routine release-engineering detail that belongs in `Verification` or a dedicated evidence record.

`Compatibility and distribution` states the actual platform, architecture, signing, notarization, and important compatibility limitations. `Release assets` identifies the project-defined deliverables without duplicating GitHub's Assets UI unnecessarily. `Verification` retains the frozen source SHA and the essential package, provenance, legal, and checksum evidence that actually passed.

## Immutability and editorial maintenance

The following published release material is immutable:

- the release source commit;
- the annotated tag and its target;
- every published binary, source, and checksum asset.

GitHub Release descriptive prose is editorially maintainable. It may be corrected, clarified, reformatted, or condensed after publication when the historical facts, release semantics, distribution limitations, signing state, verification claims, tag, and assets remain unchanged. Editorial maintenance never authorizes rebuilding, retagging, replacing an asset, changing a checksum, or strengthening an unsupported historical claim.

The body published on GitHub remains the primary historical source. Repository changelogs, tags, checksums, and preserved CI evidence may supplement only clearly supported missing detail. Obvious encoding and formatting corruption may be fixed without changing meaning.

## Published v2.1.0 release body

Title: `Store App Audit v2.1.0` · [Published 2026-09-22](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.1.0)

```markdown
## What's New / Highlights

### Added
- Manage Local APK files safely with single-file Rename/Remove, collision-checked Mass Rename, and guarded removal of exact Outdated or Unknown results.
- Resolve `Varies with device` Store versions through validated Device Specific profiles using Personal Google Session or Advanced Custom Dispenser providers, while preserving the raw public Store result.
- **Get Phone Data** captures one privacy-safe Personal Device profile through read-only ADB without running an app scan; the profile lasts only for the current session.
- Privacy-safe synthetic screenshots now document the main workflows in the README and in-app Overview.

### Changed
- Local APK comparison and quick-filter presentation now includes Device Specific and N/A states, with clearer source-aware evidence.
- Semantic status, comparison, and criticality colours adapt to light and dark themes.

### Fixed
- Phone → Local APK Folder → Phone transitions no longer leave stale Local APK state or columns behind.
- `Installer Category` no longer duplicates the useful `Installer Source` field in views or column customization.
- Personal Device ownership and recapture guards prevent stale or partial profiles from replacing valid evidence.

## Compatibility and distribution
- Version `2.1.0`; Windows File/Product version `2.1.0.0`; CPython 3.14 baseline.
- Prebuilt for Windows x64/ARM64, Linux x64/ARM64, and macOS Intel/Apple Silicon.
- Windows and Linux packages are unsigned.
- macOS packages are ad-hoc engineering signed, not Developer ID signed, and not notarized.
- Managed ADB remains read-only. Personal Device profiles are session-only; persistent profiles remain issue #200.

## Release assets
- Six platform ZIPs for Windows, Linux, and macOS on x64/ARM64.
- `PlayStoreAppAudit-v2.1.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `df2726b959963e5dbb096638d5072bd15eb1de92`.
- Quality #592 / run `35775208797`: PASS.
- Windows `35776095408`, Linux `35776120755`, and macOS `35776146620`: x64 + ARM64 PASS.
- All six packages passed frozen-SHA, architecture, package, legal/source, and release-layout validation; canonical assembly produced exactly eight files.
- All seven payload hashes matched `SHA256SUMS.txt`; a clean public re-download matched names, sizes, hashes, and the accepted local files byte-for-byte.
```

## Published v2.0.0 release body

Title: `Store App Audit v2.0.0` · [Published 2026-09-15](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.0.0)

```markdown
## What's New / Highlights

### Added
- Audit individual `.apk`, `.apks`, `.apkm`, and `.xapk` files or recursively scan a folder while keeping each physical artifact distinct.
- Compare Local APK versions with Google Play evidence without writing phone inventory history.
- Changes & History now separates Play Store listing tracking, device inventory tracking, and manual snapshots.
- About owns manual update checks, with an optional quiet startup check.

### Changed
- File and view controls are source-aware, and contextual columns appear only when applicable.
- Checked-country Store absence is presented conservatively rather than as proof of global removal.
- v2.0 returns to six-platform distribution and moves the release baseline to CPython 3.14.

### Fixed
- Stabilized About update-status layout, POSIX Local APK scanning, and macOS standalone resource packaging.

## Compatibility and distribution
- Version `2.0.0`; Windows File/Product version `2.0.0.0`; CPython 3.14 baseline.
- Prebuilt for Windows x64/ARM64, Linux x64/ARM64, and macOS Intel/Apple Silicon.
- Windows and Linux packages are unsigned.
- macOS packages are ad-hoc engineering signed, not Developer ID signed, and not notarized.
- Managed ADB remains read-only.

## Release assets
- Six platform ZIPs for Windows, Linux, and macOS on x64/ARM64.
- `PlayStoreAppAudit-v2.0.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `f6530eeecd88df552c616dbb42dd78e867ae7db3`.
- Quality run `34903816649`, Windows `34910426970`, Linux `34910428715`, and macOS `34904088998`: PASS.
- All six packages passed architecture, package, startup, legal/source, provenance, assembly, and release-layout validation.
- The exact eight-file set passed release-wide SHA-256 validation and clean public re-download verification.
```

## Published v1.99.0 release body

Title: `Play Store App Audit v1.99.0 (Win x64 Only)` · [Published 2026-09-09](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.99.0)

```markdown
## What's New / Highlights

### Added
- Scan Phone captures one coherent package snapshot with installed version, installer, enabled state, and system-app metadata.
- Optional Advanced scanning can reuse complete device metadata during Run, even after the phone disconnects.
- Alternative Distribution Discovery adds exact-package evidence from F-Droid main and optional authorized Aptoide when Google Play is conclusively unavailable in checked countries.
- Cooperative Stop preserves completed results and independent cache entries while marking the audit incomplete.

### Changed
- Maintenance Score now distinguishes checked-market absence from regional or inconclusive outcomes and applies only bounded alternative-store recovery.
- Results actions, progress, source-aware layouts, Details presentation, and warning emphasis are clearer and more consistent.
- Device Inventory comparison uses the same coherent snapshot as the audit.

### Fixed
- Device Inventory Change values, summary counts, and HTML/CSV/JSON exports remain synchronized.

## Compatibility and distribution
- Version `1.99.0`; Windows File/Product version `1.99.0.0`.
- Windows x64 standalone ZIP only; no separate Python installation is required.
- The Windows package is unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Windows ARM64, Linux, and macOS were not published for v1.99.0.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI; managed ADB remains read-only.

## Release assets
- `PlayStoreAppAudit-v1.99.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.99.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `1065744488e548663e3ba365566a9932837f5fb5`.
- Quality `34397570534`, Windows build `34397819253`, and assembly `34401780853`: PASS.
- Package SHA-256: `cc556054280ef09bb693a8fd5d6e861c138ee387f96b098788b18db3e171f6c6`.
- Third-party sources SHA-256: `873087f13af891bb20e6e52d97342ba507311f9e13d1f05b80823103e58b80a3`.
- Exact-SHA provenance, AMD64/version/startup, legal/source, three-file layout, checksum, tag-target, and public re-download validation passed.
```

## Published v1.9.0 release body

Title: `Play Store App Audit v1.9.0 (Win x64 Only)` · [Published 2026-08-25](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.9.0)

```markdown
## What's New / Highlights

### Added
- The Details Panel gains an automatic extra-wide layout for wide viewports.
- A native status bar shows operational state and active progress without duplicating source context.

### Changed
- Friendly Notes now appear consistently across the table, tooltip, Details Panel, and HTML report while raw export values remain unchanged.
- **Maintenance Score** replaces **Health Score** in user-facing text without changing the algorithm or `health_score` compatibility identifier.
- Warning colours, About hierarchy, action icons, and the main action row are clearer and more consistent.

### Fixed
- Fixed Display Settings crashes and preserved Custom layout, selection, Details content, and column widths across repeated changes and restart.

## Compatibility and distribution
- Version `1.9.0`; Windows File/Product version `1.9.0.0`.
- Windows x64 standalone ZIP only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI; managed ADB remains read-only.

## Release assets
- `PlayStoreAppAudit-v1.9.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.9.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`.
- Windows package architecture, version, startup, legal/source, provenance, and managed Platform-Tools validation passed.
- Payload SHA-256: `96677284def49dfe70612e9ca6717da432d6ebfdbbeb279f8a6a9f66f0b48306` (ZIP), `ccccbd72992bed8692388077fd409dc76bb8f64efce8fa2ef283b74797a4df95` (sources).
- `SHA256SUMS.txt` SHA-256: `0604b0541e6f4fe02df32cdbc6b9fa77f48e96403356f66ec56c20342815fa52`.
```

## Published v1.8.0 release body

Title: `Play Store App Audit v1.8.0 (Win x64 Only)` · [Published 2026-08-24](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.8.0)

```markdown
## What's New / Highlights

### Added
- Saved Smart Queries with a one-level All/Any builder and versioned persistence.
- Hidden Details mode and a focused Display Settings dialog for icons, dates, and Custom columns.

### Changed
- One compact Details control replaces permanent position buttons while preserving Auto, Right, and Below layouts.
- Advanced Settings, optional Store icons, exports, action availability, naming, and contextual help are more consistent.

### Fixed
- Busy operations now block incompatible settings/profile actions without overwriting active status messages.

## Compatibility and distribution
- Version `1.8.0`; Windows File/Product version `1.8.0.0`.
- Windows x64 standalone ZIP only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI; managed ADB remains read-only.

## Release assets
- `PlayStoreAppAudit-v1.8.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `ac328f0dffddb6b70fa7600f1291377376bc05d4`.
- Package architecture/version, startup, legal/source, provenance, settings migration, and native Windows UI validation passed.
- Payload SHA-256: `290bdb3e04ae9a763d5a280fcc76b3cf4d4afb2d7483603a52de1351cbff5239` (ZIP), `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e` (sources).
- `SHA256SUMS.txt` SHA-256: `cf12bd9e9989307895aa73b7b84341e5f5a40d3443b044fbf0617c12bef070a6`.
```

## Published v1.7.0 release body

Title: `Play Store App Audit v1.7.0 (Win x64 Only)` · [Published 2026-08-23](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.7.0)

```markdown
## What's New / Highlights

### Added
- Responsive Details layouts, structured Store request evidence, installer/source and SDK filters, versioned JSON export, reusable audit profiles, and conservative smart re-audits.

### Changed
- Store country/language resolution, market notes, and separate Store/device history are clearer and more conservative.
- Health Score is an optional maintenance heuristic, disabled by default and explicitly not a malware/security score.

### Fixed
- File/list audits no longer inherit phone language; first audits no longer imply prior inventory changes; not-found evidence remains distinct from transient failures.

## Compatibility and distribution
- Windows x64 only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI; managed ADB remains read-only.

## Release assets
- `PlayStoreAppAudit-v1.7.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- Windows x64 version, regression, Qt smoke, managed ADB, legal/source, standalone-package, and public verification passed.
- Payload SHA-256: `83f0d3ce20f89f8439406400dd1d1c081d4423dd0f3e55add3c97feab6bbbe9c` (ZIP), `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458` (sources).
- `SHA256SUMS.txt` SHA-256: `a2ba41af69bf4169f96569695a9fce69d479566cff97e1eadd2f00cce6b1b533`.
```

## Published v1.6.0 release body

Title: `Play Store App Audit v1.6.0 (Win x64 Only)` · [Published 2026-08-22](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.6.0)

```markdown
## What's New / Highlights

### Added
- Automatic Store language can follow the connected phone, and file/list audits use the selected Store country's language.
- Added remembered Right/Below Details layouts, structured Store country/language evidence, developer metadata, and grouped previous-audit changes.

### Changed
- Consolidated bounded country fallback, aligned Store icons with titles, retained structured change events, and treated the first phone inventory as a baseline.

### Fixed
- Hardened icon-cache failures, avoided language-only retries for conclusive not-found results, and prevented file/list audits from inheriting phone locale.

## Compatibility and distribution
- Windows x64 only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI; managed ADB remains read-only.

## Release assets
- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`.
- Windows x64 regression, Qt smoke, managed ADB, legal/source, standalone-package, and startup validation passed.
- Payload SHA-256: `ab90a461eb9db84579edc15bdc819e59882cf4b210d92787bb86e2ff02f9d593` (ZIP), `0f068f20ef14e0e53bd4869c66ae6542725a5c34e390cebf804279a8b28b1165` (sources).
- `SHA256SUMS.txt` SHA-256: `06899818f1defa92a3151b6e05d714d3d59eda079479624d46cbcbdcaf3e0f93`.
```

## Published v1.5.0 release body

Title: `Play Store App Audit v1.5.0 (Win x64 Only)` · [Published 2026-08-21](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.5.0)

```markdown
## What's New / Highlights

### Added
- Configurable concurrent Store workers, live regional-verification progress, optional cached Store icons, and connected-device summaries.

### Changed
- Faster bounded multi-country checks, a 25-second transport timeout, clearer progress/actions/sorting, and system-app exclusion enabled by default.

### Fixed
- Definitive not-found results no longer receive deterministic retries; network uncertainty remains distinct; unavailable rows no longer show stale icons.

## Compatibility and distribution
- Windows x64 only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI.

## Release assets
- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `6f00bea0789874bc6339286a2ffc3eb9cb2891bb`.
- Windows x64 version, regression, Qt smoke, managed ADB, standalone-package, legal/source, and three-file assembly validation passed.
- Payload SHA-256: `693203f3371cc6ddf000ac54597389c2ca0c30ca54f1a1187b5b2cc6c2e7b661` (ZIP), `b24595b3bbf6adb77846104b246956d0f171777c8be81ef6e22b8d2b68a9a719` (sources).
- `SHA256SUMS.txt` SHA-256: `533a3e88f8fbcd6ab1225a177f39817aa6098264052108384243637fac52e217`.
```

## Published v1.4.0 release body

Title: `Play Store App Audit v1.4.0 (Win x64 Only)` · [Published 2026-08-19](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.4.0)

```markdown
## What's New / Highlights

### Changed
- Qt now uses the system-default style, font, and generic scrollbar presentation while retaining the established semantic colours and branded actions.

## Compatibility and distribution
- Windows x64 only; unsigned and may trigger SmartScreen or unknown-publisher warnings.
- Python 3.13 packaging baseline; Python 3.13/3.14 Quality CI.

## Release assets
- `PlayStoreAppAudit-v1.4.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `6830e0c4a03e355f442070f00dd5008322f5dbc4`.
- Windows x64 package and release validation passed.
- Payload SHA-256: `1c9edf10c7b2b85c3cfc4095340f665815da0e7e3ef82fae664f6fc61929a6fd` (ZIP), `93ded83b5a15389924911cee2865cb1684efeca992e011c1d0d9a02f68c69d72` (sources).
- `SHA256SUMS.txt` SHA-256: `531acbb17a00a212ac6556dc1e6f92871b73ea8dc01190197304086c1f1a19ed`.
```

## Published v1.3.0 release body

Title: `Play Store App Audit v1.3.0 (Win x64 Only)` · [Published 2026-08-19](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.3.0)

```markdown
## What's New / Highlights

### Changed
- Moved Windows distribution to a native standalone package with Qt/PySide6 6.11.1, managed ADB where available, bundled third-party source material, and release-wide checksums.

## Compatibility and distribution
- Windows x64 only; unsigned.

## Release assets
- `PlayStoreAppAudit-v1.3.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.3.0-third-party-sources.tar.xz`.
- `SHA256SUMS.txt`.

## Verification
- Frozen source SHA: `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`.
- Windows x64 package, runtime, and release validation passed.
- Payload SHA-256: `e5ee2f21dca73d1fadff3f77fed6b551804db8b2fd22230e03971e9a4cded4de` (ZIP), `4020dd73b4a1cf65e8107c640cc85b502f1b96fe5ebbcf7b1603a4b830efd69c` (sources).
- `SHA256SUMS.txt` SHA-256: `beaa9fc071aeef8427ef9724a3c8a87e68d7ea5e0a6c2bfe219237758ba800c0`.
```

## Published v1.2.0 release body

Title: `Play Store App Audit v1.2.0 (Win x64 Only)` · [Published 2026-08-18](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.2.0)

```markdown
## What's New / Highlights

### Added
- Scan a connected Android phone and export its package inventory as CSV.
- Added Health Score methodology/limitations guidance and version details in About and support diagnostics.

### Changed
- Reorganized File, Tools, Help, export, and data-maintenance actions.
- Distributed Windows x64 as a validated standalone ZIP; project code uses GPL-3.0-only with separate commercial licensing available.

## Compatibility and distribution
- Windows x64 only; unsigned and may trigger SmartScreen or unknown-publisher warnings.

## Release assets
- `PlayStoreAppAudit-v1.2.0-windows-x64.zip`.
- `PlayStoreAppAudit-v1.2.0-windows-x64.zip.sha256`.

## Verification
- Frozen source SHA: `72e2ca962120de83aa5dfe7571d496f9bf334fa7`.
- ZIP SHA-256: `d72498992f93d68bcd17dbf926f52427fcb2051c8f1cbeecaac3dbf8d7a30e82`.
- Checksum sidecar SHA-256: `b41885c1d8c93b137cd0c0cee66d8233291898c524034d6f9f2ca4a087af42d4`.
```

## Published v1.1.0 release body

Title: `Play Store App Audit v1.1.0 (Win x64 Only)` · [Published 2026-08-17](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.1.0)

```markdown
## What's New / Highlights

### Added
- Added Recent Sources, easier-to-reach File/export/audit actions, and clearer ADB and app-list import guides.

### Changed
- Made the main window more compact, improved icon sizing, and simplified About.

## Compatibility and distribution
- Windows x64 only; unsigned.

## Release assets
- `PlayStoreAppAudit-v1.1.0-windows-x64.exe`.
- `PlayStoreAppAudit-v1.1.0-windows-x64.exe.sha256`.

## Verification
- Frozen source SHA: `af5f96b35d63d846530a2e09207297aa21463251`.
- Executable SHA-256: `2e59211dbfb66f20eaff45bb32dd722f65bc1d11787d50d82b31870bcedc41db`.
- Checksum sidecar SHA-256: `0157e7e2710768e234b0dbe3e0f9677bec58faccfe0254d1cc1abb32f94d683b`.
```

## Published v1.0.0 release body

Title: `Play Store App Audit v1.0.0 (Win x64 Only)` · [Published 2026-08-17](https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.0.0)

```markdown
## What's New / Highlights

### Added
- First stable Qt desktop release, with portable application-data handling, platform-aware Store/ADB paths, and bulk read-only Android package metadata collection.
- Added a stable table schema, explicit UI extension points, regression coverage, and pull-request Quality checks.

### Changed
- Consolidated runtime/state/version ownership and replaced historical module aliases and runtime monkey-patching with explicit canonical interfaces.
- Bulk device metadata avoids hundreds of individual package subprocesses on large inventories.

### Fixed
- Google Play `datePublished` is no longer accepted as the latest-update date.
- ADB subprocesses no longer flash console windows on Windows.

## Compatibility and distribution
- Windows x64 only; unsigned.

## Release assets
- `PlayStoreAppAudit-v1.0.0-windows-x64.exe`.
- `PlayStoreAppAudit-v1.0.0-windows-x64.exe.sha256`.

## Verification
- Frozen source SHA: `87cb259218f3acd3be38b43cd3343ef93f3d7ae6`.
- Windows x64 packaged-startup validation passed.
- Executable SHA-256: `6b57a5adaaad41a62e4b5045a66652782fd24a34f33f5b8ac473234d760e0509`.
- Checksum sidecar SHA-256: `0ad90919ff02c6f4097a989dd7639c54bccbd258a3ec421cbd783b5a04d77b1a`.
```
