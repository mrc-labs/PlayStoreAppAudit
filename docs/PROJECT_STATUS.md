# Project Status

Last updated: 2026-08-21

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

## Current development baseline

- Canonical application version: `1.5.0`
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

## v1.5 product work completed

The v1.5 product and UI workstream is complete.

- File-menu result actions are consolidated into one canonical Run / Export / Clear section.
- Connected-phone source summaries show manufacturer/model and Android version/API without extra ADB calls.
- `Exclude system apps from source` defaults to enabled and persists explicit choices.
- Status-chip sizing follows native font/style metrics.
- Numeric result fields use typed numeric sorting.
- Audit progress distinguishes cached/live work and exposes a real finalization state.
- Regional fallback verification exposes live progress instead of appearing idle.
- Advanced settings warn that many fallback countries can increase audit time.
- Concurrent Store workers are configurable from 4 to 32 and persisted between runs.
- The concise worker warning states that higher values can increase throttling, connection errors and latency, and that more workers are not always faster.
- The Windows HiDPI checkbox investigation found no state-dependent sizing defect, so no custom checkbox styling workaround is used.
- Experimental Play Store app icons are implemented as an opt-in feature and remain off by default.
- Icon URLs are captured from normal scraper results without adding Store metadata requests.
- Only HTTPS icon URLs are accepted.
- Icon image downloads occur only when the feature is enabled, use at most 4 concurrent requests, a 10-second timeout and a 1 MB response ceiling.
- At most 96 decoded icon images are retained in memory for the current session.
- Downloaded icon bytes are persisted under the active app-data directory and reused across restarts while the app's `play_last_update` marker remains unchanged. If no reliable update marker exists, unchanged icon URL is required instead.
- Persistent icon-cache reads and writes run outside the UI thread. The results table is shown immediately and remains usable while cached or downloaded icons populate progressively.
- The normal healthy-result audit cache retains the icon URL metadata needed to reuse or refresh icons without adding Store metadata requests.

## Store performance and reliability evidence

The real Windows/device investigation established the Store path as the dominant audit cost. ADB metadata and UI finalization are not material bottlenecks on the measured 333-package workload.

Low-risk changes retained for v1.5:

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
| 14 | 200.877 s | anomalous back-to-back run; not used for v1.5 default selection |
| 16 | 168.854 s | v1.5 default/recommended value |
| 20 | 170.657 s | slightly slower than 16 |
| 24 | 171.166 s | slower with materially higher request latency |

The 14-vs-16 cooldown repeat is no longer required for the planned v1.6 work. Keep 16 as the default unless a later performance concern deliberately reopens benchmarking. If reopened, a long unattended real-device run is acceptable as long as it remains isolated from product changes and preserves final-classification checks.

Do not reintroduce retries for propagated `NotFoundError`. Generic transient retries remain required.

## Active next-cycle work

The next development cycle starts from the v1.5 baseline. The committed near-term engineering items are:

- move the bounded fallback scheduler out of `performance_diagnostics.py` into a dedicated canonical Store service;
- consolidate terminal `NotFoundError` retry/classification handling so base and device-enriched Store paths cannot drift;
- harden persistent icon-cache disk failure handling;
- add a configurable app-details panel that can dock right or below the results table;
- improve previous-audit change visibility;
- expose country-level availability evidence in the details UX;
- review whether Store icons should sit beside the Play Store title rather than beside the package name;
- continue observing experimental icon behaviour before removing the experimental label.

The current v1.6 release-profile direction is another unsigned Windows x64 ETB, but that profile is not frozen yet.

## Forward roadmap

`ROADMAP.md` is the canonical forward-looking plan. It separates:

- v1.6 planned direction;
- v1.7 candidates;
- v2.0+ production/signing and larger product concepts;
- open product questions;
- explicitly rejected ideas.

Important current direction:

- production Windows signing is not planned before v2.0;
- macOS production signing/notarization is not planned before v2.0;
- the full six-platform production release is not planned before v2.0;
- CLI/headless mode is not planned before v2.0;
- saved profiles, incremental audit, JSON export, SDK/source/signature metadata improvements and richer anomaly diagnostics are v1.7 candidates;
- LocalAPK-style local APK auditing is a v2.0+ product/architecture exploration, with integration versus companion-app scope still open.

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
