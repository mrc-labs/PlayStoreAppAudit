# Product Roadmap

Last updated: 2026-08-22

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. It records completed active-cycle scope, remaining work, deferred ideas, explicitly rejected ideas and open product questions so that future work does not need to be reconstructed from chat history.

`PROJECT_STATUS.md` records the current shipped state and active development baseline. `PROJECT_DECISIONS.md` records durable engineering/release policy. Release assignments below are planning intent until a release profile is deliberately frozen.

## Planning rules

- Preserve the exact-SHA release model, read-only ADB policy and Store correctness semantics from `PROJECT_DECISIONS.md` unless a deliberate policy change is made there.
- Keep implementation detail in issues/PRs and current-state evidence in `PROJECT_STATUS.md`.
- Do not silently move deferred or rejected ideas into active scope.
- Do not rebuild, retag or replace published release artifacts.

## v1.6 published baseline

v1.6.0 is published and immutable as an unsigned Windows x64 Engineering Test Build.

Immutable release source SHA:

`246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`

Published project-defined assets:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`;
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`;
- `SHA256SUMS.txt`.

Release evidence and exact checksums remain recorded in `PROJECT_STATUS.md` and `HANDOFF_V1.7.md`.

## v1.7 implementation status

The planned v1.7 product work is implemented on `main`. No v1.7 release SHA or package has been frozen yet.

The v1.7 distribution target is Windows x64 only. Do not build or publish Windows ARM64, Linux or macOS v1.7 release candidates.

### Completed: responsive Details Panel

Implemented through PR #84.

- Compact icon-based `Auto / Right / Below` placement control.
- Right remains the existing/default behavior; Auto is opt-in.
- Placement and content layout are independent.
- Width-aware content reflow uses narrow/wide layouts with hysteresis.
- Wide mode avoids a rigid equal-height grid and makes materially better use of horizontal space.

### Completed: Store country vs Store language semantics

Implemented through PR #85.

Automatic Store country resolution is now:

1. explicit manual country override;
2. host/computer region;
3. Android locale region only as a late fallback when host region is unavailable;
4. final safe fallback `US`.

Automatic Store language remains independent:

- connected phone: prefer active Android system language;
- file/list audit: use the principal language of the Store country when Auto is active;
- explicit manual language override remains authoritative;
- unknown language falls back safely to English.

Android locale region is not evidence of the real Google Play account country and must not be presented as such.

Real-device validation remains required before v1.7 release freeze.

### Completed: per-app Store diagnostics

Implemented through PR #86.

Structured evidence now exposes attempted countries/languages, request path, scraper/HTML attempts, retry count, outcome and failure reason. Terminal not-found is distinct from transient/inconclusive failure, and the Details Panel shows diagnostics only when useful.

### Completed: installer/source classification and filtering

Implemented through PR #87 and PR #88.

- Stable categories for Google Play, alternative stores, sideloaded/package-installer installs, unknown/preinstalled and other installer sources.
- Raw installer package preserved separately from the display label.
- Exact legacy compatibility only, avoiding broad substring guesses.
- Built-in installer filters are reachable from the final MainWindow.

### Completed: target/min SDK maintenance filtering

Implemented through PR #88.

- Session-level `targetSdk <= N` and `minSdk <= N` filters.
- Modern/Aging target/Legacy target/Unknown compatibility filtering.
- AND composition with other built-in filters.
- SDK values remain maintenance/compatibility metadata, not a malware/security/trust score.

### Completed: saved audit profiles

Implemented through PR #90.

Profiles preserve reusable audit execution context including source expectation, Store country/language, fallback countries, workers/cache settings, device metadata options, history comparison, system-app exclusion and view preset.

Source expectation is advisory and never automatically starts ADB or opens a file. Saved audit profiles deliberately do not absorb search/filter/smart-query state.

### Completed: conservative incremental/smart re-audit

Consolidated through PR #91 around behavior already present in the app.

- Normal Run is the smart/incremental path.
- Only fresh exact-`available` results with a populated Store update date are eligible for cache reuse.
- Regional-only, fallback-only, removed, anomalous, incomplete and failed/inconclusive results run live.
- TTL is a separate freshness gate.
- `Force full refresh (ignore cache)` remains the explicit bypass path.
- Targeted problematic-result rechecks remain available.
- The active smart-re-audit policy is included in versioned JSON export context.

No second audit engine, background monitor or watchlist was introduced.

### Completed: versioned JSON export

Implemented through PR #89, with smart-policy context added in PR #91.

The `play-store-app-audit/results` versioned envelope preserves structured result/evidence/change data for downstream automation and supports both all-results and visible-results export.

### Removed from product scope: installed signing-certificate fingerprint/change detection

Do not implement installed signing-certificate fingerprint capture or change detection as a planned Play Store App Audit feature.

The previously investigated `dumpsys package` signature/hash representation is not a SHA-256 certificate fingerprint, and a correct implementation would require disproportionate APK/certificate extraction complexity for the current product. This item is removed rather than deferred.

## v1.7 remaining release-readiness work

Before freezing v1.7, prioritize validation and polish rather than feature expansion:

- real-device validation of country/language resolution, including host/phone region disagreement and phone-to-file transitions;
- observe the current experimental icon path for cache growth, CDN failures, stale behavior, large-table responsiveness and offline/cache reuse so the evidence is available for the v1.8 graduation decision;
- review final help/status wording after real-device testing;
- run normal Quality/UI gates on the final candidate before recording any release SHA;
- do not run expensive release packaging until a v1.7 release profile is deliberately frozen;
- build/package only Windows x64 for the v1.7 release profile.

## v1.8 planned scope

v1.8 is the next feature/polish cycle after v1.7 and is also Windows x64 only. Do not build or publish Windows ARM64, Linux or macOS v1.8 release candidates.

### Graduate Play Store icons from experimental

The intended v1.8 outcome is to make Store icons a normal supported feature rather than experimental, assuming the v1.7 observation period does not reveal a blocking reliability or performance issue.

The v1.8 work should include any final cache/CDN/offline/large-table hardening needed to remove the experimental label and opt-in framing cleanly.

### Saved filters / smart queries

Move the previously uncommitted saved-filter/smart-query concept into v1.8 scope.

This means saving reusable result-filter expressions rather than audit configurations. Examples include:

- `Removed from Play AND still installed`
- `Stale AND sideloaded`
- `Target SDK below threshold`
- `Installed/Store version differs`

Saved queries should reapply to any compatible result set and remain distinct from saved audit profiles, which control how an audit is run. Define the UX deliberately before implementation rather than reviving the older CRUD UI implicitly.

### Dashboard / compact summary

Move the richer compact dashboard/summary candidate into v1.8 scope.

It should be designed against the mature details panel, change overview, filters and smart queries so that it adds useful at-a-glance information rather than duplicating existing UI.

## v2.0 and later

### Production distribution milestone

No earlier than v2.0, reconsider the full production release profile:

- Windows x64/ARM64;
- Linux x64/ARM64;
- macOS x64/ARM64;
- publicly trusted Windows signing;
- Developer ID signing/notarization/stapling/Gatekeeper verification on macOS;
- full multi-platform exact-SHA assembly and release validation.

The source workflows already implementing much of this architecture should remain maintained but do not need to be exercised as a normal v1.7 or v1.8 release cost.

### CLI/headless mode

Keep CLI/headless auditing in mind for v2.0 or later, not before. A future CLI could expose the existing service layer for scheduled tasks, CI or scripting without changing the desktop application into a daemon.

### Local APK audit concept

Explore a LocalAPK-inspired capability: scan APK files stored locally and compare their local version/build information with online/current information to identify which local APK files are up to date.

Before implementation, decide whether this belongs inside Play Store App Audit as a separate source/workflow or in a companion application that reuses shared services.

### Advanced app-management concept

Active operations such as uninstall, disable, permission changes, clear data, force stop or APK installation are not planned for the normal near-term product. They conflict with the durable read-only ADB policy and require a deliberate `PROJECT_DECISIONS.md` change before consideration.

## Explicitly not planned

Unless a deliberate product decision reopens them, the following remain rejected:

- installed signing-certificate fingerprint capture/change detection;
- automatically associating unavailable Play apps with GitHub/F-Droid/developer-site alternative sources;
- audit watchlists/background monitoring;
- predefined country-set presets such as DACH/EU/worldwide.

## Handoff requirement

Before starting a new release-cycle development chat, create a handoff package so the next chat can continue from repository evidence rather than reconstructing decisions from conversation history.

For v1.7, the canonical human-readable handoff remains `HANDOFF_V1.7.md`. The reusable exporter is `../scripts/export_chat_handoff.ps1`, and it must fail closed when the working tree is dirty.
