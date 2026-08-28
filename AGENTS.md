# AGENTS.md

## Project

Play Store App Audit is a Python desktop application that audits Android package IDs against public Google Play listings and, optionally, enriches results from an Android device through ADB.

The production UI is Qt 6 / PySide6 Qt Widgets. The former CustomTkinter implementation is retired and preserved only as the historical Git tag `legacy-customtkinter-v9.3`.

Durable engineering decisions live in `docs/PROJECT_DECISIONS.md`. Current shipped/development state lives in `docs/PROJECT_STATUS.md`. Forward-looking release/feature planning lives in `docs/ROADMAP.md`. The detailed release procedures live in `docs/BUILDING.md`. Permanent release-closure and local VS Code synchronization requirements live in `docs/RELEASE_CLOSURE.md`. GitHub Actions retention and post-release housekeeping live in `docs/CI_MAINTENANCE.md`. The canonical GitHub Release body structure and historical normalized release-note wording live in `docs/RELEASE_NOTES.md`.

When old version-specific scheduling language in an operational document conflicts with the current roadmap, preserve the operational procedure but follow `PROJECT_DECISIONS.md` and `ROADMAP.md` for the current milestone assignment. Historical release wording in `CHANGELOG.md` and `RELEASE_NOTES.md` is not rewritten to match later roadmap changes.

## Architecture

All production application code belongs under `playstore_app_audit/`:

- `playstore_app_audit/app.py`: application entry point only.
- `playstore_app_audit/domain/`: typed domain models and pure business concepts.
- `playstore_app_audit/services/`: Play Store, audit, cache/history/report service boundaries.
- `playstore_app_audit/devices/`: ADB/device integration.
- `playstore_app_audit/platform/`: Windows/macOS/Linux abstraction.
- `playstore_app_audit/ui/`: Qt Widgets UI only.

The version-suffixed top-level Qt and feature modules have been removed. Internal Qt layers use descriptive package module names such as `base_window`, `audit_window`, `device_window`, `preferences_window` and `results_window`, with `main_window.py` as the public UI entry point.

Do not reintroduce cross-module runtime monkey-patching for audit selection, classification, cache bypass or ADB metadata enrichment. Keep extension points explicit and local.

The UI still uses a layered inheritance structure for proven behaviour. Reduce it incrementally only where composition or smaller focused widgets/controllers clearly improve maintainability. Do not combine a large behavioural rewrite with a structural migration.

UI code must not implement Google Play parsing, cache persistence, ADB discovery/download logic or OS detection directly.

## Runtime and dependencies

- Release packaging baseline: Python 3.13 until a deliberate, validated toolchain migration.
- Quality CI: Python 3.13 and 3.14.
- Current PySide6 baseline: `PySide6-Essentials==6.11.1`.
- Current release compiler pin: `Nuitka==4.1.3`.
- UI technology: Qt Widgets, not QML unless a demonstrated UX, maintainability or performance reason justifies migration.
- Keep `google-play-scraper` behind a service boundary because it is unofficial and replaceable.
- HTTP fallback uses `requests` + BeautifulSoup with Python's built-in `html.parser`; do not re-add `lxml` without a measured need.

Avoid adding libraries for functionality available cleanly in the Python standard library or Qt Essentials.

## Correctness rules

- Never use Google Play `datePublished` as the latest update date. Only update-specific fields such as `dateModified`, explicit `updated`, or visible `Updated on` text are valid.
- A package unavailable in one Store country is not automatically globally removed. Preserve multi-country fallback logic and uncertainty states.
- Maintenance Score is the user-facing name for the maintenance heuristic; the compatibility-sensitive internal identifier remains `health_score`. It is not a malware/security score.
- A different installed/store version is not automatically outdated; device-specific or staged rollouts are possible.
- ADB operations remain read-only with respect to installed Android applications unless a future change is explicitly approved.

## UX rules

- The Basic view must remain compact and understandable to non-expert users.
- Advanced settings remain behind the Tools menu and should warn users before changing technical behaviour.
- Presentation-only actions, including changing View presets, must not overwrite the more relevant audit/progress/status message.
- Avoid adding vertical UI sections when an existing row, menu or dialog can contain the feature cleanly.
- Status chips above the table support multi-selection.
- Production startup uses Qt's platform/default QStyle. Do not globally force Fusion or add a theme dependency without new cross-platform evidence.

## Cross-platform rules

All feature code should work on Windows, macOS and Linux unless the feature is inherently platform-specific.

Put platform-specific behaviour behind `playstore_app_audit.platform` or `playstore_app_audit.devices`, including:

- Platform-Tools download URL and executable name
- app-data directories
- Store-country detection
- subprocess console hiding
- icon/bundle handling
- packaging/signing

Do not hard-code `adb.exe`, `%LOCALAPPDATA%`, Windows-only SDK paths or Windows-only console flags in shared UI/service code.

## Release invariants

These are hard constraints unless deliberately changed through a dedicated engineering decision:

- `main` is the only permanent branch. Use short-lived branches and normal PR merge commits.
- Published release history is immutable. Do not squash, rewrite, retag or replace published release assets.
- A release profile freezes one exact full `main` SHA after Quality CI passes.
- Build workflows must reject mismatches between expected SHA, dispatch SHA and checked-out SHA.
- Do not create public RC tags.
- Release-tag pushes must not rebuild binaries. Publish the already validated artifacts.
- If source or release tooling changes after the SHA is frozen, discard and rebuild every candidate required by the selected release profile from the new exact SHA. Never mix artifacts from different SHAs.
- Do not weaken legal/source validation to make a build pass.
- Do not delete files under `.github/scripts/` merely because there are several. Verify workflow references, imports and tests before removal.
- GitHub Actions retention follows the generational policy in `docs/CI_MAINTENANCE.md`; failed/cancelled runs never replace successful generations.
- Every public GitHub Release body follows `docs/RELEASE_NOTES.md`: the four mandatory sections are `What's New / Highlights`, `Compatibility and distribution`, `Release assets`, and `Verification`, in that exact order. `Added`, `Changed`, and `Fixed` are the standard optional subheadings inside `What's New / Highlights` and empty subheadings are omitted.
- When normalizing an already published release, the body actually published on GitHub is the primary historical source. Changelog/docs may supplement only clearly supported missing details and must not silently replace or strengthen the historical claims.
- Obvious editorial mistakes in historical prose may be corrected during normalization only when the release/tag identity is unambiguous and the substantive meaning is unchanged.
- Release-note prose may be normalized after publication, but this never authorizes changing an immutable published tag, source commit, binary/source asset, or checksum file.
- Every release must finish the permanent closure procedure in `docs/RELEASE_CLOSURE.md`. Publishing alone is not release completion: post-release context Markdown must be reviewed/updated, the local VS Code checkout must be synchronized safely to canonical `main`, the local tree/SHA must be verified, and any new handoff must be generated only from that clean synchronized state.

### Permanent release closure and VS Code sync

For every current and future release:

- review and update all maintained project-context Markdown whose facts changed, including the current version-specific handoff;
- keep release history and the newer post-release `main` context clearly distinguished;
- before any local pull run `git status --short`; if dirty, stop and never reset/stash/discard automatically;
- on a clean local VS Code checkout use `git fetch --prune origin`, switch to `main`, and use `git pull --ff-only origin main`;
- verify the clean local `HEAD` equals the expected canonical post-release/documentation SHA;
- generate `REPOSITORY_SNAPSHOT.md` and chat/continuation handoffs only after that synchronization;
- do not call the release cycle closed until remote repository state, local VS Code state and context documentation agree.

The full checklist and rationale are canonical in `docs/RELEASE_CLOSURE.md` and apply to v1.7, v1.8, v1.9, v1.99, v2.0 and every later release line.

### v1.4 Windows x64 Engineering Test Build (ETB) profile

v1.4 is intentionally a public Windows x64 Engineering Test Build (ETB).

- Build Windows x64 only from the frozen SHA.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke `.github/workflows/sign-windows.yml` for v1.4.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.4.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The engineering assembler must accept only the successful unsigned Windows x64 `Build Windows - Qt6` run from the same repository and exact SHA and must reject ARM64 input.
- The public asset set is exactly three files: Windows x64 ZIP, one consolidated third-party source `tar.xz`, and one `SHA256SUMS.txt`.
- Engineering GitHub Releases use title suffix `(ETB Win x64)`; the release-body heading identifies `Engineering Test Build - Windows x64 Only`; the package must be clearly described as unsigned.

### v1.5 Windows x64 Engineering Test Build (ETB) profile

v1.5.0 remains an unsigned Windows x64 Engineering Test Build (ETB).

- Build Windows x64 only from the frozen SHA.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke `.github/workflows/sign-windows.yml` for v1.5.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.5.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The public asset set is exactly three files: `PlayStoreAppAudit-v1.5.0-windows-x64.zip`, `PlayStoreAppAudit-v1.5.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`.
- Use GitHub Release title suffix `(ETB Win x64)` and release-body heading `## Play Store App Audit v1.5.0 (Engineering Test Build - Windows x64 Only)`.
- Keep the package clearly described as unsigned. Do not spend money on signing for v1.5.

### v1.6 Windows x64 Engineering Test Build (ETB) profile

The v1.6.0 release profile is frozen as an unsigned Windows x64 ETB. Product scope is closed for the release candidate.

- Canonical application version is `1.6.0`.
- Build Windows x64 only from the exact frozen `main` SHA after the post-merge Quality gate passes.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke production Windows signing or macOS production signing/notarization for v1.6.
- Do not build Windows ARM64, Linux or macOS release candidates for v1.6.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- The public asset set is exactly `PlayStoreAppAudit-v1.6.0-windows-x64.zip`, `PlayStoreAppAudit-v1.6.0-third-party-sources.tar.xz`, and `SHA256SUMS.txt`.
- The current GitHub Release title is `Play Store App Audit v1.6.0 (Win x64 Only)`; the body heading remains `## Play Store App Audit v1.6.0 (Engineering Test Build - Windows x64 Only)`.
- Keep the package clearly described as unsigned.
- Do not add the optional richer dashboard/summary to v1.6.0.
- If source or release tooling changes after the exact release SHA is recorded, discard that candidate SHA and rebuild the required ETB artifacts from the new exact SHA.

### v1.7-v1.99 Windows x64 Engineering Test Build (ETB) profile

v1.7.0, v1.8.0 and v1.9.0 are published and immutable as unsigned Windows x64 ETBs. v1.99 deliberately continues the same Windows x64-only distribution profile unless a later explicit release decision changes it.

- Build Windows x64 only from one exact frozen `main` SHA after the required Quality gates pass.
- Use `.github/workflows/build-windows-exe.yml` with `target=x64`.
- Do not invoke production Windows signing or build Windows ARM64, Linux or macOS release candidates for v1.8, v1.9 or v1.99.
- Assemble with `.github/workflows/assemble-windows-engineering-release.yml`.
- Publish exactly three project-defined assets: the Windows x64 ZIP, one consolidated third-party source `tar.xz`, and `SHA256SUMS.txt`.
- Current/future Windows x64 ETB GitHub Release titles use suffix `(Win x64 Only)`; the release-body heading still identifies `Engineering Test Build - Windows x64 Only` and the package remains clearly described as unsigned.
- v1.7.0 is frozen at `e2d09098bc42c6f16d202d010deda3eb24d99aa3`. Do not rebuild, retag or replace it.
- v1.8.0 is frozen at `ac328f0dffddb6b70fa7600f1291377376bc05d4`. Do not rebuild, retag or replace it.
- v1.9.0 is frozen at `6c117009525f40434e9db714dadf1dd01b79f9ab`. Do not rebuild, retag or replace it.
- v1.99 requires one additional real packaged Windows x64 acceptance candidate before the final release freeze. If source changes after that user-tested candidate, it is not the final release artifact: freeze a new exact `main` SHA, rerun Quality, and build/assemble the canonical final package from the new SHA.

### v1.99 product guardrails

v1.99 is the active cycle and likely final Windows x64-only release before v2.0. Keep it controlled rather than treating it as an open-ended feature release.

- Preserve the implemented cooperative Stop/Cancel lifecycle across the real audit pipeline. Never use `QThread.terminate()` or another unsafe forced-termination mechanism. Preserve completed valid results and independent cache entries, mark the audit cancelled/incomplete, do not promote it to the completed history baseline, and return to a reusable idle state.
- Preserve the accepted C2 operations header: Run/Pause/Resume, Stop, the canonical always-present progress widget, Export Results and Clear Results in that order. The second header row keeps status chips, Hide System Apps, search and the single Details selector. Details continues to reuse the same Auto/Right/Below/Hidden state and View-menu synchronization; do not duplicate state or move operational status text out of the native status bar.
- Alternative Distribution Discovery is informational exact-package-ID evidence, not endorsement or an automatic equivalent-app association. Approved providers are Samsung Galaxy Store, Huawei AppGallery, F-Droid, Aptoide, Uptodown, APKMirror and APKPure; Amazon Appstore is excluded. Automatic checks require conclusive eligible Google Play evidence and must not run for transient, scraper or ambiguous failures.
- The v1.99 Maintenance Score update uses one mutually exclusive Google Play removal/distribution penalty selected from the best verified class: official store `-20`, FOSS repository `-40`, independent store `-45`, APK repository `-50`, or no verified alternative `-60`. Store anomaly is `-20`; Other/inconclusive is `-15`; stale/aging freshness is `-25`/`-15`; legacy/aging target SDK is `-15`/`-10`; installed/store difference is `-5`. Regional unavailability is not automatically Removed.
- An internal `health_score` rename remains a separate evidence-gated compatibility migration; it is not implied by the scoring update.
- `QDockWidget` is rejected and not planned. Retain the Details Panel's Auto/Right/Below/Hidden placement and narrow/wide/extra-wide responsiveness.
- A richer dashboard remains evidence-gated and must add a distinct workflow not already covered by existing summary, filters, Changes, Details and status surfaces.

### v2.0-or-later production profile

v2.0 is the first planned return to a full multi-platform release. Production signing remains the preferred target, but it must not be promised until provider eligibility, credentials, cost and end-to-end signing/notarization validation are confirmed.

- Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 final candidates must all come from the same frozen SHA.
- Windows final candidates require a publicly trusted code-signing provider with native post-sign verification.
- macOS final candidates require Developer ID Application signing, hardened runtime, notarization, stapling and Gatekeeper verification.
- Linux production packaging remains Nuitka standalone, not onefile, with replaceable Qt/PySide/Shiboken shared libraries.
- Assemble with `.github/workflows/assemble-release.yml` only after all six final candidates validate.
- The full production public asset set is exactly eight files: six platform ZIPs, one consolidated third-party source `tar.xz`, and one `SHA256SUMS.txt`.
- A Local APK Library is a major v2.0 product pillar: recursively scan local APK directories, parse package/version and useful SDK/icon/file metadata, and compare the local library through the existing Store/evidence/filter/report architecture. Later library-management features such as mass rename, duplicate management and cleanup belong to the v2.x backlog.

v1.3.0 at commit `fb2193dfc13d0f0e6b7be660c1342bbf87d26081` is already published and immutable. Do not rebuild, retag or replace its artifacts.

## Tests and validation

For source-code changes, complete the normal cheap Quality checks before considering the change ready:

1. `python -m compileall playstore_app_audit`
2. `python -m pytest`
3. `ruff check playstore_app_audit tests main.py`
4. Run the Qt offscreen smoke test used by CI.

Add regression tests for bugs before or together with the fix when practical.

For workflow or packaging changes, run targeted static/unit validation first. Trigger expensive Nuitka package builds only when the change genuinely requires package evidence.

For release candidates, compiler success is not sufficient. Validate package contents, architecture, version, startup behaviour, legal material and release provenance as documented in `docs/BUILDING.md`.

Ruff exceptions for inherited Qt patterns are intentionally narrow and configured per-file in `pyproject.toml`. Prefer removing an exception when relevant code is modernised rather than broadening the global ignore list.

## Git workflow

- `main` is the single canonical permanent branch.
- Use short-lived `feature/`, `fix/`, `refactor/`, `docs/`, `release/` or `agent/` branches, merge them back with normal PR merge commits, then delete them.
- Keep maintenance work scoped. Documentation cleanup, workflow restructuring, signing, API migrations and UI redesign should not be bundled without a release-engineering reason.
- Do not create permanent branches per operating system.
- Historical implementations belong in Git tags, not live maintenance branches.

## Dependency/API evolution

- Replace APIs that are already deprecated or scheduled for deprecation when semantics are understood.
- Evaluate documented preferred replacements when behaviour is equivalent and migration risk is low.
- Do not rewrite stable supported APIs merely because they are old.
- The application itself does not use Node. Follow official GitHub Action majors when their maintainers move bundled runtimes; do not add `setup-node` just to chase a newer Node LTS.

## Style

- Use type annotations on new code.
- Prefer `dataclass(slots=True)` and `Enum`/`StrEnum` for stable domain structures instead of open-ended dictionaries when introducing new APIs.
- Keep side effects at the edges: UI, filesystem, network and subprocess.
- Prefer small focused modules over new version-suffixed files.
- Do not create `*_v10.py`, `*_fixed.py` or `*_stable.py` files for normal evolution. Change canonical package modules and rely on Git history/tags for versions.
