# Product Roadmap

Last updated: 2026-08-24

## Purpose

This file is the canonical forward-looking product roadmap for Play Store App Audit. `PROJECT_STATUS.md` records current shipped state, `PROJECT_DECISIONS.md` records durable engineering/release policy, and this document assigns future product work.

## Planning rules

- Preserve the exact-SHA release model, read-only ADB policy and Store correctness semantics unless a deliberate decision changes them.
- Do not silently move deferred or rejected ideas into active scope.
- Published releases, tags and assets are immutable.
- Produce a UX audit/report before broad visual redesign work when the change is exploratory rather than already specified.

## v1.7 published baseline

v1.7.0 is published and immutable as an unsigned Windows x64 Engineering Test Build.

- Frozen release source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`.
- Public project-defined assets: Windows x64 ZIP, consolidated third-party source archive and `SHA256SUMS.txt`.
- Release evidence and checksums are recorded in `PROJECT_STATUS.md` and `HANDOFF_V1.8.md`.

## v1.8 active scope

v1.8 is the next feature/polish cycle and remains Windows x64 only. Do not build or publish Windows ARM64, Linux or macOS v1.8 release candidates. The pre-implementation UX audit and final review are complete; the directions below are approved for implementation in small, verifiable PRs.

### UX consistency and action correctness

- Define shared local availability predicates for idle state, source availability, device inventory, complete results, visible results, row/field capabilities and running operations.
- Synchronize menu, button and context-menu actions from those predicates without introducing an application-wide state-machine rewrite.
- Use one canonical export structure for the File menu and main Export control, with consistent CSV, HTML and versioned JSON actions.
- Normalize command naming in Title Case and use sentence case for explanatory tooltips.
- Replace permanent legends or tips with contextual help where this improves usable space without reducing discoverability.

### Details Panel UX v2

Replace the three permanent Auto/Right/Below controls with one compact control whose visible text is **Details**. Keep the current splitter-based Qt Widgets architecture and:

- support Auto, Right, Below and Hidden modes;
- use **Details Panel** in the View menu where the longer name improves clarity;
- persist the selected mode and restore usable table space when the panel is Hidden;
- keep hover help and accessibility metadata for the compact control;
- validate the existing responsive behavior at 1100x700, 1200x760, 1500x900 and 1600x900.

Do not use `QDockWidget` or a new UI framework for this work.

### Display and Advanced Settings

Move visual preferences such as App Icons, Custom Columns and Date Format to a focused Display Settings surface under View. Improve the remaining Advanced Settings hierarchy without changing service or persistence semantics. Candidate technical categories are Store & Cache, Device, Audit & History, and Data & Storage; Health Score remains part of the audit area.

Use simple native Windows/Qt navigation. A `QStackedWidget` with a small category list is acceptable only if it remains clearer than a single lightweight dialog after visual preferences are removed.

### Targeted naming, density and iconography polish

Replace obsolete or confusing icons where a suitable existing Qt/application asset exists; otherwise prefer clear text over an inaccurate metaphor. Do not add an icon framework or perform a global visual redesign. Keep tooltips for icon-only or technical controls and avoid redundant help on self-explanatory text buttons.

### Graduate Play Store icons from experimental

Move Store icons from experimental/opt-in framing to normal supported behavior if v1.7 observations do not reveal a blocking issue. Finish any required cache growth, CDN failure, stale-data, offline reuse or large-table responsiveness hardening.

### Saved filters / smart queries

Add reusable result-filter expressions that remain distinct from saved audit profiles. The UX/design review must define the model, fields, operators, persistence and application behavior before any Smart Queries code is written. Do not revive an older CRUD design automatically or combine unapproved implementation with the design review.

### Product identity

Keep the product name **Play Store App Audit** and use the official tagline **Android App Inventory, Store Analysis & Maintenance Toolkit** in the repository description, README and About dialog. In About, keep the hierarchy product name, version, tagline, then description; the tagline is informational rather than dominant. Do not add it to the operational main window.

### Actions housekeeping

Identify canonical release runs and remove only redundant GitHub Actions artifacts after checking that they are no longer release inputs. Never delete GitHub Release assets, tags or release sources. Improve the post-release checklist without adding a complex tracking system. Change retention behavior only when concrete evidence demonstrates a policy or implementation problem.

### CI and build budget

Every code PR may run Ruff, pytest, compileall, the lightweight Qt smoke test and targeted static checks. Do not dispatch Windows/Nuitka packaging for documentation, product identity, naming, icon polish or housekeeping changes. Native Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 are manual or limited to high-impact UI milestones. Full Windows x64 packaging is reserved for a demonstrated milestone need or the frozen release candidate; Nuitka remains a frozen-candidate tool unless an explicit exception is justified.

VS Code/Pylance Standard type checking is useful local evidence for touched code. It is not a repository build setting and does not justify a general typing refactor.

### Approved implementation sequence

1. `docs/v1.8-scope-lock-and-identity`
2. `chore/v1.8-actions-housekeeping`
3. `fix/v1.8-action-availability-and-export`
4. `ux/v1.8-naming-density-icons`
5. `feature/v1.8-details-control`
6. `feature/v1.8-display-and-settings`
7. `ux/v1.8-play-store-icons-and-smart-query-design`
8. `release/v1.8.0`, only after approved scope and any separately approved Smart Queries implementation are complete

## v1.9

v1.9 is also Windows x64 only. Its detailed product scope remains open until v1.8 is evaluated. Candidate UX evaluations are:

- a real bottom `QStatusBar` for complementary device/source, progress and operation feedback, not as a Details Panel replacement;
- a separate `QDockWidget`/docking experiment only if v1.8 reveals a real need;
- a richer dashboard/status overview only after its distinct user value is demonstrated.

A global Fluent-style visual redesign remains outside approved scope. Do not reintroduce multi-platform release packaging in v1.9 without an explicit roadmap/decision change.

## v2.0 and later

### First planned return to multi-platform distribution

v2.0 is the first planned release after v1.3 to return to the full six prebuilt platform/architecture targets:

- Windows x64 and ARM64;
- Linux x64 and ARM64;
- macOS x64 and ARM64.

Production-trust signing is the ideal target for Windows and macOS, including notarization/stapling/Gatekeeper verification on macOS, but it is not yet guaranteed. Before promising signed v2.0 packages, validate provider eligibility, credentials, cost, GitHub configuration and real end-to-end signing/notarization runs.

### CLI/headless mode

Keep CLI/headless auditing in v2.0-or-later scope. A future CLI should reuse the service layer rather than turning the desktop app into a background daemon.

### Local APK audit concept

Explore a LocalAPK-inspired workflow for locally stored APK files and version comparison. Decide first whether it belongs inside Play Store App Audit or a companion utility.

### Advanced app management

Uninstall/disable/permission/clear-data/force-stop/install actions remain outside the near-term product because they conflict with the durable read-only ADB policy. Any such work requires an explicit policy change first.

## Explicitly not planned

Unless a new product decision reopens them:

- installed signing-certificate fingerprint capture/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country presets.

## Handoff requirement

The active human-readable handoff for the v1.8 cycle is `HANDOFF_V1.8.md`. Generate a new handoff ZIP only from a clean, synchronized local `main` checkout after post-release documentation is merged, using `../scripts/export_chat_handoff.ps1`.
