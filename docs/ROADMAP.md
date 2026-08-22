# Product Roadmap

Last updated: 2026-08-22

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. It records planned release scope, deferred ideas, explicitly rejected ideas and open product questions so that future work does not need to be reconstructed from chat history.

`PROJECT_STATUS.md` records the current shipped state and active development baseline. `PROJECT_DECISIONS.md` records durable engineering/release policy. This roadmap is allowed to contain tentative product direction and release targets, provided tentative items are labelled as such.

## Planning rules

- Treat release assignments below as planning intent, not immutable promises, until the corresponding release profile is frozen.
- Keep implementation details in issues/PRs when work begins; keep this file focused on product scope, dependencies and acceptance intent.
- Preserve the exact-SHA release model, read-only ADB policy and correctness semantics from `PROJECT_DECISIONS.md` unless a deliberate policy change is made there.
- Do not silently move rejected/deferred ideas into an active release.

## v1.6 stabilization / release direction

The committed v1.6 product scope is implemented on `main`. v1.6 is now in stabilization before the release profile is frozen.

### Release profile

Current direction: **likely another unsigned Windows x64-only Engineering Test Build**, broadly following the v1.5 release profile. This is intentionally not frozen yet.

Production code signing, notarization and the full Windows/Linux/macOS x64/ARM64 production release are **not planned before v2.0**. The already implemented multi-platform/signing workflows remain preserved for that later milestone.

Version metadata remains `1.5.0` during stabilization. Only after the v1.6 release profile is deliberately frozen should canonical version metadata move to `1.6.0` and the changelog `Unreleased` section become the dated v1.6.0 entry.

### Implemented architecture and reliability

- Bounded multi-country fallback scheduling now lives in the canonical Store service rather than `performance_diagnostics.py`.
- Terminal propagated `NotFoundError` handling is consolidated in the Store path; generic transient failures still retain retry/backoff.
- Timeout/network failures remain transient or inconclusive and are not converted into false Store not-found evidence.
- Persistent app-icon cache disk/cache `OSError` failures degrade cleanly to cache miss/network fallback and cannot leave icons permanently pending.
- 16 concurrent Store workers remain the default/recommended value.
- Store language can use the connected Android system language in `auto` mode; file/list audits use the principal language of the selected Store country.
- Android locale region can initialize the Store country for a phone scan while remaining clearly labelled as inferred from Android locale, not the Google Play account country.
- Explicit manual country/language overrides remain available.
- Same-country English fallback is limited to inconclusive or metadata-incomplete cases and does not repeat conclusive terminal not-found results merely to change language.

### Implemented results/details UX

- The selected result row has a dedicated app-details panel.
- The panel can be positioned on the right or below the results table and persists the user's choice.
- Detailed information is concentrated in the panel instead of expanding the primary table indefinitely.
- The panel includes Store title, package ID, developer, Store URL, Store version/update information, country/language evidence, installed/device metadata and previous-audit changes where available.
- Experimental Store icons are shown beside the Play Store title rather than beside the package ID.
- Developer metadata is reused from the same normal Store response, without an additional metadata request.

### Implemented audit-change visibility

A grouped change-oriented overview now covers:

- newly installed apps when a real previous device inventory exists;
- apps removed from the device;
- newly available Store results;
- newly unavailable results in checked countries;
- reappeared Store listings;
- Store version changes;
- Store latest-update value changes;
- maintenance-state transitions such as Current -> Aging -> Stale;
- installer/source changes where supported by available metadata.

The first device inventory is treated as a baseline rather than as hundreds of newly installed events. Duplicate installer/source events from Store-history and device-inventory paths are collapsed in the overview.

### Implemented geographic evidence UX

Country/language request evidence is structured and exposed in the details panel. The UI can therefore show why a result is regional rather than implying global removal, for example a primary-country absence followed by fallback-country availability.

### Experimental icons maturity

The icon feature remains experimental for v1.6. Continue real-world observation of cache growth, CDN failures, stale-icon behaviour, large-table responsiveness and offline/cache reuse before considering removal of the experimental label. The feature must remain opt-in and non-blocking.

### Dashboard / summary candidate

The compact dashboard/summary candidate is **not included in the current v1.6 scope**. The existing concise summary remains sufficient for this release cycle. Reconsider a richer compact summary in a later cycle only if it adds clear value after the details panel and change overview have seen real-world use.

### Remaining v1.6 work

- Stabilization only; avoid adding new product scope unless a deliberate release decision reopens it.
- Freeze the actual v1.6 distribution profile.
- Bump canonical version metadata to `1.6.0` only after that freeze.
- Convert `CHANGELOG.md` `Unreleased` into the dated v1.6.0 entry.
- Run release-profile-specific Quality/build/legal/assembly checks from one exact frozen SHA.
- Publish only artifacts derived from that frozen SHA.

## v1.7 planned candidates

The following are intentionally deferred beyond v1.6 and are good candidates for v1.7:

- Saved audit profiles: reusable combinations of source/settings/countries/view/system-app exclusion and related audit options.
- Incremental/smart re-audit with conservative cache policy and an explicit full-refresh path.
- Versioned JSON export for automation and machine-readable downstream use.
- Target/min SDK maintenance filters and related compatibility hygiene, without presenting them as a security score.
- Installer/source classification and filtering for Play Store, alternative stores, sideloaded/unknown and other observable installer sources.
- Installed signing-certificate fingerprint capture and change detection, where available through read-only device metadata.
- Better per-app diagnostics for inconclusive/anomalous results, including attempted countries, Store path/fallback evidence, retry count and failure reason.

### Saved filters / smart queries: open clarification

This idea is not yet assigned to v1.7 until the UX is agreed. The concept is to let a user save a **result-filter expression**, not an audit configuration. Examples could be:

- `Removed from Play AND still installed`
- `Stale AND sideloaded`
- `Target SDK below threshold`
- `Installed/Store version differs`

A saved query would reapply to any compatible audit result set and act like a named dynamic view. This is distinct from a **saved audit profile**, which controls how an audit is run. Decide later whether this adds enough value beyond Custom views and normal filters.

## v2.0 and later

### Production distribution milestone

No earlier than v2.0, reconsider the full production release profile:

- Windows x64/ARM64;
- Linux x64/ARM64;
- macOS x64/ARM64;
- publicly trusted Windows signing;
- Developer ID signing/notarization/stapling/Gatekeeper verification on macOS;
- full multi-platform exact-SHA assembly and release validation.

The source workflows already implementing much of this architecture should remain maintained but do not need to be exercised as a normal v1.6/v1.7 release cost.

### CLI/headless mode

Keep CLI/headless auditing in mind for v2.0 or later, not before. A future CLI could expose the existing service layer for scheduled tasks, CI or scripting without changing the desktop application into a daemon.

### Local APK audit concept

Explore a LocalAPK-inspired capability: scan APK files stored locally and compare their local version/build information with online/current information to identify which local APK files are up to date.

This is deliberately an architecture/product question rather than a committed feature. Before implementation, decide whether it belongs:

1. inside Play Store App Audit as a separate local-APK source/workflow, sharing Store comparison services; or
2. in a separate companion application that reuses common libraries/services.

The decision should be based on UX cohesion, code reuse, product scope and whether local APK inventory/audit semantics remain understandable alongside installed-device and package-ID auditing.

### Advanced app-management concept

Active app-management operations such as uninstall, disable, permission changes, clear data, force stop or APK installation are not planned for the normal near-term product. They conflict with the current durable read-only ADB policy and would require a deliberate `PROJECT_DECISIONS.md` policy change, stronger safety boundaries and likely an explicitly advanced mode/product tier before consideration.

## Explicitly not planned

The following ideas were considered and are currently rejected for the foreseeable roadmap:

- automatically associating unavailable Play apps with GitHub/F-Droid/developer-site alternative sources;
- audit watchlists/background monitoring;
- predefined country-set presets such as DACH/EU/worldwide.

Do not reintroduce them without a new product decision.

## Handoff requirement

Before starting a new major-version development chat, create a handoff package so the next chat can continue from repository evidence instead of reconstructing decisions from conversation history.

For v1.6, the canonical human-readable handoff is `HANDOFF_V1.6.md`. The reusable exporter is `../scripts/export_chat_handoff.ps1`.

From the repository root in PowerShell, run:

```powershell
.\scripts\export_chat_handoff.ps1
```

The exporter fails closed when the working tree is dirty, creates a timestamped temporary folder and ZIP, copies the durable/status/roadmap/release/development files, and generates `REPOSITORY_SNAPSHOT.md` with the live branch/SHA/status, recent commits/tags, tracked implementation/test/workflow inventory, Python version and optional GitHub CLI release/PR metadata.

Attach the generated ZIP to the new chat. The static handoff file explains the current version-specific intent; the generated snapshot supplies live repository state. Future major-version chats should update or add the corresponding `HANDOFF_Vx.y.md` before export rather than silently reusing stale version-specific assumptions.
