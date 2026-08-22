# Project Status

Last updated: 2026-08-22

## Published release

- Latest published version: `v1.5.0`
- Immutable release commit: `6f00bea0789874bc6339286a2ffc3eb9cb2891bb`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Public assets: exactly 3 project-defined release assets
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.5.0 (ETB Win x64)`

Published v1.5.0 is immutable. Do not rebuild, retag, rewrite or replace its published commit, tag or assets. Earlier published releases remain immutable as well.

## v1.5 release evidence

The v1.5.0 release was built, assembled and published from one exact frozen `main` SHA: `6f00bea0789874bc6339286a2ffc3eb9cb2891bb`.

Release gates and evidence:

- post-merge Quality push run: `32438975177`, successful on the frozen SHA with Python 3.13 and 3.14;
- Windows x64 build run: `32443253472`, successful on the same frozen SHA;
- engineering release assembly run: `32446825765`, successful on the same frozen SHA;
- final public release asset set: exactly three project-defined files;
- published release verified as non-draft, non-prerelease and latest at publication time;
- published `v1.5.0` tag resolves to the frozen SHA;
- published assets were downloaded again after release and independently SHA-256 verified against `SHA256SUMS.txt`.

Published project-defined assets:

- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Final SHA-256 values:

- Windows x64 ZIP: `942084863817852be53d63370b07b0a080728e8467f0e158deb8c2a1af354f8f`
- third-party source archive: `b24595b3bbf6adb77846104b246956d0f171777c8be81ef6e22b8d2b68a9a719`

## Current v1.6 release state

- Canonical application version: `1.6.0`
- v1.6 release profile: **frozen as an unsigned Windows x64 Engineering Test Build**
- Planned public asset count: exactly 3 project-defined assets
- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI: Qt Widgets using the platform/default QStyle
- Managed ADB behaviour: read-only with respect to installed Android apps
- Default/recommended concurrent Store workers: **16**
- Advanced worker range: 4 to 32
- HTML Store timeout: 25 seconds
- `google-play-scraper` transport timeout: 25 seconds

The exact v1.6 release SHA is not recorded until the profile/version freeze PR is merged to `main` and the post-merge Quality run passes. That exact merge commit then becomes the source candidate for the Windows x64 build. If any source or release-tooling change is required afterward, the candidate SHA must be replaced and the required release artifacts rebuilt from the new exact SHA.

## Frozen v1.6 distribution profile

v1.6.0 deliberately uses the same lightweight release class proven by v1.5:

- Windows x64 only;
- standalone ZIP package;
- intentionally unsigned;
- no Windows ARM64 release candidate;
- no Linux release candidate;
- no macOS release candidate;
- no production Windows signing;
- no macOS Developer ID signing/notarization;
- assembly through `.github/workflows/assemble-windows-engineering-release.yml`;
- release title `Play Store App Audit v1.6.0 (ETB Win x64)`;
- release-body heading `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.

The required public project-defined assets are exactly:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Production signing, notarization and the full Windows/Linux/macOS x64/ARM64 release profile remain preserved in source but are deferred until v2.0 or later.

## v1.6 product work completed

The committed v1.6 product/engineering scope is implemented and closed for the release candidate. Do not add new product scope while preparing the release unless a deliberate decision reopens the freeze.

### Store architecture, locale and reliability

- Bounded multi-country fallback scheduling now lives in the canonical Store service rather than `performance_diagnostics.py`.
- Terminal propagated `google_play_scraper.exceptions.NotFoundError` handling is centralized in the Store path; transient failures still retain retry/backoff and uncertainty semantics.
- Store language can run in `auto` mode. A connected Android phone supplies its actual active system language where available; file/list audits use the principal language of the selected Store country.
- Android locale region may provide the initial Store country for a phone scan, but the UI explicitly treats this as inferred from Android locale rather than claiming it is the Google Play account country.
- Explicit manual Store-language and Store-country overrides remain available.
- Same-country English fallback is limited to inconclusive or metadata-incomplete cases; a conclusive terminal not-found is not retried merely to change language.
- File/list audits clear any previously active phone-locale context.
- Store country/language request evidence is structured and exposed to the details UX.
- Default/recommended Store worker count remains 16.

### Persistent icon cache and Store metadata

- Persistent icon-cache path/read/write/replace `OSError` handling degrades cleanly to cache miss/network fallback instead of leaving icons permanently pending.
- Experimental Play Store icons remain opt-in and non-blocking.
- Icons now sit beside the Play Store title rather than beside the package ID.
- Developer metadata is captured from the same normal scraper response already used by the audit, with no additional Store metadata request.
- Captured icon/developer metadata is retained through the normal healthy-result cache path.

### Selected-row details UX

- A reusable app-details panel is attached to the results table.
- The panel can be positioned on the right or below the table and persists the user's choice.
- It exposes Play Store title/package/developer/URL/version/update information, device metadata, structured country/language evidence and previous-audit changes.
- Selecting a row updates the details panel, and the first result row is selected after model reset when results exist.
- The empty panel state is intentionally minimal rather than showing empty section headings.

### Previous-audit change visibility

- Previous-audit comparison records structured change events instead of relying only on the legacy display string.
- A grouped Audit changes overview covers:
  - newly installed apps on a previously known device inventory;
  - apps removed from the device;
  - newly available Store results;
  - newly unavailable results in checked Store countries;
  - Store listings that reappeared;
  - Store version changes;
  - Store latest-update changes;
  - maintenance-state transitions such as Current -> Aging -> Stale;
  - installer/source changes where available.
- The first inventory of a device is treated as a baseline, not as hundreds of newly installed events.
- Installer/source changes reported through both Store-history and device-inventory paths are deduplicated in the grouped overview.
- Selecting an app in the change overview focuses the current result row when present; removed-device packages remain visible even though no current row exists.

### Validation checkpoints before release freeze

The completed v1.6 product slices have been exercised by the normal Quality and UI-style gates. The final change-overview slice passed:

- 262 pytest tests;
- Ruff;
- Qt offscreen smoke on Python 3.13 and 3.14;
- Windows native vs Fusion UI audit;
- macOS native vs Fusion UI audit;
- Linux native vs Fusion UI audit.

The release-engineering messaging alignment also passed the normal Quality matrix after its regression test was updated to enforce the v2.0-or-later signing policy.

These are development/pre-freeze gates, not final v1.6 release evidence. Final release evidence must come from the exact frozen `main` SHA after this release-freeze change is merged.

## Store performance and reliability evidence

The real Windows/device investigation established the Store path as the dominant audit cost. ADB metadata and UI finalization are not material bottlenecks on the measured 333-package workload.

Low-risk changes retained from v1.5 and preserved through v1.6:

- negative multi-country checks run in small ordered batches while a shared semaphore caps total in-flight Store locale requests at the configured worker limit;
- fallback-country priority and classifications remain unchanged;
- propagated `google_play_scraper.exceptions.NotFoundError` is terminal for the outer scraper retry loop because upstream has already performed its own countryless fallback;
- generic transient failures still retain retry/backoff;
- the scraper transport receives a 25-second timeout, matching the HTML path;
- timeout/network failures remain transient or inconclusive and are never converted into Store not-found evidence;
- useful aggregate Store/ADB/total audit timing diagnostics remain available without package names;
- benchmark-only detailed Store path/scraper instrumentation is not installed at normal application startup.

Measured full-refresh checkpoints with 333 live packages and the same final classification of 324 available plus 9 not found in checked countries:

| Workers | Total time | Decision |
| ---: | ---: | --- |
| 12 | 185.850 s | slower |
| 14 | 200.877 s | anomalous back-to-back run; not used for default selection |
| 16 | 168.854 s | default/recommended value |
| 20 | 170.657 s | slightly slower than 16 |
| 24 | 171.166 s | slower with materially higher request latency |

The 14-vs-16 cooldown repeat remains unnecessary. Keep 16 as the default unless a later performance concern deliberately reopens benchmarking.

Do not reintroduce retries for propagated `NotFoundError`. Generic transient retries remain required.

## Remaining v1.6 release work

Product scope is frozen. Remaining work is release execution only:

1. merge the profile/version freeze to `main`;
2. require the post-merge Quality run to pass on that exact SHA;
3. record that exact full `main` SHA as the v1.6 release candidate SHA;
4. dispatch `.github/workflows/build-windows-exe.yml` from `main` with `target=x64` and `expected_sha=<frozen SHA>`;
5. require the Windows x64 build, package validation and legal/source preparation to succeed;
6. dispatch `.github/workflows/assemble-windows-engineering-release.yml` with the same SHA and successful Windows run ID;
7. require exactly the three frozen-profile assets and verify `SHA256SUMS.txt`;
8. only then create the annotated `v1.6.0` tag and GitHub Release using the already validated assets;
9. do not rebuild on tag push.

The optional richer dashboard/summary candidate is not part of v1.6.0. The icon feature remains labelled experimental.

## Forward roadmap

`ROADMAP.md` is the canonical forward-looking plan. Important current direction:

- production Windows signing is not planned before v2.0;
- macOS production signing/notarization is not planned before v2.0;
- the full six-platform production release is not planned before v2.0;
- CLI/headless mode is not planned before v2.0;
- saved profiles, incremental audit, JSON export, SDK/source/signature metadata improvements and richer anomaly diagnostics are v1.7 candidates;
- LocalAPK-style local APK auditing is a v2.0+ product/architecture exploration.

## Durable release invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Published release history is immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- No public RC tag and no tag-triggered binary rebuild.
- Strict legal/source validation remains fail-closed.
- If source or release tooling changes after a release SHA is frozen, discard and rebuild all candidates required by that release profile from the new SHA.
- GitHub Release assets are permanent and outside automated Actions artifact cleanup.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md` and `CI_MAINTENANCE.md` for durable policy, planning and procedures.
