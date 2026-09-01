# Project Status

Last updated: 2026-09-01

## Published release

- Latest published version: `v1.9.0`
- Published: `2026-08-25T02:51:42Z`
- GitHub Release: https://github.com/mrc-labs/PlayStoreAppAudit/releases/tag/v1.9.0
- GitHub Release ID: `376114171`
- GitHub Release title: `Play Store App Audit v1.9.0 (Win x64 Only)`
- Release-body heading: `Play Store App Audit v1.9.0 (Engineering Test Build - Windows x64 Only)`
- Immutable frozen release SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`
- Annotated tag: `v1.9.0`; tag object `e61033f0ffba3d14f598da4d928aa07390dbbfa9`; peel target is the exact frozen SHA
- Release class: Engineering Test Build (ETB), Windows x64 only
- Package form: Nuitka standalone ZIP
- Application version: `1.9.0`
- Windows File/Product version: `1.9.0.0`
- Signing: intentionally unsigned
- Public project-defined assets: exactly 3

Published v1.9.0 is immutable. Do not rebuild, retag, rewrite or replace its source commit, annotated tag, release body or assets. v1.8.0 remains immutable at `ac328f0dffddb6b70fa7600f1291377376bc05d4`, and earlier published releases remain immutable as well.

## v1.9.0 release evidence

The candidate was quality-validated, built, assembled, smoke-tested, tagged, published, re-downloaded and independently reverified from one exact frozen `main` SHA: `6c117009525f40434e9db714dadf1dd01b79f9ab`.

- Canonical Quality run: `32797795985`, successful on Python 3.13 and 3.14.
- Canonical Windows x64 build run: `32798334950`, successful from the frozen SHA.
- Canonical build artifact: ID `9546290578`, `PlayStoreAppAudit-v1.9.0-windows-x64`, 179,980,464 compressed Actions bytes.
- Canonical engineering assembler run: `32801220807`, successful with the exact three-file ETB set from the same SHA.
- Canonical assembler artifact: ID `9546545528`, `PlayStoreAppAudit-v1.9.0-windows-x64-engineering-release-assets`, 106,515,133 compressed Actions bytes.
- The canonical build used Python 3.13.15 AMD64, `PySide6-Essentials==6.11.1` and `Nuitka==4.1.3`; all 403 tests passed during the build.
- Package validation confirmed PE AMD64/x64, standalone layout, application version `1.9.0`, Windows File/Product version `1.9.0.0`, intentional unsigned state, startup, required/forbidden runtime contents, legal/source material and exact-SHA provenance.
- Managed Android Platform-Tools 37.0.1 was validated. Its `adb.exe` is PE I386 and ran successfully under Windows WOW64; ADB application behavior remains read-only.
- Before tagging, the exact assembler-produced ZIP passed a clean-extraction deterministic packaged smoke with isolated application-data directories, and its hash remained unchanged.
- Publication created one annotated tag and one non-draft/non-prerelease GitHub Release; tag pushes did not rebuild the package.
- After publication, all three public assets were downloaded from the GitHub Release into a fresh directory. Exact asset count, names, byte sizes and hashes matched, `SHA256SUMS.txt` was independently parsed, and the public ZIP passed the same clean-extraction packaged smoke with isolated data directories.

Published project-defined assets:

- `PlayStoreAppAudit-v1.9.0-windows-x64.zip`: 33,477,938 bytes; asset ID `528529615`; SHA-256 `74db811d959a06709aba4d747873ec1b19894e50ba7183f463f7929b44e19c68`
- `PlayStoreAppAudit-v1.9.0-third-party-sources.tar.xz`: 73,128,144 bytes; asset ID `528529608`; SHA-256 `ccccbd72992bed8692388077fd409dc76bb8f64efce8fa2ef283b74797a4df95`
- `SHA256SUMS.txt`: 225 bytes; asset ID `528529607`; SHA-256 `eb2b5f6d5a8fe978e54367b887c65d77994307447154435e3b3ae81c4bf2bd23`

### Preserved v1.8.0 historical reference

Published v1.8.0 remains unchanged: it was published on 2026-08-24 from frozen SHA `ac328f0dffddb6b70fa7600f1291377376bc05d4` after Quality/build/assembler runs `32682693020`, `32683271942` and `32684933669`. Its public assets remain `PlayStoreAppAudit-v1.8.0-windows-x64.zip` (33,450,079 bytes; SHA-256 `b056be21804d2c22483ebee14c2f2bcbee5611a36ad6c7fea51c3dd91043991d`), `PlayStoreAppAudit-v1.8.0-third-party-sources.tar.xz` (73,128,136 bytes; SHA-256 `10ea03905fec3b9e9cf03e30a54e98f2c3ceb9d2aea423df4732a10f1551977e`) and `SHA256SUMS.txt` (225 bytes; SHA-256 `09717c84a7096351dcc8ba91609146a877ffb2eee1184b34ccfea40c39bebb6b`). Full historical evidence remains in `HANDOFF_V1.8.md` and `RELEASE_NOTES.md`.

### Post-release Actions housekeeping

Manual housekeeping run `32805211585` completed successfully on 2026-08-25 from the frozen release SHA using the unchanged generational retention policy with a 7-day grace period.

- The apply run saw 10 active artifacts and found no expired failed/cancelled runs, superseded successful runs or individual artifacts eligible for deletion.
- Active storage remains 10 artifacts / 574,199,782 bytes (547.60 MiB).
- Canonical v1.9 build artifact `9546290578` and assembler artifact `9546545528` remain available for audit.
- The v1.8 build/assembler generation and two UI-style generations remain retained within the documented grace period; no manual deletion bypassed policy.
- GitHub Release assets, tags, source commits, earlier releases, repository retention settings and the cleanup algorithm were not changed.

## Current development baseline

- Current source application version: `1.99.0`; derived Windows File/Product version: `1.99.0.0`.
- RC1 was built and technically validated from `7c3f2e768f5a6592e12a835b40a31d70a59e0bc6`, but manual acceptance rejected it as the final candidate. RC2 technical validation has passed. Local-only RC3 Phase A is accepted, Phase B1 is complete from Phase A checkpoint `a843c9a72e43cf24c2f069a06a0c40e13bcfa8e9`, Phase B2 is complete from Phase B1 checkpoint `4b848c3b00726ddc3d12248e07554969998af66d`, and the final RC3 source gate is complete from Phase B2 checkpoint `933f374c79fa959e9eb46c5f2e288ac2baedd899`; version remains `1.99.0`, Python 3.13.15 and 3.14.6 are green at 602 tests, no RC3 package has been built and remote activity remains frozen for the separate privacy workstream.
- Latest published release: immutable v1.9.0.
- Active development cycle: v1.99, likely the final Windows x64-only pre-v2.0 release.
- v1.99 remains a controlled Windows x64 ETB cycle; it is not an open-ended feature release.
- Python packaging baseline: 3.13; Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1; Nuitka: 4.1.3.
- Local credential protection dependency: `cryptography==50.0.1` (AES-GCM/HKDF-SHA256).
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers: 16; Store transport timeout: 25 seconds.
- VS Code/Pylance Standard type checking remains a local development target, not a broad typing-refactor mandate.

Always verify live `main` and open-PR state rather than treating this document as a branch pointer. The immutable v1.9 release SHA remains fixed even after post-release documentation advances `main`.

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
- v1.99 requires a user-tested packaged RC; source corrections invalidate that RC as a final candidate.
- Complete every release through `RELEASE_CLOSURE.md`, including post-release context, safe local synchronization and handoff generation only from clean synchronized `main`.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md`, `HANDOFF_V1.9.md` and `HANDOFF_V1.99.md` for durable policy, release history and continuation context.
