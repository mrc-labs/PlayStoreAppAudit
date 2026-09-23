# v2.1.0 release preparation and publication record

Date opened: 2026-09-22 CEST
Published: 2026-09-22T22:11:47Z

Status: **PUBLISHED AND IN POST-RELEASE CLOSURE.** Immutable release SHA `df2726b959963e5dbb096638d5072bd15eb1de92`; public release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v2.1.0

This checklist begins after the feature-complete Windows x64 acceptance and the mandatory release-entry component freshness gate. The dedicated release-preparation branch is `v2/release-prep-2.1.0`, created from post-freshness `main` SHA `64de5e71a6f49c405b6ad5b370f9f063c75cbdec`.

## Accepted entry evidence

- Combined feature-complete Windows x64 package: workflow run `35655658931` from exact `main` SHA `3a76e292bc45e8ff20bad39ffe4e2a5b0c0353b4`.
- Actions artifact ID: `10665003533`, name `PlayStoreAppAudit-v2.0.0-windows-x64` (the source version was deliberately still 2.0.0 at this pre-release-prep gate).
- Verified inner ZIP SHA-256: `4b26dac70281d01fef4fe08038a9a6d3ab0b48cce847fdb315eeb12ec96f0a31`.
- Human packaged acceptance: PASS, including the final Installer Category absence checks and quick regression pass.
- Release-entry freshness audit: PASS; recorded in `V2_1_RELEASE_ENTRY_FRESHNESS.md`.
- Freshness PR #203 merged normally to `main` as `64de5e71a6f49c405b6ad5b370f9f063c75cbdec`.
- Post-merge Quality #582 / workflow run `35699222465`: PASS on that exact SHA.

## Locked release contract

- Application/package version: `2.1.0`.
- Python baseline: CPython 3.14.
- Published v2.0.0 remains immutable and must not be rebuilt, retagged, rewritten or have assets replaced.
- Issue #200 (persistent Personal Device profile library) remains post-v2.1 and out of release scope.
- No public RC tag.
- Final targets: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS x64 and macOS ARM64.
- All final public platform artifacts must derive from one exact frozen release SHA.
- Expected project-defined public set remains six platform ZIPs, one consolidated third-party source archive and `SHA256SUMS.txt`.
- Production signing/notarization is never assumed from workflow presence. Record only the actual trust state proven by final production runs.
- Any source, dependency, tooling or release-document correction after the second freshness gate invalidates the candidate SHA and requires the affected gates to be repeated.

## Release-preparation checklist

- [x] Feature-complete combined Windows x64 package passed human acceptance.
- [x] Mandatory release-entry component freshness gate completed and recorded.
- [x] Freshness PR #203 merged normally and post-merge Quality #582 passed.
- [x] Dedicated v2.1.0 release-preparation branch created from post-freshness `main`.
- [x] Canonical source/package version moved from `2.0.0` to `2.1.0`.
- [x] v2.1.0 changelog entry prepared without rewriting immutable historical release facts.
- [x] Canonical v2.1.0 GitHub Release body drafted using the `docs/RELEASE_NOTES.md` structure.
- [x] Current project-status and roadmap context updated for release preparation.
- [x] Exact-head Quality #592 / run `35775208797` passed on the frozen SHA.
- [x] Mandatory second complete component-freshness gate passes immediately before exact-SHA freeze.
- [x] Clean Python 3.14 release environment re-resolved on Quality #585 / run `35700725588`; `pip check` passed and `pip list --outdated --format=json` returned exactly `[]`.
- [x] Maintained GitHub Actions, runner selections, Platform-Tools/ADB and signing/notarization source paths rechecked against current upstream support/release state.
- [x] Final pre-release freshness evidence recorded in `docs/V2_1_FINAL_PRE_RELEASE_FRESHNESS.md`; the temporary continuous audit step was removed before final exact-head Quality.
- [x] Repeated post-macOS-fix final freshness gate completed after adopting Nuitka 4.2.2; evidence is recorded in `docs/V2_1_FINAL_PRE_RELEASE_FRESHNESS_POST_MACOS_FIX.md`.
- [x] Temporary audit instrumentation was removed before the normal exact-head Quality gate.
- [x] Exact candidate SHA `df2726b959963e5dbb096638d5072bd15eb1de92` was selected only after the second freshness gate and green exact-head Quality.
- [x] Final six-platform exact-SHA gate passed: Windows `35776095408`, Linux `35776120755`, macOS `35776146620`.
- [x] Actual signing state recorded: Windows/Linux unsigned; macOS ad-hoc engineering signed, not Developer ID signed and not notarized.
- [x] Release assembly produced exactly eight project-defined public files.
- [x] `SHA256SUMS.txt` independently validated every payload.
- [x] Annotated `v2.1.0` tag was created after the frozen SHA and assets were accepted.
- [x] GitHub Release was created from the already validated assets; no tag-triggered rebuild occurred.
- [x] Public release assets were cleanly re-downloaded and names, sizes, SHA-256 values and byte identity were independently reverified.
- [ ] The final editorial/roadmap PR, post-merge local synchronization, issue #153 closure and final handoff/snapshot remain. The first closure PR, Actions housekeeping run `35793158003` and explicit artifact cleanup are complete.

## Feature scope frozen for release preparation

v2.1 includes the completed Local APK quick-filter/file-management work, Device Specific productization across phone and Local APK workflows, Personal Google Session and Advanced Custom Dispenser provider paths, process-local privacy-safe Personal Device capture, theme-aware semantic colour polish, canonical synthetic screenshots/in-app Overview, source-transition corrections and final Installer Category presentation cleanup.

Do not add new product scope during release preparation unless a genuine release-blocking defect requires the smallest focused correction. In particular, do not implement issue #200.

## Freeze rule

The release freeze is complete at `df2726b959963e5dbb096638d5072bd15eb1de92`. Every final platform artifact derives from that SHA. Later documentation-only closure commits must distinguish their newer `main` SHA from the immutable release source SHA.

The earlier candidate `459d3cf5e6c9290ec1c30e0116fd823d82660c23` remains invalidated historical evidence and was not used for publication.
