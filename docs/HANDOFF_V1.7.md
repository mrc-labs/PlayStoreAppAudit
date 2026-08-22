# Play Store App Audit v1.7 Chat Handoff

Last updated: 2026-08-22

## Purpose

This is the canonical human-readable handoff for starting the Play Store App Audit v1.7 development cycle after the successful v1.6.0 publication.

Read this file together with:

- `docs/PROJECT_STATUS.md` for the current shipped and development baseline;
- `docs/ROADMAP.md` for active priorities and later candidates;
- `docs/PROJECT_DECISIONS.md` for durable engineering/release policy;
- `AGENTS.md` for repository-wide implementation rules;
- `docs/BUILDING.md` for build/release procedures;
- `docs/RELEASE_NOTES.md` and `CHANGELOG.md` for release history.

When this handoff conflicts with a newer canonical file, the newer canonical file wins. Published releases remain immutable.

## Repository and published baseline

Repository: `mrc-labs/PlayStoreAppAudit`

Latest published release: `v1.6.0`

Release class: unsigned Windows x64 Engineering Test Build (ETB).

Immutable v1.6.0 source SHA:

`246acb15b8e9b2aa9155dc1c3a7c24dc32d19540`

Do not rebuild, retag, rewrite or replace that published commit, tag or release assets.

Published project-defined assets:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Published payload SHA-256 values:

- Windows x64 ZIP: `66e8c94bed69e53d16cf7784ab028089437078b8bc809c4385474ff83c0b55be`
- third-party source archive: `0f068f20ef14e0e53bd4869c66ae6542725a5c34e390cebf804279a8b28b1165`
- `SHA256SUMS.txt`: `0e7c7f6f1f290778139c47d929bb3ea0758022eb1199b9911c54893dd6dff8c5`

Successful v1.6 release evidence:

- post-merge Quality push run `32543925562`
- Windows x64 build run `32545213663`
- engineering release assembly run `32547942460`

The public files were downloaded again after publication and independently SHA-256 verified.

## Current technical baseline

- Canonical application version remains `1.6.0` until a later deliberate version/release freeze.
- Python packaging baseline: 3.13.
- Quality CI: Python 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`.
- `Nuitka==4.1.3`.
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle.
- ADB remains read-only with respect to installed Android apps.
- Google Play scraping remains behind the canonical Store service boundary.
- Default/recommended concurrent Store workers: 16.
- Advanced worker range: 4 to 32.
- Store transport timeout: 25 seconds.
- Experimental Play Store icons remain opt-in and non-blocking.

Always verify the live `main` SHA from GitHub or a newly generated repository snapshot rather than assuming a SHA written in this static handoff.

## Shipped v1.6 product baseline

### Store service and correctness

- Bounded multi-country fallback scheduling lives in the canonical Store service rather than performance diagnostics.
- Propagated `google_play_scraper.exceptions.NotFoundError` is terminal for the outer retry loop after the scraper's own internal fallback.
- Generic transient failures retain retry/backoff.
- Timeout/network failures remain transient or inconclusive and are never converted into false Store not-found evidence.
- Same-country English fallback is limited to inconclusive or metadata-incomplete cases and does not repeat a conclusive terminal not-found merely to change language.
- Store country/language request evidence is structured and JSON-serializable.

### Store locale behaviour shipped in v1.6

- Connected-phone `auto` Store language uses the active Android system language where available.
- File/list audits use the principal language of the selected Store country and do not inherit a previously connected phone language.
- Manual Store country and language overrides remain supported.
- v1.6 also allows Android locale region to initialize Store country for a phone scan.
- The UI correctly avoids claiming that Android locale region is the actual Google Play account country.

The last country behaviour is now intentionally under review and is the first correctness task for v1.7.

### Selected-row details panel

- A details panel is attached to the results table.
- v1.6 offers persisted Right or Below placement.
- It exposes Store title/package/developer/URL/version/update data, installed/device metadata, structured country/language evidence and previous-audit changes.
- Developer metadata is captured from the same normal Store response, without an additional request.

### Previous-audit change visibility

A grouped Audit changes view covers:

- newly installed apps when a real previous device inventory exists;
- removed-from-device packages;
- newly available Store listings;
- newly unavailable results in checked countries;
- reappeared listings;
- Store version changes;
- Store latest-update changes;
- Current/Aging/Stale maintenance transitions;
- installer/source changes.

The first device inventory is a baseline and does not create hundreds of false newly-installed events.

### Experimental Store icons

- Icons are shown beside the Play Store title rather than package ID.
- Filesystem/cache `OSError` failures degrade safely to cache miss/network fallback.
- The feature remains experimental, opt-in and non-blocking.

## v1.7 priority 1: Correct Store country vs language semantics

This is a correctness review prompted by real-world testing of v1.6.0.

Country and language must be treated as separate signals.

### Planned automatic Store language

For a connected Android phone:

1. Prefer the active Android system language obtained through read-only ADB metadata.
2. Preserve explicit manual language override.

For file/list audits without usable phone-language context:

1. Use the principal/default language of the selected Store country.
2. Preserve explicit manual language override.
3. Unknown language falls back to English.

### Planned automatic Store country resolution

Prefer the pre-v1.6 host/computer-region approach. The intended resolution chain is:

1. Host/computer region.
   - Windows: prefer `GetUserDefaultGeoName()` as the old `detect_store_country()` did.
   - Linux/macOS/other hosts: use the existing locale/environment based country extraction where available.
2. Only if host-region detection does not yield a usable ISO alpha-2 country, use Android locale region as a late fallback when available.
   - Example: Android locale `it-CH` may yield country `CH` only at this fallback stage.
3. If neither host nor Android locale yields a usable country, retain the final safe fallback `US` unless a later deliberate decision changes it.
4. Manual Store-country override always wins when explicitly selected.

Important constraints:

- Do not derive Store country from Android language alone.
- Example target behaviour: host region Switzerland + Android system language Italian -> Store country `CH`, Store language `it`.
- Android locale region is not the Google Play account country and must not be presented as such.
- A reliable supported Google Play account-country signal may be investigated, but do not use privileged/root Play Store-state scraping and do not block the host-region correction on finding such a signal.
- Language fallback must not change a conclusive geographic not-found conclusion.

### Required real-device validation

Before considering the v1.7 locale model settled, test at least:

- host CH + Android `it-CH`;
- host CH + Android `de-CH`;
- host CH + Android `fr-CH`;
- host CH + Android `en-CH`;
- host region and Android locale region disagreeing;
- Android language present but region missing/unusable;
- file/list audit after phone scan to verify phone context does not leak;
- manual country override;
- manual language override;
- localized Store title/metadata changes for multiple languages in the same country;
- multi-country fallback where availability differs geographically.

## v1.7 priority 2: Redesign details-panel placement and responsiveness

The v1.6 panel works functionally but the current Right/Below selector is visually poor and the Below layout wastes horizontal space.

### Position control direction

- Replace the current prominent selector with a compact view/layout affordance, preferably icon-based.
- Evaluate `Auto / Right / Below`.
- Do not assume Auto is the final default before visual testing.
- Preserve explicit Right and Below choices if Auto is introduced.

### Internal responsive layout direction

Panel placement and content arrangement are different concerns.

When narrow, the panel may remain primarily vertical.

When wide, especially below the results table, sections should be able to sit side by side. Candidate organization:

- Store beside Installed device;
- Country/language evidence beside Changes since previous audit;
- Notes/long free-form content may span wider when appropriate.

The actual arrangement should respond to available width rather than simply checking whether the panel position is Right or Below.

Avoid:

- one long vertical column in a wide bottom panel;
- rigid grids that create large empty areas because one section is much taller than another;
- layout churn during small splitter movements;
- a position selector that visually resembles a settings form.

Acceptance direction:

- Right remains usable at typical desktop widths;
- Below clearly benefits from horizontal space;
- resizing/repositioning causes sensible reflow;
- content remains readable at narrower sizes;
- the layout control is compact and visually coherent with the rest of the Qt UI.

## v1.7 priority 3: Better per-app diagnostics

Build on the structured Store evidence already present. Do not parse display `notes` to recover semantics.

For inconclusive/anomalous results, expose useful structured diagnostics where available:

- attempted countries;
- attempted languages;
- Store path/fallback evidence;
- retry count;
- failure reason;
- terminal not-found vs transient/inconclusive distinction.

This work should fit naturally into the redesigned details panel.

## Other v1.7 candidates

After the first priorities, consider:

- installer/source classification and filtering for Play Store, alternative stores, sideloaded/unknown and other observable installer sources;
- target/min SDK maintenance filters and compatibility hygiene without presenting them as a security score;
- installed signing-certificate fingerprint capture/change detection where available through read-only device metadata;
- saved audit profiles;
- incremental/smart re-audit with conservative cache policy and explicit full refresh;
- versioned JSON export;
- saved filters/smart queries, pending UX clarification;
- continued experimental-icon maturity testing;
- a richer compact dashboard/summary only if it adds value after the details/change UX matures.

Saved filters/smart queries mean named reusable result-filter expressions, not saved audit configurations.

## v2.0 and later

Keep out of normal v1.7 scope unless the roadmap is deliberately changed:

- full Windows/Linux/macOS x64/ARM64 production distribution;
- publicly trusted Windows signing;
- macOS Developer ID signing/notarization/stapling/Gatekeeper validation;
- CLI/headless auditing;
- LocalAPK-style local APK inventory/version comparison;
- possible advanced active app-management mode.

Active app-management actions would require an explicit change to the durable read-only ADB policy and stronger safety boundaries.

## Explicitly rejected for now

Do not reintroduce without a new product decision:

- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined DACH/EU/worldwide country-set presets.

## Git and release rules that must survive the chat boundary

- `main` is the only permanent branch.
- Use short-lived branches and normal PR merge commits only.
- Do not squash or rebase project PR history.
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting, stashing or discarding automatically.
- Published releases are immutable.
- Every release profile uses one exact frozen source SHA.
- Quality validation comes before recording a release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- ADB remains read-only with respect to installed Android apps.
- Do not trigger expensive package workflows outside a deliberately chosen release profile.

## Starting the new v1.7 chat

Use `scripts/export_chat_handoff.ps1` from a clean, up-to-date `main` checkout after the post-release housekeeping PR has merged.

The exporter should produce a timestamped `PlayStoreAppAudit-v1.7-chat-handoff-*.zip` containing this handoff, canonical project/release documents and a generated `REPOSITORY_SNAPSHOT.md` with live branch/SHA/status, recent commits/tags and optional GitHub CLI metadata.

Attach that ZIP to the new chat and instruct the new chat to read the package completely before changing the repository.
