# Product Roadmap

Last updated: 2026-08-22

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. It records planned release scope, deferred ideas, explicitly rejected ideas and open product questions so that future work does not need to be reconstructed from chat history.

`PROJECT_STATUS.md` records the current shipped state and active development baseline. `PROJECT_DECISIONS.md` records durable engineering/release policy. This roadmap may contain tentative product direction and release targets, provided tentative items are labelled as such.

## Planning rules

- Treat release assignments below as planning intent, not immutable promises, until the corresponding release profile is frozen.
- Keep implementation details in issues/PRs when work begins; keep this file focused on product scope, dependencies and acceptance intent.
- Preserve the exact-SHA release model, read-only ADB policy and Store correctness semantics from `PROJECT_DECISIONS.md` unless a deliberate policy change is made there.
- Do not silently move rejected/deferred ideas into an active release.

## v1.6 published baseline

v1.6.0 is published and immutable as an unsigned Windows x64 Engineering Test Build.

Immutable release source SHA:

`246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`

Release evidence:

- post-merge Quality push run `32543925562`;
- Windows x64 build run `32545213663`;
- engineering release assembly run `32547942460`;
- exactly three public project-defined assets;
- published asset checksums independently reverified after download.

Published project-defined assets:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`;
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`;
- `SHA256SUMS.txt`.

Do not rebuild, retag or replace any v1.6.0 release artifact.

### Shipped v1.6 product baseline

- canonical Store service with bounded multi-country fallback scheduling;
- terminal propagated `NotFoundError` handling with transient retry/backoff preserved;
- timeout/network uncertainty preserved;
- automatic Store language from active Android system language when available;
- structured Store country/language request evidence;
- selected-row details panel with Right/Below placement;
- grouped previous-audit change overview;
- Store developer metadata reused from the normal metadata response;
- experimental non-blocking Store icons beside Store titles;
- hardened persistent icon-cache failure handling;
- 16 Store workers retained as the default/recommended value.

The v1.6 country inference for phone scans can use Android locale region. Real-world testing after release identified this as a behaviour to revise in v1.7. Do not treat it as the desired final country semantic.

## v1.7 active priorities

The first v1.7 work should focus on the following two areas before broader feature expansion.

### Priority 1: Details panel redesign and adaptive layout

The v1.6 details panel is functionally useful but its position selector and internal layout need refinement.

Planned direction:

- replace the current prominent Right/Below selector with a compact layout control, preferably icon-based;
- evaluate an `Auto / Right / Below` choice, but do not commit to Auto as the default before visual/interaction testing;
- treat panel position and internal content layout as separate concerns;
- when the panel is narrow, use a primarily vertical information flow;
- when the panel is wide, especially below the table, place logical sections side by side;
- candidate pairings include Store next to Installed device, and Country/language evidence next to Changes since previous audit;
- allow the layout to reflow dynamically according to actual available width rather than hardcoding one layout solely from the selected panel position;
- avoid large dead areas or a rigid grid when section content lengths differ materially.

Acceptance direction:

- Right placement must remain usable on normal desktop widths;
- Below placement must make materially better use of horizontal space than v1.6;
- resizing the main window/splitter should not leave a visibly inappropriate layout for the available width;
- the position control should feel like a compact view/layout affordance rather than a settings form.

### Priority 2: Rework Store country vs Store language semantics

Country and language must remain conceptually independent.

Planned automatic Store language behaviour:

- for a connected Android phone, prefer the active Android system language obtained through read-only ADB metadata;
- preserve explicit manual language override;
- for file/list audits without usable phone-language context, use the principal/default language of the selected Store country unless manually overridden;
- unknown language falls back to English.

Planned automatic Store country resolution chain:

1. Prefer the host/computer region using the pre-v1.6 platform detection logic.
   - Windows: prefer `GetUserDefaultGeoName()`.
   - Linux/macOS/other hosts: use the existing locale/environment region signals where available.
2. If host-region detection cannot produce a usable ISO alpha-2 country and a connected Android locale includes a region, use that Android locale region only as a late fallback, for example `it-CH` -> `CH`.
3. If neither host nor Android locale supplies a usable region, use the final safe fallback `US`, unless a later deliberate decision changes it.
4. Preserve explicit manual Store-country override at all times.

Important semantic constraints:

- Android system language must not become a proxy for Store country.
- Example: a phone using Italian with a Swiss host region should resolve to Store country `CH` and Store language `it`.
- Android locale region is only a fallback country signal, not evidence of the real Google Play account country.
- Do not claim to know the Google Play account country unless a reliable supported signal is found.
- Language fallback must not change a conclusive geographic not-found result into a different geographic conclusion.
- Same-country English fallback remains appropriate only for inconclusive or metadata-incomplete cases, not after a conclusive terminal not-found.

Real-device validation is required before this model is considered settled. Test at least:

- host region CH with Android `it-CH`, `de-CH`, `fr-CH`, `en-CH`;
- host region and Android locale region disagreeing;
- Android locale with language but no usable region;
- file/list audit after a phone scan to ensure no phone context leaks;
- manual country override;
- manual language override;
- Store titles/metadata localization under multiple languages for the same country;
- country fallback behaviour for apps available only in some checked countries.

### Priority 3: Better per-app diagnostics

Extend the details/evidence UX for inconclusive and anomalous results, including where available:

- attempted countries;
- attempted languages;
- Store path/fallback evidence;
- retry count;
- failure reason;
- distinction between terminal not-found and transient/inconclusive failure.

This should build on the structured Store evidence introduced in v1.6 rather than parsing notes strings.

### Priority 4: Filtering and maintenance metadata

Good v1.7 candidates after the first two priorities:

- installer/source classification and filtering for Play Store, alternative stores, sideloaded/unknown and other observable installer sources;
- target/min SDK maintenance filters and compatibility hygiene without presenting them as a security score;
- installed signing-certificate fingerprint capture and change detection where available through read-only device metadata.

### Priority 5: Workflow and automation improvements

Candidates:

- saved audit profiles: reusable combinations of source/settings/countries/view/system-app exclusion and related audit options;
- incremental/smart re-audit with conservative cache policy and an explicit full-refresh path;
- versioned JSON export for automation and machine-readable downstream use.

### Saved filters / smart queries: open clarification

This idea remains uncommitted until the UX is agreed. It means saving a result-filter expression rather than an audit configuration.

Examples:

- `Removed from Play AND still installed`
- `Stale AND sideloaded`
- `Target SDK below threshold`
- `Installed/Store version differs`

A saved query would reapply to any compatible audit result set and act like a named dynamic view. This is distinct from a saved audit profile, which controls how an audit is run.

### Experimental icons maturity

Continue real-world observation of:

- cache growth;
- CDN failures;
- stale-icon behaviour;
- large-table responsiveness;
- offline/cache reuse.

The feature remains opt-in and non-blocking until there is enough evidence to remove the experimental label.

### Dashboard / summary candidate

The richer compact dashboard/summary remains deferred. Reconsider it only after the details panel and change overview have matured enough to show whether a separate summary adds real value rather than duplicating information.

## v2.0 and later

### Production distribution milestone

No earlier than v2.0, reconsider the full production release profile:

- Windows x64/ARM64;
- Linux x64/ARM64;
- macOS x64/ARM64;
- publicly trusted Windows signing;
- Developer ID signing/notarization/stapling/Gatekeeper verification on macOS;
- full multi-platform exact-SHA assembly and release validation.

The source workflows already implementing much of this architecture should remain maintained but do not need to be exercised as a normal v1.7 release cost.

### CLI/headless mode

Keep CLI/headless auditing in mind for v2.0 or later, not before. A future CLI could expose the existing service layer for scheduled tasks, CI or scripting without changing the desktop application into a daemon.

### Local APK audit concept

Explore a LocalAPK-inspired capability: scan APK files stored locally and compare their local version/build information with online/current information to identify which local APK files are up to date.

Before implementation, decide whether this belongs:

1. inside Play Store App Audit as a separate local-APK source/workflow sharing Store comparison services; or
2. in a separate companion application that reuses common libraries/services.

### Advanced app-management concept

Active app-management operations such as uninstall, disable, permission changes, clear data, force stop or APK installation are not planned for the normal near-term product. They conflict with the durable read-only ADB policy and require a deliberate `PROJECT_DECISIONS.md` change before consideration.

## Explicitly not planned

The following ideas remain rejected for the foreseeable roadmap unless a new product decision deliberately reopens them:

- automatically associating unavailable Play apps with GitHub/F-Droid/developer-site alternative sources;
- audit watchlists/background monitoring;
- predefined country-set presets such as DACH/EU/worldwide.

## Handoff requirement

Before starting a new release-cycle development chat, create a handoff package so the next chat can continue from repository evidence rather than reconstructing decisions from conversation history.

For v1.7, the canonical human-readable handoff is `HANDOFF_V1.7.md`. The reusable exporter is `../scripts/export_chat_handoff.ps1`.

From the repository root in PowerShell:

```powershell
.\scripts\export_chat_handoff.ps1
```

The exporter must fail closed when the working tree is dirty and should generate a live repository snapshot alongside the canonical handoff/project documents.
