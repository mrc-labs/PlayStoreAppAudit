# Play Store App Audit

Play Store App Audit is a Qt 6 / PySide6 desktop utility for auditing Android packages against public Google Play listings and, when an Android phone is connected through ADB, enriching the audit with device metadata.

CustomTkinter is retired. The application now has one Qt source tree intended for Windows, macOS and Linux, with `main` as the canonical production branch.

## Current architecture

The canonical entry point is:

```bash
python main.py
```

New application code lives under `playstore_app_audit/`:

- `domain/` for typed domain concepts
- `services/` for Store, audit, state/cache/history and report boundaries
- `devices/` for ADB/device integration
- `platform/` for Windows/macOS/Linux differences
- `ui/` for the Qt Widgets UI

The application code is fully contained under `playstore_app_audit/`; version-suffixed compatibility modules have been removed. See `docs/ARCHITECTURE.md` and `AGENTS.md`.

## App source

The main source card is compact and presents the two source choices on one horizontal row:

`CSV / TSV / TXT file [Choose file]  |  or  |  Android phone (ADB) [Scan phone]  |  Store country  |  Exclude system apps from source`

A short source-status line appears underneath.

The Store country is detected from the desktop operating-system region and remains editable because Google Play availability can differ by market. Store language defaults to English and can be changed in Advanced settings.

Audit concurrency is fixed internally to 16 workers.

## Google Play availability and freshness

The selected Store country is checked first. If a package is unavailable there, the configured multi-country fallback list is checked automatically. The default list is representative rather than globally exhaustive and can be changed in Advanced settings.

Status classes:

- Removed
- Stale, older than 730 days
- Aging, older than 365 and up to 730 days
- Store anomaly
- Other / unknown / error
- Current, up to 365 days

The HTML fallback accepts only update-specific date signals. `datePublished` is deliberately ignored because it can represent the original publication date rather than the latest update.

## Device / ADB features

ADB support is read-only. Depending on enabled options, an ADB audit can collect installed version, installer source, Target/Min SDK, install/update metadata, enabled state and declared sensitive permissions. Device summary, inventory history and device snapshots are also supported.

If ADB is missing, managed Platform-Tools support depends on the desktop:

- Windows: managed Platform-Tools are available where supported by the application.
- macOS: managed Platform-Tools are available where supported by the application.
- Linux x64: Google's managed Linux Platform-Tools are supported.
- Linux ARM64: Google does not provide the managed Linux archive used by this application, so use a native ADB from the system, distribution or an ARM64-compatible Android SDK.

ADB may also be installed separately and placed on `PATH`, or supplied through an Android SDK referenced by `ANDROID_SDK_ROOT` / `ANDROID_HOME`.

## Results and exports

The Basic table remains intentionally compact. Device, Technical and Custom view presets expose additional fields without cluttering the normal audit view.

Status chips above the table can be multi-selected. Search and system-app visibility filters combine with those selections.

Result exports support:

- all results as CSV
- visible results as CSV
- all results as HTML
- visible results as HTML

The File menu can also export the current phone package inventory as CSV.

## Runtime

Release builds currently use Python 3.13 because the current stable Nuitka release still labels Python 3.14 support experimental. The source should remain compatible with newer stable CPython versions, and the release baseline should move to Python 3.14 once the stable deployment toolchain fully supports it.

Qt uses the latest stable `PySide6-Essentials` satisfying `>=6.11`.

The runtime intentionally avoids unnecessary Qt Addons and no longer requires `lxml`; BeautifulSoup's standard-library `html.parser` is used for the rare HTML fallback. Pillow is kept as a build/development dependency for generating native icon formats and is not a runtime dependency.

## Quality

```bash
python -m compileall -q playstore_app_audit
python -m pytest
ruff check playstore_app_audit tests main.py
```

The Windows CI also opens the Qt UI using the offscreen platform plugin before packaging.

## Builds

Windows is the normal automatic GitHub Actions build from `main`. macOS and Linux builds are manual/on-demand only, but use the same source revision.

Release packaging uses Qt's `pyside6-deploy` / Nuitka path. See `docs/BUILDING.md` for local and CI instructions and `docs/BRANCH_MIGRATION.md` for the completed migration and legacy-branch retirement steps.
