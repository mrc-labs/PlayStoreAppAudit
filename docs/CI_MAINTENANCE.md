# CI and release maintenance

This document defines the operational maintenance policy for GitHub Actions artifacts and post-release cleanup. Release engineering invariants remain in `PROJECT_DECISIONS.md` and exact build procedures remain in `BUILDING.md`.

## Storage model

GitHub Actions artifacts are temporary pipeline material, not the permanent release archive.

- Published GitHub Release assets, version tags and source commits are the durable release record.
- Actions artifacts exist only long enough to validate, assemble, troubleshoot or publish a release.
- Once a release is published and its permanent assets are independently verified, redundant Actions copies should be deleted.
- Workflow run history and logs may remain even when their uploaded artifacts are deleted.

## Retention targets

Use explicit short retention periods on every `actions/upload-artifact` step.

- UI/style audit evidence: 3 days.
- Ordinary engineering/test build artifacts: 7 days.
- Release-candidate artifacts: 7 days.
- Final assembler artifacts: 7 days.
- Do not use long-lived Actions artifacts as a substitute for GitHub Release assets.

If a future workflow has a genuine need for longer retention, document the reason next to that workflow and keep the exception narrowly scoped.

## Post-release cleanup

After every public release:

1. verify the published release tag and permanent asset count;
2. verify the published checksums and exact release SHA;
3. delete intermediate and final Actions artifacts that are now redundant;
4. retain the GitHub Release assets unchanged;
5. update `PROJECT_STATUS.md` with the published version and any release-engineering lessons;
6. review whether any workflow created unexpectedly large or duplicate artifacts.

Do not delete Actions artifacts while they are still inputs to an assembler, signing stage or publication step.

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
