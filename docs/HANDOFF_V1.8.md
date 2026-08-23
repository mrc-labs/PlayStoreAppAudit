# Play Store App Audit v1.8 Chat Handoff

Last updated: 2026-08-23

## Purpose

This is the canonical human-readable handoff for the v1.8 development cycle after successful publication of v1.7.0. Read it with `PROJECT_STATUS.md`, `ROADMAP.md`, `PROJECT_DECISIONS.md`, `AGENTS.md`, `BUILDING.md`, `RELEASE_NOTES.md`, `CI_MAINTENANCE.md` and `RELEASE_CLOSURE.md`.

## Immutable v1.7.0 baseline

- Release: `v1.7.0`
- GitHub Release title: `Play Store App Audit v1.7.0 (Win x64 Only)`
- Release class: unsigned Windows x64 Engineering Test Build (ETB)
- Frozen source SHA: `e2d09098bc42c6f16d202d010deda3eb24d99aa3`
- Quality push run: `32609018096`
- Final Windows x64 build run: `32609148943`
- Engineering assembly run: `32610281618`
- Publish/post-publication verification run: `32610914851`

Published project-defined assets:

- `PlayStoreAppAudit-v1.7.0-windows-x64.zip` — SHA-256 `142b15e40fba3d7ed8b29e1e37b366551dde3cf65e18608434869f4528d50c1b`
- `PlayStoreAppAudit-v1.7.0-third-party-sources.tar.xz` — SHA-256 `9a3991509a8629a2827074b939975c048695b4557e2e22635eef35336c682458`
- `SHA256SUMS.txt` — SHA-256 `984d81cc77f60e10b1033199ba71b4737adb0b272c416d268a8e5025226e2ae9`

The annotated `v1.7.0` tag peels to the frozen SHA and all three public assets were re-downloaded and checksum-verified after publication. Do not rebuild, retag or replace them.

## Current technical baseline

- Canonical app version remains `1.7.0` until a deliberate v1.8 release/version freeze.
- Python packaging baseline: 3.13; Quality CI: 3.13 and 3.14.
- `PySide6-Essentials==6.11.1`; `Nuitka==4.1.3`.
- Qt 6 / PySide6 Qt Widgets using platform/default QStyle.
- ADB remains read-only with respect to installed Android apps.
- Google Play remains behind the service boundary.
- Store workers default/recommended 16; allowed advanced range 4-32; Store timeout 25 seconds.
- v1.8 and v1.9 releases are Windows x64 only and intentionally unsigned unless a new explicit product decision changes that.
- v2.0 is the first planned return to multi-platform distribution; production signing is an ideal target but is not guaranteed until real provider/credential and end-to-end validation succeeds.

## v1.7 features available as the v1.8 base

- responsive Details Panel with Auto/Right/Below placement and adaptive content layout;
- independent Store country/language semantics;
- structured Store evidence with concise user-facing diagnostics/Notes;
- installer/source classification and filters;
- SDK maintenance filters;
- versioned JSON export;
- saved audit profiles;
- conservative smart/incremental re-audit plus targeted rechecks and Force full refresh;
- separate Store-audit and phone-inventory history semantics;
- optional supported Health Score maintenance heuristic, disabled by default.

## v1.8 active scope

### Play Store icons

Graduate Play Store icons from experimental to normal supported behavior, subject to final cache/CDN/offline/large-table hardening from v1.7 observations.

### Saved filters / smart queries

Implement reusable result-filter expressions, deliberately separate from saved audit profiles. Define the UX before implementation.

### Richer compact dashboard / summary

Add useful at-a-glance information without duplicating Details Panel, change overview or filter state.

### Details Pane UX v2

The current Auto/Right/Below buttons are readable and already have hover tooltips, but they consume too much header space. Explore:

- ability to hide the Details Panel completely;
- one compact Details control/menu instead of expanding three buttons to four;
- candidate states Auto / Right / Below / Hide;
- keep platform-native Qt styling and avoid unnecessary theme dependencies;
- `QDockWidget` only as an experiment, not a predetermined solution.

### Status bar alternative

The user specifically means an Excel-like bottom status bar. Treat a true Qt `QStatusBar` as an alternative if the primary Details-control solution is not visually successful, not as a committed design. Possible uses: connected device/source identity on the left, transient status/progress centrally, compact secondary view controls on the right.

### Advanced Settings redesign

The current functional layout looks old-style. Explore category navigation plus focused pages, less stacked `QGroupBox` chrome, and moving purely visual settings to View where appropriate.

### Full UX audit before broad changes

Produce a report before implementing broad visual changes. Review all menus, buttons, icons, tooltips/statusTips, shortcuts/mnemonics, export consistency, context-menu disabled states, status chips, search/filter discoverability and permanent tips/legends. Do not automatically implement the audit findings until reviewed.

## v1.9 and v2.0 distribution roadmap

- v1.9: Windows x64 only; detailed product scope not frozen yet.
- v2.0: first planned return to Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 prebuilt releases.
- Ideally Windows/macOS will be production signed/notarized in v2.0, but do not promise that until eligibility, credentials, cost and end-to-end workflows are validated.
- CLI/headless work remains v2.0-or-later.

## Explicitly removed / not planned

Do not reintroduce without a new product decision:

- installed signing-certificate fingerprint/change detection;
- automatic alternative-source association for unavailable Play apps;
- audit watchlists/background monitoring;
- predefined country presets such as DACH/EU/worldwide.

## Release and Git rules

- `main` is the only permanent branch.
- Use short-lived branches and normal merge commits; no squash/rebase project history.
- Published releases are immutable.
- Before every local pull, run `git status --short`; if dirty, stop. Never auto-stash/reset/discard/clean user work.
- Every release uses one exact frozen SHA and tags only after artifact validation.
- Tag pushes do not rebuild binaries.
- Keep strict legal/source validation fail-closed.
- Windows x64 ETB GitHub Release titles now use `(Win x64 Only)`; body headings continue to identify `Engineering Test Build - Windows x64 Only`.
- Finish every release through `RELEASE_CLOSURE.md`, including post-release docs and safe local VS Code synchronization.

## Starting the v1.8 development chat

After this post-release documentation PR is merged, synchronize the local VS Code checkout safely to canonical `main` and verify it is clean. Only then run `scripts/export_chat_handoff.ps1`; it automatically selects the newest `docs/HANDOFF_V*.md`, so the resulting ZIP should be a v1.8 handoff and include a freshly generated `REPOSITORY_SNAPSHOT.md`.
