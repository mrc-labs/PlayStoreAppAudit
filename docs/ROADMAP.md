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

v1.9 is the active next planning cycle and remains Windows x64 only. No v1.9 feature implementation began during v1.8 release closure, and detailed product scope is not yet frozen.

Candidate UX evaluations carried forward from v1.8 are:

- a real bottom `QStatusBar` for complementary device/source, progress and operation feedback, not as a Details Panel replacement;
- a separate `QDockWidget`/docking experiment only if v1.8 usage demonstrates a real need;
- a richer dashboard/status overview only after its distinct user value is demonstrated.

A global Fluent-style visual redesign remains outside approved scope. Continue using Qt Widgets with platform/default Windows styling unless a later evidence-based decision changes that direction.

Before implementing any candidate, review actual v1.8 usage and define the user problem, interaction model, persistence impact, regression surface and acceptance evidence. Do not reopen completed v1.8 scope merely to expand the next release.

### v1.9 CI and build budget

- Normal code PRs may run Ruff, pytest, compileall, the lightweight Qt smoke test and targeted static checks.
- Do not dispatch Windows/Nuitka packaging for documentation, product identity, naming, icon polish or housekeeping changes.
- Native Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 are manual or limited to high-impact UI milestones.
- Full Windows x64 packaging is reserved for a demonstrated milestone need or the frozen release candidate.
- VS Code/Pylance Standard type checking is useful local evidence for touched code, not a repository build setting or authorization for a broad typing refactor.

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
