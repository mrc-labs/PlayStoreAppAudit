# v2.1.0 release preparation

Date opened: 2026-09-22 CEST

Status: **IN PROGRESS - release preparation only. No final release SHA is frozen and no public v2.1.0 tag or release exists yet.**

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
- [ ] Exact-head Quality passes after all release-preparation source/docs changes.
- [x] Mandatory second complete component-freshness gate passes immediately before exact-SHA freeze.
- [x] Clean Python 3.14 release environment re-resolved on Quality #585 / run `35700725588`; `pip check` passed and `pip list --outdated --format=json` returned exactly `[]`.
- [x] Maintained GitHub Actions, runner selections, Platform-Tools/ADB and signing/notarization source paths rechecked against current upstream support/release state.
- [x] Final pre-release freshness evidence recorded in `docs/V2_1_FINAL_PRE_RELEASE_FRESHNESS.md`; the temporary continuous audit step was removed before final exact-head Quality.
- [ ] Repeated post-macOS-fix final freshness gate completes after adopting Nuitka 4.2.2; the earlier gate remains historical evidence only.
- [ ] Post-fix evidence is finalized in `docs/V2_1_FINAL_PRE_RELEASE_FRESHNESS_POST_MACOS_FIX.md`, temporary audit instrumentation is removed, and normal exact-head Quality passes.
- [ ] Exact candidate SHA selected only after the second freshness gate and green exact-head Quality.
- [ ] Final six-platform exact-SHA production gate passes.
- [ ] Actual Windows/macOS signing/notarization status is recorded from real final runs.
- [ ] Release assembly produces the exact project-defined public asset set.
- [ ] `SHA256SUMS.txt` independently validates every project-defined public asset.
- [ ] Annotated `v2.1.0` tag is created only after the frozen SHA and assets are accepted.
- [ ] GitHub Release is created from already validated assets; tag push must not rebuild binaries.
- [ ] Public release assets are cleanly re-downloaded and names, sizes and SHA-256 values are independently reverified.
- [ ] Permanent closure follows `docs/RELEASE_CLOSURE.md`, including issue #153 and Actions-storage review.

## Feature scope frozen for release prep

v2.1 includes the completed Local APK quick-filter/file-management work, Device Specific productization across phone and Local APK workflows, Personal Google Session and Advanced Custom Dispenser provider paths, process-local privacy-safe Personal Device capture, theme-aware semantic colour polish, canonical synthetic screenshots/in-app Overview, source-transition corrections and final Installer Category presentation cleanup.

Do not add new product scope during release preparation unless a genuine release-blocking defect requires the smallest focused correction. In particular, do not implement issue #200.

## Freeze rule

This branch and a successful Quality run are not the final release freeze. Repeat the complete freshness audit immediately before freeze. Only after that audit and exact-head Quality are green may one full `main` SHA be selected as the v2.1.0 release SHA. Every final platform artifact must derive from exactly that SHA.

The earlier candidate `459d3cf5e6c9290ec1c30e0116fd823d82660c23` is invalidated and not for release. The macOS packaging fix and the later Nuitka 4.2.2 freshness update require a new exact candidate SHA and entirely new final platform artifacts.
