# AGENTS.md

## Project

Play Store App Audit is a Python desktop application that audits Android package IDs against public Google Play listings and, optionally, enriches results from an Android device through ADB.

The production UI is Qt 6 / PySide6. CustomTkinter is legacy and must not receive new features.

## Architecture

New code belongs under `playstore_app_audit/`:

- `playstore_app_audit/app.py`: application entry point only.
- `playstore_app_audit/domain/`: typed domain models and pure business concepts.
- `playstore_app_audit/services/`: Play Store, audit, cache/history/report service boundaries.
- `playstore_app_audit/devices/`: ADB/device integration.
- `playstore_app_audit/platform/`: Windows/macOS/Linux abstraction.
- `playstore_app_audit/ui/`: Qt Widgets UI only.

The older top-level `playstore_audit_qt_v*.py` and `playstore_audit_*_features.py` files are a temporary compatibility layer. Do not add new product features to older versioned UI files unless a migration fix specifically requires it. Prefer moving behaviour behind the package boundary and gradually deleting legacy wrappers.

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

Windows is the normal CI build and may run automatically on pushes to the active development branch.

macOS and Linux packaging are manual/on-demand builds only, to reduce CI time and resource usage. Source changes must nevertheless remain cross-platform.

Prefer Qt's supported `pyside6-deploy` / Nuitka path for release packaging when it passes our smoke tests and produces a smaller/faster artifact. Keep a fallback deployment path only until the preferred path is proven stable.

## Tests and quality

Before considering a change complete:

1. `python -m compileall playstore_app_audit`
2. `python -m pytest`
3. `ruff check playstore_app_audit tests main.py`
4. Run the Qt offscreen smoke test used by CI.
5. For packaging changes, build the Windows artifact and verify the executable starts.

Add regression tests for bugs before or together with the fix when practical.

## Git workflow

- `main` should eventually be the canonical production branch.
- Temporary feature branches should be short-lived.
- `qt6-working` and `customtkinter` are legacy branches and should be retired after the Qt package refactor is validated and the final useful differences have been reconciled.
- Do not create permanent branches per operating system. Windows/macOS/Linux should build from the same source revision.

## Style

- Use type annotations on new code.
- Prefer `dataclass(slots=True)` and `Enum`/`StrEnum` for stable domain structures instead of open-ended dictionaries when introducing new APIs.
- Keep side effects at the edges (UI, filesystem, network, subprocess).
- Prefer small focused modules over new version-suffixed files.
- Do not create `*_v10.py`, `*_fixed.py`, `*_stable.py` files for normal evolution. Change the canonical package modules and rely on Git history/tags for versions.
