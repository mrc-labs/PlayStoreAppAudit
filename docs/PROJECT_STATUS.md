# Project Status

Last updated: 2026-08-22

## Published release

- Latest published version: `v1.6.0`
- Immutable release commit: `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`
- Release class: Engineering Test Build (ETB), Windows x64 only
- Signing: intentionally unsigned
- GitHub Release title: `Play Store App Audit v1.6.0 (ETB Win x64)`
- Public project-defined assets: exactly 3

Published v1.6.0 is immutable. Do not rebuild, retag, rewrite or replace its published commit, tag or assets. Earlier published releases remain immutable as well.

## v1.6.0 release evidence

The v1.6.0 release was built, assembled and published from one exact frozen `main` SHA: `246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`.

Release gates and evidence:

- post-merge Quality push run: `32543925562`, successful on the frozen SHA with Python 3.13 and 3.14;
- Windows x64 build run: `32545213663`, successful on the same frozen SHA;
- engineering release assembly run: `32547942460`, successful on the same frozen SHA;
- final public release asset set: exactly three project-defined files;
- published release verified as non-draft and non-prerelease;
- annotated `v1.6.0` tag peels to the frozen SHA;
- published assets were downloaded again after release and independently SHA-256 verified against `SHA256SUMS.txt`.

Published project-defined assets:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Final SHA-256 values:

- Windows x64 ZIP: `66e8c94bed69e53d16cf7784ab028089437078b8bc809c4385474ff83c0b55be`
- third-party source archive: `0f068f20ef14e0e53bd4869c66ae6542725a5c34e390cebf804279a8b28b1165`
- `SHA256SUMS.txt`: `0e7c7f6f1f290778139c47d929bb3ea0758022eb1199b9911c54893dd6dff8c5`

## Current development baseline

- Canonical application version remains `1.6.0` until a later release-profile/version freeze deliberately changes it.
- Active planning cycle: `v1.7`.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials`: 6.11.1.
- Nuitka: 4.1.3.
- UI: Qt Widgets using the platform/default QStyle.
- Managed ADB behaviour remains read-only with respect to installed Android apps.
- Default/recommended concurrent Store workers remain 16.
- Store transport timeout remains 25 seconds.
- Experimental Play Store icons remain opt-in and non-blocking.

## Shipped v1.6 product baseline

### Store architecture and reliability

- Bounded multi-country fallback scheduling lives in the canonical Store service.
- Propagated `google_play_scraper.exceptions.NotFoundError` remains terminal for the outer retry loop after the scraper's own fallback.
- Generic transient failures retain retry/backoff.
- Timeout/network failures remain transient or inconclusive and are never converted into false Store not-found evidence.
- Store country/language request evidence is structured and exposed in the details UX.
- Same-country English fallback is limited to inconclusive or metadata-incomplete cases and is not used to repeat conclusive terminal not-found results.

### Locale behaviour shipped in v1.6

- In `auto` mode, a connected Android phone can provide its active system language for Store metadata.
- v1.6 also allows Android locale region to initialize Store country for phone scans.
- The UI labels that country as inferred from Android locale rather than claiming it is the Google Play account country.
- File/list audits use the principal language of the selected Store country and clear any previously active phone-language context.
- Explicit manual Store country and language overrides remain available.

This country behaviour is now under deliberate v1.7 review. The planned correction is documented in `ROADMAP.md` and `HANDOFF_V1.7.md`; do not treat the v1.6 phone-region behaviour as the desired long-term semantic.

### Details and change UX

- A selected-row details panel is attached to the results table.
- v1.6 supports persisted Right or Below placement.
- The panel exposes Store metadata, installed/device metadata, structured country/language evidence and previous-audit changes.
- A grouped Audit changes overview covers device inventory, Store availability, reappeared listings, Store version/update changes, maintenance-state transitions and installer/source changes.
- The first device inventory is treated as a baseline rather than as hundreds of newly installed events.

### Store metadata and icons

- Experimental Store icons are displayed beside the Play Store title.
- Developer metadata is captured from the same normal Store response, without an extra request.
- Persistent icon-cache filesystem failures degrade to cache miss/network fallback and cannot leave icons permanently pending.

## v1.7 immediate priorities

The first v1.7 work should focus on two issues discovered during real-world use of v1.6.0.

### 1. Details panel UX and responsive layout

- Replace the current conspicuous Right/Below selector with a compact layout control, preferably icon-based.
- Evaluate `Auto / Right / Below` rather than committing to it before visual testing.
- Treat panel placement and internal information layout as separate concerns.
- When the panel is wide, especially below the table, arrange sections side by side rather than preserving one long vertical column.
- Candidate grouping includes Store next to Installed device, and Country/language evidence next to Changes since previous audit.
- Reflow dynamically according to actual available width. Do not hardcode a rigid one-column-vs-two-column rule if a more adaptive layout is practical.

### 2. Store country and language semantics

The planned v1.7 direction separates country from language more strictly:

- Store language for a connected phone: use the active Android system language when available.
- Store country automatic detection: prefer the host/computer region using the pre-v1.6 platform logic.
- On Windows, the host-region path should prefer `GetUserDefaultGeoName()` as before.
- On other hosts, retain the existing locale/environment based region detection where available.
- Only if host-region detection cannot produce a usable country may the Android locale region be used as a late fallback, for example `it-CH` -> `CH`.
- If neither source yields a usable region, retain the final safe fallback (`US` unless a later deliberate decision changes it).
- Manual Store-country and Store-language overrides remain available.
- Do not claim that any of these signals represent the real Google Play account country unless a reliable supported signal is found.

The country/language model requires real-device validation before it is considered settled for v1.7.

## Other v1.7 candidates

- richer per-app diagnostics for inconclusive/anomalous results;
- installer/source classification and filtering;
- target/min SDK maintenance filters;
- saved audit profiles;
- incremental/smart re-audit with explicit full refresh;
- versioned JSON export;
- installed signing-certificate fingerprint capture/change detection;
- saved filters/smart queries, pending UX clarification;
- continued real-world observation of experimental icon behaviour;
- reconsideration of a compact dashboard/summary only if it adds clear value after the details/change UX matures.

See `ROADMAP.md` for prioritization and later-version items.

## Durable release and repository invariants

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Do not squash or rebase project PR history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile derives all artifacts from one exact frozen SHA.
- Quality validation comes before recording a release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- Production signing and the full six-platform production release are not planned before v2.0 unless the roadmap is deliberately changed.

See `PROJECT_DECISIONS.md`, `ROADMAP.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `HANDOFF_V1.7.md` for durable policy, planning and handoff context.
