# Play Store App Audit v1.8 Chat Handoff

Last updated: 2026-08-24

## Purpose

This is the canonical human-readable handoff for the completed v1.8 product cycle and v1.8.0 release preparation after successful publication of v1.7.0. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `RELEASE_CLOSURE.md`.

## Immutable v1.7.0 baseline

- Release: `v1.7.0`
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`
- Release class: unsigned Windows x64 Engineering Test Build (ETB)
- Frozen source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`
- Quality push run: `32609018096`
- Final Windows x64 build run: `32609148943`
- Engineering assembly run: `32610281618`
- Publish/post-publication verification run: `32610914851`

Published project-defined assets:

- `PlayStoreAppAudit-v1.7.0-windows-x64.zip` — SHA-256 `142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz` — SHA-256 `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458`
- `SHA256SUMS.txt` — SHA-256 `984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9`

The annotated `v1.7.0` tag peels to the frozen SHA and all three public assets were re-downloaded and checksum-verified after publication. Do not rebuild, retag or replace them.

On 2026-08-24 the v1.8 startup housekeeping revalidated that lineage, retained the canonical build artifact from run `32609148943` and assembler artifact from run `32610281618`, and deleted only redundant Actions copies from later runs `32610281923` and `32610918196`. Active artifact storage fell from 10 artifacts / 546.82 MiB to 8 artifacts / 274.01 MiB. The tag and three published Release assets remained unchanged; retention policy was not modified.

## Current technical baseline

- Canonical app version is `1.8.0` in the dedicated release-preparation change.
- Python packaging baseline: 3.13; Quality CI: 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle.
- ADB remains read-only with respect to installed Android apps.
- Google Play remains behind the service boundary.
- Store workers default/recommended 16; allowed advanced range 4-32; Store timeout 25 seconds.
- v1.8 and v1.9 releases are Windows x64 only and intentionally unsigned unless a new explicit product decision changes that.
- v2.0 is the first planned return to multi-platform distribution; production signing is an ideal target but is not guaranteed until real provider/credential and end-to-end validation succeeds.
- VS Code/Pylance Standard type checking is enabled locally as an additional development check. It does not alter runtime, build or release behavior and does not authorize a mass typing refactor.

## v1.7 features available as the v1.8 base

- responsive Details Panel with Auto/Right/Below placement and adaptive content layout;
- independent Store country/language semantics;
- structured Store evidence with concise user-facing diagnostics/Notes;
- installer/source classification and filters;
- SDK maintenance filters;
- versioned JSON export;
- saved audit profiles;
- conservative smart/incremental re-audit plus targeted rechecks and Force full refresh;
- separate Store-audit and phone-inventory history semantics;
- optional supported Health Score maintenance heuristic, disabled by default.

## v1.8 completed release scope

The complete UI audit, approved implementation and final stabilization review were completed on 2026-08-24 through small, verifiable PRs without a broad architectural or visual rewrite. No new feature work belongs in the v1.8.0 release candidate.

### UX consistency and action availability

- Use shared local predicates for idle, source, device-inventory, result, visible-result, row/field and running-operation capabilities.
- Synchronize menus, buttons and context menus from those predicates without adding a broad state-machine layer.
- Use one canonical CSV/HTML/versioned-JSON export structure across the File menu and main Export control.
- Normalize command naming in Title Case and tooltip explanations in sentence case.
- Remove permanent chip legends and tips where contextual help preserves discoverability with less occupied space.

### Play Store icons

Graduate Play Store icons from experimental to normal supported behavior, subject to final cache/CDN/offline/large-table hardening from v1.7 observations.

### Smart Queries

Implement reusable result-only filters, deliberately separate from saved Audit Profiles. The seven decisions in `SMART_QUERIES_UX_REVIEW.md` were explicitly approved on 2026-08-24: **Quick Filters** names the built-ins; Smart Queries use one-level All/Any conditions, curated fields/operators, one native builder/manager, versioned `smart_queries` persistence and session-only active state. There is no automatic migration of legacy `saved_filters`, and the completed query is ANDed with all existing result filters without affecting audit execution, ADB, Store lookup or cache behavior.

Permanent v1.8 guardrails exclude nested groups, scripting, regular expressions, import/export, automation and any shared Audit Profile commands or permanent main-table control.

### Details Panel UX v2

Replace the current Auto/Right/Below buttons with one compact control whose visible text is **Details**:

- support Auto, Right, Below and Hidden;
- use **Details Panel** in the View menu where the longer label improves clarity;
- persist the mode and return the full splitter area to the table while Hidden;
- keep platform-native Qt styling and avoid unnecessary theme dependencies;
- do not use `QDockWidget` or a new UI framework.

### Display and Advanced Settings

Move App Icons, Custom Columns and Date Format to Display Settings under View. Improve the remaining Advanced Settings hierarchy with lighter native Qt sections for Store & Cache, Device, Audit & History, and Data & Storage while preserving current services, warnings and persistence. Health Score remains in Audit. Use a simple `QStackedWidget`/category navigation only if it remains natural for a Windows desktop dialog after visual preferences are removed.

### Targeted iconography and product identity

Replace only confusing or obsolete icons and do not add an icon framework or perform a global visual redesign. Keep the official product name **Play Store App Audit** and add **Android App Inventory, Store Analysis & Maintenance Toolkit** to the repository description, README and About dialog. In About, keep product name, version, tagline and description in that order, with a non-dominant tagline. Do not place it in the operational main window.

### Actions housekeeping and build budget

Identify canonical release runs and remove only redundant Actions artifacts after verification. Do not delete published Release assets, tags or release sources and do not add complex tracking. Retention changes are optional and require concrete evidence of a policy or implementation problem.

Use compileall, pytest, Ruff, lightweight Qt smoke and targeted static checks for normal code PRs. Do not dispatch Windows/Nuitka builds for docs-only, product identity, naming, icon polish or housekeeping work. Run manual Windows checks at 1100x700, 1200x760, 1500x900 and 1600x900 only for high-impact UI milestones. Reserve Nuitka for the deliberately frozen release candidate unless an exception is explicitly justified.

## Deferred UX evaluation

Evaluate a complementary `QStatusBar`, a separate docking/`QDockWidget` prototype and a richer dashboard/status overview no earlier than v1.9. A status bar must not replace the Details Panel. A global Fluent-style redesign remains outside approved scope.

## Approved v1.8 PR sequence

1. `docs/v1.8-scope-lock-and-identity`
2. `chore/v1.8-actions-housekeeping`
3. `fix/v1.8-action-availability-and-export`
4. `ux/v1.8-naming-density-icons`
5. `feature/v1.8-details-control`
6. `feature/v1.8-display-and-settings`
7. `ux/v1.8-play-store-icons-and-smart-query-design`
8. `feature/v1.8-smart-queries`, after explicit approval of the separate UX review
9. `release/v1.8.0`, only after the approved scope is complete

PR1 was merged normally as GitHub PR `#105` at merge commit `d821e01dc320ed24e086164163ad855753f519fd`. It synchronized the approved scope and product identity; the GitHub repository description now uses the official tagline.

PR2 was merged normally as GitHub PR `#106` at merge commit `74ca06caca927ef21f43702dc8b35115ba101d33`. It completed the evidence-based v1.7 Actions cleanup without changing retention policy or immutable release material.

The action-availability/export implementation centralizes the final UI capability checks for loaded source, device inventory, all/visible results, row fields and running operations. The File menu and compact Export control now use the same explicit CSV/HTML/versioned-JSON action definition and handlers; row context actions are disabled when their required field or idle state is unavailable.

The naming/density/icon implementation applies consistent Title Case to operational commands, buttons and table headings while keeping explanatory tooltips in sentence case. It removes the permanent classification legend and table tip in favor of contextual help on classification chips, the table header and the table itself. The misleading computer icon was removed from Scan Phone; familiar native Open, Save and Play icons remain. A local Windows-native 1200x760 capture verified the resulting density and alignment without dispatching an Actions UI/build workflow.

The Details Panel implementation replaces the three permanent position buttons with one compact **Details** menu that is also exposed as **View > Details Panel**. Its shared Auto, Right, Below and Hidden actions keep menu/control check state synchronized, persist one normalized setting and provide icons, tooltips and accessible text. Hidden only hides the existing splitter child and returns the full result area to the table. Native Windows captures verified Auto/Hidden behavior at 1100x700, 1200x760, 1500x900 and 1600x900; no docking framework or packaging change was introduced.

The settings hierarchy implementation adds **View > Display Settings** for App Icons, Date Format and Custom Columns. **Tools > Advanced Settings** now uses a small native category list with Store & Cache, Device, Audit & History, and Data & Storage pages instead of the previous long GroupBox stack. Health Score remains in Audit & History, the expert warning remains visible, and existing setting keys and side effects are unchanged. Tests enforce the presentation/technical boundary and preservation of stored display values; native Windows checks covered both dialogs and all categories at 1100x700, 1200x760, 1500x900 and 1600x900 without dispatching a Nuitka build.

Play Store icons have completed the v1.8 graduation/hardening pass while remaining optional and disabled by default. The loader creates networking only after a disk miss, caps pending requests and decoded RAM, and stops oversized transfers. The persistent cache rejects unsafe paths and oversized files, prunes corrupt/orphaned entries, and is bounded to 512 entries / 64 MiB while retaining update-marker/CDN reuse and offline hits. Package-indexed notifications avoid scanning the full result model per icon; tests cover 10,000 rows.

The Smart Queries UX/design review in [`SMART_QUERIES_UX_REVIEW.md`](SMART_QUERIES_UX_REVIEW.md) is approved and its bounded model is implemented in the dedicated `feature/v1.8-smart-queries` workstream. **View > Quick Filters** contains the built-ins; **View > Smart Queries** exposes New, Manage, Clear and saved definitions without a permanent toolbar control. The native builder/manager supports 1-20 one-level All/Any conditions, Save without Apply, draft Apply without Save, case-insensitive replacement confirmation and deletion confirmation. Saved definitions use versioned `smart_queries` settings, active state stays in memory for the current session, and deleting an active saved definition clears it. Evaluation is pure inside the existing proxy and composes with search, status chips, system visibility, Quick Filters and the SDK Maintenance Filter. Audit Profiles, legacy `saved_filters`, audit execution, Store lookup/cache and ADB behavior remain separate and unchanged. Tests cover normalization, every operator family, missing/invalid values, persistence/CRUD, action availability, accessibility, composition and 10,000 rows with 20 conditions. Windows-native dialog checks cover 1100x700, 1200x760, 1500x900 and 1600x900; no Actions packaging or Nuitka build was dispatched.

PR `#113` completed the final stabilization pass at merge commit `35a2572a997d36af01cb018a45e49a1112a1172c`. Advanced Settings and Audit Profiles are blocked only during incompatible running operations; presentation-only Quick Filters, SDK filtering, Display Settings and table-layout reset preserve operational messages; and the result-clearing action is consistently named **Clear Results**. The post-merge Quality run and local compileall, Ruff, pytest and Qt smoke checks passed without a Nuitka build.

## v1.8.0 release preparation state

- Product and stabilization scope is closed through PRs `#105`-`#113`.
- The dedicated `release/v1.8.0` change updates canonical version metadata to `1.8.0`, release assertions and only the required current release documents.
- About, Qt application metadata and Windows package metadata derive from the canonical version; the Windows file/product version must therefore be `1.8.0.0`.
- README remains a correct description of the latest published release (`v1.7.0`) until v1.8.0 is actually published.
- No Nuitka, packaging, assembler, tag or publication action is part of release preparation.
- After the normal release-preparation merge and successful post-merge Quality run, record that exact full `main` SHA as the frozen candidate. Any later source or release-tooling change invalidates it and requires a new freeze and rebuild.

## v1.8.0 release execution checklist

### Candidate freeze

- [ ] Merge the release-preparation PR into `main` with a normal merge commit; do not squash or rebase.
- [ ] Before pulling locally, verify `git status --short` is empty; then fetch/prune, switch to `main` and pull with `--ff-only`.
- [ ] Confirm local `HEAD` equals `origin/main`, no PR remains open and annotated tag `v1.7.0` still peels to `e2d09098bc42c6f16d202d010deda3eb24d99aa3`.
- [ ] Require the post-merge Quality workflow to pass on Python 3.13 and 3.14.
- [ ] Record the exact 40-character `main` SHA and Quality run ID; treat that SHA as frozen before any expensive work.

### Windows x64 build and Nuitka

- [ ] After explicit approval, dispatch `.github/workflows/build-windows-exe.yml` from the frozen `main` SHA with `target=x64` and `expected_sha=<frozen SHA>`.
- [ ] Do not dispatch Windows ARM64, signing, Linux or macOS workflows for v1.8.0.
- [ ] Require the workflow to use Python 3.13, `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3` and to reject any dispatch/checkout SHA mismatch before build work.
- [ ] Require the native x64 job, source checks, legal preflight, standalone validation and packaged smoke test to pass from that exact SHA.
- [ ] Record the successful `Build Windows - Qt6` run ID and retain its canonical x64 artifact for assembly/audit.

### Package verification

- [ ] Verify the archive is named `PlayStoreAppAudit-v1.8.0-windows-x64.zip`, has the expected standalone layout and contains an x64 `PlayStoreAppAudit.exe` rather than ARM64 or a one-file build.
- [ ] Verify application version `1.8.0`, Windows file/product version `1.8.0.0`, startup behavior, required Qt/Python runtime content and exclusion rules.
- [ ] Verify strict packaged legal notices, corresponding-source manifest/assets, `BUILD-INFO.txt`, repository/workflow/run provenance and exact frozen SHA.
- [ ] Re-extract the ZIP independently and verify the package checksum before using it as an assembler input.

### Clean use, upgrade and distributed smoke

- [ ] On a clean Windows x64 user profile or disposable VM, extract the standalone ZIP to a new directory, launch it and verify first-run behavior without relying on a development checkout.
- [ ] In a disposable copy of a real v1.7 data profile, launch v1.8.0 and verify existing display/technical settings, cache/history and Audit Profiles remain usable; confirm no automatic `saved_filters` to Smart Queries migration occurs.
- [ ] Confirm managed ADB discovery remains read-only and no test performs application mutation on a connected device.
- [ ] Run the distributed executable with `PLAYSTORE_APP_AUDIT_SMOKE_TEST=1` and require deterministic success, then perform a normal manual launch and close.
- [ ] Check the packaged UI at 1100x700, 1200x760, 1500x900 and 1600x900 for Details modes, dialogs, Smart Queries, clipping and resize regressions.

### Assembler, assets and publication

- [ ] Dispatch `.github/workflows/assemble-windows-engineering-release.yml` from the same frozen SHA with `expected_sha=<frozen SHA>` and `windows_run_id=<successful x64 build run>`.
- [ ] Require the assembler to validate source workflow identity, repository, manual-dispatch status, success and exact head SHA, accept only the canonical x64 artifact and reject ARM64 input.
- [ ] Require exactly `PlayStoreAppAudit-v1.8.0-windows-x64.zip`, `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` and `SHA256SUMS.txt`; verify every checksum independently.
- [ ] Replace all v1.8.0 release-note placeholders only with observed successful evidence.
- [ ] Only after artifact validation and explicit publication approval, create annotated tag `v1.8.0` on the frozen SHA and publish the already validated assets without rebuilding.
- [ ] Complete post-release Actions housekeeping without deleting Release assets, tags or source history, then complete `RELEASE_CLOSURE.md` and generate the next handoff only from clean synchronized `main`.

## v1.9 and v2.0 distribution roadmap

- v1.9: Windows x64 only; detailed product scope not frozen yet.
- v2.0: first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 prebuilt releases.
- Ideally Windows/macOS will be production signed/notarized in v2.0, but do not promise that until eligibility, credentials, cost and end-to-end workflows are validated.
- CLI/headless work remains v2.0-or-later.

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
- Windows x64 ETB GitHub Release titles now use `(Win x64 Only)`; body headings continue to identify `Engineering Test Build - Windows x64 Only`.
- Finish every release through `RELEASE_CLOSURE.md`, including post-release docs and safe local VS Code synchronization.

## Continuation and handoff generation

After each merged phase, synchronize the local VS Code checkout safely to canonical `main` and keep this handoff aligned with current facts. Do not generate a continuation ZIP from a feature branch. At release closure, generate the new handoff only from the clean synchronized `main` checkout using `scripts/export_chat_handoff.ps1`; it selects the newest `docs/HANDOFF_V*.md` and includes a freshly generated `REPOSITORY_SNAPSHOT.md`.
