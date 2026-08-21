# AGENTS.md

## Project

Play Store App Audit is a Python desktop application that audits Android package IDs against public Google Play listings and, optionally, enriches results from an Android device through ADB.

The production UI is Qt 6 / PySide6 Qt Widgets. The former CustomTkinter implementation is retired and preserved only as the historical Git tag `legacy-customtkinter-v9.3`.

Durable engineering decisions live in `docs/PROJECT_DECISIONS.md`. Current shipped/development state lives in `docs/PROJECT_STATUS.md`. Forward-looking release/feature planning lives in `docs/ROADMAP.md`. The detailed release procedures live in `docs/BUILDING.md`. GitHub Actions retention and post-release housekeeping live in `docs/CI_MAINTENANCE.md`. The canonical GitHub Release body structure and historical normalized release-note wording live in `docs/RELEASE_NOTES.md`.

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
- The Health Score is a maintenance heuristic, not a malware/security score.
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

### v1.6 planning direction

The v1.6 profile is not frozen. Current roadmap direction is another unsigned Windows x64 ETB while product, UX and Store-service architecture mature.

- Do not assume a six-platform v1.6 build.
- Do not invoke production Windows signing or macOS production signing/notarization as normal v1.6 work.
- If the v1.6 profile is finalized as Windows x64 ETB, reuse the exact-SHA engineering build/assembly profile proven by v1.5.
- Follow `docs/ROADMAP.md` for v1.6 feature scope.

### v2.0-or-later production profile

Production signing and the full six-platform release are not planned before v2.0. The implementation remains preserved for that later milestone.

- Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 final candidates must all come from the same frozen SHA.
- Windows final candidates require a publicly trusted code-signing provider with native post-sign verification.
- macOS final candidates require Developer ID Application signing, hardened runtime, notarization, stapling and Gatekeeper verification.
- Linux production packaging remains Nuitka standalone, not onefile, with replaceable Qt/PySide/Shiboken shared libraries.
- Assemble with `.github/workflows/assemble-release.yml` only after all six final candidates validate.
- The full production public asset set is exactly eight files: six platform ZIPs, one consolidated third-party source `tar.xz`, and one `SHA256SUMS.txt`.

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
