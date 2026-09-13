# Play Store App Audit v2.0.0 release draft

Status: **DRAFT - not published.** Replace every verification/signing placeholder only with evidence from the final frozen SHA and final public assets.

Proposed GitHub Release title: `Play Store App Audit v2.0.0`.

```markdown
## What's New / Highlights

### Added
- Local APK analysis can audit explicit package files or recursively discover a folder while keeping local artifact identity separate from Android package identity. Supported package inputs include `.apk`, `.apks`, `.apkm` and `.xapk` containers with conservative split-container handling.
- Local APK results can compare the local installed/version evidence with Google Play evidence using the source-aware Local APK vs Store relationship without promoting Local APK data into phone inventory history.
- Changes & History now has one explicit master tracking control with separate Play Store listing and device inventory tracking, while manual device snapshots remain independently user-controlled.
- About now owns update status and can perform a fresh stable-release check on demand. An asynchronous startup check is enabled by default, remains silent when current/unavailable, and can be disabled without disabling manual About checks.

### Changed
- File is organized by the same source order as the main App Source UI: Android Phone (ADB), Local APK(s), then App List File, with source-specific commands grouped under each source.
- Customize View separates Automatic Columns from user-controlled display/custom columns. Source/context overlays such as Play Store Listing Change, Device App Inventory Change and Local APK vs Store appear automatically only when applicable.
- Definitive Google Play absence in the checked country is presented as a checked-market result rather than proof of global removal. Local APK relationship handling and Maintenance Score avoid double-counting unavailable Store evidence.
- Audit Presets remain implemented internally but are hidden from the v2.0 menu to keep the release surface focused.
- The release toolchain moves to CPython 3.14 with PySide6-Essentials/Shiboken6 6.11.2 and Nuitka 4.2.1.
- v2.0 returns to a six-platform production target after Windows x64 acceptance: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64.

### Fixed
- About update-status layout reserves stable status/action space so the card does not jump vertically between checking, current and update-available states.
- Windows source/package smoke uses the current Source Details view naming rather than the retired Device preset.

## Compatibility and distribution
- Application version: `2.0.0`; Windows File Version and Product Version: `2.0.0.0`.
- Python baseline: CPython 3.14.
- Prebuilt production targets: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64.
- Managed ADB remains read-only with respect to installed Android apps.
- Existing compatibility-sensitive serialized identifiers, including internal `health_score`, remain unchanged in v2.0.
- Signing/notarization status: **TBD from final production evidence. Do not claim production signing until the real provider/credential gates pass.**

## Release assets
Expected project-defined asset names, subject to final assembler validation:
- `PlayStoreAppAudit-v2.0.0-windows-x64.zip`
- `PlayStoreAppAudit-v2.0.0-windows-arm64.zip`
- `PlayStoreAppAudit-v2.0.0-linux-x64.zip`
- `PlayStoreAppAudit-v2.0.0-linux-arm64.zip`
- `PlayStoreAppAudit-v2.0.0-macos-x64.zip`
- `PlayStoreAppAudit-v2.0.0-macos-arm64.zip`
- `PlayStoreAppAudit-v2.0.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Frozen source SHA: **TBD**.
- Final component-freshness gate: **TBD**.
- Exact-head Quality: **TBD**.
- Windows x64 packaged human acceptance: **TBD**.
- Final six-platform build/provenance/architecture/package validation: **TBD**.
- Windows signing status: **TBD**.
- macOS signing/notarization/stapling/Gatekeeper status: **TBD**.
- Final release assembler/checksum/public re-download verification: **TBD**.
```

## Publication rule

Do not copy this draft verbatim into a public release until all `TBD` items have been replaced with evidence. If a production signing/notarization gate is unavailable or fails, state the actual resulting distribution status explicitly rather than implying a stronger trust state.
