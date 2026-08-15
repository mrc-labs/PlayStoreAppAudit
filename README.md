# Play Store App Audit - Qt6 branch

This branch contains the **PySide6 / Qt 6** GUI.

The audit engine and Play Store logic remain shared with the other UI variant. The main differences between branches are presentation and desktop-widget technology.

## Source behaviour

The `App source` section contains:

- `Choose file`
- `Scan phone with ADB`
- `Exclude system apps when loading / scanning`

When the exclusion checkbox is enabled:

- **ADB** loads third-party packages only using `adb shell pm list packages -3`;
- **CSV/TSV** removes packages classified as system while the file is loaded, using an explicit system flag when available, an exact ADB comparison when possible, or the conservative package-name fallback.

When it is disabled, all packages are loaded. `Hide system apps` remains available as a result-table display filter.

## Store settings

- `Country` is detected from the Windows Region and remains editable.
- Store language is **not exposed in the UI** and is fixed internally to `en`.
- `Parallel threads` remains configurable.

There is no longer an Advanced language/system-skip panel.

## Results

The Qt table supports:

- native sorting;
- draggable/reorderable columns;
- `Age (days)` numeric sorting;
- instant text filtering;
- clickable criticality counters;
- pastel row colouring;
- `Hide system apps` as a visual filter;
- double-click to open the Google Play listing;
- optional CSV export.

Criticality remains:

- red: Removed;
- orange: Stale, >730 days;
- yellow: Aging, >365 and <=730 days;
- blue: Store anomaly;
- purple: Other / unknown / error;
- green: Current, <=365 days.

## ADB

If ADB is missing, the app can download the current Windows Platform-Tools package directly from Google's official endpoint and install it under `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

## Build

GitHub Actions builds:

`PlayStoreAppAudit-Qt6.exe`

Artifact name:

`PlayStoreAppAudit-Windows-Qt6`

Local entry point:

`playstore_audit_qt_branch.py`
