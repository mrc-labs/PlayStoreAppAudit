# Product Roadmap

Last updated: 2026-09-01

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. `PROJECT_STATUS.md` records current shipped state, `PROJECT_DECISIONS.md` records durable engineering/release policy, and this document assigns future product work.

## Planning rules

- Preserve the exact-SHA release model, read-only ADB policy and Store correctness semantics unless a deliberate decision changes them.
- Do not silently move deferred or rejected ideas into active scope.
- Published releases, tags and assets are immutable.
- Produce a UX audit/report before broad visual redesign work when the change is exploratory rather than already specified.
- Prefer small, verifiable PRs and lightweight CI; reserve Windows/Nuitka packaging for deliberate high-impact evidence or frozen release candidates.

## v1.8 published baseline

v1.8.0 was published on 2026-08-24 as an unsigned Windows x64 Engineering Test Build and is immutable.

- Frozen release source SHA: `ac328f0dffddb6b70fa7600f1291377376bc05d4`.
- GitHub Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.8.0
- GitHub Release title: `Play Store App Audit v1.8.0 (Win x64 Only)`.
- Public project-defined assets: Windows x64 ZIP, consolidated third-party source archive and `SHA256SUMS.txt`.
- Canonical Quality/build/assembler runs: `32682693020`, `32683271942`, `32684933669`.
- Release assets were re-downloaded and independently verified after publication; exact sizes and hashes are recorded in `PROJECT_STATUS.md`, `RELEASE_NOTES.md` and `HANDOFF_V1.8.md`.
- Post-release Actions housekeeping run `32727364125` completed under the unchanged generational retention policy.

The v1.8 product and stabilization scope shipped through PRs `#105`-`#113`; release preparation shipped through PR `#114`. The release includes:

- action availability and canonical export consistency across menus and controls;
- naming, tooltip, density and targeted iconography polish;
- the compact **Details** control and **View > Details Panel** menu with Auto, Right, Below and Hidden modes;
- separate Display Settings and a clearer four-category Advanced Settings hierarchy;
- Play Store icon cache/CDN/offline/large-table hardening;
- saved one-level All/Any Smart Queries that remain result-only and separate from Quick Filters and Audit Profiles;
- the informational product tagline in repository description, README and About;
- final running-operation and status-message consistency fixes.

The approved Smart Queries contract remains documented in [`SMART_QUERIES_UX_REVIEW.md`](SMART_QUERIES_UX_REVIEW.md). Nested groups, scripting, regular expressions, import/export, automation and audit-setting behavior were not introduced.

## v1.9 published baseline

v1.9.0 was published on 2026-08-25 as an unsigned Windows x64 Engineering Test Build and is immutable.

- Frozen release source SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`.
- GitHub Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.9.0
- Canonical Quality/build/assembler runs: `32797795985`, `32798334950`, `32801220807`.
- The exact three public assets were re-downloaded and independently verified after publication; sizes and hashes are recorded in `PROJECT_STATUS.md`, `RELEASE_NOTES.md` and `HANDOFF_V1.9.md`.
- Post-release Actions housekeeping run `32805211585` passed under the unchanged generational retention policy.

The architectural/UX review's first grouped presentation-consistency scope merged through PR `#116`:

- one friendly Notes presentation shared by the table, Details Panel and user-facing HTML report, plus a complete Notes tooltip, while raw Notes remain unchanged in CSV, versioned JSON, diagnostics and Smart Queries;
- **Maintenance Score** as the user-facing name, with `health_score`, persisted Smart Query field IDs and serialized compatibility keys unchanged and no scoring-algorithm change;
- foreground-only table highlights for Installed-vs-Store **Different**, Android Compatibility **Aging target** and **Legacy target**, reusing the existing warning palette;
- About hierarchy of product title, tagline subtitle and secondary version;
- one project-owned, palette-aware QPainter icon family for Choose File, Scan Phone and Export Results, with no icon-library or theme dependency;
- a fix for Display Settings changes with populated results, including safe presentation refresh, Custom preset/check-state synchronization and preserved column widths, selection and Details state across restart.

The evidence-gated Details Panel prototype merged through PR `#117`. It adds an automatic extra-wide state at 1180 px of usable scroll-viewport width and exits that state below 1080 px, while retaining the established 760/680 px narrow/wide hysteresis. Extra-wide uses three related content groups—Store/Notes, Installed/Changes and Store evidence/diagnostics—with the horizontal action row below. It requires no new preference and does not change outer Details placement.

The final evidence-gated v1.9 UX implementation merged through PR `#118`: a complementary bottom `QStatusBar` that relocates the same canonical operational label and progress widget rather than adding a second status model. Status expands on the left and the 200 px progress bar appears on the right only during active work. The main row contains Run, Export Results and Clear Results only. Existing source/device context is intentionally not duplicated, the native size grip remains enabled, and the status bar adds no preference or persistence state and does not replace the Details Panel.

PRs `#116`, `#117` and `#118` are merged, accepted and published in v1.9.0. Release preparation merged through PR `#119`.

A global Fluent redesign, an icon library without demonstrated need, unnecessary broad architecture/type refactors and a full internal `health_score` rename were rejected for v1.9. Continue using Qt Widgets with platform/default Windows styling.

### v1.9 release evidence and cost outcome

- Normal code PRs may run Ruff, pytest, compileall, the lightweight Qt smoke test and targeted static checks.
- No Windows/Nuitka packaging was dispatched for documentation, product identity, naming, icon polish or housekeeping changes.
- Native Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 are manual or limited to high-impact UI milestones.
- The one canonical final Windows x64 package and one engineering assembler run were produced only after the exact release SHA was frozen.
- VS Code/Pylance Standard type checking is useful local evidence for touched code, not a repository build setting or authorization for a broad typing refactor.

## v1.99 pre-v2.0 closure

v1.99 is feature complete and likely the final Windows x64-only release before v2.0. Stabilization must preserve the approved scope while preparing the mandatory packaged Windows x64 acceptance candidate. The application/source version is now frozen at `1.99.0` for the release-candidate cycle.

### Cooperative Stop/Cancel

The real Run -> Pause/Resume -> Stop/Cancel lifecycle merged through PR `#122` at `c5322d42a7ebdd0f7e61fd1c25b69828d8535e25`. Preserve its identified cancellation boundaries across Store checks, regional checks, scheduling and finalization.

- Stop scheduling new work immediately and propagate a cooperative cancellation request through every queue.
- Let in-flight operations return safely or reach existing timeout boundaries; never use `QThread.terminate()` or forced termination.
- Preserve completed valid results and valid cache entries.
- Mark the audit cancelled/incomplete, do not promote it to the completed history/previous-audit baseline, and return to a reusable idle state.
- Verify that another audit can start normally after cancellation.

### Native-Windows main-action layout review

This product gate is complete. Native A/B/C comparison covered:

- Prototype A: Run/Pause/Stop, Export and Clear in the status bar.
- Prototype B: a compact upper action toolbar/command strip above results.
- Prototype C: an integrated results/header-area command layout that remains clear and uncluttered.

The integrated results-header direction won, followed by a focused C0/C1/C2 comparison of progress placement. The accepted **C2** order is Run/Pause/Resume, Stop, progress, Export Results and Clear Results. Run and Stop stay grouped; the canonical progress widget remains visibly reserved at idle and through every lifecycle state, expands between 120 and 320 px, and returns to a neutral empty state after completion. Existing action availability remains authoritative.

### Details selector and status-bar presentation

The review retained the existing Auto/Right/Below/Hidden Details selector in the second results header row alongside status chips, Hide System Apps and search. It continues to share one state with `View > Details Panel`; no mirrored state was added. The native status bar retains operational text and its size grip, while progress now occupies the stable inline C2 position in the first results header row. RC1 acceptance added 16 logical px left and 12 logical px right contents margins to the operational text label only; the status bar remains edge-to-edge and C2 does not move.

### Semantic warning typography

This gate is complete. **Different** and **Aging target** reuse the status palette's dark-yellow foreground with Qt DemiBold weight 600; **Legacy target** reuses dark orange with DemiBold weight 600; **Modern** remains Regular weight 400 and Status remains Bold weight 700. The RC1 correction from 500 to 600 reflects native Segoe UI/Qt evidence that Medium was visually indistinguishable from regular. The shared presentation mapping is used by the results table, Details Panel, context Details dialog and HTML report. Qt continues to manage selection backgrounds, while the semantic foregrounds remain readable without selection-specific colours; the native disabled-text role remains unchanged. Normal/Modern/Match/Unknown values receive no warning styling, and machine-readable exports/data are unchanged.

### RC3 local-only stabilization checkpoints

Phase A is accepted with semantic table widths, selected wrapped headers, saved/manual width restoration, compact native status-bar presentation and removal of the redundant Device Summary UI.

Phase B1 is complete and deliberately limited to column-layout persistence. `View > Column Preset` contains immutable Basic, Device and Technical layouts plus a persistent Custom layout created by manual visibility, order or width changes. Custom remains available across built-in switching, refresh/audit work and restart, and is disabled before a real or conservatively migrated layout exists. `Customize View…` retains the existing display-preference architecture: column changes update Custom, while app icons, date format and equivalent preferences remain global.

Phase B2 is complete locally. The dedicated SDK Maintenance Filter and its clear action are removed; the former filter was session-only and had no persistence keys, and the runtime hook is gone so legacy-looking settings cannot activate invisible SDK filtering after restart. Target SDK, Min SDK and Android Compatibility data remain unchanged, with Smart Queries as the advanced filtering mechanism. User-facing Audit Profiles are now **Audit Presets** while schema v1 and the internal `audit_profiles` key remain compatible. Presets apply audit-execution state only: historical presentation/filter fields may remain in stored objects but are ignored, and current search, status chips, Quick Filters, Smart Queries, Column Preset/Custom layout, Details placement, app-icon setting and date format remain untouched.

The final RC3 local source gate is complete. The top-level `File / Audit / View / Tools / Help` menus now follow command semantics: Audit owns execution, Audit Presets, all/visible result exports and Clear Results; File retains sources and raw phone-package export; View owns presentation and result filters; Tools groups Device Snapshots and Device Inventory Changes under Device History while destructive clears remain under Data Maintenance. `View > Clear All Filters` resets all session result-visibility predicates, including Hide System Apps, without changing source exclusion, current/saved data, sorting or layout/settings state. The full source gate passed on Python 3.13 and 3.14. RC3 packaging remains a later, separately authorized step.

RC4 subsequently built and packaged successfully, with the pristine-Custom packaged regression passing, but acceptance failed for one measured density issue: short-value default columns were materially wider than necessary. RC5 applied only the narrow density correction, then passed automated and user acceptance and became the accepted rollback/reference candidate.

### Scan Phone lifecycle reopening before RC6

v1.99 was explicitly reopened after RC5 acceptance for a three-phase Scan Phone lifecycle improvement. Phase A is complete locally: one internal immutable `ScanSession` now owns each completed phone-source capture and carries its captured timestamp, session/source identity, hashed/masked device association, existing summary and locale, package list/counts and system scope. The session is window/process-local, is selected only on complete current-worker success, is invalidated on file-source transitions and is protected by request-generation guards against stale worker success/failure.

Phase A reduces the normal third-party Scan Phone command sequence from the observed nine launches to four: one executable/version discovery, one authorization/device-list probe, one shared `getprop`, and one aggregate `pm list packages -3`. It reuses the device-list serial for hashed/masked identity and the shared properties for summary plus locale; the read-only Settings locale fallback runs only when the properties lack a usable locale. All-package scope still performs its required system-package classification command.

On the same connected 329-package phone, five measured end-to-end UI scans after warm-up produced min/median/mean/max `0.469 / 0.532 / 0.541 / 0.663` seconds with four launches each, versus the accepted `0.673 / 0.687 / 0.691 / 0.717` second, nine-launch baseline. Phase A intentionally adds no compact or full per-package metadata, changes no Device Inventory semantics, and does not alter Run enrichment, exports, caches, providers or scoring. RC6 is not built in Phase A.

### Alternative Distribution Discovery

Gate 4 is implemented locally with two secondary exact-package providers behind a small non-pluggable common protocol:

- F-Droid's active main repository is built in and enabled by default, using only its official per-package API.
- Aptoide is Advanced/opt-in and disabled by default; it requires an authorized store identifier and Partner API key, uses the documented exact `app/get` contract and provides a minimal authenticated connection test.

Automatic provider work is strictly eligible only for raw `play_status == "not_found_in_checked_countries"`. It runs after stable Google Play rows with one two-worker executor, 10-second request timeouts, a 20-second active-work phase budget and cooperative Pause/Resume/Stop; intentionally paused time does not consume that budget. Failures are non-fatal. Separate state-sensitive cache TTLs are 24 hours Available, 12 hours Not found and 15 minutes Inconclusive; Force Full Refresh bypasses them.

The provider API key is stored only as a versioned machine/user-bound AES-GCM/HKDF-SHA256 protected envelope using the single pinned `cryptography` dependency. This is local config-copy/casual-disclosure protection, not OS/hardware or compromised-account security. Details/App Details, conditional HTML and JSON schema v2 expose neutral provider evidence; the table, Friendly Notes, CSV, history, installer source and Google Play state remain unchanged. Gate 5 subsequently connected only conclusive Available evidence to the bounded Maintenance Score recovery described below.

The Advanced Settings limitations panel records Samsung Galaxy Store, Huawei AppGallery, Amazon Appstore, APKMirror, APKPure and Uptodown as not supported because a suitable authorized general exact-catalogue API contract was not established. No HTML scraping, fuzzy association, APK download or plugin framework is introduced.

### Maintenance Score algorithm update

Gate 5 is complete locally. Keep the user-facing **Maintenance Score** name and the compatibility-sensitive `health_score` identifier. Every row starts at 100 and receives raw, independent components:

- definitive checked-market Google Play absence, exact `not_found_in_checked_countries`: `-60`
- F-Droid main Available recovery, only while that `-60` is active: `+10`
- Aptoide Available recovery, only while that `-60` is active: `+5`
- Store anomaly (`available_in_other_country` or `available_in_fallback_locale_only`): `-20`
- Other/inconclusive Google Play state: `-15`
- stale listing, more than 730 days: `-25`
- aging listing, 366-730 days: `-15`
- legacy target SDK relative to device: `-15`
- aging target SDK relative to device: `-10`
- exact Installed-vs-Store `Different`: `-5`

F-Droid and Aptoide recovery is cumulative and deduplicated; the present mapping therefore recovers at most +15. Not found, Inconclusive, Unsupported and Not checked states recover nothing. Live and valid cached Available evidence are equivalent. No recovery applies when Google Play is available, and unsupported future providers have no scoring behavior. Regional and inconclusive Play states never receive the definitive `-60`; unknown listing age adds no freshness penalty. Independent components compose and the final score is clamped to 0-100.

Details, App Details and HTML reports expose the score components without mutating raw evidence. History does not persist scores/provider evidence, while versioned results preserve the score computed at export time. The internal `health_score` -> `maintenance_score` migration is deferred to v2.0 and will require explicit Smart Query, settings, serialized-data, backward-compatibility and migration coverage.

### Deferred and rejected UI work

- A richer Dashboard/status overview is not part of v1.99 and is not required for the v2.0 core. Revisit it in later v2.x or v3.0 only when multiple mature sources and longitudinal/history workflows justify a distinct surface.
- `QDockWidget` is rejected/not planned. Do not prototype it. Keep Auto/Right/Below/Hidden plus narrow/wide/extra-wide Details responsiveness.
- Review concrete bugs, workflow issues and polish found through real v1.9 use individually rather than accepting all observations automatically.

### Mandatory user-tested RC gate

v1.99 deliberately requires a packaged Windows x64 acceptance cycle. RC4 built and packaged successfully but failed acceptance only on the measured default-column-density issue. The source remains version `1.99.0`; the local density correction is an RC5 source checkpoint, not an RC5 package:

1. reach feature-complete candidate state;
2. freeze an RC candidate and build a real Windows x64 package;
3. provide it for thorough user acceptance testing;
4. merge corrective PRs if needed;
5. if source changed, do not treat that RC SHA/artifact as final;
6. freeze a new final exact `main` SHA only after user acceptance;
7. run final Quality, build the canonical final Windows x64 package, assemble and publish normally.

Do not create a public RC tag and never publish an earlier RC after source changes.

## v2.0 and later

### First planned return to multi-platform distribution

v2.0 is the first planned release after v1.3 to return to the full six prebuilt platform/architecture targets:

- Windows x64 and ARM64;
- Linux x64 and ARM64;
- macOS x64 and ARM64.

Production-trust signing is the ideal target for Windows and macOS, including notarization/stapling on macOS, but it must not be promised until eligibility, credentials, provider cost and complete end-to-end validation are proven. If signing is not feasible, make a new explicit release decision rather than silently weakening verification.

The v2.0 production profile continues to require one frozen SHA, signed/native post-sign validation where applicable, strict legal/source evidence and the eight-file multi-platform asset set documented in `BUILDING.md`.

### CLI/headless work

CLI/headless support remains v2.0-or-later scope. It must reuse service/domain boundaries rather than driving the Qt UI or duplicating Store/ADB logic.

### Local APK Library / modern LocalAPK successor core

A Local APK Library is a major v2.0 product pillar. The transient Local APK Audit is also deferred entirely to v2.0 because correct support requires artifact-aware identity and a vetted untrusted-APK parser/verifier boundary.

Recommended technical sequence:

1. parser/verifier spike with malformed-input, packaging and legal validation;
2. typed `LocalArtifact` model with SHA-256 artifact identity;
3. package-deduplicated Store/provider lookup and artifact fan-out;
4. transient Local APK Audit input source;
5. persistent Local APK Library.

Initial Library scope:

- scan one or more local APK directories recursively;
- parse package ID, app label, versionName/versionCode and useful SDK/icon/file/path metadata where practical;
- compare local APK versions with Google Play and, when appropriate, Alternative Distribution Discovery;
- reuse existing classification, evidence, Details, filters, Smart Queries, export/reporting and service/domain architecture.

Do not duplicate existing CSV/export capabilities. Portable mode is not a new feature; the application already supports standalone/local workflows. ADB remains read-only unless a future explicit decision authorizes install/write behavior.

### Later v2.x Local APK backlog

After the core is stable, consider metadata-template mass rename, duplicate APK detection/management, outdated-APK cleanup with preview/safety, custom commands/integrations, Windows Explorer integration and other library-management improvements. These are later 2.x candidates, not mandatory v2.0 scope.

## Explicitly removed / not planned

Do not reintroduce without a new product decision:

- installed signing-certificate fingerprint/change detection;
- broad automatic alternative-source association or fuzzy-title equivalence (distinct from approved exact-package Alternative Distribution Discovery);
- audit watchlists/background monitoring;
- predefined country presets such as DACH/EU/worldwide.
- `QDockWidget` for the Details Panel.

## Release and Git rules

- `main` is the only permanent branch.
- Use short-lived branches and normal merge commits; no squash/rebase project history.
- Published releases are immutable.
- Before every local pull, run `git status --short`; if dirty, stop. Never auto-stash/reset/discard/clean user work.
- Every release uses one exact frozen SHA and tags only after artifact validation.
- Tag pushes do not rebuild binaries.
- Keep strict legal/source validation fail-closed.
- v1.9 remains a Windows x64 ETB; do not add Windows ARM64/Linux/macOS release packaging without an explicit roadmap/decision change.
- Windows x64 ETB GitHub Release titles use `(Win x64 Only)`; body headings identify `Engineering Test Build - Windows x64 Only`.
- Finish every release through `RELEASE_CLOSURE.md`, including post-release documentation and safe local VS Code synchronization.

## Continuation and handoff generation

The active human-readable handoff is `HANDOFF_V1.99.md`; `HANDOFF_V1.9.md` is the completed v1.9 closure context. Generate continuation ZIPs only from a clean, synchronized local `main` checkout after documentation is merged, using `../scripts/export_chat_handoff.ps1`; the script selects the newest `docs/HANDOFF_V*.md` numerically and includes a freshly generated `REPOSITORY_SNAPSHOT.md`.
