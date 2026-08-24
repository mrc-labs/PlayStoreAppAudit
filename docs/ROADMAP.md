# Product Roadmap

Last updated: 2026-08-24

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

## v1.9

v1.9 is the active development cycle and remains Windows x64 only. The architectural/UX review approved a first grouped presentation-consistency PR so the related low-risk polish can share one Quality run:

- one friendly Notes presentation shared by the table, Details Panel and user-facing HTML report, plus a complete Notes tooltip, while raw Notes remain unchanged in CSV, versioned JSON, diagnostics and Smart Queries;
- **Maintenance Score** as the user-facing name, with `health_score`, persisted Smart Query field IDs and serialized compatibility keys unchanged and no scoring-algorithm change;
- foreground-only table highlights for Installed-vs-Store **Different**, Android Compatibility **Aging target** and **Legacy target**, reusing the existing warning palette;
- About hierarchy of product title, tagline subtitle and secondary version;
- one project-owned, palette-aware QPainter icon family for Choose File, Scan Phone and Export Results, with no icon-library or theme dependency.

Two ideas remain prototype/review candidates for separate later v1.9 PRs and are not part of the presentation-consistency implementation:

- an extra-wide responsive three-column Details Panel layout;
- a complementary bottom `QStatusBar` for device/source, progress and operation feedback, not as a Details Panel replacement.

A `QDockWidget` experiment and richer dashboard/status overview are deferred to v1.99 under the evidence requirements below. A global Fluent redesign, an icon library without demonstrated need, unnecessary broad architecture/type refactors and a full internal `health_score` rename are rejected for v1.9 but remain recorded for possible future reconsideration. Continue using Qt Widgets with platform/default Windows styling.

### v1.9 CI and build budget

- Normal code PRs may run Ruff, pytest, compileall, the lightweight Qt smoke test and targeted static checks.
- Do not dispatch Windows/Nuitka packaging for documentation, product identity, naming, icon polish or housekeeping changes.
- Native Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 are manual or limited to high-impact UI milestones.
- Full Windows x64 packaging is reserved for a demonstrated milestone need or the frozen release candidate.
- VS Code/Pylance Standard type checking is useful local evidence for touched code, not a repository build setting or authorization for a broad typing refactor.

## v1.99 pre-v2.0 closure

v1.99 is the likely final Windows x64-only release before v2.0. Its purpose is to review and close meaningful outstanding pre-v2.0 items, not to become an uncontrolled feature release.

Deferred candidates are deliberately conditional:

- prototype `QDockWidget` only if it provides a real workflow or usability benefit over the current Details Panel;
- add a richer dashboard/status overview only if it answers a distinct workflow not already covered by the result summary, filters and Details Panel;
- reconsider an internal `health_score` rename only as a deliberate compatibility migration with explicit persistence/serialization evidence.

Items that do not meet those evidence thresholds stay deferred or rejected. v1.99 remains on the Windows x64 ETB distribution profile unless a later explicit release decision changes it.

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

## Explicitly removed / not planned

Do not reintroduce without a new product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined country presets such as DACH/EU/worldwide.

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

The active human-readable handoff for the next cycle is `HANDOFF_V1.9.md`. Generate continuation ZIPs only from a clean, synchronized local `main` checkout after documentation is merged, using `../scripts/export_chat_handoff.ps1`; the script selects the newest `docs/HANDOFF_V*.md` and includes a freshly generated `REPOSITORY_SNAPSHOT.md`.
