# Project Status

Last updated: 2026-08-21

## Published release

- Latest published version: `v1.4.0`
- Immutable release commit: `6830e0c4a03e355f442070f00dd5008322f5dbc4`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Public assets: exactly 3
- Signing: intentionally unsigned

Published v1.4.0 must never be rebuilt, retagged, rewritten or have its assets replaced. Previous v1.3.0 is also published and immutable at `fb2193dfc13d0f0e6b7be660c1342bbf87d26081`.

## Current v1.5 baseline

- Canonical application version remains `1.4.0` until the final release-hardening PR.
- Packaging Python: 3.13
- Quality Python: 3.13 + 3.14
- `PySide6-Essentials`: 6.11.1
- Nuitka: 4.1.3
- UI: Qt Widgets using the platform/default QStyle
- Managed ADB behaviour: read-only with respect to installed Android apps
- Default/recommended concurrent Store workers for v1.5: **16**
- Advanced worker range: 4 to 32
- HTML Store timeout: 25 seconds
- `google-play-scraper` transport timeout: 25 seconds

## v1.5 release profile

`v1.5.0` is an unsigned Windows x64-only Engineering Test Build.

- one exact frozen `main` SHA
- Windows x64 only
- no Windows ARM64, Linux or macOS v1.5 release candidates
- no signing spend
- build workflow: `.github/workflows/build-windows-exe.yml` with `target=x64`
- assembler: `.github/workflows/assemble-windows-engineering-release.yml`
- release title suffix: `(ETB Win x64)`
- release body heading: `## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)`
- exactly three public assets:
  - `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
  - `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
  - `SHA256SUMS.txt`

The broader Windows/Linux/macOS x64/ARM64 production profile and production signing remain v1.6 work.

## v1.5 product work completed

The v1.5 product and UI workstream is complete on `main`.

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
- At most 96 decoded icon images are retained in memory for the current session. Image bytes are not persisted.
- The normal healthy-result audit cache may retain the icon URL only, allowing cached audits after restart to show icons without repeating Store metadata requests.

## Store performance and reliability evidence

The real Windows/device investigation established the Store path as the dominant audit cost. ADB metadata and UI finalization are not material bottlenecks on the measured 333-package workload.

Low-risk changes now retained for v1.5:

- negative multi-country checks run in small ordered batches while a shared semaphore caps total in-flight Store locale requests at the configured worker limit;
- fallback-country priority and classifications remain unchanged;
- propagated `google_play_scraper.exceptions.NotFoundError` is terminal for the outer scraper retry loop because upstream has already performed its own countryless fallback;
- generic transient failures still retain retry/backoff;
- the scraper transport receives a 25-second timeout, matching the HTML path;
- timeout/network failures remain transient or inconclusive and are never converted into Store not-found evidence;
- useful aggregate Store/ADB/total audit timing diagnostics remain available without package names;
- benchmark-only detailed Store path/scraper instrumentation is no longer installed at normal application startup for the v1.5 release path.

Measured full-refresh checkpoints with 333 live packages and the same final classification of 324 available plus 9 not found in checked countries:

| Workers | Total time | Decision |
| ---: | ---: | --- |
| 12 | 185.850 s | slower |
| 14 | 200.877 s | anomalous back-to-back run; not used for v1.5 default selection |
| 16 | 168.854 s | v1.5 default/recommended value |
| 20 | 170.657 s | slightly slower than 16 |
| 24 | 171.166 s | slower with materially higher request latency |

The separate 14-vs-16 cooldown repeat is deliberately deferred to the next release. Users can already test alternative values through Advanced settings, so v1.5 does not need further benchmark-only rebuilds.

Do not reintroduce retries for propagated `NotFoundError`. Generic transient retries remain required.

## Pre-freeze decision on architecture cleanup

Two deeper refactors are intentionally deferred rather than introduced immediately before the v1.5 freeze:

- moving the bounded fallback scheduler out of `performance_diagnostics.py` into a dedicated canonical Store service;
- consolidating the terminal NotFound retry implementation so the base and device-enriched Store paths cannot drift.

Both are worthwhile cleanup targets, but they touch proven production Store behaviour. v1.5 keeps the validated implementation and removes only benchmark-only startup instrumentation. Perform these refactors in the next development cycle with focused semantic regression tests and fresh device benchmarks.

## Remaining v1.5 work

There is no unfinished v1.4 work and no additional product feature planned before v1.5.

Remaining release steps only:

1. final version/changelog/release-text hardening for `1.5.0`;
2. post-merge Quality validation;
3. freeze one exact `main` SHA;
4. prepare strict legal/source material from that SHA;
5. build Windows x64 from that same SHA;
6. assemble and validate the exact three-file ETB release set;
7. publish without modifying the frozen SHA, tag or assets afterward.

Do not start heavy package builds before the final release-hardening code/documentation PR is merged and the candidate SHA is selected.

## Durable release invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Published release history is immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- No public RC tag and no tag-triggered binary rebuild.
- Strict legal/source validation remains fail-closed.
- If source or release tooling changes after a release SHA is frozen, discard and rebuild all candidates required by that release profile from the new SHA.
- GitHub Release assets are permanent and outside automated Actions artifact cleanup.

See `PROJECT_DECISIONS.md`, `BUILDING.md` and `CI_MAINTENANCE.md` for durable policy and procedures.
