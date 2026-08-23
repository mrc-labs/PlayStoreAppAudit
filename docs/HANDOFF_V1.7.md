# Play Store App Audit v1.7 Chat Handoff

Status: v1.7.0 published and immutable. Active continuation moved to `docs/HANDOFF_V1.8.md`.

Last updated: 2026-08-22

## Purpose

This is the canonical human-readable handoff for the Play Store App Audit v1.7 cycle after the successful v1.6.0 publication and the main v1.7 feature implementation.

Read this file together with:

- `docs/PROJECT_STATUS.md` for the current shipped and development baseline;
- `docs/ROADMAP.md` for active priorities and later scope;
- `docs/PROJECT_DECISIONS.md` for durable engineering/release policy;
- `AGENTS.md` for repository-wide implementation rules;
- `docs/BUILDING.md` for build/release procedures;
- `docs/RELEASE_NOTES.md` and `CHANGELOG.md` for release history.

When this handoff conflicts with a newer canonical file, the newer canonical file wins. Published releases remain immutable.

## Repository and published baseline

Repository: `mrc-labs/PlayStoreAppAudit`

Latest published release: `v1.6.0`

Release class: unsigned Windows x64 Engineering Test Build (ETB).

Immutable v1.6.0 source SHA:

`246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`

Do not rebuild, retag, rewrite or replace that published commit, tag or release assets.

Published project-defined assets:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Published payload SHA-256 values:

- Windows x64 ZIP: `66e8c94bed69e53d16cf7784ab028089437078b8bc809c4385474ff83c0b55be`
- third-party source archive: `0f068f20ef14e0e53bd4869c66ae6542725a5c34e390cebf804279a8b28b1165`
- `SHA256SUMS.txt`: `0e7c7f6f1f290778139c47d929bb3ea0758022eb1199b9911c54893dd6dff8c5`

Successful v1.6 release evidence:

- post-merge Quality push run `32543925562`
- Windows x64 build run `32545213663`
- engineering release assembly run `32547942460`

The public files were downloaded again after publication and independently SHA-256 verified.

## Current technical baseline

- Canonical application version remains `1.6.0` until a deliberate v1.7 version/release freeze.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`.
- `Nuitka==4.1.3`.
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle.
- ADB remains read-only with respect to installed Android apps.
- Google Play scraping remains behind the canonical Store service boundary.
- Default/recommended concurrent Store workers: 16.
- Advanced worker range: 4 to 32.
- Store transport timeout: 25 seconds.
- Play Store icons remain experimental, opt-in and non-blocking for v1.7.
- v1.7 release target is Windows x64 only.
- v1.8 release target is also Windows x64 only.

Always verify the live `main` SHA from GitHub or a newly generated repository snapshot rather than assuming a SHA written in this static handoff.

## v1.7 implemented feature set

### Responsive Details Panel

Implemented through PR #84.

- Compact icon-based `Auto / Right / Below` placement control.
- Right remains the default behavior; Auto is opt-in.
- Placement hysteresis avoids resize oscillation.
- Content layout responds independently to available width.
- Wide layouts use logical columns and full-width notes; narrow layouts stack vertically.
- Action buttons adapt to available space.

### Store country and Store language semantics

Implemented through PR #85.

Automatic Store country precedence is:

1. explicit manual country override;
2. host/computer region;
3. Android locale region only as a late fallback when host region is unavailable;
4. final safe fallback `US`.

Automatic Store language is independent:

- connected phone: prefer active Android system language;
- file/list audit: use the principal language of the selected Store country when Auto is active;
- explicit manual language override remains authoritative;
- unknown language falls back safely to English.

Android locale region is not evidence of the real Google Play account country and must not be presented as such.

### Structured per-app Store diagnostics

Implemented through PR #86.

Structured Store evidence exposes request path, attempted countries/languages, scraper/HTML attempts, retry count, outcome and failure reason. Terminal not-found is distinct from transient/inconclusive failure. Details diagnostics are generated from structured evidence, never by parsing notes text.

### Installer/source classification and filtering

Implemented through PR #87 and PR #88.

Stable categories cover Google Play, alternative stores, sideloaded/package-installer installs, unknown/preinstalled and other installer sources. Raw installer package metadata is preserved separately from display labels. Built-in installer filters are available in the final MainWindow.

### SDK maintenance filters

Implemented through PR #88.

- session-level `targetSdk <= N` and `minSdk <= N` filters;
- Modern, Aging target, Legacy target and Unknown compatibility filtering;
- AND composition with other built-in filters;
- SDK values remain maintenance/compatibility metadata, not a security/trust score.

### Versioned JSON export

Implemented through PR #89 and extended in PR #91.

The `play-store-app-audit/results` schema version 1 supports all-results and visible-results export and preserves structured Store evidence, audit changes and smart re-audit policy context.

### Saved audit profiles

Implemented through PR #90.

Profiles preserve reusable audit execution context including source expectation, Store country/language, fallback countries, workers/cache settings, device metadata options, history comparison, system-app exclusion and view preset.

Profiles deliberately do not absorb search text, result filters, smart-query state, SDK filters or custom-column state.

### Conservative smart/incremental re-audit

Formalized through PR #91 around behavior already present in the application.

- Normal Run is the smart/incremental path.
- Only fresh exact-`available` results with a populated Store update date are eligible for cache reuse.
- Regional-only, fallback-only, removed, anomalous, incomplete and failed/inconclusive results run live.
- TTL remains a separate freshness gate.
- `Force full refresh (ignore cache)` remains the explicit bypass path.
- Targeted problematic-result rechecks remain available.

No second audit engine, background monitor or watchlist was introduced.

## v1.7 scope is closed

Do not add new product features to v1.7 unless the roadmap is deliberately reopened.

The installed signing-certificate fingerprint/change-detection idea has been removed from product scope, not deferred. The investigated `dumpsys package` signature/hash representation is not a SHA-256 certificate fingerprint, while a correct implementation would add disproportionate APK/certificate extraction complexity. Do not reintroduce it in v1.8 or later without a new explicit product decision.

The remaining v1.7 work is validation and release polish.

## Required v1.7 real-device validation

Before the v1.7 release freeze, test at least:

- host CH + Android `it-CH`;
- host CH + Android `de-CH`;
- host CH + Android `fr-CH`;
- host CH + Android `en-CH`;
- host region and Android locale region disagreeing;
- Android language present but region missing/unusable;
- file/list audit after phone scan to verify phone context does not leak;
- manual country override;
- manual language override;
- localized Store title/metadata across multiple languages in the same country;
- multi-country fallback where availability differs geographically;
- Details Panel Auto/Right/Below behavior across typical window widths;
- installer and SDK filters together;
- audit profile save/apply/delete and source-expectation advisory behavior;
- JSON all/visible export with structured evidence;
- normal smart Run, targeted recheck and Force full refresh;
- current experimental icon cache/CDN/offline/large-table behavior.

## v1.7 release profile

v1.7 is an unsigned Windows x64-only Engineering Test Build.

- Build only Windows x64 from one exact frozen `main` SHA.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke Windows production signing.
- Do not build Windows ARM64, Linux or macOS v1.7 release candidates.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- Preserve the exact-SHA validation and three-file ETB asset model.
- Do not run expensive release packaging until the v1.7 release profile and candidate SHA are deliberately frozen.

## v1.8 planned scope

v1.8 is also Windows x64 only.

The items previously left pending are now assigned to v1.8:

- graduate Play Store icons from experimental to normal supported behavior, with any final hardening indicated by v1.7 observations;
- saved filters / smart queries as reusable result-filter expressions, kept distinct from saved audit profiles;
- richer compact dashboard / summary designed to complement rather than duplicate details, changes and filters.

The UX for saved filters/smart queries should be defined deliberately before implementation rather than reviving an older CRUD design automatically.

## v2.0 and later

Keep out of normal v1.7 and v1.8 scope unless the roadmap is deliberately changed:

- full Windows/Linux/macOS x64/ARM64 production distribution;
- publicly trusted Windows signing;
- macOS Developer ID signing/notarization/stapling/Gatekeeper validation;
- CLI/headless auditing;
- LocalAPK-style local APK inventory/version comparison;
- possible advanced active app-management mode.

Active app-management actions would require an explicit change to the durable read-only ADB policy and stronger safety boundaries.

## Explicitly rejected / not planned

Do not reintroduce without a new product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country-set presets.

## Git and release rules that must survive the chat boundary

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Do not squash or rebase project PR history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile uses one exact frozen source SHA.
- Quality validation comes before recording a release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- v1.7 and v1.8 are Windows x64 only.
- Do not trigger expensive package workflows outside a deliberately chosen release profile.

## Starting or continuing a development chat

Use `scripts/export_chat_handoff.ps1` from a clean, up-to-date `main` checkout after the relevant housekeeping PR has merged.

The exporter should produce a timestamped handoff ZIP containing this handoff, canonical project/release documents and a generated `REPOSITORY_SNAPSHOT.md` with live branch/SHA/status, recent commits/tags and optional GitHub CLI metadata.

Attach that ZIP to the new chat and instruct the new chat to read the package completely before changing the repository.
