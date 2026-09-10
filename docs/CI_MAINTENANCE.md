# CI and release maintenance

This document defines the operational maintenance policy for GitHub Actions artifacts, workflow-run history and post-release cleanup. Release engineering invariants remain in `PROJECT_DECISIONS.md` and exact build procedures remain in `BUILDING.md`.

## Storage model

GitHub Actions artifacts are temporary pipeline material, not the permanent release archive.

- Published GitHub Release assets, version tags and source commits are the durable release record.
- Actions artifacts exist to validate, assemble, troubleshoot or publish a release.
- Workflow run history/logs and uploaded artifacts may be deleted independently when they become redundant.
- Published GitHub Release assets are never part of automated Actions cleanup.

## Generational retention policy

Retention is based on equivalent successful build generations rather than a short fixed lifetime.

For each equivalent artifact profile, identified by workflow plus normalized artifact name/platform/architecture:

1. the newest successful generation is retained as the current valid build;
2. when a second successful generation completes, the previous successful generation receives a 7-day grace period;
3. if no newer successful generation arrives, the previous generation is deleted after that 7-day grace period;
4. if a third successful generation arrives before the grace period ends, the oldest generation is deleted immediately;
5. failed and cancelled runs never replace a successful generation and are retained for at most 7 days.

A successor must be `completed/success` and equivalent. Windows x64 does not replace Windows ARM64, a UI audit does not replace a package build, and an unsigned Windows build does not replace a signing run.

The cleanup implementation is `.github/scripts/cleanup_actions_retention.py`, invoked by `.github/workflows/actions-retention.yml` after relevant workflow completions and once daily. Deleting a fully superseded successful run removes its logs and artifacts together. When only some artifacts from a multi-profile run are superseded, only those artifacts are deleted and the run remains.

## Hard retention ceiling

GitHub still imposes an artifact/log retention ceiling independently of the generational policy. Workflow uploads should therefore use the repository-default retention instead of a short per-artifact override. For this private repository, configure the repository's **Actions > General > Artifact and log retention** to the longest desired safety ceiling supported by GitHub.

The generational housekeeping policy is responsible for deleting redundant data earlier. The repository-level ceiling exists only as a final safety limit for the current successful generation if no successor is built for a long time.

## Post-release cleanup

After every public release:

1. verify the published release tag, exact release SHA, permanent asset count and checksums;
2. record the canonical Quality, build, assembly and publication run IDs in `PROJECT_STATUS.md` and the active handoff;
3. identify the artifact generations produced by the canonical build and assembler runs;
4. confirm that no signing, assembly or publication job still needs the Actions copies;
5. retain the latest useful final build and final assembler artifact for audit, unless a later deliberate policy supersedes them;
6. delete repair, validation or repeated candidate artifacts that are redundant after publication, even when the duplicate run completed later than the canonical release run;
7. retain the GitHub Release assets, tag and source commit unchanged;
8. record the remaining Actions artifact count/storage and review unexpectedly large or duplicate artifacts/caches;
9. update `PROJECT_STATUS.md` with the published version and release-engineering lessons.

Do not delete Actions artifacts while they are still inputs to an assembler, signing stage or publication step.

The generational policy remains the normal automated safety net. A newer successful run is not automatically the canonical release run: after publication, verify the actual release lineage before manual deletion. Do not change repository retention or the generational algorithm merely because a release produced a duplicate. Change them only when concrete evidence shows that the documented policy or implementation is inadequate.

The multi-platform `UI style audit` is a deliberate manual workflow for high-impact UI milestones. Normal About, naming, icon-polish and other narrow UI PRs use lightweight Quality checks and local/manual inspection instead of automatically dispatching the three-platform capture matrix.

### v1.9.0 closure snapshot

Post-release housekeeping run `32805211585` applied the unchanged policy successfully on 2026-08-25 from frozen v1.9.0 SHA `6c117009525f40434e9db714dadf1dd01b79f9ab`.

- It saw 10 active artifacts and selected no expired failed/cancelled runs, successful runs or individual artifacts for deletion.
- Remaining Actions storage was 10 artifacts / 574,199,782 bytes (547.60 MiB).
- Canonical v1.9 build artifact `9546290578` and assembler artifact `9546545528` were retained.
- The v1.8 build/assembler generation and two UI-style generations remained within the seven-day grace period.
- No manual deletion bypassed policy, and no release asset, tag, source commit, retention setting or cleanup logic changed.

### v1.99.0 closure snapshot

The post-publication review on 2026-09-09 followed immutable v1.99.0 release SHA `1065744488e548663e3ba365566a9932837f5fb5` through canonical build run `34397819253` and assembler run `34401780853`.

- Active Actions storage contained exactly 2 artifacts / 296,203,247 bytes (282.48 MiB).
- Canonical build artifact `10123641304`, `PlayStoreAppAudit-v1.99.0-windows-x64`, occupied 184,838,528 compressed Actions bytes.
- Canonical assembler artifact `10123756577`, `PlayStoreAppAudit-v1.99.0-windows-x64-engineering-release-assets`, occupied 111,364,719 compressed Actions bytes.
- Both artifacts are the current canonical audit evidence; no redundant eligible artifact was present, so no deletion was required.
- The three GitHub Release assets, annotated tag, exact source commit, retention settings and cleanup logic remained unchanged, and repository visibility remained private.

## Engineering Test Build naming

Use **Engineering Test Build** as the canonical public label for an engineering GitHub release. The acronym is **ETB**.

For a Windows x64-only ETB:

- GitHub Release title suffix: `(Win x64 Only)`
- release-body heading: `## Play Store App Audit vX.Y.Z (Engineering Test Build - Windows x64 Only)`

Use "build" rather than "release" in the label because the GitHub object is already a Release and ETB describes the validation/trust level of the published binary build. Production releases do not use the ETB suffix.

## Local release candidates

Local directories matching `release-v*-candidate-*` are disposable release-working directories and must never be committed. They should be removed after publication and are ignored by Git.

## Performance and reliability review

Release-pipeline performance work must preserve the fail-closed legal/source model.

The post-v1.4 review specifically includes:

- measuring time spent in legal-source metadata resolution, downloads, hashing and archive assembly;
- retrying transient read-timeout failures during legal-source downloads;
- logging which source archive is being downloaded when a failure occurs;
- evaluating safe caching of already verified immutable source archives;
- avoiding repeated network or hashing work only when provenance and SHA-256 verification remain intact.

Do not weaken legal validation, source provenance checks or exact-SHA release guarantees merely to reduce runtime.
