# AGENTS.md

## Project

Play Store App Audit is a Python desktop application that audits Android package IDs against public Google Play listings and, optionally, enriches results from an Android device through ADB.

The production UI is Qt 6 / PySide6 Qt Widgets. The former CustomTkinter implementation is retired and preserved only as the historical Git tag `legacy-customtkinter-v9.3`.

Durable engineering decisions live in `docs/PROJECT_DECISIONS.md`. Current release state and the active backlog live in `docs/PROJECT_STATUS.md`. The detailed release procedure lives in `docs/BUILDING.md`.

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
- v1.3 PySide6 baseline: `PySide6-Essentials==6.11.1`.
- v1.3 release compiler pin: `Nuitka==4.1.3`.
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
- Before adding a theme dependency, evaluate native platform styling and audit existing QSS, especially scrollbar rules.

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
- A production release freezes one exact full `main` SHA after Quality CI passes.
- Windows x64/ARM64, Linux x64/ARM64 and macOS x64/ARM64 release candidates must all come from that same exact SHA.
- Build workflows must reject mismatches between expected SHA, dispatch SHA and checked-out SHA.
- Assemble and validate all six release candidates before tagging.
- A production release exposes exactly 8 public assets: six platform ZIPs, one consolidated third-party source `tar.xz`, and one `SHA256SUMS.txt`.
- Do not create public RC tags.
- Release-tag pushes must not rebuild binaries. Publish the already validated artifacts.
- If source or release tooling changes after the SHA is frozen, rebuild all six candidates from the new exact SHA. Never mix artifacts from different SHAs.
- Linux release packaging remains Nuitka standalone, not onefile, with replaceable Qt/PySide/Shiboken shared libraries.
- Do not weaken legal/source validation to make a build pass.
- Do not delete files under `.github/scripts/` merely because there are several. Verify workflow references, imports and tests before removal.

v1.3.0 at commit `fb2193dfc13d0f0e6b7be660c1342bbf87d26081` is already published and immutable. Documentation-only v1.4 work must not rebuild, retag or replace v1.3.0 artifacts.

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
- Use short-lived `feature/`, `fix/`, `refactor/`, `docs/` or release-maintenance branches, merge them back with normal PR merge commits, then delete them.
- Keep maintenance work scoped. Documentation cleanup, workflow restructuring, signing, API migrations and UI redesign should not be bundled into one PR.
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
