# Project Status

Last updated: 2026-08-19

## Published release

- Latest version: `v1.4.0`
- Release commit: `6830e0c4a03e355f442070f00dd5008322f5dbc4`
- State: published and immutable
- Release class: Engineering Test Build (ETB), Windows x64 only
- Public asset count: exactly 3
- Signing: intentionally unsigned
- Permanent release assets:
  - `PlayStoreAppAudit-v1.4.0-windows-x64.zip`
  - `PlayStoreAppAudit-v1.4.0-third-party-sources.tar.xz`
  - `SHA256SUMS.txt`

The v1.4.0 release was assembled from the exact frozen SHA after post-merge Quality passed. The Windows x64 build and three-file engineering assembler both passed strict package, architecture, startup, provenance, legal/source and checksum validation before tagging. The annotated `v1.4.0` tag points to the frozen SHA and the published assets must not be rebuilt, retagged, rewritten or replaced.

Previous `v1.3.0` remains published and immutable at `fb2193dfc13d0f0e6b7be660c1342bbf87d26081` with exactly 8 public assets covering Windows, Linux and macOS on x64 and ARM64.

## Engineering Test Build naming

Engineering public releases use **Engineering Test Build** as the canonical label and **ETB** as the acronym.

For Windows x64-only ETBs:

- Release title suffix: `(ETB Win x64)`
- Release body heading: `## Play Store App Audit vX.Y.Z (Engineering Test Build - Windows x64 Only)`

Use "build" rather than "release" in the label because ETB describes the validation/trust level of the published binary build while the GitHub object itself is already a Release.

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
- unsigned Engineering Test Build (ETB)
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

After v1.4.0 publication, the retained GitHub Actions inventory was audited and cleaned.

- Actions artifacts removed: 140
- Retained artifact data removed: approximately 5372.7 MB
- Completed historical workflow runs removed through 2026-08-16: 94
- Obsolete Python 3.12 dependency caches removed: 9, approximately 2007 MB

This cleanup did not alter GitHub Release assets, source commits or tags.

The durable replacement policy is generational rather than a short fixed artifact lifetime:

- newest successful equivalent generation: keep as current valid build;
- previous successful equivalent generation: 7-day grace after its successor completes;
- older successful generations: delete immediately when a third successful equivalent generation exists;
- failed/cancelled runs: maximum 7 days;
- GitHub Release assets: permanent and outside automated Actions cleanup.

The implementation is `.github/scripts/cleanup_actions_retention.py` plus `.github/workflows/actions-retention.yml`. See `CI_MAINTENANCE.md`.

## Current maintenance work

The first post-v1.4 maintenance workstream is intentionally scoped to cheap CI/release hygiene and reliability improvements, with no heavy package builds unless a change truly requires them.

Active/remaining items:

- finish and merge the generational Actions retention housekeeping policy;
- configure repository-level artifact/log retention as the long safety ceiling used by current successful artifacts;
- improve legal-source download resilience for transient read timeouts without weakening SHA-256/provenance validation;
- measure legal-material preparation time and evaluate safe caching of already verified immutable source archives;
- preserve strict fail-closed legal/source validation;
- delete stale merged short-lived branches after current maintenance is complete;
- keep public engineering-release naming aligned to the ETB convention.

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
- Do not keep redundant Actions artifact generations after the generational retention policy marks them obsolete.

See `PROJECT_DECISIONS.md`, `BUILDING.md` and `CI_MAINTENANCE.md` for durable policy and procedures.
