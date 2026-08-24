# Project Status

Last updated: 2026-08-24

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

### Post-release Actions housekeeping

The v1.8 startup review revalidated the v1.7.0 release lineage on 2026-08-24. The canonical final build run remains `32609148943` and the canonical assembler run remains `32610281618`. Redundant Actions artifact copies from later runs `32610281923` and `32610918196` were deleted only after confirming the immutable tag and three GitHub Release assets were unchanged.

- Active Actions artifact storage fell from 10 artifacts / 546.82 MiB to 8 artifacts / 274.01 MiB.
- The canonical final Windows build artifact and canonical assembler artifact remain available for audit.
- The six small UI-style artifacts remain subject to the existing generational policy.
- Repository retention and the generational cleanup algorithm were not changed.

## Current release-candidate baseline

- Canonical application version: `1.8.0` in the dedicated release-preparation change.
- Active cycle: `v1.8.0` release preparation; product scope is closed.
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
- VS Code/Pylance Standard type checking is available as a local development check. It does not change runtime, packaging or release configuration and is not a mandate for broad typing refactors.

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

## v1.8 release scope

v1.8 is a Windows x64-only UX/productivity cycle. The complete UI audit, approved product implementation and final stabilization pass are complete. No new feature work belongs in the release candidate.

- Graduate Play Store icons from experimental to normal supported behavior, with any cache/CDN/offline/large-table hardening indicated by v1.7 observations.
- Add saved Smart Queries as result-only filters, deliberately separate from Audit Profiles, using the approved one-level All/Any model and curated field/operator list.
- Replace the permanent Auto/Right/Below controls with one compact **Details** control and expose **Details Panel** under View, supporting Auto, Right, Below and Hidden without `QDockWidget`.
- Correct action availability through shared local predicates for source, inventory, result, visible-result, row/field and running-operation state.
- Use one canonical CSV/HTML/versioned-JSON export structure across File and the main Export control.
- Apply the approved naming, tooltip, density and targeted iconography consistency pass without a global visual redesign or icon dependency.
- Move App Icons, Custom Columns and Date Format to Display Settings and improve the remaining Advanced Settings hierarchy while preserving services and stored settings.
- Add the official product tagline to the repository description, README and About dialog, keeping it informational and outside the operational main window.
- Perform simple Actions housekeeping around canonical release runs and post-release cleanup. Retention changes remain optional and require concrete evidence.

The richer dashboard/status overview, complementary `QStatusBar`, docking experiment and any global Fluent-style redesign are not v1.8 implementation work. The first three may be evaluated in v1.9; the global redesign remains outside approved scope.

Routine PR validation is limited to compileall, pytest, Ruff, lightweight Qt smoke and targeted static checks. Manual native Windows resolution checks are reserved for high-impact UI work. Do not dispatch full Windows/Nuitka builds for documentation, identity, naming, icon polish or housekeeping; Nuitka is reserved for the deliberately frozen release candidate unless an explicit exception is justified.

### v1.8 implementation progress

- Product identity and scope lock merged in PR `#105`; the repository description, README and About presentation use the approved informational tagline.
- Actions housekeeping merged in PR `#106`; redundant v1.7 artifact copies were removed after lineage verification, while retention policy and published release material remained unchanged.
- PR `#107` centralized action availability and made File/main-control CSV, HTML and versioned-JSON exports use one canonical definition.
- PR `#108` completed the naming, density and targeted iconography pass, including removal of the permanent classification legend/table tip and a Windows-native 1200x760 check.
- PR `#109` delivered the compact **Details** / **View > Details Panel** control with Auto, Right, Below and Hidden persistence. Native Windows captures covered 1100x700, 1200x760, 1500x900 and 1600x900.
- PR `#110` separated **View > Display Settings** from the four-category technical **Advanced Settings** hierarchy while preserving setting keys and side effects. Native Windows checks covered all target resolutions.
- PR `#111` graduated and hardened optional Play Store icons with bounded pending work, decoded RAM and disk storage, offline reuse, malformed-cache defenses and 10,000-row regression coverage; it also finalized the approved Smart Queries UX design.
- PR `#112` implemented the bounded Smart Queries model, native builder/manager, versioned persistence and composition with every existing result filter without affecting audit execution, Store behavior or read-only ADB.
- PR `#113` completed final stabilization: incompatible running operations block Advanced Settings/Audit Profiles, presentation-only commands preserve operational messages and the result-clearing label is consistently **Clear Results**.
- The dedicated `release/v1.8.0` preparation updates only release metadata, release documentation and release assertions. The exact frozen `main` SHA is recorded only after its normal merge and successful post-merge Quality run.

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
