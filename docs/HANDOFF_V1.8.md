# Play Store App Audit v1.8 Chat Handoff

Last updated: 2026-08-24

## Purpose

This is the canonical human-readable handoff for the v1.8 development cycle after successful publication of v1.7.0. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `RELEASE_CLOSURE.md`.

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

- Canonical app version remains `1.7.0` until a deliberate v1.8 release/version freeze.
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

## v1.8 active scope

The complete UI audit and final review were approved on 2026-08-24. Implement the reviewed direction through small, verifiable PRs and avoid architectural work motivated only by appearance.

### UX consistency and action availability

- Use shared local predicates for idle, source, device-inventory, result, visible-result, row/field and running-operation capabilities.
- Synchronize menus, buttons and context menus from those predicates without adding a broad state-machine layer.
- Use one canonical CSV/HTML/versioned-JSON export structure across the File menu and main Export control.
- Normalize command naming in Title Case and tooltip explanations in sentence case.
- Remove permanent chip legends and tips where contextual help preserves discoverability with less occupied space.

### Play Store icons

Graduate Play Store icons from experimental to normal supported behavior, subject to final cache/CDN/offline/large-table hardening from v1.7 observations.

### Saved filters / smart queries

Implement reusable result-filter expressions, deliberately separate from saved Audit Profiles. Before any code, approve a separate UX/design review covering the model, fields/operators, persistence and application workflow. The design review belongs in `ux/v1.8-play-store-icons-and-smart-query-design` and must not imply that Smart Queries are already implemented.

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
8. `release/v1.8.0`, only after the approved scope and any separately approved Smart Queries implementation are complete

PR1 was merged normally as GitHub PR `#105` at merge commit `d821e01dc320ed24e086164163ad855753f519fd`. It synchronized the approved scope and product identity; the GitHub repository description now uses the official tagline.

PR2 was merged normally as GitHub PR `#106` at merge commit `74ca06caca927ef21f43702dc8b35115ba101d33`. It completed the evidence-based v1.7 Actions cleanup without changing retention policy or immutable release material.

The action-availability/export implementation centralizes the final UI capability checks for loaded source, device inventory, all/visible results, row fields and running operations. The File menu and compact Export control now use the same explicit CSV/HTML/versioned-JSON action definition and handlers; row context actions are disabled when their required field or idle state is unavailable.

The naming/density/icon implementation applies consistent Title Case to operational commands, buttons and table headings while keeping explanatory tooltips in sentence case. It removes the permanent classification legend and table tip in favor of contextual help on classification chips, the table header and the table itself. The misleading computer icon was removed from Scan Phone; familiar native Open, Save and Play icons remain. A local Windows-native 1200x760 capture verified the resulting density and alignment without dispatching an Actions UI/build workflow.

The Details Panel implementation replaces the three permanent position buttons with one compact **Details** menu that is also exposed as **View > Details Panel**. Its shared Auto, Right, Below and Hidden actions keep menu/control check state synchronized, persist one normalized setting and provide icons, tooltips and accessible text. Hidden only hides the existing splitter child and returns the full result area to the table. Native Windows captures verified Auto/Hidden behavior at 1100x700, 1200x760, 1500x900 and 1600x900; no docking framework or packaging change was introduced.

The settings hierarchy implementation adds **View > Display Settings** for App Icons, Date Format and Custom Columns. **Tools > Advanced Settings** now uses a small native category list with Store & Cache, Device, Audit & History, and Data & Storage pages instead of the previous long GroupBox stack. Health Score remains in Audit & History, the expert warning remains visible, and existing setting keys and side effects are unchanged. Tests enforce the presentation/technical boundary and preservation of stored display values; native Windows checks covered both dialogs and all categories at 1100x700, 1200x760, 1500x900 and 1600x900 without dispatching a Nuitka build.

Play Store icons have completed the v1.8 graduation/hardening pass while remaining optional and disabled by default. The loader creates networking only after a disk miss, caps pending requests and decoded RAM, and stops oversized transfers. The persistent cache rejects unsafe paths and oversized files, prunes corrupt/orphaned entries, and is bounded to 512 entries / 64 MiB while retaining update-marker/CDN reuse and offline hits. Package-indexed notifications avoid scanning the full result model per icon; tests cover 10,000 rows.

The Smart Queries UX/design proposal is now in [`SMART_QUERIES_UX_REVIEW.md`](SMART_QUERIES_UX_REVIEW.md). It recommends typed one-level All/Any conditions, a curated field/operator set, View-menu application, a combined native builder/manager and versioned `smart_queries` settings storage with no automatic legacy `saved_filters` migration. These decisions remain unapproved. No Smart Queries production code has been implemented, and implementation must wait for explicit review.

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
