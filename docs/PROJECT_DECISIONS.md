# Project Decisions

## Purpose

This file records durable engineering decisions for Play Store App Audit. It is not a task list and must not contain temporary workflow run IDs, one-off failures or chat-specific notes.

Changing a decision here should be deliberate and should normally happen in the same PR that changes the corresponding implementation or release policy.

## Repository and Git

### One permanent branch

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits.
- Delete short-lived branches after merge.
- Published release history is immutable. Do not rewrite, squash, retag or replace already published release commits/assets.

Rationale: one canonical integration line keeps Windows, Linux and macOS tied to the same source history and avoids platform drift.

## Application architecture

- Production UI is Qt 6 / PySide6 Qt Widgets.
- Do not migrate to QML without a demonstrated UX, maintainability or performance benefit.
- UI code coordinates presentation and interaction; Store parsing, persistence, ADB and OS behaviour remain outside the UI layer.
- Platform-specific behaviour belongs under platform/device boundaries.
- ADB operations remain read-only with respect to installed Android apps.
- Google Play scraping remains behind a replaceable service boundary.

Rationale: the current boundaries keep platform and data-side effects testable while preserving the proven desktop UI.

## Correctness

- Never use Google Play `datePublished` as latest-update data.
- One-country absence is not proof of global removal.
- Health Score is a maintenance heuristic, not a security score.
- Installed/store version differences are not automatically stale/outdated.

These are product semantics, not presentation choices.

## Exact-SHA release model

A production release uses one exact source commit.

- Quality validation comes before freezing the release SHA.
- Freeze one exact full `main` SHA.
- Build six release candidates from that exact SHA.
- Reject a build when expected, dispatch or checkout SHA differ.
- Assemble and validate all release candidates before tagging.
- Create the annotated version tag only after artifact validation.
- Tag pushes do not rebuild release binaries.
- Do not create public RC tags.
- If source or release tooling changes after the SHA freeze, rebuild all six candidates from the new SHA.

Rationale: release tags must identify the source that produced the already validated artifacts. A tag-triggered rebuild could produce different binaries or mix dependency states after validation.

## Public asset model

A production release contains exactly eight public files:

1. Windows x64 ZIP
2. Windows ARM64 ZIP
3. Linux x64 ZIP
4. Linux ARM64 ZIP
5. macOS x64 ZIP
6. macOS ARM64 ZIP
7. one consolidated third-party source `tar.xz`
8. one release-wide `SHA256SUMS.txt`

Rationale: one predictable release surface is easier for users to understand and easier to validate than platform-specific checksum/source sidecars.

## Packaging and legal model

- Windows uses standalone packaging.
- Linux uses standalone packaging, not onefile, and retains replaceable Qt/PySide/Shiboken shared libraries.
- macOS packages a `.app` inside ZIP.
- Public binary packages contain public notices/licenses/source-availability material.
- Internal validation evidence and legal manifests do not ship in public binary packages.
- Do not weaken legal validation to make CI pass.

Linux remains standalone because the bundled LGPL-covered Qt/PySide/Shiboken libraries must remain practically replaceable.

The release-wide source archive centralizes the corresponding-source material required by the binary packages and avoids six duplicated source bundles.

## Runtime policy

- v1.3 packaging baseline is Python 3.13.
- Quality/source compatibility is checked on Python 3.13 and 3.14.
- Move the packaging baseline only as a deliberate compiler/deployment-toolchain migration.
- v1.3 Qt/PySide baseline is `PySide6-Essentials==6.11.1`.
- v1.3 Nuitka pin is `Nuitka==4.1.3`.

Rationale: source compatibility can move ahead of the release compiler without making production packaging depend on an experimental or insufficiently validated toolchain.

## Release workflow structure

The release architecture is platform-isolated but source-SHA unified.

- Windows, Linux and macOS use separate manual package workflows.
- The Linux and macOS workflows each build both x64 and ARM64 release candidates in one architecture matrix.
- The Windows workflow retains its x64/ARM64 target matrix.
- All three source workflows require the same exact frozen `expected_sha` for a production release.
- The release assembler accepts distinct Windows, Linux and macOS run IDs, verifies each source workflow run and its exact head SHA, then assembles the common six-candidate/eight-public-asset release.

Rationale: separate platform workflows improve failure isolation and selective reruns without creating independent platform release lines. The frozen SHA, not the workflow file, defines release source identity.

## Legal-material preflight

Every production package workflow runs a deterministic legal-material preflight after release dependencies are installed and before Nuitka compilation.

The preflight:

- reuses the canonical source/license resolver in `prepare_release_legal_bundle.py` rather than duplicating legal policy;
- requires the installed `PySide6-Essentials` version to match the exact project pin and `shiboken6` to match it;
- resolves official Qt/PySide source archive names and SHA-256 provenance for `pyside-setup`, `qtbase`, `qtimageformats` and `qtsvg`;
- resolves the exact certifi source distribution and digest from PyPI metadata;
- verifies CPython license availability, including the exact-version upstream fallback used by the strict legal tooling;
- verifies required Nuitka legal files and the release build pin.

It intentionally resolves metadata and small legal text only. It does not download the large Qt/PySide source archives before compilation.

The preflight is an early failure gate only. Package-aware source selection, source archive downloads, legal injection and strict final validation still run after packaging. Never weaken or remove the later strict legal gate merely because the preflight passed.

## Dependency/API policy

- Prefer standard library/Qt capability over adding a dependency for simple functionality.
- Replace deprecated or scheduled-for-deprecation APIs proactively where semantics are understood.
- Prefer an explicitly documented newer replacement when behaviour is equivalent and migration risk is low.
- Do not rewrite supported APIs merely because they are old.

Rationale: forward compatibility should be evidence-based rather than cosmetic churn.

## GitHub Actions and Node policy

- The application does not depend on Node.
- Node runtime changes are inherited through official JavaScript GitHub Actions.
- Upgrade to new Node runtime generations by upgrading to supported action majors after those actions adopt the runtime.
- Do not add `setup-node` merely to chase the newest Node LTS.

Rationale: the action author, not this Python application, owns the bundled JavaScript runtime.

## Signing policy

- Public Windows distribution should use trusted Authenticode signing, not a self-signed certificate.
- Public macOS distribution should use Developer ID Application signing and Apple notarization.
- Signing credentials belong in GitHub Secrets or an external signing/secret service, never in the repository.
- Sign owned binaries/app bundles before final ZIP creation and release checksums.
- Do not re-sign third-party binaries without a specific technical/legal reason.

The exact Windows certificate/provider is still a v1.4 implementation choice and should be recorded here once selected.

## UI style policy

- v1.3 forces Qt Fusion style.
- During v1.4, test native platform style and audit custom QSS before adding a theme framework.
- Pay particular attention to QScrollBar rules, palette behaviour, focus/hover/disabled states, tables/headers and control density.
- Preserve semantic app-specific colours and usability while preferring native controls where they improve platform integration.
- If native styling is inconsistent on Linux, a platform-specific native-on-Windows/macOS and Fusion-on-Linux policy may be evaluated before adding a theme dependency.

Rationale: Qt Widgets remains current; a forced cross-platform style and QSS overrides should be evaluated before introducing a new UI technology or theme package.

## Release-script maintenance

Do not delete `.github/scripts` files based on file count or size alone.

Before removing or consolidating a release script, verify:

- direct workflow references
- imports from other release helpers
- unit/regression tests
- behaviour covered by the script
- legal/release evidence boundaries

Large legal scripts may be modularized later, but only with stable behaviour and test coverage.
