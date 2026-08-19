# Project Status

Last updated: 2026-08-19

## Published release

- Latest version: `v1.4.0`
- Release commit: `6830e0c4a03e355f442070f00dd5008322f5dbc4`
- State: published and immutable
- Public asset count: exactly 3
- Prebuilt platform: Windows x64 only
- Signing: intentionally unsigned engineering/test release
- Permanent release assets:
  - `PlayStoreAppAudit-v1.4.0-windows-x64.zip`
  - `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`
  - `SHA256SUMS.txt`

The v1.4.0 release was assembled from the exact frozen SHA after post-merge Quality passed. The Windows x64 build and three-file engineering assembler both passed strict package, architecture, startup, provenance, legal/source and checksum validation before tagging. The annotated `v1.4.0` tag points to the frozen SHA and the published assets must not be rebuilt, retagged, rewritten or replaced.

Previous `v1.3.0` remains published and immutable at `fb2193dfc13d0f0e6b7be660c1342bbf87d26081` with exactly 8 public assets covering Windows, Linux and macOS on x64 and ARM64.

## Current baselines

- Canonical application version on `main`: `1.4.0`
- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI technology: Qt Widgets
- Production application style: Qt platform/default QStyle; no production/global forced Fusion
- Managed ADB behaviour: read-only with respect to installed Android apps

## Release profiles

### v1.4 published profile

- Windows x64 only
- unsigned engineering/test publication
- build workflow: `.github/workflows/build-windows-exe.yml` with `target=x64`
- assembler: `.github/workflows/assemble-windows-engineering-release.yml`
- exact three-file public asset model
- no Windows ARM64, Linux or macOS v1.4 prebuilt packages

### v1.5 production target

The broader production path remains deferred to v1.5:

- Windows x64/ARM64
- Linux x64/ARM64
- macOS x64/ARM64
- validated publicly trusted Windows signing provider still to be selected after eligibility/cost review
- macOS Developer ID signing, hardened runtime, notarization, stapling and Gatekeeper validation
- full production assembly through `.github/workflows/assemble-release.yml`

The repository contains a Microsoft Artifact Signing implementation as one possible Windows path, but the final v1.5 provider is not locked.

## Post-v1.4 Actions cleanup

After v1.4.0 publication, the repository's retained GitHub Actions artifact inventory was audited.

- Remaining Actions artifacts before cleanup: 140
- Retained artifact data before cleanup: approximately 5372.7 MB
- Cleanup result: all 140 retained Actions artifacts deleted
- Remaining Actions artifacts immediately after cleanup: 0

This cleanup did not alter GitHub Release assets, source commits, tags or workflow history.

The durable policy is now: GitHub Release assets are the permanent distribution archive; GitHub Actions artifacts are temporary pipeline material. See `CI_MAINTENANCE.md`.

## Current maintenance work

The first post-v1.4 maintenance workstream is intentionally scoped to cheap CI/release hygiene and reliability improvements, with no heavy package builds unless a change truly requires them.

Planned/active items:

- shorten Actions artifact retention for active workflows;
- ignore disposable local `release-v*-candidate-*` directories;
- document mandatory post-release Actions artifact cleanup;
- audit all remaining workflow retention settings before v1.5 production builds;
- improve legal-source download resilience for transient read timeouts without weakening SHA-256/provenance validation;
- measure legal-material preparation time and evaluate safe caching of already verified immutable source archives;
- preserve strict fail-closed legal/source validation;
- delete stale merged short-lived branches after current maintenance is complete;
- optionally clean maintainer-only wording from older GitHub Release descriptions.

## Known v1.4 release lesson

The first Windows x64 release-build attempt reached `PREPARE PUBLIC LEGAL RELEASE MATERIAL` after compilation and validation had already succeeded, then failed because a network read operation timed out while downloading legal/source material. Re-running the same job at the same frozen SHA succeeded without source changes.

The current downloader retries HTTP opening failures, but the actual streaming read/copy path is not equally resilient to a timeout that occurs after the connection has opened. This is a post-v1.4 maintenance target. Any fix must retain exact source provenance, expected SHA-256 verification and fail-closed behaviour.

## Durable release invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits.
- Published release history is immutable.
- Every release profile derives all of its artifacts from one exact frozen SHA.
- No public RC tag and no tag-triggered binary rebuild.
- Strict legal/source validation remains mandatory.
- If source or release tooling changes after a release SHA is frozen, discard and rebuild all candidates required by that selected release profile from the new SHA.
- Do not keep long-lived Actions artifact duplicates after permanent GitHub Release publication.

See `PROJECT_DECISIONS.md`, `BUILDING.md` and `CI_MAINTENANCE.md` for durable policy and procedures.
