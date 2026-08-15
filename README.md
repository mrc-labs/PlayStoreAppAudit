# Play Store App Audit - CustomTkinter branch

This branch contains the **CustomTkinter 6** GUI.

The audit engine and Play Store logic remain shared with the Qt6 variant. The main difference is the desktop-widget layer: this branch keeps the Tkinter/ttk table stack and modernises the surrounding UI with CustomTkinter.

## App source

The source card contains:

- `Choose file`
- `Scan phone with ADB`
- `Store country`
- `Exclude system apps from source`

`Store country` is detected from the Windows Region and remains editable.

Store language is **not exposed in the UI** and is fixed internally to `en`.

Audit concurrency is **fixed internally to 16 parallel workers** and is no longer exposed as a user setting.

When `Exclude system apps from source` is enabled:

- **ADB** loads third-party packages only using `adb shell pm list packages -3`;
- **CSV/TSV** removes packages classified as system while the file is loaded, using an explicit system flag when available, an exact ADB comparison when possible, or the conservative package-name fallback.

When it is disabled, all packages are loaded. `Hide system apps` remains available as a result-table display filter.

## Results

The interactive table shows `Package Name` as the canonical package identifier. `Input name` is retained internally/exported when available but is hidden from the on-screen table because it is usually redundant.

The CustomTkinter interface provides:

- modern cards, buttons, entries and checkboxes;
- CustomTkinter HighDPI scaling on Windows;
- early Windows DPI-awareness setup before the Tk window is created;
- the existing sortable `ttk.Treeview` results table;
- `Age (days)` sorting;
- instant text filtering;
- clickable criticality counters;
- pastel row colouring;
- `Hide system apps` as a visual filter;
- double-click to open the Google Play listing;
- optional CSV export.

The Windows CI smoke test also inserts a synthetic audit row into the Treeview and verifies that the table renders it.

Criticality remains:

- red: Removed;
- orange: Stale, >730 days;
- yellow: Aging, >365 and <=730 days;
- blue: Store anomaly;
- purple: Other / unknown / error;
- green: Current, <=365 days.

## ADB

The CustomTkinter branch now explicitly supplies Python's `subprocess` module to its ADB scan implementation, fixing the previous `name 'subprocess' is not defined` runtime error.

If ADB is missing, the app can download the current Windows Platform-Tools package directly from Google's official endpoint and install it under `%LOCALAPPDATA%\PlayStoreAppAudit\platform-tools`.

## Build

GitHub Actions builds:

`PlayStoreAppAudit-CustomTkinter.exe`

Artifact name:

`PlayStoreAppAudit-Windows-CustomTkinter`

The build and local run use the DPI-aware launcher:

`playstore_audit_customtkinter_launcher.py`
