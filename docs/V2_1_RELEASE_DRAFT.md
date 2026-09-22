# Store App Audit v2.1.0 release draft

Status: **DRAFT - not published.** Replace every verification/signing placeholder only with evidence from the final frozen SHA and final public assets.

Proposed GitHub Release title: `Store App Audit v2.1.0`.

```markdown
## What's New / Highlights

### Added
- Local APK file management now supports single-file Rename/Remove, batch Mass Rename with preview/collision checks and swap/cycle-safe execution, plus guarded Remove All Outdated and Remove All Unknown actions.
- Device Specific resolution can add reproducible Store version evidence when the normal public result is `Varies with device`, using validated reference profiles while keeping the raw public Store fact unchanged.
- Device Specific provider choices include Disabled, Personal Google Session and Advanced Custom Dispenser. Personal Google Session is temporary/session-only and Device Specific metadata paths do not purchase, deliver or download APKs.
- **Get Phone Data** can capture one privacy-safe Personal Device profile from a connected Android phone through read-only ADB without running an app scan; the profile exists only for the current application session.
- Canonical privacy-safe screenshots generated from deterministic synthetic data are now used in the README gallery and the in-app Store App Audit Overview.

### Changed
- Device Specific resolved metadata is additive and separated from raw Play Store evidence. Installed/Local APK relationships may show the `(Dev. Sp.)` presentation suffix only when resolved evidence supports it.
- Local APK quick-filter presentation includes the accepted Device Specific and N/A states while preserving canonical filtering/sorting values.
- Semantic status, comparison and criticality colours are theme-aware for readable light- and dark-mode presentation.
- Release-entry component freshness updated Ruff from 0.16.7 to 0.16.8; the Python 3.14 release/tooling environment passed a fail-closed outdated-package audit.

### Fixed
- `Installer Category` no longer appears as a duplicate table/customization field in Source Details, Technical or Customize Columns; `Installer Source` remains the useful user-facing field.
- Phone -> Local APK Folder -> Phone transitions clear stale Local APK relationship/context state and restore the proper phone columns/order.
- Personal Device ownership checks prevent captured Device Specific evidence from being stale-reused as evidence for a different connected phone.
- Failed/incomplete Personal Device recapture preserves the last complete process-local profile rather than replacing it with partial evidence.

## Compatibility and distribution
- Application version: `2.1.0`; Windows File Version and Product Version: `2.1.0.0`.
- Python baseline: CPython 3.14.
- Planned prebuilt targets: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS Intel/x64 and macOS Apple Silicon/ARM64.
- Managed ADB remains read-only with respect to installed Android apps.
- The v2.1 Personal Device profile is intentionally session-only. Persistent multi-profile storage remains post-v2.1 issue #200.
- Published v2.0.0 remains immutable.
- Signing/notarization status: **TBD from final production evidence. Do not claim production signing until the real provider/credential gates pass.**

## Release assets
Expected project-defined asset names, subject to final assembler validation:
- `PlayStoreAppAudit-v2.1.0-windows-x64.zip`
- `PlayStoreAppAudit-v2.1.0-windows-arm64.zip`
- `PlayStoreAppAudit-v2.1.0-linux-x64.zip`
- `PlayStoreAppAudit-v2.1.0-linux-arm64.zip`
- `PlayStoreAppAudit-v2.1.0-macos-x64.zip`
- `PlayStoreAppAudit-v2.1.0-macos-arm64.zip`
- `PlayStoreAppAudit-v2.1.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

## Verification
- Feature-complete Windows x64 combined acceptance: PASS from pre-release-prep `main` SHA `3a76e292bc45e8ff20bad39ffe4e2a5b0c0353b4`, workflow run `35655658931`.
- Release-entry component freshness gate: PASS; evidence recorded in `docs/V2_1_RELEASE_ENTRY_FRESHNESS.md`.
- Frozen source SHA: **TBD after the second freshness gate.**
- Final pre-freeze component freshness gate: **PASS** on Quality #585 / workflow run `35700725588` at audit head `126602cfe8ef7d05139ed8005940047a1062088d`; `pip check` passed and `pip list --outdated --format=json` returned exactly `[]`. The temporary freshness step is removed before freeze.
- Exact-head Quality on the frozen candidate: **TBD.**
- Final six-platform build/provenance/architecture/package validation: **TBD.**
- Windows signing status: **TBD.**
- macOS signing/notarization/stapling/Gatekeeper status: **TBD.**
- Final release assembler/checksum/public re-download verification: **TBD.**
```

## Publication rule

Do not copy this draft verbatim into a public release until all `TBD` items have been replaced with evidence. If production signing/notarization is unavailable or fails, state the actual distribution status explicitly rather than implying a stronger trust state.
