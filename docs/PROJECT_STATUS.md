# Project Status

Last updated: 2026-09-13

## Published v1.99.0 release

- Latest published version: `v1.99.0`
- Published: `2026-09-09T20:44:16Z`
- GitHub Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.99.0
- GitHub Release ID: `385831055`
- GitHub Release title: `Play Store App Audit v1.99.0 (Win x64 Only)`
- Release-body heading: `Play Store App Audit v1.99.0 (Engineering Test Build - Windows x64 Only)`
- Immutable frozen release SHA: `1065744488e548663e3ba365566a9932837f5fb5`
- Annotated tag: `v1.99.0`; tag object `3b4088de9295e6637ced0f5a3d4246b8c8f00680`; peel target is the exact frozen SHA
- Release class: Engineering Test Build (ETB), Windows x64 only
- Package form: Nuitka standalone ZIP
- Application version: `1.99.0`; Windows File/Product version: `1.99.0.0`
- Signing: intentionally unsigned
- Project-defined release assets: exactly 3
- Repository visibility after publication and verification: `PRIVATE`

Published v1.99.0 is immutable. Do not rebuild, retag, rewrite or replace its source commit, annotated tag, release body or assets. RC8 remains the completed user-acceptance evidence and must not be reused as a release artifact; RC6 and RC7 remain failed historical candidates.

## v1.99.0 release evidence

The final package was quality-validated, built, legally inventoried, assembled, smoke-tested, tagged, published, re-downloaded and independently reverified from one exact frozen `main` SHA: `1065744488e548663e3ba365566a9932837f5fb5`.

- Legal-tooling fix PR `#126` merged normally at the frozen SHA after PR Quality run `34397322972`; post-merge Quality run `34397570534` passed on Python 3.13 and 3.14.
- Canonical Windows x64 build run `34397819253` passed from the exact SHA with Python 3.13.15 AMD64, 727 tests, `PySide6-Essentials==6.11.1`, `Nuitka==4.1.3`, PE AMD64, version checks, standalone validation, deterministic packaged smoke and `PUBLIC/STRICT` legal validation.
- Canonical build artifact: ID `10123641304`, `PlayStoreAppAudit-v1.99.0-windows-x64`, 184,838,528 compressed Actions bytes.
- Canonical engineering assembler run `34401780853` passed exact-SHA/build-lineage and exact three-file asset-set checks.
- Canonical assembler artifact: ID `10123756577`, `PlayStoreAppAudit-v1.99.0-windows-x64-engineering-release-assets`, 111,364,719 compressed Actions bytes.
- Before tagging, a clean extraction of the assembler-produced ZIP independently passed content, PE AMD64, version and deterministic packaged-smoke validation.
- After publication, exactly three assets were downloaded into a fresh directory; names, byte sizes and SHA-256 values matched both GitHub's digests and `SHA256SUMS.txt`.
- The annotated tag peels to the exact frozen SHA, the Release is non-draft/non-prerelease, and the repository remained private.

Published project-defined assets:

- `PlayStoreAppAudit-v1.99.0-windows-x64.zip`: 38,344,767 bytes; asset ID `553536304`; SHA-256 `cc556054280ef09bb693a8fd5d6e861c138ee387f96b098788b18db3e171f6c6`
- `PlayStoreAppAudit-v1.99.0-third-party-sources.tar.xz`: 73,128,144 bytes; asset ID `553536280`; SHA-256 `873087f13af891bb20e6e52d97342ba507311f9e13d1f05b80823103e58b80a3`
- `SHA256SUMS.txt`: 227 bytes; asset ID `553536279`; SHA-256 `656013312212a9de482c8986b70d9185a3e6452ef09c7077e08e411888da382c`

### Legal inventory closure

The final legal-tooling correction is evidence-driven and general. Installed `Requires-Dist` metadata now creates transitive candidates but does not by itself prove that a transitive component ships. Direct project runtime dependencies still require evidence, while transitive dependencies enter the legal inventory only when final package files or Nuitka compilation/distribution attribution prove presence. Unknown, unattributable, version-mismatched or ambiguously owned real runtime evidence remains a hard failure.

The strongest local synthetic end-to-end check reproduced the Windows build environment, verified all source archives, injected and validated the legal bundle against the preserved 633-module Nuitka report and final standalone tree, and passed `PUBLIC/STRICT`. The resulting 13-distribution runtime inventory contained `cffi` through ABI-tagged `_cffi_backend` evidence; `pycparser` was the sole metadata-only candidate and was correctly excluded. No dependency-name whitelist was added.

### Preserved v1.8.0 historical reference

Published v1.8.0 remains unchanged: it was published on 2026-08-24 from frozen SHA `ac328f0dffddb6b70fa7600f1291377376bc05d4` after Quality/build/assembler runs `32682693020`, `32683271942` and `32684933669`. Its public assets remain `PlayStoreAppAudit-v1.8.0-windows-x64.zip` (33,450,079 bytes; SHA-256 `b056be21804d2c22483ebee14c2f2bcbee5611a36ad6c7fea51c3dd91043991d`), `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` (73,128,136 bytes; SHA-256 `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e`) and `SHA256SUMS.txt` (225 bytes; SHA-256 `09717c84a7096351dcc8ba91609146a877ffb2eee1184b34ccfea40c39bebb6b`). Full historical evidence remains in `HANDOFF_V1.8.md` and `RELEASE_NOTES.md`.

### Post-release Actions housekeeping

The post-publication review found exactly the two canonical v1.99 artifacts and no redundant eligible artifacts, so no deletion was needed.

- Active storage: 2 artifacts / 296,203,247 bytes (282.48 MiB).
- Canonical build artifact `10123641304` and assembler artifact `10123756577` remain available for audit.
- GitHub Release assets, tags, source commits, earlier releases, repository retention settings and cleanup logic were not changed.

## Current development baseline

- Current source application version: `2.0.0`; derived Windows File/Product version: `2.0.0.0`.
- Latest published release: immutable v1.99.0 at release SHA `1065744488e548663e3ba365566a9932837f5fb5`.
- Active v2.0 release-preparation PR: `#151` on `v2/release-prep-2.0.0`; the exact final release SHA is not frozen yet.
- Python release-packaging and Quality baseline: 3.14.
- `PySide6-Essentials`: 6.11.2; Nuitka: 4.2.1.
- Local credential protection dependency: `cryptography==50.0.1` (AES-GCM/HKDF-SHA256).
- Windows x64 packaged acceptance must pass before the final six-platform production gate.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers: 16; Store transport timeout: 25 seconds.
- VS Code/Pylance Standard type checking remains a local development target, not a broad typing-refactor mandate.

Always verify live `main` and open-PR state rather than treating this document as a branch pointer. The immutable v1.99.0 release SHA remains fixed even after post-release documentation advances `main`.

### Scan Phone lifecycle Phases A and B checkpoints

The local-only Phase A checkpoint introduces an internal immutable `ScanSession` for one completed phone-source capture. It owns the captured timestamp, unique session/source identity, existing hashed/masked device association, existing device summary, Android locale, package tuple, package counts and all/third-party scope. A session is selected atomically only after the worker completes; request-generation guards ignore stale success/failure signals, and file selection clears device session/locale/summary state. The lifetime is process/window-local only: it is not written to settings, audit history, Device Inventory, Play Store/provider caches or exports, and it never stores a raw serial.

The production third-party Scan Phone path now performs one ADB executable/version discovery, one `adb devices` validation/authorization probe, one shared `adb shell getprop` capture and one aggregate `adb shell pm list packages -3` enumeration. The serial already returned by `adb devices` supplies the existing hashed/masked identity, eliminating `get-serialno`. Manufacturer/model, Android version/API/security patch and Android locale all reuse the same parsed properties; `settings get system system_locales` remains a read-only fallback only when those properties contain no usable locale. All-package scope retains its existing additional `pm list packages -s` classification call.

The same connected phone returned 329 third-party packages in one warm-up and five measured end-to-end offscreen UI iterations. Each measured scan used exactly four ADB subprocesses with no locale fallback: `0.500`, `0.538`, `0.532`, `0.663` and `0.469` seconds; min/median/mean/max were `0.469 / 0.532 / 0.541 / 0.663` seconds. Against the accepted `0.673 / 0.687 / 0.691 / 0.717` second, nine-launch baseline, median improved by `0.155` seconds (`22.5%`) and launches fell from nine to four. Phase A adds no versionCode, installer, enabled-state or rich per-package metadata; no Advanced full-scan option, Run enrichment, Device Inventory semantic, result/export schema, provider, scoring or cache behavior changed.

Phase B keeps the same immutable, process/window-local session and adds one compact per-package T1 record. Every successful Standard Scan captures `package_name`, installed `versionCode`, raw installer package, the existing friendly installer source/category, enabled state and system classification where available. It does not collect or fabricate versionName, target/min SDK, install/update timestamps, permissions, compatibility or full/raw dumpsys data. The supported third-party path replaces plain enumeration with `pm list packages -3 -i --show-versioncode` and adds `pm list packages -3 -d`; unsupported flags degrade through aggregate-only installer/plain enumeration and unavailable fields remain unknown.

At Run, a still-connected matching phone retains the existing concurrent rich T2 collector. A disconnected or different phone does not block Store auditing: captured T1 versionCode, installer, enabled and system values survive, while rich-only values remain unavailable. Installed vs Store remains the existing versionName comparison and is Unknown without installed versionName. Device Inventory Change and its successful-audit baseline now use the coherent T1 package set/versionCode/installer/enabled/system state; Scan, stopped audits and failed audits do not promote it, and missing compact values are not classified as changes.

The Phase B benchmark used the same 329-package phone, third-party-only setting, one warm-up and five end-to-end offscreen UI measurements. Iterations were `0.633`, `0.669`, `0.734`, `0.699` and `0.701` seconds, each with exactly five launches: `adb version`, `adb devices`, shared `getprop`, compact package enumeration and the disabled-set query. Min/median/mean/max were `0.633 / 0.699 / 0.687 / 0.734` seconds. Median increased `0.167` seconds (`31.4%`) from Phase A but only `0.012` seconds (`1.7%`) from the old nine-launch RC5 median while adding the compact snapshot.

The Python 3.13.15 x64 Phase B source gate is green at 231 focused tests and 650 full tests. Compileall, full Ruff, `pip check`, `git diff --check`, the canonical Qt source smoke, deterministic event-loop/source-entry smoke and explicit fake-device connected/disconnected Scan/Run smoke all passed. No Nuitka or package build was run.

### Scan Phone lifecycle Phase C source validation

The Advanced Settings > Device opt-in **Collect full device metadata during Scan Phone** uses `collect_full_device_metadata_on_scan` and defaults to OFF, including missing or malformed settings. Standard Scan retains the five-launch compact path. Advanced Scan calls the same production full collector once, reusing the session's SDK/installer/enabled inputs after a fresh authorization/device match. Its supported path adds one matching-device check and one device-selected bulk dump; no second collector exists.

An explicit receipt certifies full package coverage, usable versionCode/target/min SDK inputs, valid device context and absence of cancellation. COMPLETE full snapshots are immutable, process/window-local and reused by Run with zero additional full-collector, dumpsys or rich ADB calls, connected or disconnected. INCOMPLETE capture discards rich partials and retains compact T1 data with a concise status message; connected Run may retry normal T2 enrichment. Sensitive permissions keep their existing preference. Device Inventory remains exclusively the coherent compact T1 snapshot and only successful audits promote its baseline.

The final source gate passed on Python **3.13.15 x64: 699 tests**, PySide6 6.11.1, and Python **3.14.6 x64: 699 tests**, PySide6 6.11.2 (Quality permits Qt 6.11+). All 49 new Phase C tests passed. Compileall, required helper compilation, repository-wide Ruff, both `pip check` runs, PowerShell helper syntax, Qt offscreen source smoke and deterministic event-loop/fake-device full Scan > disconnect > cached Run smoke passed. The full suite retains all 650 pre-Phase-C tests. No release dependency/toolchain pin changed.

At the historical pre-RC6 source checkpoint, five measured iterations after priming on the current Pixel 11 Pro/315-app phone gave min/median/mean/max seconds: Standard `0.543 / 0.617 / 0.601 / 0.661` (5 ADB launches); Standard T2 `4.571 / 4.695 / 4.727 / 5.079` (6); Standard + T2 `5.120 / 5.238 / 5.328 / 5.740` (11); Advanced `4.634 / 4.917 / 4.847 / 5.076` (7); Advanced collector subphase `4.074 / 4.318 / 4.273 / 4.488` (2 additional). Run reuse had 2.161 ms median overhead, zero additional collector/dumpsys/ADB calls, and avoided 4.693 s of current T2 collection. Advanced dumpsys was `3.906 / 4.080 / 4.070 / 4.257` s, approximately 12.42 MB and 83.0% of total median. Paired surrounding ADB commands saved approximately 0.503 s through context reuse.

The user confirmed replacing the historical Pixel 10 Pro/329-app phone with the Pixel 11 Pro and fewer apps. Current Standard is 0.070 s/10.2% below historical RC5 and Advanced is 3.722 s/43.1% below the historical 8.639 s combined reference, but those cross-device changes must not be credited entirely to software. A supplementary five-iteration comparison of exact committed Phase B vs current C on the same Pixel 11 confirms no material Standard regression: 0.634 vs 0.613 s median, five launches each. The same-device Advanced vs Standard + T2 saving is 0.321 s/6.1%; the historical Phase B compact cost remains 0.167 s/31.4% above Phase A. Detailed iterations, deltas, command accounting and attribution are in the [Phase C validation report](SCANSESSION_PHASE_C_VALIDATION.md). Instrumentation remains ignored/local under `artifact/phase-c/`. No Nuitka, RC6 package or remote operation occurred.

## Shipped in v1.9.0

The accepted product/UX implementation merged through PRs `#116`, `#117` and `#118`; release preparation merged through PR `#119`.

- Shared friendly Notes presentation across table, complete tooltip, Details Panel and HTML report while preserving raw Notes in machine-readable data and compatibility paths.
- **Maintenance Score** terminology on user-facing surfaces while keeping `health_score` and existing v1.8 Smart Query/serialized compatibility.
- Foreground-only warning colours for **Different**, **Aging target** and **Legacy target**.
- Improved About hierarchy and one coordinated project-owned icon family for Choose File, Scan Phone and Export Results.
- Display Settings populated-table crash fix with safe presentation refresh, Custom-preset synchronization and preserved widths, sorting/filtering, selection, Details content and restart consistency.
- Details Panel narrow/wide/extra-wide responsiveness based on actual viewport width, with 760/680 and 1180/1080 px hysteresis and the accepted three-column grouping.
- A native `QStatusBar` reusing the same canonical status label and progress widget, with active-only progress, no duplicate source/device identity and no new state/persistence model.

## Feature-complete v1.99 direction

The feature-complete scope is canonical in `ROADMAP.md`, `PROJECT_DECISIONS.md` and `HANDOFF_V1.99.md`. Stabilization and the mandatory packaged Windows x64 acceptance candidate must preserve these boundaries:

- preserve the cooperative safe Stop/Cancel lifecycle merged through PR `#122` at `c5322d42a7ebdd0f7e61fd1c25b69828d8535e25`;
- preserve the locally accepted C2 operations-header layout after the A/B/C and C0/C1/C2 native comparisons: Run/Pause/Resume, Stop, always-present canonical progress, Export Results and Clear Results;
- keep operational status text in the compact edge-to-edge native status bar, with its size grip, 16 logical px left and 12 logical px right label-content margins, symmetric vertical centering and no residual card-era bottom gap; keep the single synchronized Auto/Right/Below/Hidden Details selector on the second results header row with chips, Hide System Apps and search;
- retain the RC3 Phase A semantic table-width policy, bounded Store URL/long-text defaults, compact Maintenance Score, selected two-line headers and final-model saved-width restore; do not replace it with body-value `ResizeToContents` behavior;
- retain the RC5 source-checkpoint density defaults for short values: Last Update 104, Age 78, Android Compatibility 120, Installed vs Store 116, Enabled State 88, Device Inventory Change 130, Maintenance Score 86, Target SDK 74, Min SDK 70, Sensitive Permissions Count 124 (127 with normal Segoe UI header metrics), HTTP Status 78 and System App 78 logical px; HTTP Status and System App use intentional two-line headers, while Store URL remains 250 px;
- retain the RC3 Phase B1 `View > Column Preset` contract: Basic, Device and Technical are immutable built-ins, while manual visibility/order/width changes create or update the separately persisted Custom layout; built-in switching, refresh and restart must not destroy Custom;
- keep `View > Customize View…` as the existing presentation dialog: column changes update Custom, while app icons, date format and equivalent presentation preferences remain global and outside the Custom layout;
- keep the dedicated SDK Maintenance Filter absent; Target SDK, Min SDK and Android Compatibility collection/presentation remain intact, and Smart Queries own advanced SDK/compatibility result conditions;
- use **Audit Presets** as the user-facing name while retaining schema-v1 `audit_profiles` storage compatibility; applying a preset changes only next-audit execution state and never search, status chips, Quick Filters, Smart Queries, Column Preset/Custom state, Details placement, app-icon visibility or date format;
- retain the final `File / Audit / View / Tools / Help` ownership: File for sources and raw phone-package export, Audit for execution/presets/result export/Clear Results, View for layouts/Details/result filters, Tools for Advanced Settings plus Device History and Data Maintenance, and Help for guides/methodology/update/diagnostics/About;
- keep `View > Clear All Filters` presentation-only: it resets search, status chips, Quick Filter, active Smart Query and the session-only Hide System Apps visibility filter without changing current results, saved query/preset definitions, audit/cache/history data, sorting, Column Preset/Custom state or other presentation/audit settings;
- keep the redundant `Tools > Device Summary…` dialog absent while retaining device-summary collection and its snapshot/diagnostic/metadata/log/export consumers; connected-device source identity may show available Android version/API metadata but not a new serial identifier;
- preserve the completed warning hierarchy across table, Details and HTML surfaces: dark-yellow DemiBold 600 **Different/Aging target**, dark-orange DemiBold 600 **Legacy target**, Regular 400 **Modern**, and Bold 700 Status, with native selected/disabled roles and unchanged raw values;
- retain the dedicated device-inventory-history clear boundary: remove only separately keyed `Device Inventory Change` baselines while preserving Device Snapshots, Store cache, previous-audit history, provider cache, settings and current results;
- default **Show app icon** on when its setting is absent while preserving every explicitly saved on or off value and the existing lazy/cached/non-fatal loading behavior;
- preserve the locally completed Alternative Distribution Gate 4: built-in F-Droid main plus Advanced/authorized Aptoide behind one non-pluggable exact-package provider model, eligible only after raw `not_found_in_checked_countries`;
- keep provider evidence secondary/non-fatal and separate from Google Play state, installer source and criticality; Maintenance Score may consume only current conclusive Available evidence through the accepted bounded recovery mapping;
- retain AES-GCM/HKDF protected Aptoide config credentials with honest local copy/casual-disclosure limits, and never expose plaintext/protected credentials or machine identity in diagnostics/exports;
- keep provider facts in Details/App Details, conditional HTML and explicit JSON schema v2; keep table columns, Friendly Notes, CSV and provider history unchanged;
- keep Samsung Galaxy Store, Huawei AppGallery, Amazon Appstore, APKMirror, APKPure and Uptodown listed as not supported in the provider limitations panel; do not scrape them;
- preserve the locally completed Gate 5 Maintenance Score: definitive checked-market Play absence `-60`, cumulative/deduplicated F-Droid `+10` and Aptoide `+5` recovery only while that penalty is active, Store anomaly/Other `-20`/`-15`, stale/aging `-25`/`-15`, legacy/aging target `-15`/`-10`, Different `-5`, and 0-100 clamping;
- defer the internal `health_score` rename to v2.0 and retain all v1.99 compatibility identifiers;
- defer Local APK Audit entirely to v2.0, where it follows a parser/verifier spike, typed SHA-256 `LocalArtifact` identity and package-deduplicated Store/provider fan-out;
- require a real packaged Windows x64 user-tested RC before final v1.99 release freeze;
- treat `QDockWidget` as rejected/not planned;
- keep a richer Dashboard out of v1.99 and the v2.0 core; revisit it only in later v2.x or v3.0 when mature multi-source/history workflows justify it.

Concrete bugs and polish found through actual v1.9 use may be reviewed individually. They are not automatically accepted scope.

## v2.0 and later direction

v2.0 remains the first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 release distribution. Production signing/notarization is preferred but conditional on real eligibility, credentials, cost and end-to-end validation. CLI/headless support must reuse domain/service layers rather than drive Qt.

A Local APK Library / modern LocalAPK successor core is a major v2.0 product pillar. Its technical sequence begins with a vetted untrusted-APK parser/verifier boundary, then a typed `LocalArtifact` model with SHA-256 identity and package-deduplicated Store/provider fan-out, followed by transient Local APK Audit and the persistent Library. Mass rename, duplicate management, safe outdated-APK cleanup, custom integrations and Explorer integration remain later v2.x candidates.

### v2.0 Local APK parser foundation checkpoint

The first v2.0 source checkpoint implements the parser boundary and typed
artifact model without UI, persistence or Store/provider fan-out. A bounded
standard-library ZIP preflight feeds only `AndroidManifest.xml` and optionally
`resources.arsc` to pinned `pyaxmlparser==0.3.31`. A bounded snapshot makes the
exact file SHA-256 and parsed metadata refer to the same captured bytes; package
ID remains a distinct identity. The immutable model preserves file/path/time,
package/version/SDK, label/icon-reference and compact manifest metadata without
inventing missing values; typed failures cover malformed, limited, unsupported
and detected split inputs.

The checkpoint extracts no signing certificate data and performs no
cryptographic signature verification. `.apks`, `.aab` and split APKs are not
supported. Focused source validation covers real compiled AXML/ARSC fixtures,
identity separation and archive limits. No Nuitka package or non-Windows target
was built. Full details and remaining packaging risk are in
`LOCAL_APK_PARSER.md`.

### v2.0 Local APK Store fan-out checkpoint

The second v2.0 source checkpoint adds a Qt-independent service that accepts
immutable `LocalArtifact` objects, deduplicates their exact package lookup keys
within one Store/provider context, and reuses the existing healthy-result cache,
canonical Play Store batch service and Alternative Distribution phase. The
first-seen package order and original artifact order are deterministic; distinct
artifact SHA-256 identities remain intact, while same-package artifacts share
one immutable package-evidence object. Existing per-package Store failure states
and the definitive `not_found_in_checked_countries` provider gate are unchanged.

The coordinator adds no thread pool and no Local APK-specific cache. Different
country/language/provider/refresh contexts use separate calls, leaving existing
context-aware cache keys in control across operations. No Local APK UI,
persistence, scanning or packaged acceptance is included. The next milestone is
the transient Local APK Audit input source.

### v2.0 transient Local APK Audit checkpoint

The v2 development source now provides the first user-facing Local APK workflow:
`Choose APK(s)` selects one or more standalone `.apk` files, which are parsed on
a cooperative background source worker with request-generation protection.
Valid artifacts remain usable after partial parse failure; zero valid artifacts
does not establish a source. The existing package fan-out then performs Store and
eligible provider work once per exact package while emitting one ordered result
row for every SHA-distinct artifact.

Local APK rows expose filename, local label/version/version code, SHA-256 and
Store evidence in the shared table/export path, with bounded richer parser
metadata in Details. They do not use installed-version or system-app semantics,
inherit phone locale state, enter package-keyed audit history, or promote Device
Inventory/ScanSession baselines. Absolute local paths are not included in result
rows or default exports. This workflow remains session-transient; directory
scanning and persistent Local APK Library state belong to the separate core
checkpoint below.

### v2.0 persistent Local APK Library core checkpoint

Phase 5a is complete at the domain/service boundary. The project-owned
`local_apk_library.json` schema starts at version 1 and stores registered roots,
path-independent artifacts identified only by exact SHA-256, and separate
physical path-to-SHA location associations. Identical bytes at multiple paths
remain one artifact with every location retained. Changed bytes at one path
create a new SHA identity without mutating or deleting the old record; completed
rescans retain unseen locations as not present.

Recursive scanning is deterministic, case-insensitive for `.apk`, ignores other
formats and directory links/reparse points, calls the existing bounded parser,
supports cooperative cancellation/progress, and preserves valid results across
bounded typed issues. Partial, failed and cancelled root scans cannot falsely
mark all prior locations missing. Version/schema/shape failures are typed, and
JSON saves use a flushed sibling temporary file plus atomic replacement.

The core makes no Store/provider/cache calls and persists no remote evidence.
Its audit projection reconstructs one deterministic present `LocalArtifact` per
exact SHA for the existing package-deduplicated fan-out boundary. This core
remains available as future infrastructure and is not mutated by the current
session-local source. v1.99.0 remains the current published release.

### v2.0 Local APK source UX/correctness checkpoint

The dedicated persistent Library manager was removed from the current v2.0 UX.
The three-card layout is ordered `Android Phone (ADB) / Local APK(s) / App List
File`, retaining the compact decorative `or` separators. `Choose APK(s)` selects physical files and its compact menu selects a folder for
recursive, case-insensitive `.apk` discovery. Discovery performs no parsing,
hashing or network work; Run performs bounded parsing and then reuses the
package-deduplicated Store/provider fan-out.

Interactive results use one row per physical file, including a local-only
Location field in the schema, Technical view and Details. Identical bytes retain
one SHA identity internally but remain separate physical rows; package-equal
files share Store/cache work. Default exports and remote requests exclude the
Location and other private local evidence.

Basic, Source Details and Technical are source-aware built-in column presets;
the retired Device preset migrates to Source Details without altering a saved
Custom layout. Built-ins reapply canonical order and semantic widths when a new
source is established and always keep Notes last. Customize View separates
Common from Advanced / Technical fields without changing saved visibility,
order or widths. Local APK defaults to the
non-lexicographic relationship priority Outdated, Unknown, Different,
Device-specific, Newer and Match, then Store criticality and APK identity;
manual sorting remains authoritative until another source is established.

Local APK table rows keep ordinary cells neutral while Local APK vs Store and
Store Status retain independent semantic cells, including through selection;
the filter chips are explicitly labelled Store Status. Selected cells suppress
the Windows current-cell focus edge without changing row selection or keyboard
navigation. Installed vs Store and Local APK vs Store values use their existing
semantic colours with the same Bold 700 typography and centered alignment as
Store Status. Status text is symbol-free, and the green `<=365 days` state is
named Recent Update while its internal `green` key, rank and semantics remain
unchanged. Source summaries name
Phone, Local APK or App List, while Store Country is uppercase in the UI and
lowercase in execution/cache contexts. Store date presentation uses
Last Store Update and Store Age (Days) without changing internal/export keys.
Windows file reveal uses `SHOpenFolderAndSelectItems`, with a checked native
parent-folder fallback, and debug sessions retain first-party DEBUG while
limiting known recoverable pyaxmlparser warning signatures and urllib3 noise.
The canonical scraper result now propagates HTTPS icon URL and developer through
locale/fallback resolution into every healthy Store row and normal cache writes,
so Local APK, ADB and App List share the same metadata path. Any healthy available
live or cached row still missing an icon is eligible for bounded,
package-deduplicated asynchronous metadata completion; successful results start
the existing icon loader and update only icon/developer cache fields.

Store status uses the conservative `Not Found` wording. Installed and Local
APK versions share ordered Match/Outdated/Newer/Different/Device-specific/Unknown
semantics and source-aware scoring. Outdated costs 10 Maintenance Score points;
Local Unknown costs 15 only when local evidence is missing while a usable Store
version exists, so Store-side absence is not double-counted. Structured update dates win over localized
visible text, and `--debug` creates an opt-in per-session app-data log. The
persistent Library core/data remains intact as future infrastructure. v1.99.0
remains the current published release.

## Explicitly removed / rejected

Do not reintroduce without a new explicit product decision:

- installed signing-certificate fingerprint/change detection;
- broad automatic alternative-source association or fuzzy-title equivalence (the approved exact-package informational discovery is distinct);
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country-set presets;
- `QDockWidget` for the Details Panel.

## Durable release and repository invariants

- `main` is the only permanent branch; use short-lived branches and normal PR merge commits.
- Before any local pull, require a clean working tree; never reset, stash or discard automatically.
- Published releases are immutable and all release artifacts derive from one exact frozen SHA.
- Quality precedes SHA freeze; tagging follows artifact validation; tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed; ADB remains read-only.
- v1.99's user-tested packaged-RC requirement is satisfied by RC8; its ZIP remains acceptance evidence and is not the official final release artifact.
- Complete every release through `RELEASE_CLOSURE.md`, including post-release context, safe local synchronization and handoff generation only from clean synchronized `main`.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `HANDOFF_V1.9.md` and `HANDOFF_V1.99.md` for durable policy, release history and continuation context.
