# Project Status

Last updated: 2026-08-23

## Published release

- Latest published version: `v1.7.0`
- Immutable release commit: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`
- Release-body heading: `Play Store App Audit v1.7.0 (Engineering Test Build - Windows x64 Only)`
- Public project-defined assets: exactly 3

Published v1.7.0 is immutable. Do not rebuild, retag, rewrite or replace its source commit, tag or assets. Earlier published releases remain immutable as well.

## v1.7.0 release evidence

The release was built, assembled, tagged, published and re-downloaded from one exact frozen `main` SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.

- Final Quality push run: `32609018096`, successful on Python 3.13 and 3.14.
- Final Windows x64 build run: `32609148943`, successful on the same frozen SHA.
- Engineering release assembly run: `32610281618`, successful with the exact three-file ETB asset set.
- Publish/post-publication verification run: `32610914851`, successful.
- Annotated tag `v1.7.0` peels to the frozen SHA.
- Published assets were re-downloaded and independently checksum-verified after publication.

Published project-defined assets and SHA-256 values:

- `PlayStoreAppAudit-v1.7.0-windows-x64.zip`: `142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz`: `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458`
- `SHA256SUMS.txt`: `984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9`

## Current development baseline

- Canonical application version: `1.7.0` until a deliberate v1.8 version freeze changes it.
- Active planning/development cycle: `v1.8`.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1.
- Nuitka: 4.1.3.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers: 16.
- Store transport timeout: 25 seconds.
- v1.8 release target: Windows x64 only.
- v1.9 release target: Windows x64 only.
- v2.0 is the first planned return to multi-platform distribution. Production signing is the preferred target but is not guaranteed until provider/credential and end-to-end validation succeed.

Always verify the live `main` SHA from GitHub or a freshly generated repository snapshot rather than treating this static document as a branch pointer.

## Shipped in v1.7.0

- Responsive Details Panel with Auto/Right/Below placement and adaptive content layout.
- Independent Store country and Store language resolution with host/device fallback semantics.
- Structured per-app Store evidence and compact diagnostics with human-readable Notes.
- Installer/source classification and filtering.
- target/min SDK maintenance filters and compatibility-state filtering.
- Versioned JSON export for all/visible results.
- Saved audit profiles separated from result-filter state.
- Conservative smart/incremental re-audit behavior plus targeted rechecks and Force full refresh.
- Clear separation of Store audit history from phone inventory history and first-baseline wording.
- Health Score promoted from experimental presentation to optional supported maintenance heuristic, still disabled by default.

Play Store app icons remain experimental in v1.7.0 and are carried into v1.8 for graduation/hardening.

## v1.8 planned scope

v1.8 is a Windows x64-only UX/productivity cycle.

- Graduate Play Store icons from experimental to normal supported behavior, with any cache/CDN/offline/large-table hardening indicated by v1.7 observations.
- Add saved filters / smart queries as reusable result-filter expressions, deliberately separate from audit profiles.
- Add a richer compact dashboard / summary that complements rather than duplicates details, changes and filters.
- Details Pane UX v2: allow hide/show and test replacing the three position buttons with one compact control/menu offering Auto, Right, Below and Hide.
- Treat an Excel-like bottom `QStatusBar` as an alternative UX experiment if the primary Details Pane control concept is not attractive; possible uses include connected device/source identity, transient status and compact secondary view controls.
- Review tooltip/statusTip consistency across icon-only and non-obvious controls; do not add redundant tooltips to already self-explanatory text buttons.
- Redesign Advanced Settings because the current stacked `QGroupBox`/form presentation looks dated; favor clearer category navigation and less visual chrome while retaining native Qt widgets.
- Perform a full menu/button/iconography/clarity audit and produce a report before implementing broad visual changes.
- Review export-menu consistency and context-menu enable/disable behavior as part of the UX audit.

## v1.9 distribution constraint

v1.9 is also Windows x64 only. Product scope is intentionally not frozen yet, but do not introduce Windows ARM64/Linux/macOS release packaging for v1.9 unless a new explicit product decision changes the roadmap.

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
- Every release finishes the permanent closure procedure in `RELEASE_CLOSURE.md`, including post-release context updates and safe local VS Code synchronization.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `HANDOFF_V1.8.md` for durable policy, planning and continuation context.
