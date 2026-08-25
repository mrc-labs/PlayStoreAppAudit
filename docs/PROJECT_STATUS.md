# Project Status

Last updated: 2026-08-25

## Published release

- Latest published version: `v1.8.0`
- GitHub Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.8.0
- Immutable release commit: `ac328f0dffddb6b70fa7600f1291377376bc05d4`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Package form: Nuitka standalone ZIP
- Application version: `1.8.0`
- Windows File/Product version: `1.8.0.0`
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.8.0 (Win x64 Only)`
- Release-body heading: `Play Store App Audit v1.8.0 (Engineering Test Build - Windows x64 Only)`
- Public project-defined assets: exactly 3

Published v1.8.0 is immutable. Do not rebuild, retag, rewrite or replace its source commit, annotated tag or assets. Earlier published releases remain immutable as well.

## v1.8.0 release evidence

The candidate was built, assembled, validated, tagged, published and re-downloaded from one exact frozen `main` SHA: `ac328f0dffddb6b70fa7600f1291377376bc05d4`.

- Final Quality push run: `32682693020`, successful on Python 3.13 and 3.14.
- Final Windows x64 build run: `32683271942`, successful from the frozen SHA.
- Canonical build artifact: ID `9505311410`, `PlayStoreAppAudit-v1.8.0-windows-x64`, 179,954,097 compressed Actions bytes.
- Engineering release assembly run: `32684933669`, successful with the exact three-file ETB set from the same SHA.
- Canonical assembler artifact: ID `9505354895`, `PlayStoreAppAudit-v1.8.0-windows-x64-engineering-release-assets`, 106,488,770 compressed Actions bytes.
- Publication used authenticated direct GitHub Release creation after explicit tag verification; there is no separate v1.8 publication workflow/run.
- Annotated tag `v1.8.0` peels to the frozen SHA.
- The published Release is neither draft nor prerelease and was published on 2026-08-24.
- All three assets were re-downloaded into a fresh directory and independently verified after publication.
- The published v1.7.0 tag still peels to `e2d09098bc42c6f16d202d010deda3eb24d99aa3`; its three asset names, sizes and digests were rechecked unchanged.

Published project-defined assets:

- `PlayStoreAppAudit-v1.8.0-windows-x64.zip`: 33,450,079 bytes; SHA-256 `b056be21804d2c22483ebee14c2f2bcbee5611a36ad6c7fea51c3dd91043991d`
- `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz`: 73,128,136 bytes; SHA-256 `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e`
- `SHA256SUMS.txt`: 225 bytes; SHA-256 `09717c84a7096351dcc8ba91609146a877ffb2eee1184b34ccfea40c39bebb6b`

The downloaded Windows and source-archive hashes match `SHA256SUMS.txt`. Package validation confirmed PE AMD64/x64, standalone layout, application version `1.8.0`, Windows File/Product version `1.8.0.0`, intentional unsigned state, startup, legal/source material and exact-SHA provenance. Clean-profile, v1.7-profile upgrade, packaged smoke and normal startup checks passed. DPI-aware native Windows UI checks passed at logical client sizes 1100x700, 1200x760, 1500x900 and 1600x900.

### Post-release Actions housekeeping

Manual housekeeping run `32727364125` completed successfully from the frozen release SHA using the existing generational retention policy with a 7-day grace period.

- The apply run found no expired failed/cancelled runs, superseded successful runs or individual artifacts eligible for deletion.
- Active storage remains 10 artifacts / 573,766,431 bytes (547.19 MiB).
- The canonical v1.8 final build and assembler artifacts remain available for audit.
- The previous v1.7 canonical generation and two UI-style generations remain retained during the documented grace period; no manual deletion bypassed that policy.
- GitHub Release assets, tags, source commits and previous releases were not modified.
- Repository retention and the generational cleanup algorithm were not changed because no concrete policy failure was found.

## Current v1.9 release-candidate baseline

- Canonical current-source application version: `1.9.0`; derived Windows File/Product version: `1.9.0.0`.
- Latest published version remains immutable v1.8.0 until all v1.9.0 exact-SHA release gates pass.
- Current development cycle: v1.9.0 release readiness; the approved product/UX feature scope is closed.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1.
- Nuitka: 4.1.3.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers: 16.
- Store transport timeout: 25 seconds.
- v1.9 release target: Windows x64 only.
- v2.0 is the first planned return to multi-platform distribution. Production signing is preferred but not promised until provider, credentials, cost and end-to-end validation succeed.
- VS Code/Pylance Standard type checking is a local development check only; it does not change runtime, packaging or release configuration.

Always verify the live `main` SHA from GitHub or a freshly generated repository snapshot rather than treating this document as a branch pointer. The release SHA above remains immutable even when post-release documentation advances `main`.

## Shipped in v1.8.0

- Shared local action-availability predicates and synchronized menu/button/context states, including incompatible-operation blocking for Advanced Settings and Audit Profiles.
- One canonical CSV/HTML/versioned-JSON export definition shared by the File menu and main Export control.
- Consistent Title Case command naming, sentence-case explanatory tooltips and **Clear Results** terminology.
- Reduced permanent UI density by removing the classification legend and static table tip in favor of contextual help.
- Compact **Details** control and **View > Details Panel** menu with Auto, Right, Below and Hidden modes plus persistence.
- Separate Display Settings for App Icons, Date Format and Custom Columns.
- Reorganized Advanced Settings with Store & Cache, Device, Audit & History, and Data & Storage categories while preserving existing settings/services.
- Play Store icon graduation and cache/CDN/offline/large-table hardening, with bounded pending requests, decoded memory and persistent storage.
- Saved Smart Queries using the approved one-level All/Any model, curated fields/operators, versioned persistence and session-only active state, kept separate from Quick Filters and Audit Profiles.
- Informational product tagline in repository description, README and About without adding permanent operational UI.
- Preservation of active operational status messages when presentation-only filters and display/layout commands are used.

The implementation and stabilization work merged normally through PRs `#105`-`#113`; release preparation merged through PR `#114`. No broad architecture rewrite, global Fluent redesign, docking framework or new UI dependency was introduced.

## v1.9 direction

v1.9 remains Windows x64 only. Its first approved implementation scope merged through PR `#116` as one grouped presentation-consistency change covering:

- one friendly Notes presentation shared by the table, Details Panel and HTML report, with a complete Notes tooltip and unchanged raw-data/Smart Query semantics;
- **Maintenance Score** user-facing terminology while compatibility-sensitive `health_score` identifiers and the algorithm remain unchanged;
- warning-palette foreground highlights for version differences and aging/legacy Android targets;
- improved About hierarchy;
- coordinated project-owned QPainter icons for Choose File, Scan Phone and Export Results;
- the Display Settings populated-table crash fix, safe presentation refresh, Custom preset synchronization and preservation of selection, Details content and column widths across changes and restart.

The subsequent native Windows prototype merged through PR `#117` and added a third automatic Details Panel state at wide Below-mode viewport widths. The internal layout now enters extra-wide at 1180 px and exits at 1080 px, preserving the existing 760/680 px narrow/wide hysteresis. Its three columns group Store/Notes, Installed/Changes and Store evidence/diagnostics; decisions continue to use the actual scroll viewport, require no preference or persistence migration, and preserve the outer Auto/Right/Below/Hidden behavior. Width-aware minimum heights make compact panels scroll instead of clipping wrapped content.

The complementary native `QStatusBar` implementation merged through PR `#118`. It hosts the same existing operational `status_label` as an expanding left item and the same existing progress bar as a compact 200 px right item, so there is still one status channel and one progress widget. Progress is visible only during active source, audit or finalization work; idle, completion and failure states keep the status message without a stale bar. The main action row now contains Run, Export Results and Clear Results only. Existing source/device identity remains outside the status bar, the native size grip is retained, and there is no new preference, persistence state or Details Panel role.

PRs `#116`, `#117` and `#118` are merged and accepted. No further v1.9 product features are planned; current work is limited to version freeze, release documentation, validation and genuine release blockers.

`QDockWidget` and richer dashboard experiments are deferred to v1.99 and require a demonstrated benefit. A global Fluent redesign, an unnecessary icon library, broad architecture/type refactors and an internal `health_score` migration remain outside v1.9 scope.

v1.99 is the likely final Windows x64-only pre-v2.0 release. It is intended to close meaningful outstanding work rather than expand without control.

## v2.0 direction

v2.0 is the first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 release distribution. Ideally Windows and macOS packages will use production-trust signing/notarization, but this remains contingent on real credential/provider eligibility, cost and successful end-to-end validation. CLI/headless work remains v2.0-or-later scope.

## Explicitly removed / not planned

Do not reintroduce without a new explicit product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country-set presets.

## Durable release and repository invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only; no squash/rebase project history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- Quality validation comes before freezing a release SHA; tag only after artifact validation; tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- Every release finishes `RELEASE_CLOSURE.md`, including post-release context updates, safe local VS Code synchronization and a handoff generated from clean synchronized `main`.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `HANDOFF_V1.8.md` and `HANDOFF_V1.9.md` for durable policy, release history and continuation context.
