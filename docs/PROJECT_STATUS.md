# Project Status

Last updated: 2026-08-22

## Published release

- Latest published version: `v1.6.0`
- Immutable release commit: `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.6.0 (ETB Win x64)`
- Public project-defined assets: exactly 3

Published v1.6.0 is immutable. Do not rebuild, retag, rewrite or replace its published commit, tag or assets. Earlier published releases remain immutable as well.

## v1.6.0 release evidence

The v1.6.0 release was built, assembled and published from one exact frozen `main` SHA: `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`.

Release gates and evidence:

- post-merge Quality push run: `32543925562`, successful on Python 3.13 and 3.14;
- Windows x64 build run: `32545213663`, successful on the same frozen SHA;
- engineering release assembly run: `32547942460`, successful on the same frozen SHA;
- final public release asset set: exactly three project-defined files;
- annotated `v1.6.0` tag peels to the frozen SHA;
- published assets were downloaded again after release and independently SHA-256 verified against `SHA256SUMS.txt`.

Published project-defined assets and SHA-256 values:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`: `66e8c94bed69e53d16cf7784ab028089437078b8bc809c4385474ff83c0b55be`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`: `0f068f20ef14e0e53bd4869c66ae6542725a5c34e390cebf804279a8b28b1165`
- `SHA256SUMS.txt`: `0e7c7f6f1f290778139c47d929bb3ea0758022eb1199b9911c54893dd6dff8c5`

## Current development baseline

- Canonical application version remains `1.6.0` until a later release-profile/version freeze deliberately changes it.
- Active planning/development cycle: `v1.7`.
- Baseline entering the v1.7/v1.8 scope-policy update: `fefd2c766b2fa6cf034813e7c0adbc67779e4bcf`.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1.
- Nuitka: 4.1.3.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB behaviour remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers remain 16.
- Store transport timeout remains 25 seconds.
- Play Store icons remain experimental, opt-in and non-blocking throughout v1.7.
- v1.7 release target: Windows x64 only.
- v1.8 release target: Windows x64 only.

No v1.7 binary release has been frozen or built by the work recorded below.

## v1.7 implemented on main

### Responsive details panel

- Replaced the prominent Right/Below selector with a compact icon-based `Auto / Right / Below` control.
- Preserved Right as the existing/default behavior; Auto is opt-in.
- Added placement hysteresis so Auto does not oscillate around one resize threshold.
- Made the details content independently responsive: narrow layouts flow vertically, while wide layouts use balanced logical columns and full-width notes.
- Made details action buttons adapt between stacked and horizontal layouts.

Implemented through PR #84.

### Store country and language semantics

- Store country and Store language are now resolved independently.
- Automatic country precedence is manual override, host/computer region, Android locale region only as a late fallback, then `US`.
- Android locale region is explicitly not presented as Google Play account country.
- Connected-phone Auto language follows the active Android system language when available.
- File/list audits do not inherit stale phone locale context.
- Manual Store country and Store language overrides remain authoritative.

Implemented through PR #85.

### Per-app Store diagnostics

- Store evidence now carries structured request path, scraper/HTML attempts, retry count, outcome and failure reason.
- Terminal not-found is distinguished from transient/inconclusive failure.
- The Details Panel shows a Store diagnostics section only when the row benefits from it.
- Diagnostics are generated from structured evidence rather than parsing notes text.

Implemented through PR #86.

### Installer/source classification and filtering

- Device metadata preserves the raw installer package separately from its display label.
- Stable installer categories distinguish Google Play, alternative stores, sideloaded/package-installer installs, unknown/preinstalled and other installers.
- Legacy data compatibility recognizes only exact previously emitted formats rather than arbitrary substrings.
- Built-in installer filters are reachable from the final MainWindow filter menu.

Implemented through PR #87 and the filter-menu restoration in PR #88.

### SDK maintenance filters

- Added session-level `targetSdk <= N` and `minSdk <= N` filters.
- Added Modern, Aging target, Legacy target and Unknown compatibility-state filtering.
- SDK filters combine with the other built-in filters using AND semantics.
- SDK metadata is explicitly presented as compatibility/maintenance context, not a malware, security or trust score.

Implemented through PR #88.

### Versioned JSON export

- Added machine-readable `play-store-app-audit/results` schema version 1.
- JSON exports include application version, UTC generation timestamp, scope, context and full structured result rows.
- Structured Store evidence and structured audit-change records are preserved rather than flattened to display text.
- Both all-results and visible-results JSON export are available under File > Export Results.
- Local source file paths are deliberately omitted from the export context.

Implemented through PR #89.

### Saved audit profiles

- Added versioned saved audit profiles under Tools > Audit profiles.
- Profiles preserve Store country/language, fallback countries, workers/cache settings, device-metadata options, history comparison, system-app exclusion, source expectation and view preset.
- A saved country becomes an explicit country override when the profile is applied, making the profile reproducible across hosts.
- Source expectation is advisory: applying a phone profile does not automatically start ADB, and applying a file profile does not open a file automatically.
- Search text, result-filter presets, SDK filters and custom-column state are intentionally not part of audit profiles.

Implemented through PR #90.

### Conservative smart re-audit policy

- Normal Run remains the smart/incremental path rather than introducing a second audit engine.
- Only fresh exact-`available` results with a populated Store update date are eligible for cache reuse.
- Regional-only, fallback-only, removed, anomalous, incomplete and failed/inconclusive checks remain live.
- TTL remains a separate freshness gate.
- Tools > Force full refresh explicitly bypasses cache for the run.
- Existing targeted problematic-result rechecks remain available.
- Versioned JSON export now describes the active smart re-audit/cache policy in machine-readable context.

Implemented through PR #91.

## v1.7 remaining release validation

The v1.7 feature scope is closed. Remaining work is validation and release polish, not feature expansion.

### Real-device validation

The v1.7 country/language model should receive deliberate real-device validation before release freeze, especially:

- host CH with Android `it-CH`, `de-CH`, `fr-CH` and `en-CH`;
- host and Android region disagreement;
- Android language with no usable region;
- phone audit followed by file audit, verifying no phone-context leakage;
- manual country and language overrides;
- Store localization and multi-country fallback behavior.

### Experimental icons during v1.7

Continue observing cache growth, CDN failures, stale behavior, large-table responsiveness and offline/cache reuse during v1.7 validation. Icons remain opt-in and non-blocking for v1.7.

The planned v1.8 direction is to graduate icons from experimental to a normal supported feature, with any final hardening required by v1.7 observations.

## Removed feature

Installed signing-certificate fingerprint capture/change detection is no longer planned for Play Store App Audit.

The investigated `dumpsys package` signature/hash representation is not a SHA-256 certificate fingerprint, while a correct implementation would add disproportionate APK/certificate extraction complexity. Do not carry this item forward into v1.8 or later roadmaps unless a new product decision explicitly reopens it.

## v1.8 planned carry-forward

Items previously left pending are now assigned to v1.8 rather than remaining indefinite:

- graduate Play Store icons from experimental to normal supported behavior;
- saved filters / smart queries, with UX defined separately from saved audit profiles;
- richer compact dashboard / summary, designed to complement rather than duplicate details, changes and filters.

v1.8 remains Windows x64 only.

## Durable release and repository invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Do not squash or rebase project PR history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- Quality validation comes before recording a release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- v1.7 and v1.8 are Windows x64 only.
- Production signing and the full six-platform production release are not planned before v2.0 unless the roadmap is deliberately changed.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `HANDOFF_V1.7.md` for durable policy, planning and handoff context.
