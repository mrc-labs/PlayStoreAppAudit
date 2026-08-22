# Play Store App Audit v1.6 Chat Handoff

Last updated: 2026-08-22

## Purpose

This file is the human-readable handoff for completing the Play Store App Audit v1.6.0 release and then moving into later planning. Product scope for v1.6 is closed; the remaining work is exact-SHA release execution.

Canonical live sources:

- `docs/PROJECT_STATUS.md` for current shipped/release state;
- `docs/ROADMAP.md` for forward-looking planning;
- `docs/PROJECT_DECISIONS.md` for durable engineering/release policy;
- `AGENTS.md` for repository-wide implementation rules;
- `docs/BUILDING.md` for build/release procedures;
- `docs/RELEASE_NOTES.md` and `CHANGELOG.md` for release history and release-body structure.

When this handoff conflicts with a newer canonical file, the newer canonical file wins. Historical published releases and their assets remain immutable.

## Repository and latest published release

Repository: `mrc-labs/PlayStoreAppAudit`

Latest published release while preparing v1.6.0: `v1.5.0`, an unsigned Windows x64 Engineering Test Build.

Immutable v1.5.0 release source SHA:

`6f00bea0789874bc6339286a2ffc3eb9cb2891bb`

Do not rebuild, retag, rewrite or replace that published commit, tag or release assets.

Published v1.5.0 project-defined assets:

- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Payload SHA-256 values:

- Windows x64 ZIP: `942084863817852be53d63370b07b0a080728e8467f0e158deb8c2a1af354f8f`
- third-party source archive: `b24595b3bbf6adb77846104b246956d0f171777c8be81ef6e22b8d2b68a9a719`

Successful v1.5 release evidence:

- Quality push run `32438975177`
- Windows x64 build run `32443253472`
- engineering release assembly run `32446825765`

## Current technical baseline

- Canonical v1.6 application version: `1.6.0`
- Python packaging baseline: 3.13
- Quality CI: Python 3.13 and 3.14
- `PySide6-Essentials==6.11.1`
- `Nuitka==4.1.3`
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle
- ADB remains read-only with respect to installed Android apps
- Google Play scraping remains behind the canonical Store service boundary
- default/recommended concurrent Store workers: 16
- Advanced worker range: 4 to 32
- Store transport timeout: 25 seconds
- experimental Play Store icons remain opt-in and non-blocking

Always verify the live `main` SHA from GitHub or a newly generated repository snapshot rather than assuming a SHA written in this static handoff.

## Frozen v1.6.0 release profile

v1.6.0 is frozen as an **unsigned Windows x64-only Engineering Test Build**.

Release execution rules:

- build Windows x64 only;
- use `.github/workflows/build-windows-exe.yml` with `target=x64`;
- do not build Windows ARM64, Linux or macOS release candidates;
- do not invoke production Windows signing;
- do not invoke macOS Developer ID signing/notarization;
- assemble with `.github/workflows/assemble-windows-engineering-release.yml`;
- use one exact post-Quality `main` SHA for build and assembly;
- publish only after the assembled artifacts validate;
- tag pushes must not rebuild binaries.

Exactly three public project-defined assets are allowed:

- `PlayStoreAppAudit-v1.6.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Release title:

`Play Store App Audit v1.6.0 (ETB Win x64)`

Release-body heading:

`## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`

The release must clearly state that the Windows package is unsigned.

Production signing and the full Windows/Linux/macOS x64/ARM64 production profile are deferred until v2.0 or later.

## v1.6 product scope completed

### Store architecture and reliability

- The bounded multi-country fallback scheduler lives in the canonical Store service rather than `performance_diagnostics.py`.
- Propagated `google_play_scraper.exceptions.NotFoundError` is terminal for the outer retry loop after the scraper's own fallback; generic transient failures retain retry/backoff.
- Timeout/network failures remain transient or inconclusive and are never converted into false Store not-found evidence.
- Same-country English fallback is used only for inconclusive or metadata-incomplete cases, not to repeat conclusive terminal not-found results.
- Store request country/language evidence is structured.
- Default/recommended Store workers remain 16.

### Device locale / Store locale

- In `auto` mode, a connected Android phone uses its actual active system language where available.
- Android locale region can initialize the Store country for phone scans.
- Example: `it-CH` means Store request preference `CH / it`.
- The UI identifies country inference as coming from Android locale and does not claim it is the Google Play account country.
- File/list audits use the principal language of the selected Store country and clear any previously active phone-language context.
- Explicit manual country/language overrides remain supported.

### Icon cache and Store metadata

- Persistent icon-cache filesystem `OSError` failures degrade safely to cache miss/network fallback and cannot leave a permanent pending state.
- Experimental icons are displayed beside the Play Store title rather than beside package ID.
- Developer metadata is captured from the same normal Store response, with no additional Store request.
- Icon/developer metadata is retained through the normal healthy-result cache path.

### Selected-row details panel

- Details panel is attached to the results table.
- User can choose Right or Below and the position is persisted.
- Panel exposes Store title/package/developer/URL/version/update data, installed/device metadata, structured country/language evidence and previous-audit changes.
- Selecting a result updates the panel; the first result is selected after reset when available.

### Change-oriented previous-audit view

Grouped Audit changes view covers:

- newly installed apps when a real previous device inventory exists;
- removed-from-device packages;
- newly available Store listings;
- newly unavailable results in checked countries;
- reappeared listings;
- Store version changes;
- Store latest-update changes;
- Current/Aging/Stale maintenance transitions;
- installer/source changes.

The first device inventory is a baseline and does not create hundreds of false newly-installed events. Installer/source events known through multiple comparison paths are deduplicated.

### Explicitly not included in v1.6.0

- richer optional dashboard/summary area;
- saved audit profiles;
- incremental/smart re-audit;
- versioned JSON export;
- target/min SDK maintenance filters;
- signing-certificate fingerprint change tracking;
- active app management;
- CLI/headless mode;
- full signed six-platform release.

## Current validation baseline before final release execution

The final v1.6 product slice passed normal development gates with:

- 262 pytest tests;
- Ruff;
- Qt offscreen smoke on Python 3.13 and 3.14;
- Windows native vs Fusion UI audit;
- macOS native vs Fusion UI audit;
- Linux native vs Fusion UI audit.

The engineering release workflow/policy alignment also passed the Quality matrix after its regression test was updated to enforce the unsigned ETB/v2.0-signing policy.

These are not final v1.6 release evidence. Final evidence must come from the exact frozen release SHA after the profile/version freeze is merged to `main`.

## Immediate release-execution sequence

1. Merge the v1.6 profile/version freeze with a normal merge commit.
2. Require the post-merge Quality push run to succeed on that exact `main` SHA.
3. Record that exact full SHA as the v1.6 release SHA.
4. Dispatch `.github/workflows/build-windows-exe.yml` from `main` with:
   - `target=x64`
   - `expected_sha=<frozen release SHA>`
5. Require the Windows x64 build/package/legal checks to pass and record the successful `Build Windows - Qt6` run ID.
6. Dispatch `.github/workflows/assemble-windows-engineering-release.yml` from the same SHA with:
   - `expected_sha=<same frozen release SHA>`
   - `windows_run_id=<successful x64 build run>`
7. Require the assembler to emit exactly the three frozen-profile assets with no extra directories.
8. Verify `SHA256SUMS.txt` against the actual final artifacts.
9. Prepare the release body using the canonical section order in `docs/RELEASE_NOTES.md`; do not claim checks that have not actually passed.
10. Create annotated tag `v1.6.0` on the same frozen SHA only after artifact validation.
11. Create the GitHub Release and upload the already validated assets.
12. Verify the published tag/SHA/release/assets/checksums again after publication.
13. Treat the published v1.6.0 release as immutable.

If source code or release tooling changes after step 3, discard the candidate SHA and repeat the required build/assembly from the new exact `main` SHA. Never mix artifacts from different SHAs.

## v1.7 candidates

Keep these out of v1.6.0 unless the freeze is deliberately reopened:

- saved audit profiles;
- incremental/smart re-audit with explicit full refresh;
- versioned JSON export;
- target/min SDK maintenance filters;
- installer/source classification/filtering improvements;
- installed signing-certificate fingerprint capture/change detection;
- richer per-app diagnostics for inconclusive/anomalous results.

Saved filters / smart queries remain an open UX question. They mean named reusable result-filter expressions, not saved audit configuration.

## v2.0 and later

Do not schedule these before v2.0 without a deliberate roadmap change:

- full six-platform production release;
- publicly trusted Windows signing;
- macOS Developer ID signing/notarization/stapling/Gatekeeper validation;
- CLI/headless auditing;
- LocalAPK-style local APK inventory/version comparison;
- possible advanced active app-management mode.

The LocalAPK concept remains open: decide later whether local APK auditing belongs inside Play Store App Audit or in a separate companion application sharing common services.

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
- Before any local pull, run `git status --short`; if dirty, stop rather than resetting/stashing/discarding automatically.
- Published releases are immutable.
- Every release profile uses one exact frozen source SHA.
- Quality validation comes before recording the release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- Do not trigger package workflows outside the frozen release profile.

## Handoff package

Run `scripts/export_chat_handoff.ps1` from the repository root. It creates a timestamped ZIP containing this handoff, canonical project/release documents and a generated live repository snapshot.

From the VS Code integrated PowerShell at the repository root:

```powershell
.\scripts\export_chat_handoff.ps1
```

The script intentionally refuses to create a handoff from a dirty working tree.

A new chat should read the package completely, verify live GitHub state, and continue from the exact current release stage rather than repeating product planning that is already closed.
