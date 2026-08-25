# Play Store App Audit v1.9 Chat Handoff

Last updated: 2026-08-25

Status: **v1.8.0 is published and immutable; v1.9 PR1, PR2 and PR3 are merged and accepted; the v1.9.0 release-readiness/version-freeze work is active.**

## Start here

This is the canonical human-readable continuation file after v1.8 closure. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `RELEASE_CLOSURE.md` and the generated `REPOSITORY_SNAPSHOT.md` in the current handoff package.

Before changing anything:

1. verify live GitHub repository, open-PR and release state;
2. run `git status --short` and stop if the local working tree is dirty;
3. on a clean checkout, fetch/prune, switch to `main` and pull with `--ff-only`;
4. verify local `HEAD` equals `origin/main` and read the current roadmap/decisions;
5. do not modify, rebuild, retag or replace v1.8.0 or any earlier published release.

## Latest immutable release

- Release: `v1.8.0`
- URL: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.8.0
- Title: `Play Store App Audit v1.8.0 (Win x64 Only)`
- Profile: intentionally unsigned Windows x64 Engineering Test Build, Nuitka standalone ZIP
- Frozen source SHA: `ac328f0dffddb6b70fa7600f1291377376bc05d4`
- Application version: `1.8.0`
- Windows File/Product version: `1.8.0.0`
- Quality run: `32682693020`
- Windows x64 build run: `32683271942`
- Engineering assembler run: `32684933669`
- Publication: direct authenticated GitHub Release operation after tag verification; no separate v1.8 publication workflow/run
- Post-release housekeeping run: `32727364125`

Published assets verified after re-download:

- `PlayStoreAppAudit-v1.8.0-windows-x64.zip` - 33,450,079 bytes - SHA-256 `b056be21804d2c22483ebee14c2f2bcbee5611a36ad6c7fea51c3dd91043991d`
- `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` - 73,128,136 bytes - SHA-256 `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e`
- `SHA256SUMS.txt` - 225 bytes - SHA-256 `09717c84a7096351dcc8ba91609146a877ffb2eee1184b34ccfea40c39bebb6b`

The annotated tag peels exactly to the frozen SHA. v1.7.0 was rechecked unchanged at `e2d09098bc42c6f16d202d010deda3eb24d99aa3` during v1.8 publication verification.

## Actions state after v1.8

Housekeeping run `32727364125` applied the existing generational policy successfully. It found no run or artifact eligible for deletion inside the 7-day grace window.

- Active state: 10 artifacts / 573,766,431 bytes (547.19 MiB).
- Retain v1.8 build artifact ID `9505311410` and assembler artifact ID `9505354895` as the current canonical release evidence.
- Allow the documented policy to age out superseded v1.7/UI generations; do not bypass it without a new point-in-time lineage check.
- Repository retention settings and cleanup logic were not changed.
- Published Release assets are not Actions artifacts and must never be removed by housekeeping.

## Current technical baseline

- Current source application/release-candidate version: `1.9.0`; derived Windows File/Product version: `1.9.0.0`.
- Latest published version remains immutable v1.8.0 until the v1.9.0 exact-SHA package, assembly and publication gates pass.
- Python packaging baseline: 3.13; Quality CI: 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- UI: Qt 6 / PySide6 Qt Widgets with platform/default QStyle.
- Google Play access remains behind service boundaries.
- Managed ADB remains read-only with respect to installed Android apps.
- Store workers default/recommended 16; Store timeout 25 seconds.
- VS Code/Pylance Standard checking is a local development aid, not a runtime/build change or broad typing mandate.
- v1.9 release distribution remains unsigned Windows x64 only.
- v2.0 is the first planned return to multi-platform distribution; production signing remains conditional, not promised.

## v1.8 shipped product baseline

- Unified action availability and CSV/HTML/versioned-JSON export definitions.
- Consistent command naming, contextual help, reduced static UI density and final running-operation safeguards.
- Compact persistent Details Panel modes: Auto, Right, Below and Hidden.
- Focused Display Settings and four-category Advanced Settings hierarchy.
- Play Store icon cache/CDN/offline/large-table hardening.
- Saved one-level All/Any Smart Queries, distinct from Quick Filters and Audit Profiles.
- Informational product tagline in repository description, README and About.

Detailed implementation and validation evidence is in `HANDOFF_V1.8.md` and `PROJECT_STATUS.md`.

## v1.9 planning boundary

The first approved v1.9 implementation merged through PR `#116` as one grouped presentation-consistency PR:

- share one friendly Notes presentation across the table, Details Panel and HTML report, add the complete Notes tooltip and preserve raw Notes/Smart Query compatibility;
- use **Maintenance Score** everywhere user-facing while retaining `health_score` and the current algorithm;
- add foreground-only semantic warning colours to version differences and aging/legacy target values;
- refine the About title/tagline/version hierarchy;
- use one project-owned QPainter icon family for Choose File, Scan Phone and Export Results;
- prevent Display Settings from crashing with populated, sorted or filtered results by using a safe presentation refresh, and keep the Custom preset, column visibility, selection, Details content and widths synchronized across changes and restart.

The separate native Windows prototype merged through PR `#117` and added an automatic extra-wide Details Panel state for usable scroll-viewport widths at or above 1180 px, with exit hysteresis at 1080 px. It keeps Store/Notes, Installed/Changes and Store evidence/diagnostics in three columns with the existing horizontal action row below. At a 1200 px viewport, representative rows reduced required scroll-content height by approximately 29-156 px compared with the existing two-column layout; the 1080 px exit edge still provides approximately 346 px per column without content clipping. Width-aware section minimums ensure compact-height panels scroll instead of truncating wrapped text.

The complementary native `QStatusBar` implementation merged through PR `#118` after native Windows acceptance. It reparents the same canonical `status_label` and progress bar instead of creating or synchronising duplicate status widgets. The label expands on the left; the compact 200 px progress bar appears on the right only while the existing operation flags report active source, audit or finalization work. The action row consequently contains Run, Export Results and Clear Results only. Source/device identity stays in its existing UI because duplicating it did not add value; the native size grip remains enabled. The status bar neither replaces the Details Panel nor adds a preference or persistence state, and `_set_presentation_status()` continues to protect operational feedback.

The v1.9 product/UX feature scope is closed. Release-readiness work may update version metadata, release documentation and genuine release blockers only; it must not reopen accepted UX decisions or start v1.99 work.

`QDockWidget` and richer dashboard/status overview experiments are deferred to v1.99 and require a demonstrated distinct benefit. v1.99 is the likely final Windows x64-only release before v2.0 and should close meaningful pre-v2.0 work rather than become an uncontrolled feature release.

A global Fluent redesign, an icon library without demonstrated need, unnecessary broad architecture/type refactors and a full internal `health_score` rename are rejected for v1.9 but remain recorded for possible future reconsideration. Multi-platform distribution, production signing and CLI/headless mode remain v2.0-or-later.

## Smart Queries guardrails

Smart Queries remain result-only filters and are not audit configuration. Preserve the approved contract in `SMART_QUERIES_UX_REVIEW.md`:

- Quick Filters are built-ins; Smart Queries are saved structured filters.
- One-level All/Any only, with curated fields/operators.
- Versioned `smart_queries` persistence and session-only active state.
- No automatic legacy `saved_filters` migration.
- Composition with existing table filters without changing audit execution, Store lookup/cache or ADB.
- No nested groups, scripting, regex, import/export, automation or shared Audit Profile commands.

## Explicitly removed / not planned

Do not reintroduce without a new explicit product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined country presets such as DACH/EU/worldwide.

## CI and release budget

- Normal code PRs: compileall, Ruff, pytest, lightweight Qt smoke and targeted static checks.
- Use native Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 only for high-impact UI milestones.
- Do not run Nuitka for docs-only, naming, icon polish or housekeeping.
- A full Windows x64 build is for a justified high-impact milestone or the deliberately frozen v1.9 release candidate.
- Do not create public RC tags.

## Repository and closure rules

- `main` is the only permanent branch; use short-lived branches and normal PR merge commits.
- No squash/rebase project history.
- Before every pull, require a clean working tree; never auto-stash/reset/discard user work.
- Published release history is immutable.
- Freeze one exact SHA only after required Quality gates pass; reject dispatch/checkout mismatches.
- Tag only after final artifact validation, and never rebuild on tag push.
- Keep legal/source validation fail-closed.
- Finish every future release through `RELEASE_CLOSURE.md`.

The generated handoff snapshot records the actual post-release documentation SHA of `main`. Do not confuse it with the immutable v1.8.0 source SHA above.
