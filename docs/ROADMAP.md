# Product Roadmap

Last updated: 2026-08-23

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

v1.8 is the next feature/polish cycle and remains Windows x64 only. Do not build or publish Windows ARM64, Linux or macOS v1.8 release candidates.

### Graduate Play Store icons from experimental

Move Store icons from experimental/opt-in framing to normal supported behavior if v1.7 observations do not reveal a blocking issue. Finish any required cache growth, CDN failure, stale-data, offline reuse or large-table responsiveness hardening.

### Saved filters / smart queries

Add reusable result-filter expressions that remain distinct from saved audit profiles. Example concepts include `Removed from Play AND still installed`, `Stale AND sideloaded`, target-SDK thresholds and installed/Store-version differences. Define the UX deliberately before implementation rather than reviving an older CRUD design automatically.

### Richer compact dashboard / summary

Design a compact at-a-glance summary against the mature Details Panel, change overview, filters and smart queries. It must add information rather than duplicate existing UI.

### Details Pane UX v2

Explore a more space-efficient control model:

- allow the Details Panel to be hidden completely;
- prefer testing one compact Details control/menu instead of expanding the current three buttons to four;
- candidate menu states: Auto, Right, Below and Hide;
- keep hover help for icon-only/non-obvious controls;
- preserve Right as the current default unless testing justifies a deliberate change;
- treat `QDockWidget` as an experiment only, not a committed redesign, because it may look too traditional relative to the current card/table UI.

### Status-bar alternative experiment

If the primary Details-control concept is not visually successful, evaluate a real bottom `QStatusBar` similar to Excel's status bar as an alternative or complementary interaction surface. Possible content includes connected device/source identity on the left, transient status/progress in the middle, and compact secondary view controls on the right. Do not commit to moving Details placement controls there until the prototype is visually convincing and discoverable.

### Advanced Settings redesign

The current stacked `QGroupBox`/`QFormLayout` presentation is functionally correct but visually dated. Explore a more modern native-Qt settings structure such as category navigation on the left and a focused settings page on the right, with less boxed visual chrome. Reconsider whether purely visual settings such as columns/icons belong under View rather than Advanced Settings.

### Full UI/menu/button clarity audit

Before broad implementation, produce a report covering:

- File/View/Tools/Help menu grouping and naming;
- primary and secondary button hierarchy;
- icon consistency and use of native/modern desktop metaphors;
- tooltip policy for icon-only/non-obvious controls and `statusTip` opportunities;
- keyboard shortcuts/mnemonics where useful;
- export-menu consistency across the main button and File menu;
- right-click actions disabled when unavailable rather than silently doing nothing;
- status chips, search/filter discoverability and redundant permanent tips/legends.

Do not turn this audit into automatic code changes before the report is reviewed.

## v1.9

v1.9 is also Windows x64 only. Its detailed product scope is intentionally left open until v1.8 is evaluated. Do not reintroduce multi-platform release packaging in v1.9 without an explicit roadmap/decision change.

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
