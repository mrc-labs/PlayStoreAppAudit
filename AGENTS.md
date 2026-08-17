# AGENTS.md

## Project

Play Store App Audit is a Python desktop application that audits Android package IDs against public Google Play listings and, optionally, enriches results from an Android device through ADB.

The production UI is Qt 6 / PySide6. The former CustomTkinter implementation is retired and preserved only as the historical Git tag `legacy-customtkinter-v9.3`.

## Architecture

All production application code belongs under `playstore_app_audit/`:

- `playstore_app_audit/app.py`: application entry point only.
- `playstore_app_audit/domain/`: typed domain models and pure business concepts.
- `playstore_app_audit/services/`: Play Store, audit, cache/history/report service boundaries.
- `playstore_app_audit/devices/`: ADB/device integration.
- `playstore_app_audit/platform/`: Windows/macOS/Linux abstraction.
- `playstore_app_audit/ui/`: Qt Widgets UI only.

The version-suffixed top-level Qt and feature modules have been removed. The internal Qt layers use descriptive package module names such as `base_window`, `audit_window`, `device_window`, `preferences_window` and `results_window`, with `main_window.py` as the public UI entry point.

Cross-module runtime monkey-patching for audit selection, classification, cache bypass and ADB metadata enrichment has been removed. UI layers customise behaviour through explicit overridable hooks such as row classification, cache loading and metadata collection/enrichment. Keep future extension points explicit and local rather than mutating imported modules at runtime.

The UI still uses a layered inheritance structure for proven behaviour. Reduce that structure incrementally only where composition or smaller focused widgets/controllers clearly improve maintainability. Do not combine a large behavioural rewrite with a structural migration.

UI code must not implement Google Play parsing, cache persistence, ADB discovery/download logic, or OS detection directly.

## Runtime and dependencies

- Release-build Python baseline: Python 3.13. Keep the source compatible with newer stable CPython releases and move the release baseline to Python 3.14 when the stable deployment/compiler toolchain officially supports it without an experimental warning.
- Qt: latest stable PySide6 Essentials release satisfying `>=6.11`.
- UI technology: Qt Widgets, not QML unless there is a demonstrated UX/performance reason to migrate.
- Store retrieval: keep `google-play-scraper` behind a service boundary because it is unofficial and replaceable.
- HTTP fallback: `requests` + BeautifulSoup using Python's built-in `html.parser`; do not re-add `lxml` unless a measured correctness/performance need justifies it.

Avoid adding libraries for functionality available cleanly in the Python standard library or Qt Essentials.

## Correctness rules

- Never use Google Play `datePublished` as the latest update date. Only update-specific fields such as `dateModified`, explicit `updated`, or visible 'Updated on' text are valid.
- A package unavailable in one Store country is not automatically globally removed. Preserve the multi-country fallback logic and its uncertainty states.
- The Health score is a maintenance heuristic, not a malware/security score.
- A different installed/store version is not automatically 'outdated'; device-specific or staged rollouts are possible.
- ADB operations are read-only unless a future change is explicitly approved.

## UX rules

- The Basic view must remain compact and understandable to non-expert users.
- Advanced settings remain behind the Tools menu and should warn users before changing technical behaviour.
- Presentation-only actions, including changing View presets, must not overwrite the more relevant audit/progress/status message.
- Avoid adding vertical UI sections when an existing row/menu/dialog can contain the feature cleanly.
- Status chips above the table support multi-selection.

## Cross-platform rules

All feature code should work on Windows, macOS and Linux unless the feature is inherently platform-specific.

Put platform-specific behaviour behind `playstore_app_audit.platform` or `playstore_app_audit.devices`:

- Platform-Tools download URL and executable name
- app-data directories
- Store-country detection
- subprocess console hiding
- icon/bundle handling
- packaging/signing

Do not hard-code `adb.exe`, `%LOCALAPPDATA%`, Windows-only SDK paths, or Windows-only console flags in shared UI/service code.

## Build policy

Windows x64 is the normal CI build and runs automatically for relevant pushes to `main`.

Windows ARM64 remains available only as an explicit manual engineering build.

macOS and Linux packaging are manual/on-demand builds only, to reduce CI time and resource usage. Source changes must nevertheless remain cross-platform.

Prefer the shared Nuitka standalone build path for Windows release packaging. Validate the actual packaged runtime, not only the compiler exit code: required Qt/PySide files must be present, forbidden components must be absent, and the packaged application must pass architecture, version and startup validation.

Linux CI runners require the small Qt/X11/EGL runtime set installed by the manual build workflow. macOS packaging intentionally excludes the unused `platforminputcontexts`/Qt Virtual Keyboard plugin, which avoids pulling an unavailable QtVirtualKeyboardQml framework into the app bundle.

Generated binaries, deployment directories and generated icon files must never be committed to source control. They belong in CI artifacts or local ignored paths.

## Tests and quality

Before considering a change complete:

1. `python -m compileall playstore_app_audit`
2. `python -m pytest`
3. `ruff check playstore_app_audit tests main.py`
4. Run the Qt offscreen smoke test used by CI.
5. For packaging changes, build the Windows artifact and verify the executable starts.
6. For macOS/Linux packaging changes, validate that the produced app/binary exists and has a plausible non-trivial size.

Add regression tests for bugs before or together with the fix when practical.

Ruff exceptions for inherited Qt patterns are intentionally narrow and configured per-file in `pyproject.toml`. Prefer removing an exception when the relevant code is modernised rather than broadening the global ignore list.

## Git workflow

- `main` is the single canonical permanent branch.
- Use short-lived `feature/`, `fix/`, `refactor/` or `release/` branches as appropriate, merge them back into `main`, then delete them.
- Do not create permanent branches per operating system. Windows/macOS/Linux must build from the same source revision.
- Historical implementations belong in Git tags, not live maintenance branches.

## Style

- Use type annotations on new code.
- Prefer `dataclass(slots=True)` and `Enum`/`StrEnum` for stable domain structures instead of open-ended dictionaries when introducing new APIs.
- Keep side effects at the edges (UI, filesystem, network, subprocess).
- Prefer small focused modules over new version-suffixed files.
- Do not create `*_v10.py`, `*_fixed.py`, `*_stable.py` files for normal evolution. Change the canonical package modules and rely on Git history/tags for versions.
