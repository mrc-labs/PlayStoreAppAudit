# Play Store App Audit v1.8 Final Handoff

Last updated: 2026-08-24

Status: **v1.8.0 published and immutable. Active continuation is `docs/HANDOFF_V1.9.md`.**

## Purpose

This file closes the v1.8 product and release cycle. It records the exact immutable release evidence, completed scope, validation and post-release housekeeping. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `RELEASE_CLOSURE.md`.

## Immutable v1.8.0 release

- Release: `v1.8.0`
- URL: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.8.0
- GitHub Release title: `Play Store App Audit v1.8.0 (Win x64 Only)`
- Release class: unsigned Windows x64 Engineering Test Build (ETB)
- Package form: Nuitka standalone ZIP
- Frozen source SHA: `ac328f0dffddb6b70fa7600f1291377376bc05d4`
- Application version: `1.8.0`
- Windows File/Product version: `1.8.0.0`
- Quality push run: `32682693020`
- Final Windows x64 build run: `32683271942`
- Engineering assembly run: `32684933669`
- Publication: authenticated direct GitHub Release creation after explicit tag verification; no separate v1.8 publication workflow/run
- Post-release Actions housekeeping run: `32727364125`

The annotated `v1.8.0` tag peels exactly to the frozen SHA. The Release is published, non-draft and non-prerelease. Do not rebuild, retag, rewrite or replace its tag, source commit or assets.

Published project-defined assets:

- `PlayStoreAppAudit-v1.8.0-windows-x64.zip` - 33,450,079 bytes - SHA-256 `b056be21804d2c22483ebee14c2f2bcbee5611a36ad6c7fea51c3dd91043991d`
- `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` - 73,128,136 bytes - SHA-256 `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e`
- `SHA256SUMS.txt` - 225 bytes - SHA-256 `09717c84a7096351dcc8ba91609146a877ffb2eee1184b34ccfea40c39bebb6b`

Canonical retained Actions artifacts:

- Build artifact ID `9505311410`, `PlayStoreAppAudit-v1.8.0-windows-x64`, 179,954,097 compressed Actions bytes.
- Assembler artifact ID `9505354895`, `PlayStoreAppAudit-v1.8.0-windows-x64-engineering-release-assets`, 106,488,770 compressed Actions bytes.

## Release validation

The approved assembler output was used without rebuilding or modification. Post-publish verification re-downloaded exactly three assets into a fresh directory and confirmed their names, sizes and SHA-256 values. The two payload hashes match the published `SHA256SUMS.txt`.

Candidate validation confirmed:

- PE AMD64/x64 architecture and standalone, not onefile, package layout;
- application version `1.8.0` and Windows File/Product version `1.8.0.0`;
- Python 3.13.15 x64, `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3` provenance;
- intentional unsigned state and correct SmartScreen/unknown-publisher explanation;
- startup, packaged smoke, strict legal/source material and exact frozen-SHA provenance;
- clean extraction and normal launch/close;
- v1.7 profile upgrade with existing preferences, display/technical settings and Audit Profiles preserved;
- independent empty Smart Queries initialization with no automatic legacy `saved_filters` migration;
- DPI-aware native Windows UI behavior at logical client sizes 1100x700, 1200x760, 1500x900 and 1600x900.

The v1.7.0 annotated tag was also rechecked at `e2d09098bc42c6f16d202d010deda3eb24d99aa3`, and its three published asset names, sizes and digests remained unchanged.

## Actions housekeeping

Run `32727364125` applied the existing 7-day generational retention policy from the frozen v1.8 SHA and completed successfully.

- Active artifact state after the run: 10 artifacts / 573,766,431 bytes (547.19 MiB).
- No failed/cancelled run, superseded successful run or individual artifact was yet eligible for deletion.
- The v1.8 build and assembler artifacts were retained as canonical audit evidence.
- The prior v1.7 generation and two UI-style generations remain under the documented grace policy.
- No GitHub Release asset, tag, source commit or prior release was changed.
- Repository retention and cleanup logic were not changed because no concrete policy failure was found.

## Completed v1.8 scope

v1.8 shipped through small normal-merge PRs `#105`-`#114` without a broad architecture rewrite, new UI framework or global visual redesign.

- Action availability is synchronized through shared local predicates for source, inventory, results, visible results, row/field capability and running operations.
- File and main-control export actions share one canonical CSV/HTML/versioned-JSON definition.
- Command naming, tooltip case, **Clear Results**, density and targeted iconography are consistent.
- The compact **Details** control and **View > Details Panel** menu support persistent Auto, Right, Below and Hidden modes without `QDockWidget`.
- Display Settings owns App Icons, Date Format and Custom Columns.
- Advanced Settings uses Store & Cache, Device, Audit & History, and Data & Storage categories while preserving existing services and settings.
- Play Store icons graduated from experimental presentation and received bounded cache/CDN/offline/large-table hardening while remaining optional and disabled by default.
- Smart Queries implement the approved one-level All/Any result-filter model, curated fields/operators, versioned persistence and session-only active state.
- Smart Queries remain separate from Quick Filters, Audit Profiles, legacy `saved_filters`, audit execution, Store lookup/cache and read-only ADB.
- The informational tagline appears in repository description, README and About, not the operational main window.
- Incompatible operations block Advanced Settings/Audit Profiles, and presentation-only actions preserve operational messages.

## Permanent Smart Queries guardrails

Smart Queries remain a filter over already loaded results. Do not expand them into nested groups, scripting, regular expressions, import/export, automation, background execution or audit configuration. Do not merge their commands or persistence with Audit Profiles.

The approved design contract remains in `SMART_QUERIES_UX_REVIEW.md`.

## Deferred beyond v1.8

The following were not implemented in v1.8:

- complementary bottom `QStatusBar` evaluation, no earlier than v1.9;
- separate `QDockWidget`/docking prototype only if real need emerges in v1.9;
- richer dashboard/status overview only after distinct UX value is demonstrated;
- global Fluent-style visual redesign, outside approved scope;
- multi-platform binaries, production signing and CLI/headless work, no earlier than v2.0.

v1.9 remains Windows x64 only and begins with planning rather than an already frozen feature scope. Production signing remains an ideal v2.0 target, not a promise.

## Explicitly removed / not planned

Do not reintroduce without a new explicit product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country presets.

## Release and repository rules

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits; no squash/rebase history.
- Before every pull, run `git status --short`; if dirty, stop without automatic reset/stash/discard.
- Published releases, tags, source commits and assets are immutable.
- Every release derives its artifacts from one exact frozen SHA.
- Tag only after artifact validation; tag pushes never rebuild binaries.
- Keep strict legal/source validation fail-closed.
- ADB remains read-only with respect to installed Android apps.
- Distinguish immutable release SHA `ac328f0dffddb6b70fa7600f1291377376bc05d4` from the newer documentation-only post-release `main` SHA.
- Complete every release through `RELEASE_CLOSURE.md`.

## Continuation

Continue v1.9 planning from `HANDOFF_V1.9.md`. The final exported handoff ZIP must be generated only after this documentation is merged, local `main` is synchronized with `origin/main`, and `git status --short` is empty. `scripts/export_chat_handoff.ps1` selects the newest versioned handoff and records the actual post-release `main` SHA in `REPOSITORY_SNAPSHOT.md`.
