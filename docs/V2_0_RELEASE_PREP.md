# v2.0.0 release preparation

Date opened: 2026-09-13 CEST

Status: **IN PROGRESS - release preparation only. No release SHA is frozen and no public v2.0.0 tag or release exists yet.**

This checklist begins after PR #150 merged to `main` at `d2a00f8e7f1ca3d2bbe7c9e69b312f911f98e61d` and post-merge Quality passed. The dedicated release-preparation branch is `v2/release-prep-2.0.0`.

## Locked release contract

- Application/package version: `2.0.0`.
- Python baseline: CPython 3.14.
- Windows x64 remains the primary human-acceptance platform.
- The first v2.0.0 package candidate is Windows x64 only.
- No public RC tags.
- Do not start the final six-platform production gate until the Windows x64 v2.0.0 package passes human acceptance.
- Final production targets: Windows x64, Windows ARM64, Linux x64, Linux ARM64, macOS x64 and macOS ARM64.
- All final public platform artifacts must come from one exact frozen release SHA.
- Project-defined public assets are the six platform ZIPs, one consolidated third-party source archive and `SHA256SUMS.txt`.
- Signing/notarization is preferred but may be claimed only after real provider/credential validation succeeds on the final production path.
- Named Custom Views and the internal `health_score` to `maintenance_score` migration remain post-2.0 work.
- CLI/headless remains post-2.0 work.
- Audit Presets remain implemented internally but hidden from the v2.0 user-facing menu.

## Release-preparation checklist

- [x] Final v2 product/UX polish merged through PR #150.
- [x] Post-merge Quality passed on `main`.
- [x] Dedicated v2.0.0 release-preparation branch created from post-PR #150 `main`.
- [x] Source/package version moved from `1.99.0` to `2.0.0` in canonical version metadata.
- [ ] Exact-head Quality passes after all release-preparation source/docs changes.
- [ ] v2.0.0 changelog entry finalized without rewriting immutable historical release facts.
- [ ] Canonical v2.0.0 GitHub Release body drafted using `docs/RELEASE_NOTES.md` structure.
- [ ] Mandatory final component-freshness gate completed and recorded after all product changes, immediately before exact-SHA freeze.
- [ ] Clean Python 3.14 release environment re-resolved and checked for outdated release-path/transitive packages.
- [ ] Maintained GitHub Actions, runner selections, Platform-Tools/ADB and signing/notarization paths rechecked against current stable upstreams.
- [ ] Exact candidate SHA selected only after the final freshness gate and green Quality.
- [ ] Native Windows x64 v2.0.0 standalone package built from the exact candidate SHA.
- [ ] Windows package architecture, version metadata, startup smoke, legal/source bundle and release provenance pass.
- [ ] Human Windows x64 packaged acceptance passes.
- [ ] Any package correction invalidates the candidate and restarts exact-head Quality/freshness/package acceptance as required.
- [ ] Final exact-SHA six-platform production gate passes.
- [ ] Final signing/notarization status recorded from actual production evidence.
- [ ] Release assembly produces the exact project-defined asset set.
- [ ] `SHA256SUMS.txt` independently validates all project-defined public assets.
- [ ] Annotated `v2.0.0` tag created only after the final exact SHA and assets are accepted.
- [ ] GitHub Release published and public assets re-downloaded/reverified.

## Product acceptance already completed before release preparation

The accepted v2 product branch passed human Windows checks for the final File-menu source grouping, About/update-status behavior, Customize View layout and the other final UI polish. Audit Presets were intentionally removed from the visible v2.0 menu surface while their implementation was retained for possible post-2.0 reuse.

The Python 3.14 migration candidate also passed a native Windows x64 standalone-package gate using CPython 3.14.7, PySide6-Essentials/Shiboken6 6.11.2 and Nuitka 4.2.1. That package used version `1.99.0` intentionally and is migration evidence only; it is not a v2.0.0 release artifact.

## Freeze rule

Do not treat this branch, this checklist, a successful Quality run or the earlier Python 3.14 package as the final release freeze. The exact v2.0.0 release SHA is chosen only after the final component-freshness gate is complete and the Windows x64 v2.0.0 candidate has passed the required automated and human acceptance sequence.
