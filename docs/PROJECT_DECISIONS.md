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

Rationale: one canonical integration line keeps platform work tied to the same source history and avoids release drift.

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

Every public release profile uses one exact source commit.

- Quality validation comes before freezing the release SHA.
- Freeze one exact full `main` SHA.
- Reject a build when expected, dispatch or checkout SHA differ.
- Assemble and validate every candidate required by the selected release profile before tagging.
- Create the annotated version tag only after artifact validation.
- Tag pushes do not rebuild release binaries.
- Do not create public RC tags.
- If source or release tooling changes after the SHA freeze, rebuild every candidate required by that profile from the new SHA.
- Never mix release artifacts from different source SHAs.

Rationale: release tags identify the source that produced already validated artifacts. A tag-triggered rebuild could produce different binaries or dependency states after validation.

## Release profiles

### v1.4 Windows x64 Engineering Test Build (ETB)

v1.4 intentionally publishes one unsigned Windows x64 Engineering Test Build (ETB).

- The Windows x64 package comes from one exact frozen SHA.
- Build it with `.github/workflows/build-windows-exe.yml` using `target=x64`.
- Do not invoke Windows production signing for v1.4.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.4.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The engineering assembler accepts only the successful unsigned Windows x64 `Build Windows - Qt6` run from the same repository and exact SHA and rejects ARM64 input.
- The public v1.4 asset set is exactly three files:
  1. Windows x64 ZIP
  2. one consolidated third-party source `tar.xz`
  3. one release-wide `SHA256SUMS.txt`
- Engineering GitHub Releases use title suffix `(ETB Win x64)`; the release-body heading identifies `Engineering Test Build - Windows x64 Only`; the package remains clearly described as unsigned.

Rationale: v1.4 provides a real public ETB checkpoint while minimizing runner cost and avoiding production-trust claims before credential-backed signing validation exists.

### v1.5 Windows x64 Engineering Test Build (ETB)

v1.5.0 intentionally keeps the unsigned Windows x64 Engineering Test Build profile.

- The Windows x64 package comes from one exact frozen SHA.
- Build with `.github/workflows/build-windows-exe.yml` using `target=x64`.
- Do not invoke Windows production signing for v1.5.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.5.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The public v1.5.0 asset set is exactly three files: `PlayStoreAppAudit-v1.5.0-windows-x64.zip`, `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`.
- The GitHub Release title suffix is `(ETB Win x64)` and the release-body heading is `## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)`.
- The Windows package remains clearly described as unsigned. No signing spend is part of normal v1.5 work.

Rationale: v1.5 focuses on product/UI work and another validated Windows x64 engineering checkpoint without incurring production-signing or multi-platform release cost.

### v1.6 Windows x64 Engineering Test Build (ETB)

The v1.6.0 public release profile is frozen as an unsigned Windows x64 Engineering Test Build.

- Canonical application version is `1.6.0`.
- The Windows x64 package must come from one exact frozen `main` SHA after the post-merge Quality gate passes.
- Build with `.github/workflows/build-windows-exe.yml` using `target=x64`.
- Do not invoke Windows production signing for v1.6.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.6.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The public v1.6.0 asset set is exactly three files: `PlayStoreAppAudit-v1.6.0-windows-x64.zip`, `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`.
- The GitHub Release title is `Play Store App Audit v1.6.0 (ETB Win x64)` and the release-body heading is `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.
- The Windows package is intentionally unsigned.
- The optional richer dashboard/summary candidate is not part of v1.6.0.
- Any source or release-tooling change after the exact release SHA is recorded invalidates the candidate and requires a new exact SHA and rebuild of the ETB artifacts.

Rationale: v1.6 focuses on Store-service maturity, locale correctness, details/change UX and reliability while preserving a low-cost, already validated public distribution profile. Production signing and multi-platform release cost remain deferred.

### v1.7, v1.8 and v1.9 Windows x64 Engineering Test Builds (ETB)

v1.7, v1.8 and v1.9 deliberately continue the unsigned Windows x64-only Engineering Test Build profile. v1.7.0 is published and immutable; v1.8 and v1.9 continue the same distribution constraint.

For all three release lines:

- the Windows x64 package must come from one exact frozen `main` SHA after the required Quality/UI gates pass;
- build with `.github/workflows/build-windows-exe.yml` using `target=x64`;
- do not invoke Windows production signing;
- do not build or publish Windows ARM64, Linux or macOS release candidates;
- assemble with `.github/workflows/assemble-windows-engineering-release.yml`;
- publish exactly three project-defined assets: the Windows x64 ZIP, one consolidated third-party source `tar.xz`, and one release-wide `SHA256SUMS.txt`;
- use GitHub Release title suffix `(Win x64 Only)` while the body heading continues to identify `Engineering Test Build - Windows x64 Only`; clearly describe the package as unsigned;
- any source or release-tooling change after an exact release SHA is recorded invalidates that candidate and requires a new exact SHA and rebuild of the ETB artifacts.

The v1.8 product-scope expansion and the v1.9 release line do not change the distribution profile. Windows ARM64 and non-Windows release artifacts remain outside v1.7, v1.8 and v1.9.

Rationale: v1.7, v1.8 and v1.9 remain focused desktop product iterations. Keeping one validated Windows x64 profile avoids unnecessary signing and multi-platform release cost before the v2.0 distribution milestone.

### v2.0-or-later production release milestone

v2.0 is the first planned return to the full six-platform production release architecture. Production signing is the preferred outcome, but public-trust signing/notarization must remain conditional until provider eligibility, credentials, cost and end-to-end verification are proven.

- Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 final candidates all derive from one exact frozen SHA.
- Windows final candidates must use a validated publicly trusted code-signing provider with native post-sign verification.
- macOS final candidates pass through Developer ID Application signing, hardened runtime, notarization, stapling and Gatekeeper verification.
- Linux remains Nuitka standalone with replaceable Qt/PySide/Shiboken shared libraries.
- Assemble with `.github/workflows/assemble-release.yml` only after all six candidates validate.
- The full production asset set is exactly eight files: six platform ZIPs, one consolidated third-party source `tar.xz`, and one `SHA256SUMS.txt`.

Rationale: the production architecture can remain maintained and testable without forcing signing credentials, publisher eligibility, notarization setup or six-target release cost into v1.6, v1.7 or v1.8.

## Packaging and legal model

- Windows uses standalone packaging.
- Linux uses standalone packaging, not onefile, and retains replaceable Qt/PySide/Shiboken shared libraries.
- macOS packages a `.app` inside ZIP.
- Public binary packages contain public notices/licenses/source-availability material.
- Internal validation evidence and legal manifests do not ship in public binary packages.
- Do not weaken legal validation to make CI pass.

Linux remains standalone because the bundled LGPL-covered Qt/PySide/Shiboken libraries must remain practically replaceable.

The release-wide source archive centralizes corresponding-source material required by the published binary packages. The source union is profile-specific: Windows x64 ETB profiles use the exact source evidence from their Windows x64 candidate; the future full production profile merges all six platform candidates.

## Runtime policy

- Packaging baseline is Python 3.13.
- Quality/source compatibility is checked on Python 3.13 and 3.14.
- Move the packaging baseline only as a deliberate compiler/deployment-toolchain migration.
- Current Qt/PySide baseline is `PySide6-Essentials==6.11.1`.
- Current Nuitka pin is `Nuitka==4.1.3`.

Rationale: source compatibility can move ahead of the release compiler without making packaging depend on an insufficiently validated toolchain.

## Release workflow structure

Package workflows are platform-isolated and exact-SHA guarded:

- `.github/workflows/build-windows-exe.yml`
- `.github/workflows/build-linux.yml`
- `.github/workflows/build-macos.yml`

Trust/assembly workflows are purpose-specific:

- `.github/workflows/sign-windows.yml`: future Windows production-signing stage, not planned for normal execution before v2.0;
- `.github/workflows/assemble-windows-engineering-release.yml`: unsigned Windows x64 engineering asset assembly for ETB profiles such as v1.4/v1.5/v1.6/v1.7/v1.8/v1.9/v1.9;
- `.github/workflows/assemble-release.yml`: future six-platform production asset assembly, not planned for normal execution before v2.0.

The engineering assembler verifies source workflow identity, manual-dispatch status, success, repository and exact head SHA, rejects ARM64 source artifacts, validates the Windows x64 candidate and emits the three-file engineering release set.

The full assembler accepts distinct signed-Windows, Linux and production-macOS run IDs, verifies workflow identity/status/repository/exact SHA, validates all six candidates and emits exactly eight files when the future full-production profile is selected.

Rationale: separate assembly profiles preserve exact-SHA and legal guarantees while allowing lightweight ETB releases without unnecessary platform/signing work.

## GitHub Actions generational retention

GitHub Actions artifacts and artifact-producing run history use a generational cleanup policy. Published GitHub Release assets remain outside this cleanup.

- The newest successful equivalent generation is the current valid build.
- A superseded previous successful generation receives a 7-day grace period.
- A third successful equivalent generation deletes the oldest immediately.
- Failed/cancelled runs do not replace successful generations and are retained for at most 7 days.
- Equivalence includes workflow identity and normalized artifact/platform/architecture identity.
- Artifact uploads use repository-default retention as the hard safety ceiling.

Implementation and operational details live in `CI_MAINTENANCE.md`.

Rationale: preserve the latest valid build during inactive periods while preventing redundant generations from recreating multi-gigabyte Actions storage growth.

## Legal-material preflight

Every package workflow runs a deterministic legal-material preflight after release dependencies are installed and before Nuitka compilation.

The preflight:

- reuses the canonical source/license resolver in `prepare_release_legal_bundle.py` rather than duplicating legal policy;
- requires the installed `PySide6-Essentials` version to match the exact project pin and `shiboken6` to match it;
- resolves official Qt/PySide source archive names and SHA-256 provenance for `pyside-setup`, `qtbase`, `qtimageformats` and `qtsvg`;
- resolves the exact certifi source distribution and digest from PyPI metadata;
- verifies CPython license availability, including the exact-version upstream fallback used by the strict legal tooling;
- verifies required Nuitka legal files and the release build pin.

It intentionally resolves metadata and small legal text only. Package-aware source selection, source archive downloads, legal injection and strict final validation still run after packaging. Never weaken or remove the later strict legal gate merely because the preflight passed.

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

Production signing is implemented in source but deliberately deferred from normal v1.6/v1.7/v1.8/v1.9 release work. Reconsider production signing and full production distribution no earlier than the v2.0 milestone.

### macOS production target, v2.0 or later

Production macOS release candidates use Developer ID Application signing followed by Apple notarization.

- Legal/public package files are injected before the final signature.
- Nested Mach-O code and nested bundles are signed inside-out, then the top-level `.app` is signed.
- Production signatures enable the hardened runtime and a secure timestamp.
- `codesign --deep` is used for recursive verification, not as the production signing strategy.
- The notarization upload archive is temporary and is not a public release artifact.
- Production flow requires Apple notarization status `Accepted`, staples the ticket to the app, validates the staple, verifies the code signature and passes a Gatekeeper assessment before creating the release ZIP.
- Strict legal runtime evidence is refreshed after the final signed/stapled app state and validated before the release ZIP is created.
- Engineering mode remains available with ad-hoc signing and non-canonical artifact names.
- Developer ID certificate material and App Store Connect notary API credentials live in GitHub Secrets and are materialized only in temporary runner files/keychains.

Required production secrets when this milestone is activated:

- `MACOS_DEVELOPER_ID_APPLICATION_P12_BASE64`
- `MACOS_DEVELOPER_ID_APPLICATION_P12_PASSWORD`
- `MACOS_DEVELOPER_ID_TEAM_ID`
- `MACOS_NOTARY_API_KEY_P8_BASE64`
- `MACOS_NOTARY_KEY_ID`
- `MACOS_NOTARY_ISSUER_ID`

### Windows production target, v2.0 or later

Production Windows release candidates require a publicly trusted code-signing provider suitable for publicly distributed Win32 applications. The repository currently implements Microsoft Artifact Signing Public Trust as one option, but provider choice is deferred until the production milestone.

- Native x64 and ARM64 packages are compiled first by `build-windows-exe.yml` from the exact frozen SHA.
- `.github/workflows/sign-windows.yml` accepts only a successful exact-SHA Windows build from the same repository.
- Azure authentication uses GitHub OIDC through `azure/login`; no publisher private key or PFX is stored in the repository or GitHub Secrets.
- The signing action runs on a supported x64 Windows runner and signs only the owned top-level `PlayStoreAppAudit.exe`.
- The final signed ARM64 package is re-extracted, signature-verified and smoke-tested on a native Windows ARM64 runner.
- SHA-256 file digests and RFC3161 timestamping are required.
- Non-target package files are hash-guarded; legal evidence and strict package validation are refreshed after signing.
- Self-signed certificates and Private Trust/test profiles are not valid for public release distribution.

If Microsoft Artifact Signing is selected later, required production configuration outside source control is:

- GitHub Secrets: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
- GitHub repository variables: `WINDOWS_ARTIFACT_SIGNING_ENDPOINT`, `WINDOWS_ARTIFACT_SIGNING_ACCOUNT_NAME`, `WINDOWS_ARTIFACT_SIGNING_CERTIFICATE_PROFILE_NAME`

Rationale: the current signing implementation stays ready as one option without forcing cost, eligibility or credential setup into near-term releases.

## UI style policy

Qt selects the production application QStyle from the platform/default environment. The application does not globally force Fusion or another QStyle.

The v1.4 cross-platform render audit on Qt/PySide 6.11.1 established:

- Windows default style is `windows11` and provides a more platform-appropriate control treatment than explicit Fusion.
- macOS default style is `macos` and provides a more platform-appropriate control treatment than explicit Fusion.
- Linux hosted/Xvfb default style resolves to Fusion, so removing the global override preserves the existing Fusion appearance in that validated Linux environment.

Policy:

- Do not call `QApplication.setStyle(...)` globally without a new cross-platform evidence-based reason.
- Preserve Qt Widgets; the audit provides no reason to migrate to QML.
- Do not add a theme dependency merely to make controls look newer.
- Preserve semantic app-specific colours and branded primary actions.
- Let Qt/platform style own generic font and scrollbar presentation unless new evidence justifies an override.
- Re-run the cross-platform UI style audit for changes to `app.py`, shared UI QSS or the audit harness.

## Release-script maintenance

Do not delete `.github/scripts` files based on file count or size alone.

Before removing or consolidating a release script, verify:

- direct workflow references;
- imports from other release helpers;
- unit/regression tests;
- behaviour covered by the script;
- legal/release evidence boundaries.

Large legal scripts may be modularized later, but only with stable behaviour and test coverage.