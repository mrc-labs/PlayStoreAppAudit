# Project Status

Last updated: 2026-08-20

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

### v1.5 target

`v1.5.0` remains a Windows x64-only Engineering Test Build (ETB):

- unsigned Windows x64 only
- one exact frozen `main` SHA
- build workflow: `.github/workflows/build-windows-exe.yml` with `target=x64`
- engineering assembler: `.github/workflows/assemble-windows-engineering-release.yml`
- exactly 3 public assets: `PlayStoreAppAudit-v1.5.0-windows-x64.zip`, `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`
- release title suffix: `(ETB Win x64)`
- release body heading: `## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)`
- no Windows ARM64, Linux or macOS v1.5 release candidates
- no production signing or signing spend

### v1.6 production target

The broader production path is deferred to v1.6:

- Windows x64/ARM64
- Linux x64/ARM64
- macOS x64/ARM64
- validated publicly trusted Windows signing provider still to be selected after eligibility/cost review
- macOS Developer ID signing, hardened runtime, notarization, stapling and Gatekeeper validation
- full production assembly through `.github/workflows/assemble-release.yml`

The repository contains a Microsoft Artifact Signing implementation as one possible Windows path, but the final v1.6 provider is not locked.

## Post-v1.4 maintenance completed

The post-v1.4 CI/storage and release-tooling maintenance workstreams are complete on `main`.

Merged checkpoints:

- CI/storage maintenance merge: `4538793ea5da5e5ac30d894bcf80f27bf53320a0`
- legal-source download resilience merge: `6c6080c89f841355d760c19de00e94a6c43daa2d`

Operational cleanup completed:

- Actions artifacts removed: 140
- Retained artifact data removed: approximately 5372.7 MB
- Completed historical workflow runs removed through 2026-08-16: 94
- Obsolete Python 3.12 dependency caches removed: 9, approximately 2007 MB
- Repository artifact/log retention safety ceiling: 400 days, the maximum currently allowed for this private repository
- All stale merged remote `agent/*` branches from the v1.4 workstream were deleted after merge verification

The durable Actions replacement policy is generational rather than a short fixed artifact lifetime:

- newest successful equivalent generation: keep as current valid build;
- previous successful equivalent generation: 7-day grace after its successor completes;
- older successful generations: delete immediately when a third successful equivalent generation exists;
- failed/cancelled runs: maximum 7 days;
- GitHub Release assets: permanent and outside automated Actions cleanup.

Artifact uploads use repository-default retention as a hard safety ceiling. Intelligent early cleanup is implemented by `.github/scripts/cleanup_actions_retention.py` plus `.github/workflows/actions-retention.yml`. A manual post-merge housekeeping run completed successfully and removed two superseded successful runs, with no failed/cancelled runs old enough for deletion at that checkpoint.

The v1.4 release also exposed one transient network read timeout while preparing legal/source material. The downloader now retries transient metadata/archive read failures that occur after connection establishment, discards partial `.download` files before retry, keeps source archives streamed to disk, does not retry deterministic SHA-256 mismatch, and replaces the destination only after exact expected SHA-256 verification. Focused regression coverage and timing instrumentation for legal preparation are now in place.

## v1.5 implementation progress

The first v1.5 product/UI workstream is complete on `main`:

- File-menu result actions now have one canonical late-stage builder and appear as one uninterrupted `Run Play Store audit` / `Export Results` / `Clear Results` section.
- Connected-phone scans enrich the compact App source summary with manufacturer/model and Android version/API by reusing the device summary already collected after ADB scanning; security patch and masked serial remain available in the tooltip.
- `Exclude system apps from source` now defaults to checked, persists explicit user choices, preserves an already stored `false`, and resets to the default `true`.
- Selected/bold status chips size against their actual selected font with `QFontMetrics` and native style margins/frame metrics instead of fixed padding.
- Health Score and the other numeric table fields use typed numeric sorting, including deterministic blank/None handling.
- Audit status now distinguishes cached and live work and exposes a real native indeterminate `Finalizing…` state before final rows, health scoring, inventory annotations, summary and column updates are presented as completed.
- The unchecked-checkbox HiDPI investigation is resolved by evidence without a product workaround. Diagnostic PR #47 reproduced the supplied Windows appearance using Qt/PySide 6.11.1 with the native `windows11` style at 175% scaling. Checked and unchecked states reported the same 16 x 16 logical indicator metrics and the same control size hint, so there is no state-dependent HiDPI sizing defect. The visual difference is the native Windows checkbox state rendering. Keep the platform/default style; do not add forced Fusion, a theme dependency or a custom global checkbox indicator override for v1.5.

The diagnostic checkbox branch/PR was deliberately closed unmerged after collecting evidence; it does not alter production UI or CI configuration.

## Remaining backlog

There is no unfinished v1.4 release work.

Future work should start from current `main` and the durable project documents rather than recreating v1.4 release state. Remaining items are intentionally future-facing:

- v1.5 product backlog: evidence-driven audit performance investigation/optimization and experimental opt-in app icons;
- measure before changing audit concurrency or retry behaviour; do not increase the existing worker count without evidence;
- use timing output from the next real Windows x64 package build before deciding whether cross-run caching of verified immutable source archives is worthwhile;
- complete v1.5 version/changelog hardening only after the remaining product work is merged, then freeze one exact `main` SHA and build Windows x64 only;
- keep v1.5 as an unsigned Windows x64-only ETB with exactly three public assets and no signing spend;
- move publicly trusted Windows signing, macOS Developer ID/notarization validation and the full Windows/Linux/macOS x64/ARM64 production profile to v1.6;
- keep ETB naming and generational Actions retention unchanged unless a dedicated engineering decision replaces them;
- continue ordinary dependency/API maintenance only with targeted evidence and without weakening release/legal gates.

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
