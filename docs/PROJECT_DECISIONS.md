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
- Maintenance Score is the user-facing name for the maintenance heuristic, not a security score. The compatibility-sensitive internal and persisted identifier remains `health_score` until a separate migration is deliberately approved.
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
- The current GitHub Release title is `Play Store App Audit v1.6.0 (Win x64 Only)` and the release-body heading is `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.
- The Windows package is intentionally unsigned.
- The optional richer dashboard/summary candidate is not part of v1.6.0.
- Any source or release-tooling change after the exact release SHA is recorded invalidates the candidate and requires a new exact SHA and rebuild of the ETB artifacts.

Rationale: v1.6 focuses on Store-service maturity, locale correctness, details/change UX and reliability while preserving a low-cost, already validated public distribution profile. Production signing and multi-platform release cost remain deferred.

### v1.7, v1.8, v1.9 and v1.99 Windows x64 Engineering Test Builds (ETB)

v1.7, v1.8, v1.9 and v1.99 deliberately continue the unsigned Windows x64-only Engineering Test Build profile. v1.7.0, v1.8.0 and v1.9.0 are published and immutable; v1.99 continues the same distribution constraint unless a later explicit release decision changes it.

For all four release lines:

- the Windows x64 package must come from one exact frozen `main` SHA after the required Quality/UI gates pass;
- build with `.github/workflows/build-windows-exe.yml` using `target=x64`;
- do not invoke Windows production signing;
- do not build or publish Windows ARM64, Linux or macOS release candidates;
- assemble with `.github/workflows/assemble-windows-engineering-release.yml`;
- publish exactly three project-defined assets: the Windows x64 ZIP, one consolidated third-party source `tar.xz`, and one release-wide `SHA256SUMS.txt`;
- use GitHub Release title suffix `(Win x64 Only)` while the body heading continues to identify `Engineering Test Build - Windows x64 Only`; clearly describe the package as unsigned;
- any source or release-tooling change after an exact release SHA is recorded invalidates that candidate and requires a new exact SHA and rebuild of the ETB artifacts.

The immutable v1.7.0 release SHA is `e2d09098bc42c6f16d202d010deda3eb24d99aa3`. The immutable v1.8.0 release SHA is `ac328f0dffddb6b70fa7600f1291377376bc05d4`. The immutable v1.9.0 release SHA is `6c117009525f40434e9db714dadf1dd01b79f9ab`.

The completed v1.8/v1.9 product scope and the active v1.99 cycle do not change the distribution profile. Windows ARM64 and non-Windows release artifacts remain outside v1.7, v1.8, v1.9 and v1.99.

v1.99 adds a deliberately authorized packaged acceptance candidate before final release. After feature completion, freeze an RC candidate, build a real Windows x64 package and obtain thorough user acceptance. If corrections change source, that RC SHA and artifact are not final. Freeze a new exact `main` SHA only after acceptance, rerun Quality, then build and assemble the canonical final Windows x64 package from that new SHA. No public RC tag is created.

Rationale: v1.7, v1.8, v1.9 and v1.99 remain focused desktop product iterations. Keeping one validated Windows x64 profile avoids unnecessary signing and multi-platform release cost before the v2.0 distribution milestone.

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
- `.github/workflows/assemble-windows-engineering-release.yml`: unsigned Windows x64 engineering asset assembly for ETB profiles such as v1.4/v1.5/v1.6/v1.7/v1.8/v1.9/v1.99;
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

Production signing is implemented in source but deliberately deferred from normal v1.6/v1.7/v1.8/v1.9/v1.99 release work. Reconsider production signing and full production distribution no earlier than the v2.0 milestone.

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

## v1.9 UX review decisions

The v1.9 architectural/UX review approved one grouped presentation-consistency implementation:

- friendly Notes text comes from one pure presentation-service function used by the table, Details Panel and user-facing HTML report, while raw `notes` data remains unchanged for CSV, versioned JSON, diagnostics and persisted Smart Query compatibility;
- the table keeps compact single-line rows and exposes the complete friendly Notes text through a tooltip;
- **Maintenance Score** replaces **Health Score** in user-facing labels, help and reports without renaming `health_score` or changing the algorithm;
- Installed-vs-Store **Different**, Android Compatibility **Aging target** and **Legacy target** use foreground-only warning colours from the existing status palette;
- About keeps the product title dominant, uses the tagline as the subtitle and places the version beneath it as secondary information;
- Choose File, Scan Phone and Export Results use one small project-owned, palette-aware QPainter icon family. No third-party icon library or global theme is introduced;
- Display Settings uses a safe presentation-data refresh instead of manually emitting `layoutChanged`, activates and synchronizes the Custom preset only when its columns change, and preserves populated-table sorting, filtering, selection, Details content and column widths across changes and restart.

The separate evidence-gated Details Panel prototype was accepted. Its automatic internal layout has three states based only on the actual usable scroll-viewport width: the established narrow/wide enter/exit thresholds remain 760/680 px, while extra-wide enters at 1180 px and exits at 1080 px. Extra-wide groups Store/Notes, Installed/Changes and Store evidence/diagnostics in three columns, with actions horizontal below. It introduces no preference or persistence migration, does not change Auto/Right/Below/Hidden placement, and must preserve complete scrollable content at compact panel heights.

The separate complementary `QStatusBar` prototype was accepted after native Windows comparison. The real Qt status bar reparents the same existing `status_label` as its expanding left item and the same existing progress widget as a fixed 200 px right item; no mirrored label, second progress indicator or new operational state model is introduced. Progress is shown only while the established source/audit/finalization state reports active work, avoiding stale idle/completion/error progress. The main action row contains Run, Export Results and Clear Results only. Existing source/device identity is intentionally not duplicated. The native size grip remains enabled, presentation-only status guards remain authoritative, and the status bar introduces no preference or persistence requirement and does not replace the Details Panel.

The accepted v1.9 UX implementations merged through PRs `#116`, `#117` and `#118`. The v1.9 product/UX feature scope is closed; release-readiness work does not reopen it without a genuine release blocker.

The following remain rejected for v1.9: a global Fluent redesign, an icon library without demonstrated need, broad architecture/type refactors and a full internal `health_score` rename. They remain recorded for possible evidence-based future reconsideration rather than being erased from project history.

## v1.99 product decisions

v1.99 is feature complete and likely the final Windows x64-only release before v2.0. Stabilization and release-candidate work must preserve the frozen product scope.

### Cooperative audit Stop/Cancel

The real cooperative Stop/Cancel lifecycle merged through PR `#122` at `c5322d42a7ebdd0f7e61fd1c25b69828d8535e25` alongside Run and Pause/Resume.

- Stop scheduling new work immediately and propagate cancellation through Store checks, regional checks and finalization queues.
- Let in-flight operations exit safely or reach existing timeout boundaries; never use `QThread.terminate()` or an equivalent forced termination.
- Preserve completed valid results and independently valid cache entries.
- Mark the audit cancelled/incomplete rather than completed, and never promote it to the completed previous-audit/history baseline.
- Return the application to a reusable idle state so a later audit starts normally.

The implementation covers the Store and regional-check scheduling boundaries, preserves valid partial work and independent cache entries, separates successful-result finalization from history/baseline persistence, and returns to a reusable idle state. These semantics remain required for later v1.99 changes.

### Main actions, Details selector and status bar

The first v1.99 product/operational UX gate is complete. Native-Windows A/B/C comparison selected the integrated results-header direction, and the focused C0/C1/C2 comparison selected **C2**. The first results header row keeps Run/Pause/Resume and Stop together, followed by the same canonical progress widget, then Export Results and Clear Results. The progress widget has a 120 px minimum and 320 px maximum, expands into available inline space, and remains present in the same geometry for Idle, Running, Paused, Resumed, Stopping, Finalizing and Completed. Idle/completed presentation is a neutral empty determinate track with no percentage or animation; active operations retain the established determinate or busy behavior.

The second results header row keeps the multi-select status chips, Hide System Apps, search and the existing Details selector. Details retains one synchronized Auto/Right/Below/Hidden model shared with `View > Details Panel`; it is not duplicated or moved to the status bar. The native status bar retains the single canonical operational text label and size grip, with no mirrored status or progress state. RC1 native Windows review established 16 logical px left and 12 logical px right contents margins on that label; the full-width status-bar frame remains edge-to-edge and the C2 header geometry is unaffected.

The second v1.99 product gate finalized one shared semantic warning presentation across the results table, Details Panel, context Details dialog and HTML report. Installed-vs-Store **Different** and Android Compatibility **Aging target** reuse the existing status palette's dark-yellow foreground at Qt DemiBold weight 600. **Legacy target** reuses the stronger dark-orange foreground at DemiBold weight 600. **Modern** and other normal values remain Regular weight 400 and the first Status column remains Bold weight 700. The stronger Legacy severity is communicated by its dark-orange colour rather than a different font weight. RC1 native Segoe UI/Qt evidence required moving Different/Aging from 500 to 600 because Medium was visually indistinguishable from regular. Qt continues to manage the table selection background; the semantic foregrounds remain readable on selected and unselected rows without selection-specific colours. Disabled labels retain the native disabled role, and the application continues to use its established light presentation rather than claiming an unsupported dark theme. CSV, JSON, raw models, classifications, scoring, persistence and schemas are unchanged.

RC1 from `7c3f2e768f5a6592e12a835b40a31d70a59e0bc6` passed package/technical validation but was not accepted as final. The narrow correction keeps version `1.99.0`, adds `Tools > Data Maintenance > Clear Device Inventory History…` for only the per-device `inventory_<sanitized-device-id>.json` comparison baselines, and preserves explicit Device Snapshots, Play Store audit cache, previous-audit history, provider cache, settings and current results. A later completed device audit establishes a new per-device baseline. **Show app icon** now defaults on only when the setting is absent; existing saved true and false values remain authoritative, and icon loading remains lazy, cached and non-fatal. The next package will be RC2; it is not yet built or accepted.

### RC3 Column Preset and Custom layout persistence

RC3 Phase B1 renames only the user-facing preset concept to **Column Preset** and the existing Display Settings dialog to **Customize View**. Basic, Device and Technical remain immutable built-in definitions. Any manual header resize/reorder or Customize View visibility change captures the resulting table state as Custom; applying a built-in never mutates or deletes that saved Custom state. Custom is unavailable until a real or conservatively migrated layout exists and then survives sorting, filtering, refresh/audit work, built-in switching and restart.

The deliberately small settings extension keeps `view_preset` as the effective identifier and stores Custom visibility, full visual order and widths in `custom_view_columns`, `custom_view_order` and `custom_view_widths`, gated by `custom_view_exists`. The existing `qt_header_state` remains a compatibility alias and the source for conservative RC2/Phase A migration; `qt_header_schema_version` keeps its existing invalidation role. Malformed/partial values are sanitized or fall back to the Phase A semantic defaults without wiping unrelated settings. App-icon visibility, date format and equivalent presentation preferences remain global and are not members of Custom.

### RC3 SDK filtering and Audit Preset boundary

The dedicated SDK Maintenance Filter is retired in RC3 Phase B2. It was an in-process, session-only additional result predicate with no settings keys and no startup restoration; removing its UI and install hook guarantees that no old or legacy-looking settings value can reactivate it invisibly. Target SDK, Min SDK and Android Compatibility remain first-class collected/presented data, classification/scoring inputs and Smart Query fields. Smart Queries are the advanced mechanism for SDK and compatibility result conditions. The versioned JSON filter-context member remains neutral and structurally compatible rather than forcing an unrelated schema change.

The same checkpoint renames Audit Profiles to **Audit Presets** only on user-facing surfaces. The compatibility-sensitive settings key remains `audit_profiles`, schema version remains 1 and existing saved names remain valid. A preset owns audit-execution state only: source expectation, Store locale/country, cache and refresh-related choices, worker count, device metadata/permission enrichment, history/compare behavior and source-system exclusion. It never applies search, status chips, Quick Filters, Smart Queries, SDK-filter remnants, Column Preset or Custom layout state, Details placement, app-icon visibility, date format or another presentation preference. Historical unrelated fields remain safe to retain in stored schema-v1 objects but are ignored during application; new preset captures omit the historical `view_preset` presentation field.

### RC3 final command ownership and result-filter reset

The final v1.99 menu ownership is semantic and permanent unless a later deliberate UX decision changes it. File owns source/input operations and raw phone-package-list export. Audit owns audit execution, targeted recheck, full refresh, execution-only Audit Presets, result export and Clear Results. View owns Column Preset/Custom, Customize View, Details placement and result filtering. Tools owns Advanced Settings, non-destructive Device History inspection and separately grouped destructive Data Maintenance. Help owns guides, methodology, update checks, diagnostics and About. Result exports exist under Audit only; the header export surface continues to use the same canonical handlers and synchronized availability.

`View > Clear All Filters` is a session presentation command. It clears search, multi-status chips, Quick Filter, the active Smart Query and Hide System Apps because that checkbox is an unpersisted result-visibility predicate. It deliberately does not change the separately persisted source-exclusion choice, results, sorting, saved Smart Queries, Audit Presets, caches/history, Column Preset/Custom state, Details placement, app icons, date format or audit/store settings. The retired SDK filter has no live predicate or persistence to clear. Presentation-status guards remain authoritative during active operations.

### Alternative Distribution Discovery

The Gate 4 implementation is an informational exact-package feature and is secondary to Google Play evidence. It never replaces or reinterprets Google Play availability/country evidence, installer source or criticality. Automatic checks run only after the canonical raw state `play_status == "not_found_in_checked_countries"`; available, regional fallback, transient and inconclusive Google Play states are ineligible. Gate 5 consumes only current conclusive Available provider evidence as a bounded recovery inside Maintenance Score while preserving all underlying states.

The deliberately small, non-pluggable `AlternativeDistributionProvider` protocol has two v1.99 implementations sharing one typed result/state model, one bounded executor, one independent cache and one presentation/export path:

- **F-Droid main repository** is built in, enabled by default and may be disabled in Advanced Settings. It uses only the official per-package API for active packages in the main repository, requires exact `packageName` equality and never queries the archive, full index, search, third-party repositories or APK URLs.
- **Aptoide** is Advanced/opt-in and disabled by default. It requires a user-supplied authorized `store_name` and Partner API key. It uses the documented `app/get` exact `package_name` request with `Authorization: ApiKey …`; the API key is never placed in the URL. The response's exact package and documented `file.vername`/`file.vercode` fields are used. No documented reliable public listing URL was established, so the UI does not invent one. A small `apps/get` request with the configured store and `limit=1` powers **Test connection** without depending on a permanent package.

The canonical states are Available, Not found, Inconclusive, Unsupported and Not checked. A provider must return its documented exact absence response to produce Not found; ambiguous, malformed, authentication, rate-limit, network and server failures remain Inconclusive. Availability means only that a provider returned an active listing for the exact Android package identifier. It does not establish safety, publisher authorization, binary equivalence, official status or Google Play equivalence.

Provider execution is a separate non-fatal phase after stable Google Play rows. One independent executor allows at most two total provider requests, with a 10-second request timeout and 20-second active-work phase budget. Pause prevents new submissions without consuming that phase budget, Resume continues pending work, and Stop prevents new submissions while preserving already completed evidence. The existing C2 progress widget switches to busy/indeterminate without moving; status text remains in the native status bar.

The independent `alt-v1` cache keys provider, exact normalized package ID and, for Aptoide, normalized non-secret store name. Available results live for 24 hours, Not found for 12 hours and Inconclusive for 15 minutes; Unsupported/Not checked are not cached. Force Full Refresh bypasses it. No provider history/change events are introduced.

Aptoide's protected config value uses `cryptography` AES-GCM with an HKDF-SHA256 key derived from application context, a local machine-identity digest and local user identity. The versioned `v1:` envelope contains random salt, nonce and authenticated ciphertext; no raw key, derived key or machine identifier is stored. Windows uses MachineGuid, Linux uses established machine-id files and macOS uses the platform UUID, with a weaker deterministic host/user/network-node fallback. This protects against casual config disclosure and trivial copied-config reuse, not a compromised account, reverse engineering, hardware attack or enterprise threat model. Decryption failure retains the ciphertext, disables/unavailable-gates Aptoide and asks for credential replacement without plaintext fallback.

Advanced Settings includes provider controls and a compact expandable availability/limitations panel for F-Droid, Aptoide, Samsung Galaxy Store, Huawei AppGallery, Amazon Appstore, APKMirror, APKPure and Uptodown. The latter six are explicitly not implemented because no approved general exact-catalogue API contract was established; the application does not scrape them.

Evidence appears only in the separate **Alternative distribution** subsection of Details/App Details and a conditional HTML section. Friendly Notes and the results-table columns/filters are unchanged. Versioned JSON is explicitly schema v2 with a deterministic `alternative_distribution.providers` collection; CSV remains unchanged. Secrets, protected envelopes and machine identifiers are excluded from exports and diagnostics. The common model intentionally has no speculative `provider_class`.

### Maintenance Score v1.99 update

Gate 5 is implemented locally. The user-facing name remains **Maintenance Score** and every app starts at 100. The algorithm uses raw, non-overlapping components:

- exact `play_status == "available"`: Google Play availability `0`;
- exact `play_status == "not_found_in_checked_countries"`: checked-market Google Play absence `-60`;
- `available_in_other_country` or `available_in_fallback_locale_only`: Store anomaly `-20`, never `-60`;
- any other/inconclusive Google Play state: `-15`, never stacked with the definitive `-60`;
- stale listing, more than 730 days: `-25`;
- aging listing, 366-730 days: `-15`;
- unknown/unusable listing age: `0` freshness penalty;
- legacy target SDK relative to the connected device: `-15`;
- aging target SDK relative to the connected device: `-10`;
- exact conclusive Installed-vs-Store `Different`: `-5`.

Only while the definitive checked-market absence `-60` component is active, current conclusive F-Droid main availability recovers `+10` and current conclusive Aptoide availability recovers `+5`. The recoveries are cumulative and provider IDs are deduplicated, so the current maximum is the natural sum `+15`: no verified alternative gives a net Store effect of `-60`, Aptoide `-55`, F-Droid `-50`, and both `-45`. Cached and live Available evidence score identically. Not found, Inconclusive, Unsupported and Not checked evidence provides no recovery. Unsupported/future providers have no score branch. Provider presence never raises a Google Play-available app's score.

The raw Google Play, provider, installer and classification values are never mutated. The score breakdown exposes the base Google Play component and each provider recovery separately in Details, App Details and HTML reports. Independent freshness, SDK and version components continue to compose; the final result is clamped to 0-100.

Audit history stores neither Maintenance Score nor provider evidence, so its baseline schema and comparison semantics remain unchanged. Versioned result exports retain the score calculated for that audit and are not recomputed retroactively. The compatibility-sensitive `health_score` field, Smart Query ID, settings key and serialized key remain unchanged in v1.99; the internal rename is deferred to v2.0 as a separate compatibility migration.

### Explicit UX decisions

- `QDockWidget` is rejected and not planned. Retain Auto/Right/Below/Hidden Details placement with narrow/wide/extra-wide internal responsiveness.
- A richer Dashboard/status overview is not part of v1.99 or required for the v2.0 core. Revisit it in later v2.x or v3.0 only when mature multi-source and longitudinal/history workflows justify it.
- Concrete bugs and polish found through real v1.9 use may be considered individually; they are not automatically in scope.

Multi-platform distribution, production signing and CLI/headless mode remain v2.0-or-later work.

### v2.0 Local APK Library pillar

Local APK Audit is deferred entirely to v2.0 rather than entering v1.99 with package-only identity. The v2.0 sequence is: parser/verifier spike; typed `LocalArtifact` plus SHA-256 artifact identity; package-deduplicated Store/provider fan-out; transient Local APK Audit; persistent Local APK Library.

The Library will scan one or more local APK directories recursively, parse package ID, app label, versionName/versionCode and useful SDK/icon/file/path metadata where practical, and compare local versions with Google Play and Alternative Distribution Discovery when appropriate. Reuse the existing classification, evidence, Details, filters, Smart Queries, export/reporting and service/domain architecture; do not duplicate existing CSV/export behavior. Portable/local workflow already exists and is not a new feature. ADB remains read-only unless a future explicit decision authorizes installation or other write behavior.

Later v2.x candidates include metadata-template mass rename, duplicate APK detection/management, outdated-APK cleanup with preview/safety, custom commands/integrations, Windows Explorer integration and other library-management improvements after the core is stable.

## Release-script maintenance

Do not delete `.github/scripts` files based on file count or size alone.

Before removing or consolidating a release script, verify:

- direct workflow references;
- imports from other release helpers;
- unit/regression tests;
- behaviour covered by the script;
- legal/release evidence boundaries.

Large legal scripts may be modularized later, but only with stable behaviour and test coverage.
