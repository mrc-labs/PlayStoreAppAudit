# Play Store App Audit v1.99 Chat Handoff

Last updated: 2026-08-29

Status: **v1.9.0 is published, independently verified and immutable. Post-release housekeeping is complete. v1.99 implementation is active: cooperative audit Stop is merged on `main`; local product gates have productionized C2, semantic warnings and the F-Droid/Aptoide alternative-distribution evidence phase. Remote activity remains frozen until explicitly resumed.**

## Start here

Read this file with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `RELEASE_CLOSURE.md` and the generated `REPOSITORY_SNAPSHOT.md` in a current handoff package.

Before changing anything:

1. verify the live GitHub `main`, open-PR, release and branch state;
2. run `git status --short` and stop if the local working tree is dirty;
3. on a clean checkout, fetch/prune, switch to `main` and pull with `--ff-only`;
4. verify local `HEAD` equals `origin/main` and read the current roadmap/decisions;
5. inspect the complete relevant implementation and tests before modifying code;
6. do not modify, rebuild, retag or replace v1.9.0, v1.8.0 or any earlier published release.

The immutable v1.9 release SHA is not expected to equal later post-release documentation `main`. Always distinguish release lineage from current repository context.

## Latest immutable release

- Release/tag: `v1.9.0`
- Published: `2026-08-25T02:51:42Z`
- URL: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.9.0
- Release ID: `376114171`
- Title: `Play Store App Audit v1.9.0 (Win x64 Only)`
- Profile: intentionally unsigned Windows x64 Engineering Test Build, Nuitka standalone ZIP
- Frozen source SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`
- Annotated tag object: `e61033f0ffba3d14f598da4d928aa07390dbbfa9`
- Tag peel target: exact frozen source SHA
- Application version: `1.9.0`; Windows File/Product version: `1.9.0.0`
- Canonical Quality run: `32797795985`, passed on Python 3.13 and 3.14
- Canonical Windows x64 build run/artifact: `32798334950` / ID `9546290578`, `PlayStoreAppAudit-v1.9.0-windows-x64`
- Canonical engineering assembler run/artifact: `32801220807` / ID `9546545528`, `PlayStoreAppAudit-v1.9.0-windows-x64-engineering-release-assets`

Published assets, all independently re-downloaded and verified:

- `PlayStoreAppAudit-v1.9.0-windows-x64.zip` — ID `528529615` — 33,477,938 bytes — SHA-256 `74db811d959a06709aba4d747873ec1b19894e50ba7183f463f7929b44e19c68`
- `PlayStoreAppAudit-v1.9.0-third-party-sources.tar.xz` — ID `528529608` — 73,128,144 bytes — SHA-256 `ccccbd72992bed8692388077fd409dc76bb8f64efce8fa2ef283b74797a4df95`
- `SHA256SUMS.txt` — ID `528529607` — 225 bytes — SHA-256 `eb2b5f6d5a8fe978e54367b887c65d77994307447154435e3b3ae81c4bf2bd23`

Package validation confirmed PE AMD64/x64, application 1.9.0, Windows File/Product 1.9.0.0, standalone content, intentional unsigned state, startup, legal/source material and exact-SHA provenance. Clean extracted packaged smoke passed before tagging and again after public re-download with isolated data directories; the ZIP checksum remained canonical.

## Actions state after v1.9

Post-release housekeeping run `32805211585` passed from the frozen SHA using the unchanged seven-day generational policy.

- No run or artifact was eligible for deletion.
- Active state: 10 artifacts / 574,199,782 bytes (547.60 MiB).
- Retain v1.9 build artifact `9546290578` and assembler artifact `9546545528` as canonical audit evidence.
- v1.8 build/assembler and two UI-style predecessor generations remain in grace.
- No manual deletion, retention-policy change, build, assembler or release mutation occurred during housekeeping.

## Current technical baseline

- Current source application version remains `1.9.0`; no v1.99 version bump has occurred.
- Python packaging baseline: 3.13; Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`; `cryptography==50.0.1`; `Nuitka==4.1.3`.
- UI: Qt 6 / PySide6 Qt Widgets with platform/default QStyle.
- Google Play access remains behind services; UI must not absorb Store/device/business behavior.
- Managed ADB is read-only with respect to installed Android apps.
- Store workers default/recommended 16; Store timeout 25 seconds.
- Basic view remains compact; advanced behavior remains separated.
- Presentation-only changes must not overwrite active operational status.
- No broad architecture, inheritance, typing, theme or dependency rewrite is authorized by v1.99 planning.

## Shipped v1.9 UX baseline to preserve

- Friendly Notes presentation is shared across the table, full tooltip, Details and HTML report; raw Notes remain intact in machine-readable exports/data and persisted query compatibility.
- **Maintenance Score** is the user-facing name; `health_score` remains the compatibility-sensitive internal identifier.
- Warning values **Different**, **Aging target** and **Legacy target** use the canonical warning foreground palette.
- Display Settings safely refreshes populated/sorted/filtered tables and keeps Custom preset, checkboxes, real columns, widths, selection and Details state synchronized across restart.
- Details uses Auto/Right/Below/Hidden outer placement and viewport-based narrow/wide/extra-wide inner responsiveness with 760/680 and 1180/1080 px hysteresis.
- The native status bar owns the same canonical status label and progress widget; progress is active-only, source/device identity is not duplicated, and the native size grip is enabled.

## v1.99 scope boundary

v1.99 is likely the final Windows x64-only ETB before v2.0. It closes meaningful pre-v2.0 work and concrete v1.9 use findings; it is not an open-ended feature release. Split implementation into reviewable PRs with local validation before pushes. Do not start multiple high-risk product changes in one PR.

## Priority 1: cooperative Stop/Cancel

Complete on current `main` through PR `#122`, merge SHA `c5322d42a7ebdd0f7e61fd1c25b69828d8535e25`. The application now provides Run -> Pause/Resume -> Stop with cooperative cancellation.

Required behavior:

- stop scheduling new work immediately;
- propagate cooperative cancellation through Store checks, regional checks and finalization queues;
- allow in-flight work to exit safely or reach existing timeout boundaries;
- never use `QThread.terminate()` or equivalent forced termination;
- preserve already completed valid results and independently valid cache entries;
- clearly mark the audit cancelled/incomplete rather than completed;
- never promote an incomplete audit to the completed previous-audit/history baseline;
- return to a reusable idle state and allow another audit to start normally.

The implementation and regression coverage identify the Store/fallback scheduling, pause/resume, finalization, failure, clear/restart and subsequent-audit boundaries. Preserve this behavior during later v1.99 product work.

## Priority 2: comparative main-action layout review

Complete locally. Native-Windows A/B/C comparison selected the integrated results/header direction. A focused C0/C1/C2 comparison then selected **C2**.

Compare native-Windows prototypes with screenshots/evidence at representative widths and DPI levels:

- Prototype A: Run/Pause/Stop, Export and Clear in the status bar.
- Prototype B: compact upper action toolbar/command strip above results.
- Prototype C: integrated results/header-area commands if clear and uncluttered.

The production order is Run/Pause/Resume, Stop, the canonical progress widget, Export Results and Clear Results. Run and Stop remain grouped. Progress is permanently reserved at 120-320 px so command geometry does not move between Idle, Running, Paused, Resumed, Stopping, Finalizing and Completed. Idle/completed progress is neutral and empty; active determinate/busy behavior is unchanged. The prototype selector, runner and prototype-only tests were removed after selection.

## Priority 3: Details selector and status-bar presentation

Complete for the first product gate. The second results header row keeps multi-select status chips, Hide System Apps, search and the same Details selector. Auto/Right/Below/Hidden remains one state synchronized with `View > Details Panel`; there is no status-bar duplicate. The native status bar keeps the canonical operational text and size grip, with no progress or primary commands added there.

## Priority 4: semantic warning typography

Complete locally. One pure semantic presentation mapping now serves the results table, selected-row Details Panel, context Details dialog and user-facing HTML report.

- **Different** and **Aging target**: existing dark-yellow status foreground, Qt Medium weight 500.
- **Legacy target**: existing dark-orange status foreground, Qt DemiBold weight 600.
- Normal values: normal weight with no warning colour.
- Status column: remains Bold weight 700.
- Selected rows: Qt continues to manage the selection background; the semantic foregrounds remain readable without selection-specific colours.
- Disabled labels: the native disabled-text palette role is retained.
- CSV, versioned JSON, raw data, classifications, scoring, settings and schemas: unchanged.

The application retains its established light presentation; this gate does not add or claim a new dark theme.

## Priority 5: Alternative Distribution Discovery

Complete locally as Gate 4. This is secondary exact-package evidence only and never reinterprets Google Play state, installer source, criticality or Maintenance Score.

- Eligibility is exactly raw `play_status == "not_found_in_checked_countries"`; all available/regional/transient/inconclusive states are skipped.
- F-Droid main is built in and default-enabled, using only the official active per-package API. Exact ID is mandatory; the archive, search, full index, third-party repos and APK URLs are not used.
- Aptoide is Advanced/opt-in and default-disabled. It requires an authorized `store_name` and Partner API key, sent only via the documented `Authorization: ApiKey …` header to exact `app/get` requests. The API does not document a reliable public listing URL, so none is fabricated.
- One non-pluggable protocol and typed Available/Not found/Inconclusive/Unsupported/Not checked result model are shared by orchestration, caching, Details, App Details, HTML and JSON.
- One independent provider executor is capped at two total requests, with 10-second request timeouts and a 20-second phase budget. Pause blocks new submissions; Resume continues; Stop prevents new submissions and retains completed evidence. Provider failure never fails successful Google Play work.
- The separate `alt-v1` cache uses 24-hour Available, 12-hour Not found and 15-minute Inconclusive TTLs, includes normalized Aptoide store name without the key, and is bypassed by Force Full Refresh. There is no provider history.
- Aptoide's saved key uses a versioned AES-GCM/HKDF-SHA256 envelope bound to a local machine-identity digest and local user. This deters casual config disclosure/copying only; it is not OS/hardware/compromised-account security. Identity or authentication failure retains the ciphertext and requires key replacement.
- Advanced Settings includes F-Droid/Aptoide controls, masked Replace/Remove/Test connection actions and an expandable provider limitations panel. Samsung, Huawei, Amazon, APKMirror, APKPure and Uptodown are not supported; no scraping is used.
- Provider evidence is separate in Details/App Details and conditional HTML. JSON is explicit schema v2 with ordered `alternative_distribution.providers`; CSV, table columns/filters, Friendly Notes, history and scoring remain unchanged. Credentials, envelopes and machine identity never enter exports or diagnostics.

## Priority 6: Maintenance Score algorithm

The user-facing concept remains **Maintenance Score**. Approved target penalties:

- Removed with no verified alternative distribution: `-60`
- Removed with only an APK repository: `-50`
- Removed with an independent store: `-45`
- Removed with a FOSS repository: `-40`
- Removed with at least one official OEM store: `-20`
- Store anomaly: `-20`
- Other/inconclusive Google Play state: `-15`
- stale listing, more than 730 days: `-25`
- aging listing, more than 365 and no more than 730 days: `-15`
- legacy target SDK relative to the connected device: `-15`
- aging target SDK relative to the connected device: `-10`
- installed version differs from Google Play: `-5`

Scoring semantics:

1. Removed/alternative penalties are mutually exclusive alternatives for one Google Play availability component. Never apply `-60` and then an alternative penalty.
2. With multiple verified providers, select the best class: `official_store > foss_repository > independent_store > apk_repository`. Do not stack providers.
3. Other independent score components continue to compose; keep existing bounds/clamping unless a real defect is found.
4. Failed queries or inconclusive evidence never count as positive availability evidence.
5. Regional unavailability is not automatically Removed. Discovery may run, but Removed substitutions apply only if the underlying Google Play state genuinely qualifies.
6. Review persisted history/versioned-data implications before implementation so score changes do not silently corrupt comparisons.
7. Update all user-facing methodology/help/report text and tests with the algorithm.

An internal `health_score` -> `maintenance_score` rename is separate and evidence-gated. Any migration must explicitly cover saved Smart Query IDs, settings, serialized/versioned data, backward compatibility and migration tests. It may remain deferred.

## Evidence-gated/rejected UI items

- Richer dashboard/status overview: implement only if a prototype proves a distinct workflow beyond Summary, status chips, Quick Filters, Smart Queries, Changes, Details and the improved status bar.
- `QDockWidget`: rejected/not planned. Do not prototype it. Retain Auto/Right/Below/Hidden and narrow/wide/extra-wide Details behavior.
- Concrete bugs/workflow problems/polish found through real v1.9 use: assess each against scope; do not automatically accept everything.

## Mandatory v1.99 user-tested RC

v1.99 authorizes one additional packaged acceptance candidate before public release:

1. reach feature-complete candidate state;
2. freeze an RC candidate;
3. build a real Windows x64 packaged RC;
4. provide it for thorough user acceptance testing;
5. collect real-use corrections and merge focused corrective PRs if required;
6. if source changes, the RC SHA/artifact is not final;
7. freeze a new final exact `main` SHA only after acceptance;
8. run final Quality;
9. build the canonical final Windows x64 package;
10. assemble and publish normally.

Never create a public RC tag or publish an earlier candidate after source changes.

## v2.0 roadmap

Preserve the established v2.0 goals:

- Windows x64 and ARM64;
- Linux x64 and ARM64;
- macOS x64 and ARM64;
- production signing/notarization if feasible and fully validated;
- CLI/headless support built on domain/service layers rather than driving Qt.

Add a major v2.0 pillar: **Local APK Library / modern LocalAPK successor core**.

Initial v2.0 scope:

- scan one or more local APK directories recursively;
- parse package ID, app label, versionName/versionCode and useful SDK/icon/file/path metadata where practical;
- compare local versions with Google Play and Alternative Distribution Discovery when appropriate;
- reuse classification, evidence, Details, filters, Smart Queries, export/reporting and service/domain boundaries.

Do not duplicate existing CSV/export capability. Portable/local workflow already exists and is not a new feature. ADB remains read-only unless a future explicit decision authorizes install/write behavior.

Later 2.x candidates, not mandatory v2.0 scope: metadata-template mass rename, duplicate detection/management, safe previewed outdated-APK cleanup, custom commands/integrations, Windows Explorer integration and other library-management improvements after the core is stable.

## Validation and release budget

- Normal source PRs: compileall, full pytest, Ruff, canonical Qt offscreen smoke and relevant targeted checks.
- Use native Windows evidence for UX changes where required.
- Do not run Nuitka for documentation, planning, ordinary narrow UI polish or housekeeping.
- Package only when the change genuinely requires runtime evidence, at the mandatory v1.99 user-tested RC, and at the final exact-SHA release gate.
- Keep strict legal/source and exact-SHA validation fail-closed.
- Do not create public RC tags.

## Repository and handoff rules

- `main` is the only permanent branch; use short-lived branches and normal merge commits.
- Never squash/rewrite published project history.
- Before pulls, require a clean tree; never auto-stash/reset/discard user work.
- Complete releases through `RELEASE_CLOSURE.md`.
- `scripts/export_chat_handoff.ps1` numerically selects `HANDOFF_V1.99.md` over `HANDOFF_V1.9.md`; no script change is required.
- Generate the next handoff ZIP only after the closure PR is reviewed and merged, local VS Code `main` is safely synchronized to canonical remote `main`, and the tree is clean.
