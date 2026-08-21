# Product Roadmap

Last updated: 2026-08-21

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. It records planned release scope, deferred ideas, explicitly rejected ideas and open product questions so that future work does not need to be reconstructed from chat history.

`PROJECT_STATUS.md` records the current shipped state and active development baseline. `PROJECT_DECISIONS.md` records durable engineering/release policy. This roadmap is allowed to contain tentative product direction and release targets, provided tentative items are labelled as such.

## Planning rules

- Treat release assignments below as planning intent, not immutable promises, until the corresponding release profile is frozen.
- Keep implementation details in issues/PRs when work begins; keep this file focused on product scope, dependencies and acceptance intent.
- Preserve the exact-SHA release model, read-only ADB policy and correctness semantics from `PROJECT_DECISIONS.md` unless a deliberate policy change is made there.
- Do not silently move rejected/deferred ideas into an active release.

## v1.6 planned direction

### Release profile

Current direction: **likely another unsigned Windows x64-only Engineering Test Build**, broadly following the v1.5 release profile. This is intentionally not frozen yet.

Production code signing, notarization and the full Windows/Linux/macOS x64/ARM64 production release are **not planned before v2.0**. The already implemented multi-platform/signing workflows remain preserved for that later milestone.

### Architecture and reliability

- Move the bounded multi-country fallback scheduler out of `performance_diagnostics.py` into a dedicated canonical Store service.
- Consolidate terminal `NotFoundError` handling so base and device-enriched Store paths use one retry/classification implementation and cannot drift.
- Preserve the current semantics: propagated scraper `NotFoundError` is terminal; timeout/network failures remain transient or inconclusive.
- Harden the persistent app-icon cache against disk/cache `OSError` failures so a failed local cache operation cannot leave an icon permanently pending and can degrade cleanly to cache miss/network fallback.
- Keep 16 concurrent Store workers as the default/recommended value. The previously proposed 14-vs-16 cooldown benchmark is no longer required for v1.6 unless a later performance concern deliberately reopens it. If it is reopened, it may be run as an unattended real-device benchmark with the phone connected and no product changes coupled to the test.

### Results-table and details UX

- Add an app-details panel for the selected result row.
- Allow the user to choose whether the details panel is docked on the **right** or **below** the results table.
- Prefer detailed information in the panel rather than continually adding columns to the primary table.
- Candidate details include Play Store title, package ID, developer, Store URL, Store version/update information, country evidence, installed/device metadata and previous-audit changes where available.
- Re-evaluate the experimental app-icon placement. Current candidate: show the Store icon beside the **Play Store title** rather than beside the package name, because the icon represents Store metadata rather than package identity. Confirm the final table/panel treatment during the v1.6 UX pass.

### Audit-change visibility

Add a clearer change-oriented view for comparison with a previous audit, building on the existing previous-audit capability. Candidate change groups:

- newly installed;
- removed from device;
- newly available on Play;
- newly unavailable in checked countries;
- reappeared on Play;
- Store version changed;
- Store latest-update value changed;
- maintenance status transition such as Current -> Aging -> Stale;
- installer/source changed where device metadata supports it.

### Geographic evidence UX

Expose the country-level evidence behind availability classifications without changing the established semantics. A details view should be able to show, for example, primary-country absence followed by fallback-country availability, making clear why the final result is regional rather than global removal.

### Experimental icons maturity

Continue real-world observation of the opt-in icon feature before removing the `experimental` label. Review cache growth, CDN failures, stale-icon behaviour, large-table responsiveness and offline/cache reuse. Do not make the feature blocking.

### Dashboard / summary candidate

Candidate for v1.6, not yet committed: a compact audit summary showing counts such as available, primary-country unavailable, fallback-only, removed/inconclusive and Current/Aging/Stale. Preferred first UX exploration is a **compact summary area above the results table**, optionally collapsible, rather than another permanent side panel. Final placement remains open until the details-panel layout is designed.

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
