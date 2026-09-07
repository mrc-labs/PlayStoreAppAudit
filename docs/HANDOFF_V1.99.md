# Play Store App Audit v1.99 Chat Handoff

Last updated: 2026-09-07

Status: **v1.9.0 is published, independently verified and immutable. v1.99 remains version 1.99.0. RC5 passed automated and user acceptance and is the accepted rollback/reference candidate. Phases A/B are accepted. Phase C optional full Scan passes source validation (699 tests on each required Python) and five-iteration benchmarks on the user's replacement Pixel 11 Pro/315-app device. The local `feat: add optional full scan enrichment` checkpoint is READY FOR RC6 BUILD as a source candidate; no package build or remote activity has occurred.**

## Start here

Read this file with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `RELEASE_CLOSURE.md` and the generated `REPOSITORY_SNAPSHOT.md` in a current handoff package.

During the current LOCAL-ONLY freeze, use branch `prototype/v1.99-native-actions` and verify the local Phase C commit subject `feat: add optional full scan enrichment`, whose parent is `f7d100d67697b947bea6f6dec7206516e0a41276`. Inspect local status/history/references only; do not fetch, pull, push, create PRs or mutate GitHub. Phase C does not package RC6; that is the next separately authorized session. Read the complete [SCANSESSION_PHASE_C_VALIDATION.md](SCANSESSION_PHASE_C_VALIDATION.md) before proceeding.

When a later session explicitly resumes the canonical remote workflow, before changing anything:

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

- Current source application version is frozen at `1.99.0` for release-candidate preparation.
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

v1.99 is feature complete and likely the final Windows x64-only ETB before v2.0. Stabilization and the mandatory packaged acceptance candidate must not reopen product scope. Any concrete acceptance correction remains a narrow, reviewable change with complete local validation.

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

Complete for the first product gate, with RC1 and RC3 Phase A acceptance corrections. The second results header row keeps multi-select status chips, Hide System Apps, search and the same Details selector. Auto/Right/Below/Hidden remains one state synchronized with `View > Details Panel`; there is no status-bar duplicate. The native status bar keeps the canonical operational text and size grip, with no progress or primary commands added there. Its full-width native frame remains edge-to-edge while the canonical text label has 16 logical px left and 12 logical px right contents margins. Phase A adds small symmetric vertical label padding and removes the residual card-era bottom gap through style/font-derived layout sizing; C2 horizontal geometry is unchanged.

## Priority 4: semantic warning typography

Complete locally. One pure semantic presentation mapping now serves the results table, selected-row Details Panel, context Details dialog and user-facing HTML report.

- **Different** and **Aging target**: existing dark-yellow status foreground, Qt DemiBold weight 600.
- **Legacy target**: existing dark-orange status foreground, Qt DemiBold weight 600.
- Normal values, including **Modern**: Regular weight 400 with no warning colour.
- Status column: remains Bold weight 700.
- Selected rows: Qt continues to manage the selection background; the semantic foregrounds remain readable without selection-specific colours.
- Disabled labels: the native disabled-text palette role is retained.
- CSV, versioned JSON, raw data, classifications, scoring, settings and schemas: unchanged.

The application retains its established light presentation; this gate does not add or claim a new dark theme.

## RC1 manual-acceptance corrections

The packaged RC1 from `7c3f2e768f5a6592e12a835b40a31d70a59e0bc6` passed technical validation but is not accepted as final. Native Windows 11 review at 175% scaling required these narrow corrections while retaining application version `1.99.0`:

- inset only the operational status label's contents, leaving the native status bar edge-to-edge and C2 untouched;
- promote **Different** and **Aging target** from Medium 500 to DemiBold 600 because Segoe UI/Qt rendered 500 indistinguishably from regular; keep **Legacy target** at 600, **Modern** at 400 and Status at 700;
- add `Tools > Data Maintenance > Clear Device Inventory History…`, which removes only separately keyed per-device comparison baselines; it preserves explicit Device Snapshots, Play Store audit cache, previous-audit history, provider cache, settings and current results;
- default **Show app icon** to on only when the preference is absent; existing saved on and off choices remain unchanged. Icon loading retains its existing lazy, cached, non-fatal behavior.

RC2 technical validation has passed; it is not the final accepted candidate.

## RC3 Phase A local-only stabilization

Phase A is deliberately limited to independent visual and device-summary UX corrections:

- one centralized semantic table-width policy classifies compact, medium, primary and bounded long-text columns without inspecting body values or using `ResizeToContents`;
- Maintenance Score remains compact, Store URL remains one line and bounded, and saved/manual header widths are restored after the final table-model replacement so they remain authoritative across restart;
- the table uses one font/style-derived header height with explicit two-line titles for **Maintenance Score**, **Installed vs Store**, **Android Compatibility**, **Device Inventory Change** and **Sensitive Permissions Count**; body-row height and native sorting remain unchanged;
- the native status bar remains edge-to-edge with its size grip and 16/12 logical px horizontal text insets, while symmetric vertical padding, explicit centering and removal of the residual central bottom gap make the footer compact without moving C2 operations;
- `Tools > Device Summary…` and its dialog are removed as redundant UI only; device-summary collection, snapshots, diagnostics, metadata, logs and exports remain available;
- connected-device source identity includes available Android version/API metadata without adding a serial number or permanent row; missing version/API parts are omitted and file sources are unchanged.

Phase A did not change Audit Profiles/Presets, Custom preset semantics, Smart Queries, SDK Maintenance Filter, full menu architecture, Export Results placement or Clear All Filters. Those remained outside that checkpoint. No RC3 package was built.

The Phase A source gate passed under Python 3.13.15 x64: focused coverage, the full 585-test suite, compileall, Ruff, `pip check`, `git diff --check` and both Qt offscreen smoke paths are green. Native Windows geometry also passed at 100% and actual 175% scaling for 1100, 1320 and 1600 logical px. No Nuitka/package build was run.

## RC3 Phase B1 local-only Column Presets

Phase B1 renames the user-facing preset submenu to `View > Column Preset` and the existing presentation dialog to `Customize View…`. Basic, Device and Technical remain immutable built-in layouts. Resizing or reordering the live header, or changing column visibility in Customize View, promotes the resulting layout to Custom without mutating the originating built-in. Custom is disabled until a real or conservatively migrated custom layout exists; later built-in selection, filtering, sorting, data refresh, audits and restart preserve it.

Custom owns only the table layout: `custom_view_columns` stores visible columns, `custom_view_order` stores full visual order, and `custom_view_widths` stores per-column widths. `custom_view_exists` distinguishes a real Custom layout from an absent default. `view_preset` remains the effective preset identifier. The existing `qt_header_state` and `qt_header_schema_version` remain a compatibility bridge for RC2/Phase A saved header state; valid legacy state is migrated without discarding widths/order, old explicit Custom visibility is retained where possible, and malformed/partial values fall back safely to Phase A semantic widths. Show app icon, date format and other presentation preferences remain global and are not copied into Custom.

## RC3 Phase B2 local-only audit configuration simplification

Phase B2 removes the dedicated `SDK Maintenance Filter…` and `Clear SDK Filter` surface plus its session-global result-filter hook. Inspection confirmed that the retired filter never used settings persistence or startup restoration: its only state was the in-process `SdkMaintenanceFilter(target_sdk_max, min_sdk_max, compatibility)` value. The hook is no longer installed, so seeded legacy-looking values are inert across restart and cannot leave a hidden filter active. The versioned JSON context retains its existing `filters.sdk` shape with neutral values to avoid an unrelated schema change. Target SDK, Min SDK and Android Compatibility collection, table/Details/export data, classification, Maintenance Score inputs and Smart Query fields remain unchanged; Smart Queries are now the advanced SDK/compatibility filtering mechanism.

The user-facing **Audit Profiles** name becomes **Audit Presets**, including `Save Current as Preset…` and `Manage Presets…`. The internal settings key remains `audit_profiles` and schema version remains 1. Existing names and execution settings remain loadable. Historical `view_preset` or nested filter/presentation fields may remain in the stored object, but preset application ignores them; new captures omit `view_preset`. Only source expectation, Store country/language and the existing cache, worker, device-enrichment, permissions, inventory/history and source-exclusion execution options apply. Search, status chips, Quick Filters, Smart Queries, retired SDK-filter values, Column Preset/Custom state, Details placement, app icons, date format and other presentation preferences remain unchanged.

Phase B2 did not perform the later final menu/source gate, add Clear All Filters, move Export Results, group Device History or build/package RC3.

The Phase B2 source gate passed under Python 3.13.15 x64: 167 focused tests and the full 601-test suite are green, together with compileall, full Ruff, `pip check`, `git diff --check`, the canonical Qt source smoke and deterministic Qt event-loop smoke. Phase A table/status/device behavior, Phase B1 Custom persistence and explicit app-icon-off semantics remain green. No Nuitka/package build was run.

The Phase B1 source gate passed under Python 3.13.15 x64: 75 focused tests and the full 596-test suite are green, together with compileall, full Ruff, `pip check`, `git diff --check`, the canonical Qt source smoke and the deterministic Qt event-loop smoke. Phase A wrapped-header, saved-width, compact status-bar and device-source regressions remain green. No Nuitka/package build was run.

## RC3 final local-only menu and source gate

The final top-level ownership is `File / Audit / View / Tools / Help`. File contains only source/input work, current phone-package-list export and Exit. Audit contains Run Audit, recheck, Force Full Refresh, execution-only Audit Presets, the canonical all/visible CSV/JSON/HTML result exports and Clear Results. Export Results is no longer duplicated under File; the Audit export actions and the C2 header export control retain the same established handlers and synchronized all/visible availability policy.

View owns Column Preset, Customize View, the synchronized Details Panel selector, the preserved distinct Reset Table Layout command, Quick Filters, Smart Queries and Clear All Filters. Clear All Filters resets only current result visibility: search, multi-status chip selection, Quick Filter, the active Smart Query and the session-only Hide System Apps checkbox. It does not change source-time system exclusion, results, sorting, saved Smart Queries, Audit Presets, caches/history, Column Preset/Custom visibility/order/widths, Details placement, app icons, date format or audit/store settings. The retired SDK filter has no runtime hook to reset. Operational/progress status remains authoritative while work is active.

Tools contains Advanced Settings, `Device History` and `Data Maintenance`. Device History groups the existing Device Snapshots submenu—preserving Save Current and Compare commands—with Device Inventory Changes. The three destructive clear actions remain together only under Data Maintenance. Help contains the ADB and app-list guides, Maintenance Score methodology, update/diagnostic actions and About. Device Summary and the SDK Maintenance Filter remain absent, and no stale Audit Profiles, View Presets or Display Settings label remains on the production menu surface.

The final source gate passed with 80 focused tests and 602 full tests on both Python 3.13.15 x64 and Python 3.14.6 x64. Compileall, full repository Ruff, helper compilation, `pip check`, PowerShell helper syntax, `git diff --check`, the canonical Qt source smoke and deterministic event-loop/source-entry smoke are green. The Phase A, B1 and B2 regression contracts remain covered. Native Windows review passed with the platform `windows11` QStyle at real 175% scaling and Qt-rendered 100% scaling for 1100, 1320 and 1600 logical px, including active C2/progress, menus and long labels, Details Auto, headers and the compact status bar. No Nuitka, package build or remote activity occurred.

## RC4 density failure and RC5 source checkpoint

RC4 itself built and packaged successfully. Its fresh packaged defaults also passed the mandatory pristine-Custom check across untouched restart: Basic remained active, `custom_view_exists` remained false and Custom remained disabled. Packaged acceptance nevertheless failed for one confirmed issue at native Windows 175% / 168 DPI: short-value columns consumed materially more horizontal space than their representative values required.

The local RC5 source checkpoint keeps the centralized compact/medium/primary/long-text policy and changes only short-value defaults. Last Update, Age (Days), Android Compatibility, Installed vs Store, Enabled State, Device Inventory Change, Maintenance Score, Target SDK, Min SDK, Sensitive Permissions Count, HTTP Status and System App now prefer 104, 78, 120, 116, 88, 130, 86, 74, 70, 124, 78 and 78 logical px respectively. Normal Segoe UI metrics produce those exact widths except Sensitive Permissions Count at 127 px to retain its accepted two-line title. Store URL remains bounded at 250 px. HTTP Status and System App intentionally join the existing two-line header set; the shared header remains 40 logical px and body rows remain 24 logical px.

Font/header growth is capped by each column's semantic maximum and does not inspect result values or use `ResizeToContents`. Loading representative rows does not change widths. Built-in presets continue to apply current semantic defaults without creating or mutating Custom, while genuine saved/manual widths—including a 140 px Maintenance Score—remain authoritative across restart. Native source geometry and screenshots passed at Qt-rendered 100% and actual 175% for 1100, 1320 and 1600 logical px; Details Auto remains usable on the right at 1600. The Python 3.13.15 x64 source gate passed with 115 focused tests and 610 full tests, plus compileall, Ruff, `pip check`, `git diff --check`, the isolated Qt source smoke and deterministic event-loop smoke. RC5 subsequently passed its automated and user acceptance and is retained as the accepted rollback/reference candidate; later source changes require RC6.

## Scan Phone lifecycle Phases A and B checkpoints

Phase A is complete locally. `playstore_app_audit.services.scan_session.ScanSession` is a frozen, slotted internal model for one completed Scan Phone source. It carries an aware `captured_at`, unique session/source IDs, existing hashed/masked device identity, manufacturer/model, Android version/API/security patch, Android locale, immutable package/system-package collections, counts and third-party/all-package scope. Its lifetime is the current window/process only; it is not persisted or exported.

The production worker now validates authorization once, parses one shared `getprop` snapshot for both device summary and locale, reuses the serial already present in `adb devices` for hashed/masked identity and enumerates packages with the same RC5 commands (`pm list packages -3` for third-party-only; all packages plus `-s` exact classification when system apps are included). `settings get system system_locales` remains a non-fatal read-only fallback only when the shared properties lack a usable locale. The UI selects a session atomically after complete success. Monotonic request IDs ignore stale discovery, success and failure signals; switching to a file clears the selected session/summary/locale, while a failed replacement scan cannot promote partial state.

The same real phone returned 329 third-party packages in the warm-up and every measured run. Five end-to-end offscreen UI scans were `0.500`, `0.538`, `0.532`, `0.663` and `0.469` seconds: min/median/mean/max `0.469 / 0.532 / 0.541 / 0.663` seconds. Each used exactly one `adb version`, one `adb devices`, one `adb shell getprop`, zero `get-serialno`, one `adb shell pm list packages -3` and zero locale fallbacks: four launches total versus the accepted nine-launch baseline. Median improved from `0.687` to `0.532` seconds (`0.155` seconds / `22.5%`).

Phase B is complete locally. The same ScanSession now holds an immutable compact T1 record for every scanned package: installed `versionCode`, raw installer package, the existing friendly installer source/category, enabled state and system classification. Standard Scan never collects or fabricates versionName, target/min SDK, install/update timestamps, permissions, compatibility or full/raw dumpsys output. The supported third-party command path is exactly `adb version`, `adb devices`, shared `getprop`, aggregate `pm list packages -3 -i --show-versioncode` and aggregate `pm list packages -3 -d`; compact enumeration replaces the old plain enumeration. Unsupported flags degrade only through installer-capable and plain aggregate enumeration, with unknown fields left unavailable.

Run binds the exact ScanSession into its internal result. A still-connected phone must match its hashed identity before the existing rich T2 collector runs. A disconnected/different phone does not prevent Store work: the T1 compact versionCode, installer, enabled and system values remain in results while versionName, SDK, compatibility, timestamps and permissions remain unavailable. Installed vs Store remains versionName-to-versionName and therefore Unknown without T2 versionName. Device Inventory Change and successful-audit promotion now consume the coherent T1 package/versionCode/installer/enabled/system snapshot; no T2 hybrid is promoted, missing installer/state does not create a false change, and Scan/stopped/failed work never advances the baseline.

The same real 329-package phone produced one warm-up and five measured end-to-end offscreen UI Standard Scans. Iterations were `0.633`, `0.669`, `0.734`, `0.699` and `0.701` seconds with five launches each; min/median/mean/max were `0.633 / 0.699 / 0.687 / 0.734` seconds. Against Phase A, median increased `0.167` seconds (`31.4%`); against the original RC5 median, it increased only `0.012` seconds (`1.7%`) while adding the compact snapshot.

The Python 3.13.15 x64 Phase B source gate passed at 231 focused tests and 650 full tests, plus compileall, full Ruff, `pip check`, `git diff --check`, canonical Qt source smoke, deterministic event-loop/source-entry smoke and explicit fake-device connected/disconnected Scan/Run smoke. RC5 menus, Custom/table widths, status bar, Audit Presets, Clear All Filters, Store/provider enrichment, Maintenance Score, exports and Phase A source/locale isolation remained covered. That checkpoint introduced no Advanced full-scan setting, full collector during Scan, package build or remote activity.

Phase C is now implemented locally. Advanced Settings > Device adds **Collect full device metadata during Scan Phone**, key `collect_full_device_metadata_on_scan`, strictly default OFF. Standard Scan keeps compact Phase B behavior. Advanced Scan calls the existing full collector once with session context; available device API/installer/enabled inputs are reused. One fresh authorization/hash match pins the long-running full commands to the same phone. All five real-device iterations confirm five Standard launches plus two additional full-phase launches for Advanced.

The session stores immutable parsed full fields only after an explicit COMPLETE receipt; partial/failed/cancelled capture discards rich partials and preserves compact T1. Run reuses COMPLETE fields with zero collector/dumpsys/ADB calls whether attached or disconnected. INCOMPLETE capture allows normal matching-device T2 fallback, otherwise compact-only results. Existing permission configuration, Installed vs Store meaning, Compatibility classification, T1 inventory authority, successful-only baseline promotion and stale-request/close guards remain intact. A new scan replaces the session; restart does not retain it.

The Phase C source gate is green: Python 3.13.15 x64/PySide6 6.11.1 and Python 3.14.6 x64/PySide6 6.11.2 each passed 699 tests, repository-wide Ruff, compileall/helper compilation, `pip check`, canonical Qt source smoke and deterministic event-loop full Scan/disconnect/cached Run smoke. All 49 new focused tests passed; all 650 previous tests remain. Native Advanced Settings layout also passed with the platform windows11 style at real 175% scaling.

The user confirmed replacing the old Pixel 10 Pro/329-app reference with a Pixel 11 Pro and 315 apps. Five timed iterations after priming give median Standard 0.617 s/5 launches, Standard T2 4.695 s/6, combined 5.238 s/11, Advanced 4.917 s/7, and Advanced collector 4.318 s/2 additional. Advanced dumpsys is 4.080 s median, approximately 12.42 MB and 83.0% of total. Run after Advanced costs 2.161 ms median with zero additional collector/dumpsys/ADB calls, avoiding 4.693 s of repeated current-device T2 work. Current-device Advanced saves 0.321 s/6.1% versus Standard + T2; paired surrounding ADB command timings save 0.503 s from context reuse. Historical 10.2% Standard and 43.1% combined improvements include the changed phone and cannot be attributed solely to software. Full distributions/iterations/deltas are in the validation report. **READY FOR RC6 BUILD**, with packaging deferred to the next session. Local benchmark/smoke scripts are ignored under `artifact/phase-c/`. No Nuitka, `build_windows_exe.bat`, package, remote activity or release-history mutation occurred.

The additional same-device Standard check uses the exact committed Phase B source and current C on Pixel 11 Pro/315 apps, five measurements each after priming: medians 0.634 vs 0.613 s, five launches and no dumpsys throughout. This confirms no material Standard regression without relying on the cross-device historical comparison.

## Priority 5: Alternative Distribution Discovery

Complete locally as Gate 4. This is secondary exact-package evidence only and never reinterprets Google Play state, installer source or criticality. Gate 5 uses only current conclusive Available evidence as bounded Maintenance Score recovery without changing those underlying facts.

- Eligibility is exactly raw `play_status == "not_found_in_checked_countries"`; all available/regional/transient/inconclusive states are skipped.
- F-Droid main is built in and default-enabled, using only the official active per-package API. Exact ID is mandatory; the archive, search, full index, third-party repos and APK URLs are not used.
- Aptoide is Advanced/opt-in and default-disabled. It requires an authorized `store_name` and Partner API key, sent only via the documented `Authorization: ApiKey …` header to exact `app/get` requests. The API does not document a reliable public listing URL, so none is fabricated.
- One non-pluggable protocol and typed Available/Not found/Inconclusive/Unsupported/Not checked result model are shared by orchestration, caching, Details, App Details, HTML and JSON.
- One independent provider executor is capped at two total requests, with 10-second request timeouts and a 20-second active-work phase budget. Pause blocks new submissions without consuming that budget; Resume continues; Stop prevents new submissions and retains completed evidence. Provider failure never fails successful Google Play work.
- The separate `alt-v1` cache uses 24-hour Available, 12-hour Not found and 15-minute Inconclusive TTLs, includes normalized Aptoide store name without the key, and is bypassed by Force Full Refresh. There is no provider history.
- Aptoide's saved key uses a versioned AES-GCM/HKDF-SHA256 envelope bound to a local machine-identity digest and local user. This deters casual config disclosure/copying only; it is not OS/hardware/compromised-account security. Identity or authentication failure retains the ciphertext and requires key replacement.
- Advanced Settings includes F-Droid/Aptoide controls, masked Replace/Remove/Test connection actions and an expandable provider limitations panel. Samsung, Huawei, Amazon, APKMirror, APKPure and Uptodown are not supported; no scraping is used.
- Provider evidence is separate in Details/App Details and conditional HTML. JSON is explicit schema v2 with ordered `alternative_distribution.providers`; CSV, table columns/filters, Friendly Notes and history remain unchanged. Gate 4 itself did not change scoring; Gate 5 later consumes only conclusive Available evidence through the documented bounded recovery. Credentials, envelopes and machine identity never enter exports or diagnostics.

## Priority 6: Maintenance Score algorithm

Complete locally as Gate 5. The user-facing concept remains **Maintenance Score** and the compatibility field remains `health_score`.

- Exact `not_found_in_checked_countries` applies one checked-market Google Play absence component of `-60`.
- Only while that component is active, current conclusive F-Droid main Available evidence recovers `+10` and Aptoide Available evidence recovers `+5`. Recovery is cumulative and provider IDs are deduplicated, so the present maximum is +15 and the net Store effect with both is `-45`.
- Not found, Inconclusive, Unsupported and Not checked provider states recover nothing. Live and valid cached Available evidence score identically. Unsupported future providers have no scoring behavior.
- Google Play available receives availability `0` and provider recovery `0`; provider evidence is never an unconditional bonus.
- `available_in_other_country` and `available_in_fallback_locale_only` remain Store anomaly `-20`; other/inconclusive Play states receive `-15`. Neither receives the definitive `-60`, and availability penalties do not stack.
- Listing age is `-15` for 366-730 days and `-25` above 730; unknown/unusable age adds nothing.
- Aging target is `-10`, Legacy target `-15`, and exact conclusive Installed-vs-Store `Different` is `-5`.
- Independent components compose and the final score is clamped to 0-100. Details, App Details and HTML expose the component breakdown.
- Raw Play/provider/installer/classification values and the provider cache are unchanged. History stores neither score nor provider evidence; versioned exports retain the score calculated for that audit rather than recomputing it.

The internal `health_score` -> `maintenance_score` migration is deferred to v2.0. Smart Query IDs, settings and serialized compatibility keys remain unchanged in v1.99.

## Deferred/rejected UI items

- Richer Dashboard/status overview: not v1.99 and not required for the v2.0 core; revisit only in later v2.x or v3.0 when mature multi-source and longitudinal/history workflows justify it.
- `QDockWidget`: rejected/not planned. Do not prototype it. Retain Auto/Right/Below/Hidden and narrow/wide/extra-wide Details behavior.
- Concrete bugs/workflow problems/polish found through real v1.9 use: assess each against scope; do not automatically accept everything.

## Mandatory v1.99 user-tested RC

v1.99 authorizes the required packaged acceptance cycle before public release. RC4 built and packaged successfully but failed acceptance only on default column density. Corrective RC5 subsequently passed automated and user acceptance and is the accepted rollback/reference candidate. The later ScanSession source changes invalidate it as a final candidate, so RC6 must repeat the separately authorized build and packaged acceptance cycle after Phases B/C and the final source gate:

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

Add a major v2.0 pillar: **Local APK Library / modern LocalAPK successor core**. Local APK Audit is also deferred entirely to v2.0.

Recommended technical sequence:

1. parser/verifier spike;
2. typed `LocalArtifact` with SHA-256 artifact identity;
3. package-deduplicated Store/provider fan-out;
4. transient Local APK Audit;
5. persistent Local APK Library.

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
