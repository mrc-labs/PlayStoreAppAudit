# Play Store App Audit v1.6 Chat Handoff

Last updated: 2026-08-21

## Purpose

This file is the human-readable handoff for starting a new development chat for Play Store App Audit v1.6 and later planning. It is intentionally concise enough to attach to a new chat while still preserving the decisions that should not be reconstructed from conversation history.

The canonical live sources remain:

- `docs/PROJECT_STATUS.md` for current shipped/development state;
- `docs/ROADMAP.md` for forward-looking release and feature planning;
- `docs/PROJECT_DECISIONS.md` for durable engineering/release policy;
- `AGENTS.md` for repository-wide implementation rules;
- `docs/BUILDING.md` for build/release procedures;
- `docs/RELEASE_NOTES.md` and `CHANGELOG.md` for release history.

When this handoff conflicts with a newer canonical file, the newer canonical file wins. Historical release wording and immutable published artifacts must not be rewritten to match later planning changes.

## Repository and latest release

Repository: `mrc-labs/PlayStoreAppAudit`

Latest published release at this handoff: `v1.5.0`, an unsigned Windows x64 Engineering Test Build.

Immutable v1.5.0 release source SHA:

`6f00bea0789874bc6339286a2ffc3eb9cb2891bb`

Do not rebuild, retag, rewrite or replace that published commit, tag or release assets.

The final v1.5.0 public project-defined assets are exactly:

- `PlayStoreAppAudit-v1.5.0-windows-x64.zip`
- `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`
- `SHA256SUMS.txt`

Payload SHA-256 values:

- Windows x64 ZIP: `942084863817852be53d63370b07b0a080728e8467f0e158deb8c2a1af354f8f`
- third-party source archive: `b24595b3bbf6adb77846104b246956d0f171777c8be81ef6e22b8d2b68a9a719`

Successful release evidence:

- Quality push run `32438975177`
- Windows x64 build run `32443253472`
- engineering release assembly run `32446825765`

## Current technical baseline

- Python packaging baseline: 3.13
- Quality CI: Python 3.13 and 3.14
- `PySide6-Essentials==6.11.1`
- `Nuitka==4.1.3`
- Qt 6 / PySide6 Qt Widgets, using platform/default QStyle
- ADB remains read-only with respect to installed Android apps
- Google Play scraping remains behind a replaceable service boundary
- default/recommended concurrent Store workers: 16
- Advanced worker range: 4 to 32
- Store transport timeout: 25 seconds
- experimental Play Store icons are opt-in and non-blocking

The new chat should verify the current `main` SHA from the generated repository snapshot rather than assuming the SHA at the time this static file was written.

## v1.6 release direction

The v1.6 public release profile is intentionally not frozen yet.

Current direction is likely another unsigned Windows x64-only Engineering Test Build, reusing the proven exact-SHA engineering release model from v1.5.

Do not assume Windows ARM64, Linux, macOS, Windows production signing or Apple notarization are v1.6 work.

Production signing and the full Windows/Linux/macOS x64/ARM64 production release are not planned before v2.0.

## v1.6 committed work

### Store architecture and reliability

1. Move the bounded multi-country fallback scheduler out of `performance_diagnostics.py` into a dedicated canonical Store service.
2. Consolidate terminal `NotFoundError` retry/classification handling so base and device-enriched Store paths cannot drift.
3. Preserve semantics: propagated scraper `NotFoundError` is terminal; timeout/network failures remain transient or inconclusive.
4. Harden persistent icon-cache disk failure handling so `OSError` cannot leave icons permanently pending and cache failures degrade safely.

The old 14-vs-16 worker benchmark is no longer required unless a later performance concern deliberately reopens it. Keep 16 as the baseline.

### Results and details UX

5. Add an app-details panel for the selected result row.
6. Let the user configure the panel dock position: right or below the results table.
7. Prefer detailed metadata in this panel rather than continually adding primary-table columns.
8. Include, where available: Play Store title, package ID, developer, Store URL, Store version/update information, country evidence, device metadata and previous-audit changes.
9. Re-evaluate Store icon placement. Current preferred candidate is beside the Play Store title rather than beside package name, because the icon is Store metadata.
10. Expose country-level evidence behind final availability classifications without weakening the existing regional/unavailability semantics.

### Audit-change visibility

11. Improve the existing previous-audit comparison with a clearer change-oriented view. Candidate groups include newly installed, removed from device, newly available, newly unavailable, reappeared, Store version/update change, Current/Aging/Stale transition and installer/source change when available.

### Experimental icons

12. Continue observing icon cache growth, CDN failures, stale-icon behaviour, large-table responsiveness and offline reuse before removing the `experimental` label.

### Optional v1.6 candidate

13. Consider a compact, optionally collapsible summary area above the results table with counts such as available, fallback-only, removed/inconclusive and Current/Aging/Stale. This is not yet committed and should be designed together with the details panel.

## v1.7 candidates

Keep these out of v1.6 unless scope is deliberately changed:

- saved audit profiles;
- incremental/smart re-audit with explicit full refresh;
- versioned JSON export;
- target/min SDK maintenance filters;
- installer/source classification and filtering;
- installed signing-certificate fingerprint capture/change detection;
- richer per-app diagnostics for inconclusive/anomalous results.

Saved filters / smart queries remain an open UX question. They mean named reusable result-filter expressions such as `Removed from Play AND still installed`, not saved audit configuration. Decide later whether they add enough value beyond Custom views and ordinary filters.

## v2.0 and later

Do not schedule these before v2.0 without a deliberate roadmap change:

- full six-platform production release;
- publicly trusted Windows signing;
- macOS Developer ID signing/notarization/stapling/Gatekeeper validation;
- CLI/headless auditing;
- LocalAPK-style local APK inventory/version comparison;
- possible advanced active app-management mode.

The LocalAPK concept is intentionally open: decide later whether local APK auditing belongs inside Play Store App Audit as another source/workflow or in a separate companion application sharing common services.

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
- Quality validation comes before freezing a release SHA.
- Tag only after candidate artifacts validate.
- Tag pushes do not rebuild binaries.
- Strict legal/source validation remains fail-closed.
- Do not trigger expensive package builds unless package evidence is actually required.

## Local development environment

Expected Windows repository path:

`%USERPROFILE%\Progetti\git\PlayStoreAppAudit`

The local development virtual environment should be `.venv` under the repository root and use Python 3.13.

Normal cheap validation:

```powershell
python -m compileall playstore_app_audit
python -m pytest
python -m ruff check .
```

The v1.5-local baseline immediately before this handoff passed 213 tests and Ruff, and the GUI started successfully from source. The next chat must treat the generated live snapshot and current CI as authoritative if test counts have changed.

## Files to attach to the new chat

Run `scripts/export_chat_handoff.ps1` from the repository root. It creates a timestamped ZIP in the user's temporary directory containing the files below plus a generated live repository snapshot.

Core files:

- `docs/HANDOFF_V1.6.md`
- `docs/ROADMAP.md`
- `docs/PROJECT_STATUS.md`
- `docs/PROJECT_DECISIONS.md`
- `AGENTS.md`
- `docs/BUILDING.md`
- `docs/RELEASE_NOTES.md`
- `CHANGELOG.md`
- `README.md`
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`

Generated evidence:

- `REPOSITORY_SNAPSHOT.md` with current branch/SHA/status, recent commits/tags, tracked source/test/workflow file list, Python version and optional GitHub CLI release/PR metadata.

Attach the generated ZIP to the new chat. The handoff Markdown is also inside it, so a separate attachment is optional.

## Command to prepare the handoff package

From the **VS Code integrated PowerShell** at the repository root:

```powershell
.\scripts\export_chat_handoff.ps1
```

The script intentionally refuses to create a handoff from a dirty working tree.

## Suggested first message for the v1.6 chat

Use something equivalent to:

> Read the attached Play Store App Audit v1.6 handoff package completely before making changes. Treat `PROJECT_DECISIONS.md` as durable policy, `PROJECT_STATUS.md` as current state and `ROADMAP.md` as forward planning. Verify the live repository state against `REPOSITORY_SNAPSHOT.md` and connected GitHub before writing. Continue v1.6 from the committed work in the handoff, using short-lived branches and normal PR merge commits only. Do not touch immutable published v1.5.0 artifacts/tag/source. Start by proposing the safest implementation order for the v1.6 Store-service refactors and details-panel work, then proceed autonomously unless a product decision is genuinely ambiguous.
